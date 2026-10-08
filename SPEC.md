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
  This legacy helper searches the first role/location using search_country.
  The CLI uses plan_queries and search_query across preferences, within its
  request budget; failed queries do not discard successful batches.
  Search does not perform relevance classification.
- `rank_jobs(candidates, profile)` — one call returns every candidate ID once,
  in strongest-fit order with reasons. Empty input returns []. Missing key raises
  ValueError; request/shape/ID errors raise RankingError. Retry once, then retain
  assessments without a ranked shortlist or drafts.
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

- 2026-10-08: Contact citation recovery records rejected model actions and
  identifies the offending URL/excerpt. Accept whitespace-only differences while
  retaining the exact original source excerpt; never accept paraphrases. If a
  quote exists in a cached but unread section, inspect that section before asking
  for a corrected selection. Keep retry/model budgets and provenance checks.

- 2026-10-08: After repeated live 3.5 Flash-Lite 503s, user-authorized alternative
  gemini-3.1-flash-lite passed minimal and research-schema probes. Use it for
  contact research only, record model in trace. Other stages retain existing
  model. No automatic fallback or billing changes; free usage requires a free
  project and available quota. This supersedes today's initial no-switch decision.

- 2026-10-08: Live diagnostics found intermittent Gemini 503s on otherwise
  successful request shapes. A recovered model/validation retry must not turn
  a later completed no-contact decision into a failed role. Preserve retry errors
  in the trace; no-contact remains failed if page extraction exhausted retries.
  No model switch: identical initial research requests succeeded with current model.

- 2026-10-08: Gemini research 503 is a temporary provider failure. Keep one
  retry per operation, but wait 15 seconds before retrying (or honor supplied
  Retry-After up to 60 seconds; longer delays skip retry). Give an actionable
  message without suggesting invalid keys, no-contact, or poor job fit.

- 2026-10-08: First guided-UI slice: profile summary -> assessed job selection
  -> existing research/drafting -> review. Show all assessed jobs, recommend and
  initially select top three, allow explicit override of no-fit judgments. Persist
  selection per search run, reject empty/duplicate/unassessed IDs before calls.
  Carry original job IDs into outreach; do not mutate ranking. Contact approval
  between research and drafting remains the next slice, not represented as live.

- 2026-10-08: Add consent-labelled PDF resume import to local UI. Extract text
  with pypdf (5 MB, 10 pages, 40k characters maximum; encrypted/scanned/empty
  pages rejected without model calls). Send extracted text to Gemini for a
  structured proposed background, with one retry on provider/output failure.
  Upload bytes are memory-only and never served or persisted. Preview replaces
  background only after user saves; preserve preferences and constraints. No
  inferred target roles, tenure, metrics, or experience. No agent loop or OCR.

- 2026-10-07: Add work_experience records (title, company, start_date, end_date,
  achievements), plus projects, education, and skills lists. Keep legacy
  experience_bullets as uncategorized facts for lossless compatibility. At least
  one background fact is required. Model inputs use a deterministic facts list
  with each achievement attached to its explicit role/date context; no inferred
  tenure or qualifications. UI supports add/remove role cards and separate
  background sections. Migrate only explicit headings/associations, preserve
  uncertain facts for user review, and back up the private profile locally.

- 2026-10-07: Replace UI YAML editing with a prefilled structured profile form.
  Repeatable fields preserve each experience bullet/role/location verbatim;
  optional preferences and drafting restrictions remain explicit user inputs.
  Preserve contact/resume metadata when saving. Validate through the existing
  profile loader and atomically write YAML; no extraction or invented facts.

- 2026-10-07: Local UI accepts provider keys once through password fields.
  Persist in gitignored .local/keys.json with owner-only directory/file permissions;
  this is local plaintext storage, not an encrypted vault. Never return saved
  values to the browser. Blank inputs retain existing keys; saved keys override
  terminal keys for UI workers. Add a macOS double-click launcher using the
  existing virtual environment. No terminal activation/export required.

