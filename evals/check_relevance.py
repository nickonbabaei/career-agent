"""Opt-in live smoke checks using fictional profiles and postings."""
import argparse
import json
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from agent.models import Profile, JobPosting
from agent.relevance import classify_relevance, RelevanceError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Make Gemini calls using GEMINI_API_KEY')
    args = parser.parse_args()
    if not args.live:
        parser.error('Pass --live to authorize up to six Gemini calls (three cases plus retries).')
    profile = Profile(name='Fictional Candidate', target_roles=['Python Developer'],
                      locations=['Toronto'], experience_bullets=['Built and deployed Python REST APIs.'],
                      never_claim=['Do not claim senior titles previously held.'])
    job = JobPosting('Senior Python Developer', 'Fictional Company', 'Toronto',
                     'Build Python REST APIs in Toronto. Senior title; no minimum years stated.',
                     'https://example.com/fictional-job')
    cases = [
        ('never_claim_is_not_a_role_exclusion', profile, job, True),
        ('unrelated_role', profile, replace(job, title='Dental Hygienist',
          description='Provide clinical dental hygiene care; active dental hygiene license required.'), False),
        ('explicit_work_arrangement_conflict', replace(profile, work_arrangements=['remote']),
          replace(job, description='Build Python REST APIs. On-site five days weekly; no remote work.'), False),
    ]
    results = []
    for name, candidate, posting, expected in cases:
        result = {'case': name, 'expected': expected, 'errors': []}
        for attempt in (1, 2):
            try:
                decision = classify_relevance(posting, candidate)
                result.update(actual=decision.is_relevant, reason=decision.reason,
                              passed=decision.is_relevant == expected)
                break
            except RelevanceError as error:
                result['errors'].append(str(error))
                result['passed'] = False
        results.append(result)
        print(json.dumps(result, indent=2))
    output = Path('drafts') / f'eval-{uuid4().hex}.json'
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f'Saved: {output.resolve()}')
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
