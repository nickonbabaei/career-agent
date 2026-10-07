"""Offline contract and workflow regressions; no credentials or network required."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from agent.models import Profile, JobPosting, Draft, RelevanceDecision
from agent.profile import load_profile, ProfileConfigError
from agent.fixtures import load_sample_jobs
from agent.tools import plan_queries, merge_batches, search_query, JobSearchError
from agent.ranking import rank_jobs, RankingError
from agent import workflow as w


def job(n, **kwargs):
    return JobPosting('Engineer', 'Example', 'Toronto', 'Build Python apps',
                      f'https://example.com/{n}', **kwargs)


def gemini(value):
    response = Mock()
    response.json.return_value = {'candidates': [{'finishReason': 'STOP', 'content': {
        'parts': [{'text': json.dumps(value)}]}}]}
    return response


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.profile = Profile('Example', ['Engineer', 'Developer'], ['Toronto', 'Remote'], ['Built a prototype'])
        self.env = patch.dict(os.environ, {'GEMINI_API_KEY': 'fake', 'OPENWEBNINJA_API_KEY': 'fake'})
        self.clock_value = 1000.0
        def advance(seconds):
            self.clock_value += seconds
        clock_patch = patch.object(w.time, 'monotonic', side_effect=lambda: self.clock_value)
        sleep_patch = patch.object(w.time, 'sleep', side_effect=advance)
        clock_patch.start()
        sleep_patch.start()
        self.addCleanup(clock_patch.stop)
        self.addCleanup(sleep_patch.stop)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_saved_results_reassesses_without_search(self):
        from dataclasses import asdict
        from agent.saved_results import load_saved_jobs
        with self.run_directory():
            source = Path('source.json')
            original = json.dumps({'found': 2, 'jobs': [{'job': asdict(job(1))}],
                                   'unassessed_jobs': [asdict(job(2))]})
            source.write_text(original)
            self.assertEqual(len(load_saved_jobs(str(source))), 2)
            with patch.object(w, 'search_query') as search, patch.object(w, 'classify_relevance', return_value=RelevanceDecision(True, 'Fit evidence')) as classify, patch.object(w, 'rank_jobs', return_value=[{'id': 2, 'reason': 'Comparative evidence'}, {'id': 1, 'reason': 'Next'}]), patch.dict(os.environ, {'OPENWEBNINJA_API_KEY': ''}):
                directory, report = w.run_workflow(self.profile, max_jobs=2, from_results=str(source))
            search.assert_not_called()
            self.assertEqual(classify.call_count, 2)
            self.assertEqual(report['unassessed'], 0)
            self.assertEqual(report['search_requests'], 0)
            self.assertEqual(source.read_text(), original)
            text = (directory / 'shortlist.md').read_text()
            self.assertIn('Ranking comparison: Comparative evidence', text)
            self.assertEqual(text.count('Fit assessment:'), 2)
            source.write_text(json.dumps({'found': 3, 'jobs': []}))
            with self.assertRaises(ValueError): load_saved_jobs(str(source))

    def test_quota_stops_and_resume_preserves_success(self):
        from agent.quota import QuotaError
        limited = QuotaError({'http_status': 429, 'retry_after_seconds': 2})
        with self.run_directory(), patch.object(w, 'search_query', return_value=[job(1), job(2), job(3)]), patch.object(w, 'rank_jobs', return_value=[{'id': i, 'reason': 'Fit'} for i in (1, 2, 3)]) as rank, patch.object(w.time, 'sleep') as sleep:
            with patch.object(w, 'classify_relevance', side_effect=[RelevanceDecision(True, 'Match'), limited, limited]) as classify:
                directory, r = w.run_workflow(self.profile, max_jobs=3, max_search_requests=1)
            self.assertEqual(classify.call_count, 3)
            self.assertIn(unittest.mock.call(2), sleep.call_args_list)
            rank.assert_not_called()
            self.assertEqual((r['status'], r['assessed'], r['failed'], r['pending']), ('quota_limited', 1, 1, 1))
            source = directory / 'results.json'
            original = source.read_text()
            with patch.object(w, 'search_query') as search, patch.object(w, 'classify_relevance', return_value=RelevanceDecision(True, 'Match')) as classify:
                _, resumed = w.run_workflow(self.profile, max_jobs=3, resume_results=str(source))
            search.assert_not_called()
            self.assertEqual(classify.call_count, 2)
            self.assertEqual((resumed['reused'], resumed['assessed'], resumed['unassessed']), (1, 3, 0))
            self.assertEqual(source.read_text(), original)
            self.profile.experience_bullets.append('Changed profile')
            with self.assertRaises(ValueError):
                w.run_workflow(self.profile, resume_results=str(source))

    def test_quota_long_delay_stops_without_retry(self):
        from agent.quota import QuotaError, quota_error
        response = Mock()
        response.headers = {'Retry-After': '120'}
        response.json.return_value = {'error': {'message': 'secret raw text', 'details': [
            {'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [
                {'quotaId': 'RequestsPerDay', 'description': 'secret'}]}]}}
        error = quota_error(response)
        self.assertEqual(error.details['retry_after_seconds'], 120)
        self.assertNotIn('secret', str(error))
        with self.run_directory(), patch.object(w, 'search_query', return_value=[job(1)]), patch.object(w, 'classify_relevance', side_effect=error) as classify, patch.object(w.time, 'sleep') as sleep, patch.object(w, 'rank_jobs') as rank:
            _, report = w.run_workflow(self.profile, max_search_requests=1)
            self.assertEqual(report['status'], 'quota_limited')
            self.assertEqual(classify.call_count, 1)
            sleep.assert_not_called()
            rank.assert_not_called()

    def test_ranking_quota_resume_only_ranks(self):
        from agent.quota import QuotaError
        with self.run_directory(), patch.object(w, 'search_query', return_value=[job(1)]), patch.object(w, 'classify_relevance', return_value=RelevanceDecision(True, 'Match')):
            with patch.object(w, 'rank_jobs', side_effect=QuotaError({'http_status': 429, 'retry_after_seconds': 90})):
                directory, r = w.run_workflow(self.profile, max_search_requests=1)
            self.assertEqual(r['assessed'], 1)
            with patch.object(w, 'classify_relevance') as classify, patch.object(w, 'rank_jobs', return_value=[{'id': 1, 'reason': 'Only candidate'}]):
                _, r = w.run_workflow(self.profile, resume_results=str(directory / 'results.json'))
            classify.assert_not_called()
            self.assertEqual(r['status'], 'completed')

    def test_pacing_covers_retry_ranking_and_drafting(self):
        starts = []
        def classify(*args):
            starts.append(('relevance', self.clock_value))
            if len(starts) == 1:
                raise w.RelevanceError('temporary failure')
            self.clock_value += 2  # request duration counts toward spacing
            return RelevanceDecision(True, 'Match')
        def rank(*args):
            starts.append(('ranking', self.clock_value))
            return [{'id': 1, 'reason': 'Only candidate'}]
        def draft(posting, profile):
            starts.append(('drafting', self.clock_value))
            return Draft(posting, 'Hello', 'Supported message')
        with self.run_directory(), patch.object(w, 'search_query', return_value=[job(1)]), patch.object(w, 'classify_relevance', side_effect=classify), patch.object(w, 'rank_jobs', side_effect=rank), patch.object(w, 'draft_outreach', side_effect=draft):
            _, report = w.run_workflow(self.profile, max_search_requests=1, generate_drafts=True, gemini_rpm=10)
        self.assertEqual([t for _, t in starts], [1000, 1006, 1012, 1018])
        self.assertEqual(report['gemini_rpm'], 10)
        self.assertEqual(report['drafted'], 1)

    def test_invalid_pacing_fails_before_calls(self):
        with patch.object(w, 'search_query') as search:
            for value in (0, -1, True, 1.5):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    w.run_workflow(self.profile, gemini_rpm=value)
            search.assert_not_called()

    def test_query_grid_remote_and_dedup(self):
        self.profile.target_roles.append('Engineer')
        queries = plan_queries(self.profile)
        self.assertEqual(len(queries), 4)
        self.assertEqual(queries[1]['query'], 'Developer in Toronto')
        self.assertEqual(queries[2]['work_from_home'], 'true')
        self.assertEqual(queries[2]['country'], 'ca')
        a, b = job(1, provider_id='same'), job(2)
        self.assertEqual(merge_batches([[a, job(3)], [job(9, provider_id='same'), b]]), [a, job(3), b])
        self.assertEqual(len(merge_batches([[a], [a]])), 1)
        self.assertEqual(len(merge_batches([[a, b]])), 2)  # same title is not a duplicate

    def test_old_profile_and_fixtures_still_load(self):
        self.assertEqual(load_profile('profile/profile.yaml.example').employment_preferences, [])
        self.assertEqual(len(load_sample_jobs('fixtures/jobs.sample.json')), 3)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.yaml'
            path.write_text('name: Example\ntarget_roles: [Engineer]\nlocations: [Toronto]\nexperience_bullets: [Built demo]\nemployment_preferences: permanent\n')
            with self.assertRaises(ProfileConfigError): load_profile(path)

    def test_api_params_and_provider_id(self):
        response = Mock()
        response.json.return_value = {'status':'OK','data':{'jobs':[{
            'job_title':'Engineer','employer_name':'Example','job_description':'Build',
            'job_apply_link':'https://example.com/1','job_id':'123','job_location':None}]}}
        with patch('agent.tools.requests.get', return_value=response) as get:
            params=plan_queries(self.profile)[2]
            result=search_query(params)
            self.assertEqual(get.call_args.kwargs['params'],params)
            self.assertEqual(result[0].provider_id,'123')
            self.assertEqual(result[0].location,'Not specified')

    def test_ranking_rejects_hallucinated_duplicate_missing_ids(self):
        candidates=[{'id':1,'job':{},'decision':{}},{'id':2,'job':{},'decision':{}}]
        for ids in ([1,1],[1,3],[1],[True,2]):
            with self.subTest(ids=ids), patch('agent.ranking.requests.post',return_value=gemini({'ranking':[{'id':i,'reason':'Match'} for i in ids]})):
                with self.assertRaises(RankingError):rank_jobs(candidates,self.profile)
        with patch('agent.ranking.requests.post',return_value=gemini({'ranking':[{'id':2,'reason':'Stronger'},{'id':1,'reason':'Gap'}]})):
            self.assertEqual(rank_jobs(candidates,self.profile)[0]['id'],2)
        with patch('agent.ranking.requests.post') as post:
            self.assertEqual(rank_jobs([],self.profile),[])
            post.assert_not_called()

    @contextlib.contextmanager
    def run_directory(self):
        cwd=os.getcwd()
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            os.chdir(directory)
            try: yield
            finally: os.chdir(cwd)

    def test_budget_counts_retries_and_preserves_success(self):
        with self.run_directory(), patch.object(w,'search_query',side_effect=[JobSearchError('oops'),[job(1)],[job(2)]]) as search, patch.object(w,'classify_relevance',return_value=RelevanceDecision(True,'Match')),patch.object(w,'rank_jobs',return_value=[{'id':2,'reason':'Best'},{'id':1,'reason':'Next'}]),patch.object(w,'draft_outreach') as draft:
            directory,r=w.run_workflow(self.profile,max_search_requests=3,top_k=1)
            self.assertEqual(search.call_count,3)
            self.assertEqual(r['queries_not_attempted'],2)
            self.assertEqual(r['shortlist'][0]['id'],2)
            self.assertEqual(r['found'],2)
            draft.assert_not_called()
            self.assertIn('Best',(directory/'shortlist.md').read_text())
            self.assertEqual(json.loads((directory/'results.json').read_text())['search_requests'],3)

    def test_failed_query_retains_other_results_and_drafts_only_top(self):
        with self.run_directory(),patch.object(w,'search_query',side_effect=[JobSearchError('oops'),JobSearchError('oops'),[job(1),job(2)]]),patch.object(w,'classify_relevance',return_value=RelevanceDecision(True,'Match')),patch.object(w,'rank_jobs',return_value=[{'id':2,'reason':'Best'},{'id':1,'reason':'Next'}]),patch.object(w,'draft_outreach',return_value=Draft(job(2),'Subject','Body')) as draft:
            _,r=w.run_workflow(self.profile,max_search_requests=3,top_k=1,generate_drafts=True)
            self.assertEqual(r['status'],'completed_with_errors')
            self.assertEqual(r['drafted'],1)
            self.assertEqual(draft.call_args.args[0].source_url,job(2).source_url)

    def test_ranking_failure_does_not_draft(self):
        with self.run_directory(),patch.object(w,'search_query',return_value=[job(1)]),patch.object(w,'classify_relevance',return_value=RelevanceDecision(True,'Match')),patch.object(w,'rank_jobs',side_effect=RankingError('bad')) as ranking,patch.object(w,'draft_outreach') as draft:
            _,r=w.run_workflow(self.profile,max_search_requests=1,generate_drafts=True)
            self.assertEqual(r['status'],'ranking_failed')
            self.assertEqual(ranking.call_count,2)
            draft.assert_not_called()

    def test_empty_and_failed_search(self):
        for result,status in (([], 'completed'),(JobSearchError('bad'),'search_failed')):
            with self.subTest(status=status),self.run_directory(),patch.object(w,'search_query') as search,patch.object(w,'rank_jobs',return_value=[]):
                if isinstance(result,Exception):search.side_effect=result
                else:search.return_value=result
                _,r=w.run_workflow(self.profile,max_search_requests=1)
                self.assertEqual(r['status'],status)
                self.assertEqual(r['search_requests'],1)

    def test_limit_and_failure_continue(self):
        with self.run_directory(),patch.object(w,'search_query',return_value=[job(1),job(2),job(3)]),patch.object(w,'classify_relevance',side_effect=[w.RelevanceError('bad'),w.RelevanceError('bad'),RelevanceDecision(False,'No')]),patch.object(w,'rank_jobs',return_value=[]):
            _,r=w.run_workflow(self.profile,max_search_requests=1,max_jobs=2)
            self.assertEqual((r['failed'],r['checked'],r['unassessed']),(1,2,2))


if __name__=='__main__': unittest.main()
