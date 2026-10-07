# Small live regression checks

Run from the repository root with the virtual environment active and
GEMINI_API_KEY exported:

```sh
python -m evals.check_relevance --live
```

This sends three fictional profile/posting pairs to Gemini, with one retry per
provider failure (at most six calls). It does not search JSearch or send messages.
Results and reasons are printed and saved under ignored drafts/eval-*.json.
A failure or unexpected boolean exits nonzero. Missing configuration stops visibly.

The cases cover a never_claim constraint being mistaken for a role exclusion,
an unrelated profession, and an explicit remote/on-site preference conflict.
Read the reasons too: three passing booleans do not establish overall quality.
The offline tests in tests/ check plumbing, not these model judgments.

For the first real shortlist, manually check whether each ranking reason cites
actual profile/posting evidence, flags unknown seniority and eligibility, and
places supported matches above roles with major unverified requirements.

Drafting has not changed in this slice. When reviewing drafts, verify every
experience claim against the profile, preserve prototype/production and
contribution/leadership distinctions, distinguish a recruiter from its client,
and never invent a recipient or unnamed employer. A larger draft-quality eval
suite and automated judging remain future work.

## Contact-aware drafting regression check

`python -m unittest discover -s evals -p 'test_*.py' -v` exercises named-contact
and hiring-team fallback context/greetings with fictional data and mocked Gemini.
It does not score generated prose. For live Morningstar/Exadel runs, check:

- Name/title/company have supporting inspected source excerpts.
- The contact is relevant without claiming ownership of the specific opening.
- Employee messages request a possible referral; agency messages request help
  with the opening or the correct colleague, without guessing an unnamed client.
- Featured contacts are not falsely described as article authors.
- Candidate claims remain in the profile; no inflated seniority or relationship.
- Provider errors remain failures, not fabricated contacts or silent no-match.