- 2026-10-07: Start local v0.2 UI using a loopback-only Python HTTP server and
  browser HTML/CSS/JavaScript, reusing existing CLI workflows in one background
  subprocess at a time. Edit validated local profile YAML, start discovery,
  resume assessments, research a saved shortlist, and review contacts/evidence.
  Save user edits as separate review JSON; never overwrite generated evidence or
  send messages. No accounts, remote hosting, resume ingestion, or billing changes.
  Same-origin requests plus a per-server token protect writes. Only known run
  directories are readable. This local UI is not a multi-user deployment.

- 2026-10-01: Research recovery: reject LinkedIn-targeted queries before Tavily;
  give model actionable validation feedback on retry. A premature contact citing
  a discovered but unread page triggers a read, never acceptance from snippets.
  Failed extraction retries once, then marks that URL unavailable and continues
  to other discovered sources within the same budgets. Provider/validation
  failures with no eventual contact remain failed, not successful no-contact.
  All corrections/errors remain in trace. No drafting or sending changes.

- 2026-10-01: Prevent premature no-contact outcomes. If the model proposes none,
  the controller first performs a company-wide people search (no location or
  exact-title restriction), then inspects up to two distinct discovered pages,
  prioritizing directory paths, within existing budgets. Broaden an unsuccessful
  location-specific search before allowing none. Record model proposals and
  controller overrides separately. No-result searches may finish without page
  reads. Budget limits and provider failures remain explicit; no invented contact.

- 2026-10-01: Connect saved shortlist -> bounded public-contact research ->
  personalized draft in agent.shortlist_outreach. Default all shortlisted jobs;
  --ranks selects positions for testing. No discovery/reclassification/ranking.
  Each job permits 3 search requests, 5 extraction requests, and 12 research
  model requests, including retries. Cached section reads consume model steps
  but no web calls. Shared Gemini pacing and bounded quota retry across jobs.
  Exhausted provider failures skip the job; genuine no-contact/budget exhaustion
  uses hiring-team fallback. Persist research actions, pages, excerpts and errors.
- 2026-10-01: Relevant role plus supported company affiliation suffices for a
  contact; specific opening ownership/referral ability is optional and never
  assumed. Model claims require exact excerpts from inspected sections, covering
  name, title and organization; validate provenance mechanically, retain human
  review for semantic accuracy. No invented contacts, email guessing, LinkedIn
  fetching, attribution of marketing articles to featured staff, or automatic
  sending. Named drafts ask employees about a possible referral and recruiters
  about the role or correct colleague. Do not guess unnamed client employers.
  Offline synthetic contact/drafting evals precede live two-company validation.

- 2026-10-01: Preserve all text returned by page extraction in local evidence;
  do not silently cut at 16000 characters. This does not guarantee the provider
  extracted the whole webpage. Supply numbered 4000-character sections with
  offsets, and bounded keyword-selected previews. Prefer About/People/Team
  directory URLs over services/articles when choosing the probe's two pages.
  Selection remains a transparent heuristic, not contact verification. No new
  calls, autonomous loop, or drafting changes. Legacy truncated artifacts require
  fetching again to recover discarded text.

- 2026-10-01: Start public-web contact research with Tavily search/extract using
  TAVILY_API_KEY. First slice is an evidence probe, not autonomous contact
  selection or personalized drafting. Search sends only a company/role query;
  extraction reads public URLs returned by that search. No profile sent to the
  search provider, guessed emails, LinkedIn scraping, or sending. Basic search
  and extraction only; no automatic provider fallback or billing changes.
  Probe retries once, logs failures, and saves evidence under ignored drafts/.
  Search snippets are leads, not verified employment/contact claims.
