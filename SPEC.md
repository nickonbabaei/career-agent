# SPEC — Outreach Agent

An open-source agent that finds jobs matching a user's profile, researches
roles and companies, and drafts tailored outreach messages — with a human
reviewing and sending every message. Built FDE-style: spec first, fixed
workflow backbone, trust layer throughout.

## Vision

A job seeker signs in with LinkedIn (profile context), submits a resume,
and inputs the role types they're looking for. The agent finds matching
jobs, drafts tailored outreach to hiring managers/teams, builds a job
tracker, and serves every draft in a review queue. The user approves, edits,
or rejects each message — nothing is ever sent without explicit per-message
approval.

## Architecture

Fixed workflow backbone (steps are known and always the same):

```
find jobs → relevance filter → research role/company → match background → draft → human review → (approved) send
```

- A small agent loop lives inside the research step (company/hiring-team
  lookup), where the steps can't be fixed in advance.
- Relevance filtering ("is this posting a fit for this profile?") is a
  single-call classification step.
- Rationale: pick the simplest architecture that works (Lecture 1 rule).

## Scope

### Handles
- Job discovery: searches job listings via a third-party job API based on
  the user's target role types and locations. No hand-rolled LinkedIn
  scraper (ToS risk).
- Relevance classification: filters postings against the user profile.
- Research: role requirements, company context, and hiring-team contacts —
  best effort. Uses LinkedIn job posts' "who to reach out to" section when
  present; falls back to a "hiring team" draft when not.
- Drafting: tailored outreach messages (email; LinkedIn messages are
  manual copy-paste — API won't allow sending).
- Job tracker: every role logged with status (found → drafted → approved →
  sent → replied).
- Review queue: approve / edit / reject per draft.

### Refuses / never does
- Never sends anything without explicit per-message human approval.
- Never submits job applications.
- Never scrapes LinkedIn in ToS-violating ways.
- Never invents experience — drafts draw only from the user's profile
  (resume + LinkedIn + experience bullets).

## Permissions

_TODO — to be spec'd. Draft direction:_
- Reads: user profile directory, job API (public listings only).
- Writes: drafts, tracker entries, logs/traces.
- Sends: email only via user's connected Gmail, only after per-message
  approval. No LinkedIn sending, ever.

## Tool contracts

_TODO — to be spec'd. Tools so far:_
- `search_jobs(profile)` — returns `list[JobPosting]` from a third-party API
  using target roles and locations. Empty results return `[]`. Provider errors
  raise `JobSearchError`; the future workflow retries once, then ends the run
  with a logged error. The current unimplemented stub raises `NotImplementedError`
  immediately. Search does not perform relevance classification.
- `fetch_posting(url)` — returns posting text; fails: dead link / parse
  failure → skip role, log reason.
- `classify_relevance(posting, profile)` — returns fit/no-fit + reason.
- `research_company(posting)` — returns company context + hiring-team
  contacts (best effort).
- `draft_outreach(posting, research, profile)` — returns draft message.
- `send_email(draft)` — gated behind human approval; returns message ID.

## Escalation

_TODO — to be spec'd. Draft direction:_
- Every send requires explicit human approval — the approval gate IS the
  escalation path.
- Tool fails twice in a row → skip the role, log it, continue the run.
- Anything outside scope → refuse and log, never improvise.

## Decisions log

- 2026-09-29: Add the live search contract in agent/tools.py, leaving its
  implementation to the user. A separate agent/fixtures.py loader reads an
  explicitly labeled fictional JSON jobs fixture for offline development.
  It validates fields and returns JobPosting objects without searching,
  filtering, network calls, or automatic fallback from live search. Invalid
  fixture files raise FixtureError immediately; valid empty lists return [].

- 2026-09-29: First implementation slice defines Python dataclasses for Profile,
  JobPosting, RelevanceDecision, and Draft, plus a YAML profile loader. Required
  profile fields are name and nonempty lists of target_roles, locations, and
  experience_bullets. Optional fields are email, linkedin_url, resume_path,
  and never_claim. Unknown keys and invalid types fail immediately with a
  ProfileConfigError; no retry for local configuration errors. Resume paths
  and LinkedIn URLs are stored as metadata only, not read or fetched.

- 2026-09-28: First v0.1 milestone is an offline CLI run with synthetic
  fixtures, validated YAML profile config, a fixed pipeline, and drafts saved
  locally for review. Fixture mode is explicitly labeled and does not perform
  model classification or generate tailored outreach. Live search, relevance,
  and drafting implementations belong to the user; scaffold exposes contracts.
- 2026-09-28: At the user's request, defer eval sets and the drafting-eval merge
  requirement until after the first full run. Verify scaffold plumbing now.
  Also defer enrichment, resume/LinkedIn ingestion, send integration, tracker,
  advanced preferences, claim IDs, and external tracing. v0.1 uses only explicit
  profile experience bullets and posting context; default recipient is hiring team.
- 2026-09-28: A tool failure retries once, then records a visible failure.
  Search failure ends the run; per-role failure skips that role and continues.
  Unimplemented functions and invalid config fail immediately. Empty search
  results and rejected jobs are successful outcomes distinct from errors.
  Each run writes JSON results and Markdown drafts into a unique ignored local
  directory. Fixture runs are marked as such in every draft.

- 2026-09-28: Open-source on GitHub so anyone can use it. User background
  is config (`profile/`), not hardcoded.
- 2026-09-28: LinkedIn sign-in is for profile context only (who the user
  is) — not for sending or scraping (API/ToS constraints).
- 2026-09-28: Hiring-manager identification via LinkedIn "who to reach out
  to" when present; "hiring team" fallback otherwise.
- 2026-09-28: Send mechanism (proposed): Gmail send behind per-message
  approval; LinkedIn outreach manual copy-paste.
- 2026-09-28: Role sourcing: agent finds jobs via third-party job API
  (not user-pasted URLs, not LinkedIn scraping).
- 2026-09-28: Stack mirrors the Cartwheel agent repo (agent/, SPEC.md,
  evals, observability, trust layer) applied to a real use case.
