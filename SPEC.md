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
  with a logged error. Missing local configuration raises ValueError immediately.
  The initial implementation searches the first role/location in Canada only.
  Search does not perform relevance classification.
- `fetch_posting(url)` — returns posting text; fails: dead link / parse
  failure → skip role, log reason.
- `classify_relevance(posting, profile)` — returns fit/no-fit + reason.
- `research_company(posting)` — returns company context + hiring-team
  contacts (best effort).
- `draft_outreach(job, profile)` — one Gemini call returns a validated Draft;
  missing key raises ValueError, provider/format errors raise DraftingError.
- `save_draft(draft)` — saves a unique Markdown file under ignored drafts/;
  returns its path, raises DraftSaveError on filesystem failure.
- `send_email(draft)` — gated behind human approval; returns message ID.

## Escalation

_TODO — to be spec'd. Draft direction:_
- Every send requires explicit human approval — the approval gate IS the
  escalation path.
- Tool fails twice in a row → skip the role, log it, continue the run.
- Anything outside scope → refuse and log, never improvise.

## Decisions log

- 2026-09-30: Distinguish recruiting agencies from actual employers using
  explicit posting text. When recruiting for a client, say "the role you're
  recruiting for" and never infer the unnamed client's identity. When ambiguous,
  refer simply to the role. Missing leadership evidence means "not documented",
  not a claim that the candidate has an individual-contributor background.

- 2026-09-30: Add agent.cli and reusable workflow.run_workflow. Search once,
  process up to --max-jobs postings (default 3, first results not ranked),
  classify each and draft only relevant jobs. Retry provider/save failures once,
  log both attempts, skip a role after its second failure, and continue. Failed
  search ends the run. Save incremental results.json and Markdown in a unique
  ignored drafts/run-* directory, retaining decisions and errors. Missing config
  fails before network calls. Failure to persist run results stops visibly.

- 2026-09-30: Refine outreach to 60-100 words in three short paragraphs,
  connecting one supported experience example to one concrete responsibility
  from the posting. Avoid generic cover-letter openings and application claims.
  End with a simple conversation request. Recipient-level personalization awaits
  verified contact research; retain Hiring team now. Format checks are not an
  assessment of message quality; live review and deferred evals remain necessary.

- 2026-09-30: Add one-message drafting using the existing Gemini model and
  JSON schema API. Use only explicit experience bullets for candidate claims,
  respect never_claim, and use posting facts for tailoring. No research or
  invented contacts. Body addresses Hiring team, targets 80-150 words, and
  ends with a low-pressure conversation request. Append the profile name locally.
  Save Markdown with job context and a pending-human-review label under ignored
  drafts/, using unique filenames. The one-draft demo checks the first search
  result and drafts only if relevant; retries a failed step once, then stops
  visibly. Full multi-job CLI wiring and eval sets remain deferred.

- 2026-09-29: Tighten relevance reasons to separate Match, Gap, and Location
  evidence within the existing reason string. Preserve original experience
  scope (prototype versus production, contribution versus leadership). Surface
  explicit unmet or unverified requirements without inventing experience or
  remote eligibility. Compare previous and revised prompts on identical inputs
  as a manual check, not a claim of measured general quality improvement.

- 2026-09-29: Correct relevance handling of never_claim after observed false
  rejections. These constraints govern statements about the candidate, not job
  eligibility or desired seniority. Do not reject solely because a posting has a
  title the candidate has not held or because of a never_claim entry. Assess
  actual responsibilities and explicit qualification evidence; describe unknowns
  without treating absent experience as a proven mismatch. Preserve these
  constraints for factual explanations and future outreach drafting.

- 2026-09-29: Correct Gemini selection to gemini-3.5-flash-lite after a 404
  on a new project. Google's availability notice restricts 2.5 models to prior
  users and recommends 3.5 Flash-Lite for new projects; its standard input/output
  currently has Free-tier pricing. Preserve the no-paid-fallback policy.

- 2026-09-29: Switch relevance from OpenAI to Gemini 2.5 Flash-Lite after the
  user confirmed a Gemini Free-tier project. Use GEMINI_API_KEY, one standard
  generateContent request, structured JSON, and the existing decision contract.
  No automatic provider/model fallback or billing changes. Free usage depends on
  the key's project remaining Free tier; code cannot infer billing from the key.
  Quota errors stop the call. Start with fictional inputs because unpaid-service
  content may be used to improve Google products. Preserve prompt policy and
  local validation; defer evals as previously agreed.

- 2026-09-29: Relevance uses one OpenAI Responses API request per job, with
  gpt-4.1-mini as the initial configurable baseline (OPENAI_MODEL override).
  OPENAI_API_KEY stays in the environment. Keep plausible matches and reasonable
  stretch roles; reject clear role/location/qualification mismatches. Unknown
  qualifications are not invented or automatically treated as disqualifications;
  explain uncertainty. Posting/profile text is data, not executable instructions.
  Send preferences, experience bullets, and never_claim, not contact identifiers.
  Strict JSON output must contain boolean is_relevant and nonempty string reason.
  Missing configuration raises ValueError. Request failures, refusal, incomplete
  output, and malformed decisions raise RelevanceError, never a false no-fit.
  The future workflow owns one retry then logging/skipping; the classifier itself
  makes one request with a 60-second timeout and store=false. Evals remain deferred.

- 2026-09-29: Implement the first live search with JSearch search-v2 using
  OPENWEBNINJA_API_KEY from the environment. One request uses the first target
  role and first location, with country=ca for this initial Canadian slice.
  No pagination or multi-preference search yet. Timeout is 30 seconds; the
  future workflow owns retries. Missing key/preferences raise ValueError before
  any request. HTTP, connection, and response-shape errors raise JobSearchError.
  Title, company, description, and apply link must be nonempty strings; absent
  location is represented as "Not specified". An unusable posting fails the
  response visibly rather than silently dropping it.

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
