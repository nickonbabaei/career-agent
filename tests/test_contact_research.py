import contextlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from agent.models import JobPosting, Profile, Draft
from agent.contact_research import research_contact, validate_contact, SCHEMA
from agent.research_runtime import Runtime, ResearchError
from agent.research_tools import section_index
from agent.shortlist_outreach import run


def action(kind, **kwargs):
    value = {k: '' for k in SCHEMA['required']}
    value.update(action=kind, section_id=0, evidence=[], uncertainties=[])
    value.update(kwargs)
    return value


def page(company, name):
    text = f'{company}\n{name} - AI Engineer\nWorks on AI systems.'
    url = f'https://{company.lower()}.example/team'
    return {'url': url, 'text': text, 'sections': section_index(text), 'retrieved_at': '2026-10-01'}


def finish(p, company, name):
    return action('finish', name=name, title='AI Engineer', organization=company,
                  relationship='employee', public_url=p['url'], reason='Relevant AI role at company.',
                  uncertainties=['Opening ownership unknown.'], evidence=[{'url': p['url'], 'excerpt': p['text']}])


class ContactResearchTests(unittest.TestCase):
    def test_unread_finish_reads_source_before_accepting(self):
        p = page('Alpha', 'Alex Example')
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        trace = {}
        actions = [action('search', query='Alpha people'), finish(p, 'Alpha', 'Alex Example'), finish(p, 'Alpha', 'Alex Example')]
        with patch('agent.contact_research.model_json', side_effect=actions), patch('agent.contact_research.search_web', return_value=[{'url': p['url']}]), patch('agent.contact_research.read_page', return_value=p) as read, patch('agent.research_runtime.time.sleep'):
            self.assertEqual(research_contact(job, Runtime(), trace)['name'], 'Alex Example')
        read.assert_called_once()
        self.assertEqual(trace['overrides'][0]['executed']['action'], 'read')

    def test_failed_page_recovers_on_another_source(self):
        from agent.research_tools import ResearchToolError
        p = page('Alpha', 'Alex Example')
        bad = 'https://alpha.example/broken'
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        trace = {}
        actions = [action('search', query='Alpha people'), action('read', url=bad), action('read', url=p['url']), finish(p, 'Alpha', 'Alex Example')]
        with patch('agent.contact_research.model_json', side_effect=actions), patch('agent.contact_research.search_web', return_value=[{'url': bad}, {'url': p['url']}]), patch('agent.contact_research.read_page', side_effect=[ResearchToolError('empty'), ResearchToolError('empty'), p]), patch('agent.research_runtime.time.sleep'):
            self.assertEqual(research_contact(job, Runtime(), trace)['name'], 'Alex Example')
        self.assertEqual(trace['counts']['read'], 3)
        self.assertEqual(trace['failed_urls'], [bad])

    def test_linkedin_query_rejected_with_feedback_before_web_call(self):
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        trace = {}
        def model(prompt, context, schema):
            if not context['validation_feedback']:
                return action('search', query='site:linkedin.com Alpha')
            return action('none', reason='No evidence')
        with patch('agent.contact_research.model_json', side_effect=model), patch('agent.contact_research.search_web', return_value=[]) as search, patch('agent.research_runtime.time.sleep'):
            with self.assertRaises(ResearchError):
                research_contact(job, Runtime(), trace)
        self.assertNotIn('linkedin', search.call_args.args[0])
        self.assertTrue(trace['validation_feedback'])

    def test_rejects_unread_or_invented_evidence(self):
        p = page('Alpha', 'Alex Example')
        a = finish(p, 'Alpha', 'Alex Example')
        with self.assertRaises(ResearchError): validate_contact(a, [])
        a['name'] = 'Invented Person'
        with self.assertRaises(ResearchError): validate_contact(a, [p])

    def test_two_companies_research_and_draft_without_reranking(self):
        jobs = [JobPosting('AI Engineer', c, 'Toronto', 'Build AI systems', f'https://{c.lower()}.example/job') for c in ('Alpha', 'Beta')]
        pages = [page('Alpha', 'Alex Example'), page('Beta', 'Blair Example')]
        actions = []
        for job, p, name in zip(jobs, pages, ('Alex Example', 'Blair Example')):
            actions.extend([action('search', query=f'{job.company} AI engineering team'),
                            action('read', url=p['url']), finish(p, job.company, name)])
        source = {'found': 2, 'jobs': [{'id': i, 'job': asdict(j), 'decision': {'is_relevant': True, 'reason': 'Fit'}} for i, j in enumerate(jobs, 1)],
                  'shortlist': [{'id': 1}, {'id': 2}]}
        cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path('source.json').write_text(json.dumps(source))
                with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake', 'TAVILY_API_KEY': 'fake'}), patch('agent.research_runtime.time.sleep'), patch('agent.contact_research.model_json', side_effect=actions), patch('agent.contact_research.search_web', side_effect=[[{'url': p['url'], 'title': 'Team', 'snippet': 'Lead'}] for p in pages]) as search, patch('agent.contact_research.read_page', side_effect=pages), patch('agent.shortlist_outreach.draft_outreach', side_effect=lambda j, p, contact: Draft(j, 'Role inquiry', f"Hi {contact['name']},")) as drafting, contextlib.redirect_stdout(io.StringIO()):
                    directory, report = run('source.json', Profile('Example', ['AI Engineer'], ['Toronto'], ['Built a prototype']))
                self.assertEqual(report['status'], 'completed')
                self.assertEqual(search.call_args_list[0].args[0], 'Alpha AI engineering team')
                self.assertEqual(search.call_args_list[1].args[0], 'Beta AI engineering team')
                self.assertEqual(drafting.call_args_list[0].kwargs['contact']['name'], 'Alex Example')
                self.assertEqual(drafting.call_args_list[1].kwargs['contact']['name'], 'Blair Example')
                self.assertTrue((directory / 'review.md').exists())
                self.assertEqual(json.loads(Path('source.json').read_text()), source)
            finally:
                os.chdir(cwd)

    def test_no_contact_and_budget_are_bounded(self):
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        trace = {}
        with patch('agent.contact_research.model_json', return_value=action('none', reason='No evidence.')), patch('agent.contact_research.search_web', return_value=[]) as initial_search, patch('agent.research_runtime.time.sleep'):
            self.assertIsNone(research_contact(job, Runtime(), trace))
        self.assertEqual(trace['status'], 'no_verified_contact')
        initial_search.assert_called_once()
        with patch('agent.contact_research.model_json', return_value=action('search', query='Alpha team')), patch('agent.contact_research.search_web', return_value=[]) as search, patch('agent.research_runtime.time.sleep'):
            research_contact(job, Runtime(), trace)
        self.assertEqual(search.call_count, 3)
        self.assertEqual(trace['counts']['search'], 3)

    def test_provider_failure_retries_then_raises_without_contact(self):
        from agent.research_tools import ResearchToolError
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        trace = {}
        with patch('agent.contact_research.model_json', return_value=action('search', query='Alpha team')), patch('agent.contact_research.search_web', side_effect=ResearchToolError('provider unavailable')) as search:
            with self.assertRaises(ResearchToolError):
                research_contact(job, Runtime(), trace)
        self.assertEqual(search.call_count, 2)
        self.assertEqual(trace['counts']['search'], 2)
        self.assertIsNone(trace['contact'])
        self.assertEqual(len(trace['errors']), 2)

    def test_malformed_selection_retries_without_unbounded_calls(self):
        trace = {}
        p = page('Alpha', 'Alex Example')
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        with patch('agent.contact_research.model_json', return_value=finish(p, 'Alpha', 'Alex Example')) as model, patch('agent.research_runtime.time.sleep'):
            with self.assertRaises(ResearchError):
                research_contact(job, Runtime(), trace)
        self.assertEqual(model.call_count, 2)
        self.assertIsNone(trace['contact'])

    def test_immediate_none_forces_broad_search_and_two_page_reads(self):
        job = JobPosting('Engineer', 'Beta', 'Toronto', 'Build', 'https://beta.example/job')
        pages = [page('Beta', 'Blair Example'), page('Beta', 'Casey Example')]
        pages[1]['url'] = 'https://beta.example/people'
        trace = {}
        with patch('agent.contact_research.model_json', return_value=action('none', reason='No Toronto contact.')), patch('agent.contact_research.search_web', return_value=[{'url': p['url']} for p in pages]) as search, patch('agent.contact_research.read_page', side_effect=pages) as read, patch('agent.research_runtime.time.sleep'):
            research_contact(job, Runtime(), trace)
        self.assertEqual(search.call_count, 1)
        self.assertNotIn('Toronto', search.call_args.args[0])
        self.assertEqual(read.call_count, 2)
        self.assertEqual(len(trace['overrides']), 3)
        self.assertEqual(trace['status'], 'no_verified_contact')

    def test_local_search_then_none_broadens_and_finds_contact(self):
        job = JobPosting('Engineer', 'Alpha', 'Toronto', 'Build', 'https://alpha.example/job')
        p = page('Alpha', 'Alex Example')
        trace = {}
        actions = [action('search', query='Alpha Toronto engineering'), action('none', reason='No local contact'),
                   action('none', reason='No local contact'), finish(p, 'Alpha', 'Alex Example')]
        with patch('agent.contact_research.model_json', side_effect=actions), patch('agent.contact_research.search_web', side_effect=[[], [{'url': p['url']}]]), patch('agent.contact_research.read_page', return_value=p), patch('agent.research_runtime.time.sleep'):
            contact = research_contact(job, Runtime(), trace)
        self.assertEqual(contact['name'], 'Alex Example')
        self.assertEqual(trace['counts']['search'], 2)
        self.assertEqual(trace['counts']['read'], 1)
