"""Research contacts and draft for saved shortlist positions, without reranking."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from agent.cli import positive_integer
from agent.models import JobPosting
from agent.profile import load_profile
from agent.saved_results import load_saved_jobs
from agent.contact_research import research_contact
from agent.research_runtime import Runtime, ResearchError
from agent.research_tools import ResearchToolError
from agent.quota import QuotaError
from agent.drafting import draft_outreach, DraftingError
from agent.storage import save_draft, DraftSaveError


def selected_jobs(path, ranks=None):
    """Validate saved shortlist references before network calls; return rank/job pairs."""
    load_saved_jobs(path)
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    shortlist = report.get('shortlist')
    if not isinstance(shortlist, list) or not shortlist:
        raise ValueError('Saved report has no shortlist.')
    entries = {}
    for entry in report['jobs']:
        ident = entry.get('id')
        if type(ident) is not int or ident in entries:
            raise ValueError('Invalid or duplicate saved job ID.')
        entries[ident] = entry
    ids = []
    for item in shortlist:
        ident = item.get('id') if isinstance(item, dict) else None
        if type(ident) is not int or ident not in entries or ident in ids:
            raise ValueError('Invalid shortlist job reference.')
        if entries[ident].get('decision', {}).get('is_relevant') is not True:
            raise ValueError('Shortlist references a job without a positive assessment.')
        ids.append(ident)
    ranks = ranks or list(range(1, len(ids) + 1))
    if len(set(ranks)) != len(ranks) or any(type(r) is not int or not 1 <= r <= len(ids) for r in ranks):
        raise ValueError('Choose distinct positions within the saved shortlist.')
    return [(r, JobPosting(**entries[ids[r - 1]]['job'])) for r in ranks]


def run(path, profile, ranks=None, rpm=10):
    jobs = selected_jobs(path, ranks)
    runtime = Runtime(rpm)
    for key in ('GEMINI_API_KEY', 'TAVILY_API_KEY'):
        if not os.environ.get(key, '').strip():
            raise ValueError(f'Set {key} in this terminal.')
    directory = Path('drafts') / f'outreach-{uuid4().hex}'
    directory.mkdir(parents=True)
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'source_results': str(Path(path).resolve()),
              'status': 'running', 'gemini_rpm': rpm, 'jobs': [], 'nothing_sent': True}
    def persist():
        temporary = directory / 'results.json.tmp'
        temporary.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        temporary.replace(directory / 'results.json')
    persist()
    for rank, job in jobs:
        print(f'Researching shortlist #{rank}: {job.title} | {job.company}')
        entry = {'rank': rank, 'title': job.title, 'company': job.company, 'status': 'researching',
                 'research': {}, 'errors': []}
        report['jobs'].append(entry)
        persist()
        try:
            contact = research_contact(job, runtime, entry['research'], persist)
            entry['status'] = 'drafting'
            persist()
            draft = runtime.call(lambda: draft_outreach(job, profile, contact=contact),
                                 entry['errors'], 'draft', DraftingError, model=True)
            entry['draft'] = {'subject': draft.subject, 'body': draft.body}
            persist()
            saved = runtime.call(lambda: save_draft(draft, directory), entry['errors'], 'save', DraftSaveError)
            entry.update(status='drafted_pending_review', draft_file=saved.name)
        except QuotaError as error:
            entry.update(status='quota_limited')
            if entry['research'].get('status') == 'researching':
                entry['research']['status'] = 'quota_limited'
            entry['errors'].append({'stage': 'quota', **error.details})
            report['status'] = 'quota_limited'
            persist()
            break
        except (ResearchError, ResearchToolError, DraftingError, DraftSaveError, ValueError) as error:
            entry.update(status='failed')
            entry['errors'].append({'stage': 'job', 'message': str(error)})
            if entry['research'].get('status') == 'researching':
                entry['research']['status'] = 'failed'
            print(f'Skipping role: {error}')
        persist()
    if report['status'] != 'quota_limited':
        report['status'] = 'completed_with_errors' if any(e['status'] == 'failed' for e in report['jobs']) else 'completed'
    report['unattempted_ranks'] = [r for r, _ in jobs if r not in {e['rank'] for e in report['jobs']}]
    persist()
    lines = ['# Outreach review', '', f"Status: {report['status']}", '', 'PENDING HUMAN REVIEW. Nothing sent.', '']
    for entry in report['jobs']:
        lines += [f"## {entry['rank']}. {entry['title']} | {entry['company']}", '', f"Status: {entry['status']}", '']
        contact = entry['research'].get('contact')
        if contact:
            lines += [f"Contact: {contact['name']} — {contact['title']} — {contact['organization']}", '',
                      f"Public page: {contact['public_url']}", '', contact['reason'], '',
                      'Opening ownership and referral ability are not assumed.', '']
            lines += [f"Uncertainty: {u}" for u in contact['uncertainties']]
            for evidence in contact['evidence']:
                lines += ['', f"Source: {evidence['url']}", '', evidence['excerpt'], '']
        else:
            lines += [f"No selected contact: {entry['research'].get('reason', entry['research'].get('status', 'unavailable'))}", '']
        for error in entry['errors']:
            lines += [f"Error: {error}", '']
        if 'draft' in entry:
            lines += [f"### {entry['draft']['subject']}", '', entry['draft']['body'], '']
    (directory / 'review.md').write_text('\n'.join(lines), encoding='utf-8')
    return directory.resolve(), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--profile', default='profile/profile.yaml')
    parser.add_argument('--ranks', nargs='+', type=positive_integer, help='Shortlist positions; default all')
    parser.add_argument('--gemini-rpm', type=positive_integer, default=10)
    args = parser.parse_args()
    try:
        directory, report = run(args.results, load_profile(args.profile), args.ranks, args.gemini_rpm)
    except (ValueError, OSError) as error:
        parser.exit(1, f'Stopped: {error}\n')
    print(f"Status: {report['status']}\nReview: {directory / 'review.md'}\nNothing sent.")
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
