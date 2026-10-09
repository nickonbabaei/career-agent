"""Draft from explicit saved recipient choices, without repeating research."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from agent.models import JobPosting
from agent.profile import load_profile
from agent.contact_research import validate_contact, eligible_title
from agent.drafting import draft_outreach, DraftingError
from agent.storage import save_draft, DraftSaveError
from agent.research_runtime import Runtime, ResearchError
from agent.quota import QuotaError


def validate_choices(report, choices):
    """Return chosen job/contact pairs. Reject incomplete choices before any calls."""
    if report.get('stage') != 'contact_review' or report.get('status') == 'running':
        raise ValueError('Choose a finished contact-research run.')
    jobs = report.get('jobs', [])
    if not isinstance(choices, dict) or set(choices) != {str(e['rank']) for e in jobs}:
        raise ValueError('Choose a recipient option or Skip for every job.')
    selected = []
    for entry in jobs:
        choice = choices[str(entry['rank'])]
        if not isinstance(choice, dict):
            raise ValueError('Invalid recipient choice.')
        mode = choice.get('mode')
        contact = None
        if mode == 'skip':
            continue
        if entry.get('verification', {}).get('concern') == 'flagged':
            raise ValueError('This job has an authenticity concern and cannot be drafted. Choose Skip.')
        if mode == 'researched':
            research = entry.get('research', {})
            contact = research.get('contact')
            if research.get('status') != 'contact_found' or not contact:
                raise ValueError('This job has no supported researched contact.')
            try:
                contact = validate_contact(contact, research.get('inspected', []))
            except ResearchError as error:
                raise ValueError('Saved contact evidence could not be validated. Choose another recipient option or repeat research.') from error
        elif mode == 'manual':
            supplied = choice.get('contact')
            if choice.get('confirmed') is not True or not isinstance(supplied, dict):
                raise ValueError('Confirm the details of your supplied contact.')
            contact = {}
            for key in ('name', 'title', 'organization'):
                value = supplied.get(key)
                if not isinstance(value, str) or not value.strip() or len(value) > 200 or '\n' in value or '\r' in value:
                    raise ValueError('Provide a name, title, and organization for the contact.')
                contact[key] = value.strip()
            if supplied.get('relationship') not in ('employee', 'recruiter'):
                raise ValueError('Choose employee or recruiter.')
            if not eligible_title(contact['title']):
                raise ValueError('Choose a non-executive employee or recruiter, not a director, VP, chief or founder.')
            contact.update(source='user_supplied', relationship=supplied['relationship'],
                           public_url='', evidence=[], reason='Contact supplied and confirmed by the user.',
                           uncertainties=['Affiliation supplied by user; not independently verified. Opening ownership and referral ability unknown.'])
        else:
            raise ValueError('Choose a named researched contact, your own contact, or Skip. Generic outreach is no longer offered.')
        selected.append((entry, JobPosting(**entry['job']), contact, mode))
    if not selected:
        raise ValueError('Choose at least one job to draft for.')
    return selected


def run(source, choices_path, profile):
    original = json.loads(Path(source).read_text())
    choices = json.loads(Path(choices_path).read_text())
    selected = validate_choices(original, choices)
    directory = Path('drafts') / f'outreach-{uuid4().hex}'
    directory.mkdir(parents=True)
    report = dict(created_at=datetime.now(timezone.utc).isoformat(), status='running', stage='drafts',
                  source_research=str(Path(source).resolve()), jobs=[], nothing_sent=True)
    runtime = Runtime()
    def persist():
        temp = directory / 'results.json.tmp'
        temp.write_text(json.dumps(report, indent=2))
        temp.replace(directory / 'results.json')
    persist()
    for original_entry, job, contact, mode in selected:
        entry = dict(rank=original_entry['rank'], title=job.title, company=job.company,
                     status='drafting', recipient_mode=mode, research={'contact':contact}, errors=[])
        report['jobs'].append(entry)
        print(f'Drafting: {job.title} | {job.company}', flush=True)
        persist()
        try:
            draft = runtime.call(lambda: draft_outreach(job, profile, contact), entry['errors'], 'draft', DraftingError, model=True)
            entry['draft'] = dict(subject=draft.subject, body=draft.body)
            saved = runtime.call(lambda: save_draft(draft, directory), entry['errors'], 'save', DraftSaveError)
            entry.update(status='drafted_pending_review', draft_file=saved.name)
        except QuotaError as error:
            entry.update(status='quota_limited')
            entry['errors'].append({'stage':'quota', **error.details})
            report['status'] = 'quota_limited'
            persist()
            break
        except (DraftingError, DraftSaveError, ValueError) as error:
            entry['status'] = 'failed'
            entry['errors'].append({'stage':'draft', 'message':str(error)})
        persist()
    if report['status'] == 'running':
        report['status'] = 'completed_with_errors' if any(j['errors'] and j['status']=='failed' for j in report['jobs']) else 'completed'
    report['unattempted_ranks'] = [e['rank'] for e, _, _, _ in selected if e['rank'] not in {j['rank'] for j in report['jobs']}]
    persist()
    return directory, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', required=True)
    parser.add_argument('--choices', required=True)
    args = parser.parse_args()
    try:
        directory, report = run(args.results, args.choices, load_profile('profile/profile.yaml'))
    except (ValueError, OSError) as error:
        parser.exit(1, f'Stopped: {error}\n')
    print(f"Status: {report['status']}\nReview files: {directory}\nNothing sent.")
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
