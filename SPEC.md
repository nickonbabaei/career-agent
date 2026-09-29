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
- `search_jobs(role_types, locations)` — returns postings; fails: API
  error → retry once, then skip run with logged error.
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