- 2026-10-01: Research result contract: status, actual-employer assessment,
  contact name/title/organization/public URL, employee/recruiter relationship,
  evidence excerpts and source URLs, uncertainty, and reason for selection.
  No contact is a valid outcome distinct from provider failure. Later bounded
  research loop permits three search attempts and five page-read attempts
  (including retries), with a separate model-call cap. Confirm recruiter versus
  employer before seeking referrals; unnamed clients stay unknown. Contact
  evidence must come from inspected pages and remain reviewable. This slice
  does not change drafting or wire research into the main CLI yet.

- 2026-10-01: CLI workflows pace Gemini request starts at a configurable
  --gemini-rpm (positive integer, default 10), shared across classification,
  ranking, drafting and retries within one run. First call starts immediately;
  elapsed request/retry-wait time counts toward spacing. Local saves/search and
  reused decisions do not consume slots. This conservative default is not a
  claim about provider quota; concurrent processes and token/day limits remain
  outside this per-run limiter. Record the setting without changing assessment
  compatibility. Existing bounded quota retry/stop remains the fallback.

- 2026-09-30: Add --resume-results, distinct from reassessment: retain validated
  decisions, retry failed/pending classifications, then rerank in a new directory.
  Record a profile/classifier fingerprint for new runs and reject mismatches;
  legacy reports lack this evidence, so warn explicitly and assume the current
  profile matches for recovery. Resume supports classification/ranking recovery;
  reject --draft on resume to avoid duplicating previously generated messages.
  Save every posting before classification so interruptions remain recoverable.
  max-jobs caps the candidate set, not the number of new calls.
- 2026-09-30: Gemini 429 is a shared provider failure, not a per-job rejection.
  Record sanitized quota identifiers and retry timing. Respect Retry-After or
  RetryInfo: retry once after at most 60 seconds, default 30 if unspecified;
  longer waits or persistent 429 end with quota_limited, retaining progress.
  No subsequent job/ranking calls after persistent quota failure. Counts separate
  attempted, successful assessments, failures and pending jobs. Ordinary errors
  retain retry-once/skip behavior. No prompt or drafting-content changes.

- 2026-09-30: Ranking explanations must compare against another supplied role,
  citing a material evidence difference or acknowledging a near tie. Preserve
  exact experience scope; posting requirements are never candidate achievements.
  Display one fit assessment and a separate comparative rationale.
  Add --from-results to reassess saved postings with the current profile and
  prompts, without JSearch. Reclassify rather than reuse stale decisions; save a
  new run with source provenance and leave the source untouched. The max-jobs
  cap still applies. Invalid/incomplete saved posting data fails before API calls.

- 2026-09-30: Broader discovery uses a deduplicated role/location query grid,
  location-major order, within --max-search-requests (default 4, including
  retries). Each query fetches one page; Remote uses work_from_home=true with
  the explicit profile search_country (default ca). Log truncated coverage and
  query failures, retain successful batches, and interleave batches before
  --max-jobs (default 10). Deduplicate by provider job ID or exact apply URL;
  do not collapse distinct postings just because title/company match.
- 2026-09-30: Optional seniority_preferences, employment_preferences, and
  work_arrangements describe acceptable options; empty lists mean unspecified.
  Explicit conflicts reject; missing data remains unknown. Preferences never
  become claims about qualifications. Existing YAML profiles remain valid.
- 2026-09-30: After individual classification, one comparative Gemini call ranks
  all relevant assessed jobs using full postings/profile and fit reasons. Return
  every candidate exactly once by locally assigned ID with an evidence-based
  ranking explanation. Validate IDs/duplicates/completeness; keep top --top-k
  (default 3), generate drafts only when --draft is supplied. Ranking failure
  after one retry retains assessments and saves no misleading ordered shortlist.
  Shortlist ranks only assessed results, not all jobs on the market. Save full
  JSON and readable shortlist Markdown. Include search coverage and count
  skipped/unassessed jobs. Regression tests use mocks; separate opt-in live
  synthetic cases assess prompt behavior without claiming model accuracy from mocks.

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
