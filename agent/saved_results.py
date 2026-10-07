"""Validated reuse of saved postings; no decisions or profile data are reused."""
import json
from pathlib import Path
from agent.models import JobPosting


def load_saved_jobs(path: str) -> list[JobPosting]:
    """Return assessed then unassessed postings; invalid data raises ValueError.

    No network calls or writes. Requires complete found-count coverage so an
    interrupted report cannot silently masquerade as the full discovery set.
    """
    try:
        report = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(report, dict) or not isinstance(report.get('jobs'), list):
            raise ValueError('Expected a run report with jobs.')
        remaining = report.get('unassessed_jobs', [])
        if not isinstance(remaining, list):
            raise ValueError('Invalid unassessed_jobs.')
        rows = [entry['job'] for entry in report['jobs']] + remaining
        if type(report.get('found')) is not int or len(rows) != report['found']:
            raise ValueError('Saved report does not contain every discovered posting.')
        jobs = []
        required = {'title', 'company', 'location', 'description', 'source_url'}
        for row in rows:
            if not isinstance(row, dict) or not required <= row.keys() or row.keys() - required - {'provider_id'}:
                raise ValueError('Invalid saved posting fields.')
            if any(not isinstance(row[k], str) or not row[k].strip() for k in required):
                raise ValueError('Saved posting has missing text.')
            if not isinstance(row.get('provider_id', ''), str):
                raise ValueError('Invalid provider ID.')
            jobs.append(JobPosting(**row))
        return jobs
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
        raise ValueError(f'Cannot reuse saved results: {error}') from error


def load_saved_decisions(path: str, fingerprint: str) -> dict:
    """Validate reusable decisions and compatibility; legacy reports warn upstream."""
    report = json.loads(Path(path).read_text(encoding='utf-8'))
    previous = report.get('assessment_fingerprint')
    if previous is not None and previous != fingerprint:
        raise ValueError('Profile or classifier changed; use --from-results to reassess instead.')
    decisions = {}
    for index, entry in enumerate(report['jobs'], 1):
        decision = entry.get('decision')
        if decision is None:
            continue
        if (not isinstance(decision, dict) or set(decision) != {'is_relevant', 'reason'}
                or type(decision['is_relevant']) is not bool
                or not isinstance(decision['reason'], str) or not decision['reason'].strip()):
            raise ValueError('Invalid saved relevance decision.')
        decisions[index] = decision
    return {'decisions': decisions, 'legacy': previous is None}
