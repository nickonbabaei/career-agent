# Outreach Agent

An open-source agent that finds jobs matching your profile and drafts
tailored outreach messages — with you reviewing and sending every message.

## How it works

```
find jobs → relevance filter → research role/company → match background → draft → human review → send
```

1. **Onboard** — sign in with LinkedIn (profile context), drop in your
   resume, tell it what roles you want.
2. **Agent works** — finds matching jobs, researches each role and company,
   drafts a tailored outreach message per role.
3. **You review** — every draft lands in a review queue. Approve, edit, or
   reject. Nothing sends without your explicit approval, per message.
4. **Tracker** — every role is logged: found → drafted → approved → sent →
   replied.

## The stack

Built like a production agent, not a demo script:

| Layer | In this repo |
|---|---|
| Spec | `SPEC.md` — scope, permissions, tool contracts, escalation |
| Agent runtime | `agent/` — fixed workflow + research sub-loop |
| Context | `profile/` — your resume, LinkedIn, target roles |
| Trust & governance | Per-message approval gates, audit log of sends |
| Observability | `observability/` — traces of every run |
| Evals | `evals/` — draft-quality rubric + regression cases |
| Surfaces | `server/` — review-queue UI (v2; CLI first) |

## Repo map

```
AGENTS.md              instructions for your coding agent
SPEC.md                spec: scope, permissions, tool contracts, escalation
profile/               user background — the single source of truth (see profile.yaml.example)
agent/                 the workflow runtime, tools, approval gates
  models.py            shared data structures (not AI models)
  profile.py           YAML profile loading and validation
  tools.py             query planning, JSearch integration, deduplication
  relevance.py         Gemini prompt, structured output, relevance classification
  ranking.py           comparative ranking of relevant jobs
  drafting.py          grounded outreach prompt and Gemini call
  storage.py           unique Markdown files saved for human review
  draft_one.py         one-job search/filter/draft/save demo
  workflow.py          multi-job workflow and incremental run reports
  cli.py               terminal arguments and run summary
  fixtures.py          fictional sample-job loader for offline development
fixtures/              synthetic inputs; no real job listings
server/                review-queue UI (v0.2)
observability/         traces of every run
evals/                 draft-quality rubric + regression cases (v0.3)
```

## Status

🚧 Early scaffold — spec in progress. See `SPEC.md` for what's decided
and what's still open.

## Roadmap

- **v0.1** — CLI: profile config → job search → relevance filter → drafts
  printed/saved for review.
- **v0.2** — Review-queue UI, Gmail send behind approval gate, job tracker
  artifact.
- **v0.3** — Eval suite (draft-quality judge), observability traces,
  hiring-team enrichment.

## Setup

### Local browser UI

On macOS, double-click **Start Career Desk.command** in the project folder.
It uses the existing virtual environment and opens your browser. Keep its window
open while using the app; Ctrl+C stops the server. No activation or key exports
are required. Alternatively, from the project folder run:

```sh
.venv/bin/python -m server.app --open
```

Open http://127.0.0.1:8765. The UI uses the same Python workflows as the CLI.
Use **Edit profile & preferences** for a prefilled form with add/remove entries
for roles, locations, and experience highlights. Optional preferences and drafting
restrictions are collapsible. Saving validates the data and writes YAML internally;
existing contact and resume metadata are preserved. Cancel discards form edits.
Work experience is grouped into collapsible role cards (title, company, dates,
achievements); use Move up to put recent roles first. Projects, education, and
skills have separate sections. Older profiles still load: their original bullets
appear under Additional background until organized. Structured achievements carry
their role/date context into model inputs. Changed profiles require fresh assessment.

Inside the profile form, choose a resume PDF and consent to sending its extracted
text to Gemini, then click **Extract & preview profile**. Review the proposed
background, confirm target roles/locations, and Save profile to commit it. Cancel
leaves the saved profile untouched. Import replaces background rather than merging
old achievements; preferences and drafting restrictions are preserved. PDFs remain
in memory and are not stored. Limits: 5 MB, 10 pages, 40,000 text characters;
encrypted or scanned/empty pages require a new text-based export (no OCR yet).
Install updated requirements before restarting the server. A model call plus at
most one retry uses Gemini quota; this feature does not change model billing.
It starts a background search,
shows saved shortlists, and researches contacts/drafts from a selected shortlist.
Resume assessments is available for interrupted search runs. Research reruns
start fresh; they do not resume an interrupted research loop.

Open **API setup** and save your JSearch, Gemini, and Tavily keys once. Saved keys
take effect on the next run, including after restarting the app. They are stored
in `.local/keys.json`, excluded from Git and readable only by your local user.
This file is plaintext, not an encrypted credential vault. Saved values are never
returned to the browser. Blank fields preserve existing values; enter a replacement
to update a key. Saved keys override exported keys for UI runs. CLI commands still
use environment variables. The indicators show presence, not verified API access.

Only one UI-started run executes at a time. Avoid simultaneous CLI runs sharing
the same quota. Stopping the server stops its worker; incremental results
remain saved. This is a local single-user interface, not a hosted service.

Review copies are saved separately in `review-edits.json` within the selected
outreach run. Copy message uses the currently edited text. No sending or approval
action exists. Profile edits do not update existing assessments: start a fresh
search when preferences change. Existing CLI commands remain available.

Research recovery now skips a page after two failed extractions and can inspect
another source within budget. A contact citing an unread discovered page triggers
a read before acceptance; rejected actions receive corrective feedback.

The scaffold provides data structures, profile loading, and fictional sample
job loading, live JSearch integration, Gemini relevance filtering, and drafting
with local review files. Requires Python 3.10+.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Try the loader from the repository root using the placeholder profile:

```sh
python -c 'from agent.profile import load_profile; p = load_profile("profile/profile.yaml.example"); print(p.name, p.target_roles)'
```

To configure your own profile, copy `profile/profile.yaml.example` to the
gitignored `profile/profile.yaml` and replace the placeholder values. Required:
`name`, `target_roles`, `locations`, and `experience_bullets`. Optional: `email`,
`linkedin_url`, `resume_path`, `never_claim`, `search_country` (default `ca`),
`seniority_preferences`, `employment_preferences`, and `work_arrangements`.
The three preference lists describe acceptable options; empty means unspecified. Resume and LinkedIn fields are
metadata for now; the loader does not read or fetch their contents.

`agent/models.py` defines the objects passed between steps. `agent/profile.py`
converts YAML into a `Profile`, rejecting missing or incorrectly typed values
with `ProfileConfigError`. Dataclass type hints describe the other contracts;
they do not automatically validate future API or model responses.

## Try the sample jobs

With the virtual environment active, run from the repository root:

```sh
python - <<'PY'
from agent.profile import load_profile
from agent.fixtures import load_sample_jobs

profile = load_profile("profile/profile.yaml.example")
jobs = load_sample_jobs("fixtures/jobs.sample.json")
print("Target roles:", profile.target_roles)
print("FICTIONAL SAMPLE JOBS - no live search or relevance filtering")
for job in jobs:
    print(f"{job.title} | {job.company} | {job.location}")
PY
```

The fixture loader returns all three fictional postings, including an unrelated
role for future filtering practice. It does not use the profile to search or
decide fit. The `fictional` marker and sample titles identify these as examples.

## Try live search

`agent/tools.py` provides `search_jobs(profile) -> list[JobPosting]`. It searches
the first target role and first location only, using profile `search_country`.
This is a single-query helper; the CLI below searches across preferences.
Pagination remains deferred. It never substitutes sample results.

Set your key privately in your zsh terminal (input is hidden):

```sh
read -s "OPENWEBNINJA_API_KEY?Paste your API key, then press Enter: "
export OPENWEBNINJA_API_KEY
```

Then make one live request:

```sh
python - <<'PY'
from agent.profile import load_profile
from agent.tools import search_jobs

profile = load_profile("profile/profile.yaml.example")
jobs = search_jobs(profile)
print(f"Found {len(jobs)} jobs")
for job in jobs:
    print(f"{job.title} | {job.company} | {job.location}")
PY
```

The example searches Forward Deployed Engineer in Toronto. To use your own
preferences, load `profile/profile.yaml` instead. Only role and location are
sent to JSearch, not your experience or contact details. Missing configuration
raises `ValueError`; request/response failures raise `JobSearchError`. Missing
location is labeled "Not specified"; missing required job fields fail visibly.
The workflow handles retries; this function does not retry on its own.

## Classify one job

Export `GEMINI_API_KEY` privately in the same terminal as your JSearch key:

```sh
read -s "GEMINI_API_KEY?Paste your Gemini API key, then press Enter: "
export GEMINI_API_KEY
```

Create your local `profile/profile.yaml` from the example and fill in real
experience bullets before assessing personal fit. The placeholder bullets in
the example are not a meaningful representation of your qualifications.

The following makes one JSearch request and, if any jobs are returned, one
Gemini request. It sends your preferences, experience bullets, and never_claim
constraints to Gemini along with the posting, omitting name/contact fields.

```sh
python - <<'PY'
from agent.profile import load_profile
from agent.tools import search_jobs
from agent.relevance import classify_relevance

profile = load_profile("profile/profile.yaml")
jobs = search_jobs(profile)
if jobs:
    job = jobs[0]
    decision = classify_relevance(job, profile)
    print(f"{job.title} | {job.company}")
    print("Relevant:", decision.is_relevant)
    print("Reason:", decision.reason)
else:
    print("No jobs returned; no model call made.")
PY
```

The classifier uses `gemini-3.5-flash-lite` standard generateContent with JSON
schema output. Use a key from a project that remains on Free tier with billing
not enabled. The code does not check project billing status; the model also has
paid pricing if you later enable billing. It never switches providers/models on
failure. Free quotas can vary; inspect them in AI Studio. Google may use free-tier
content to improve products, so begin with fictional inputs.

The prompt in `agent/relevance.py` keeps plausible matches and explains unknowns.
Blocked, incomplete, malformed, and failed responses raise `RelevanceError`, not
no-fit decisions. Each invocation makes one request; workflow code owns
retries. No additional Python dependency is needed.

## Build a ranked shortlist

With both keys exported and the virtual environment active:

```sh
python -m agent.cli --max-search-requests 4 --max-jobs 10 --top-k 3
```

Search plans each target-role/location combination, with locations outermost.
Remote searches use `work_from_home=true` and your `search_country`; remote
eligibility still needs review. The search cap includes retries, so a failure
can reduce query coverage. Each query fetches one page. Results are interleaved
across queries and deduplicated by provider ID or exact application URL.

Up to `--max-jobs` unique postings are individually classified. One further
Gemini call compares all relevant assessed jobs and selects the top `--top-k`.
This is the best shortlist within the assessed set, not a search of every job.
Expect up to ten classification calls plus one ranking call with these defaults,
plus at most one retry per failed step. Free-tier quota may limit the run.

Each run saves `results.json` and readable `shortlist.md` in a unique ignored
`drafts/run-*` folder. Reports include unassessed jobs, unattempted query counts,
decisions, ranking reasons, and errors. Failed queries retain other successful
results; failed jobs are skipped after one retry. Ranking failure saves the
assessments without an ordered shortlist. Local persistence errors stop visibly.

Drafting is now opt-in. To also draft for the shortlisted jobs:

```sh
python -m agent.cli --max-search-requests 4 --max-jobs 10 --top-k 3 --draft
```

This adds up to three drafting calls plus retries and saves Markdown drafts for
review. Nothing sends. Use `--help` for all arguments.

## Checks

```sh
python -m unittest discover -s tests -v
```

These tests use synthetic inputs and mocked APIs, with no keys or network needed.
They check search budgets, deduplication, ranking validation, and failure behavior;
they do not measure model quality. See `evals/README.md` for optional live cases.

## Earlier one-job demo

The earlier single-job demo also remains available:

With your local profile filled in and both OPENWEBNINJA_API_KEY and GEMINI_API_KEY
exported in the activated terminal, run from the repository root:

```sh
python -m agent.draft_one
```

This searches once, classifies only the first posting, and drafts only if relevant.
It makes one JSearch call and at most two Gemini calls, plus one retry per failed
step. If the first job is rejected or search returns nothing, no draft is made.
After a second failure this one-job demo stops visibly. Use agent.cli above for
multi-job runs. It uses the same Gemini Free-tier project; it does not enable billing.

Drafting sends experience bullets and never_claim constraints alongside the job,
without contact fields. Your profile name is appended locally as a signature.
Review the printed message and the unique Markdown file saved under gitignored
`drafts/`. Each artifact is labeled pending human review and not sent. No send
functionality exists. Output validation checks format, not factual accuracy;
verify every claim and edit the draft before copying it elsewhere.

## Reassess the same discovered jobs

```sh
python -m agent.cli --from-results drafts/run-YOUR-RUN/results.json --max-jobs 29 --top-k 3
```

Replace the path with the original run report. This makes no JSearch requests
and requires only GEMINI_API_KEY. It reassesses saved postings with the current
profile and prompts, including previously unassessed jobs, up to --max-jobs.
For 29 postings, expect 29 classification calls and one ranking call if any are
relevant, plus retries. Outputs go to a new run; the source is unchanged.
Posting freshness is unchanged: this is a comparison on saved data, not a new
search. Review fit evidence and the separate comparative ranking explanation.
Near ties should be stated honestly instead of given invented distinctions.

## Resume after a quota failure

```sh
python -m agent.cli --resume-results drafts/run-YOUR-RUN/results.json --max-jobs 29 --top-k 3
```

Unlike `--from-results`, this reuses successful relevance decisions and calls
Gemini only for failed/pending jobs, then ranks the relevant results. No JSearch
requests occur. Use the new run's results.json for any subsequent resume. The
source remains unchanged. The cap covers the first N saved jobs, including reused
decisions; set it high enough to include the full set. Resume currently restores
assessment/ranking only and cannot be combined with --draft.

New reports fingerprint the profile and classifier configuration. A mismatch
requires reassessment. Legacy reports cannot verify compatibility and print a
warning; only resume them with the same profile used originally.

On Gemini 429, the workflow records allowlisted quota IDs and retry timing (when
provided), waits for the provider's delay up to 60 seconds, then retries once.
With no timing supplied it waits 30 seconds. Longer delays or a repeated 429
save progress with status `quota_limited` and stop further calls. This does not
bypass quotas or automatically resume later. Ordinary errors still retry once
and skip the affected job. Draft content/prompt behavior is unchanged.

Reports distinguish attempted classifications in this invocation (`checked`),
successful assessments including reused decisions (`assessed`), `reused`, failed
jobs, and pending jobs. `unassessed` includes failed and pending classifications.
Quota diagnostics do not necessarily identify the reset time or quota window;
consult the supplied quota ID when present rather than assuming a daily limit.

## Pace Gemini requests

CLI runs now default to `--gemini-rpm 10`: request starts are spaced at least
six seconds apart. Set a positive integer appropriate to your model/project's
limits in AI Studio, for example `--gemini-rpm 5` for twelve-second spacing.
The first request starts immediately; request duration and quota retry waits
count toward spacing. Classification, ranking, drafting and retries share the
same pacing schedule. Reused decisions and local saves do not consume slots.

This is a configurable application setting, not a detected Gemini quota. It
applies to one CLI run only; simultaneous runs or other apps on the project
can still exhaust shared limits. Token/day quotas are not managed by this
limiter. Existing quota-stop and resume behavior remains in place. Direct
single-job helpers and eval scripts do not use this workflow pacing.

To continue an interrupted run with pacing:

```sh
python -m agent.cli --resume-results drafts/run-YOUR-RUN/results.json --max-jobs 29 --top-k 3 --gemini-rpm 10
```

Changing pacing does not invalidate saved assessments. Reports record the
configured rate. No model, prompt, billing, or profile changes are needed.

## Contact research: first evidence probe

The first slice adds public search/page-extraction tools and research data
contracts. It does not yet select a person, run a Gemini research loop, or alter
drafting. Existing shortlist and drafting commands remain available.

Create a Tavily account at https://www.tavily.com/ and export the key privately:

```sh
read -s "TAVILY_API_KEY?Paste your Tavily key, then press Enter: "
export TAVILY_API_KEY
python -m agent.research_probe --query 'Caspian One AI recruitment team Toronto'
```

This makes one basic search and reads up to two search-result pages. Each failed
operation retries once: at most two search attempts and four page-read attempts.
It saves snippets, extracted text, timestamps and visible errors to a unique
ignored drafts/research-*/evidence.json. Empty search is distinct from provider
failure. Evidence remains untrusted; no contact is automatically verified.
No Gemini calls, private candidate profile, guessed emails, LinkedIn scraping,
or messages are involved. Only public company/role details belong in the query.

Tavily search/extract consume provider credits; this tool does not enable billing
or switch providers. Check the provider dashboard for your current allowance.
Next: inspect the evidence, then implement the bounded Gemini contact-selection
loop and validate its contact/source claims before personalized drafting.

The evidence probe preserves **all text returned by Tavily**, prioritizes
About/Team/People directory paths when selecting its two pages, and writes
`evidence-preview.md` alongside `evidence.json`. The preview contains up to three
4000-character sections selected by contact-related keywords. These are leads,
not verified contact judgments; marketing text may also match those keywords.
Full text and numbered character ranges remain in JSON. `read_section(page, id)`
can retrieve any saved section without another API call. Provider extraction may
itself omit content; preserving its response does not prove webpage completeness.
Old truncated files cannot recover discarded text without fetching again.

## Research contacts and draft from a saved shortlist

With GEMINI_API_KEY and TAVILY_API_KEY exported in the same activated terminal:

```sh
python -m agent.shortlist_outreach \
  --results drafts/run-YOUR-RUN/results.json \
  --ranks 2 3 \
  --gemini-rpm 10
```

`--ranks` means shortlist positions, not job IDs. Omit it to process the whole
saved shortlist. This does not call JSearch, reclassify, or rerank. It uses the
current profile for drafting; reassess separately if the shortlist is stale.

For each job, Gemini chooses searches, reads returned URLs, inspects cached
sections, and selects a contact or returns no contact. Company affiliation plus
a relevant role is enough; specific hiring ownership/referral ability is not
assumed. Each job is capped at 3 Tavily search attempts, 5 extraction attempts,
and 12 Gemini research attempts, including retries. Drafting adds one Gemini
call (at most two with retry). Pacing is shared across research and drafting.
All extracted page text is retained locally; only inspected sections go into
model context. Exact evidence citations must come from those sections.

A successful no-contact result uses the existing hiring-team draft. Exhausted
provider failures skip that job and are recorded; persistent Gemini quota errors
stop further jobs. Source and existing drafts are never overwritten. This command
currently creates a fresh outreach run each time; it does not support automatic
resume of its research loop. You can select only unfinished ranks on a new run.

Review `drafts/outreach-*/review.md` for contacts, sources, uncertainties and
messages. `results.json` contains the full research trace and page text; individual
draft Markdown files are also saved. Exact-quote validation checks provenance,
not whether every inference is true: verify affiliation and relevance yourself.
An email address is not required or guessed. Nothing sends.

Offline checks:

```sh
python -m unittest discover -s tests -v
python -m unittest discover -s evals -p 'test_*.py' -v
```

The two-company integration check uses synthetic web/model responses. Live search
quality and personalized wording must still be checked on real runs.

### Preventing premature research fallback

A model-proposed `none` now triggers controller checks: perform a company-wide
people search if one has not been completed, then inspect up to two distinct
returned pages (directory paths first) before accepting no contact. These actions
stay within the existing search/read budgets. An empty search needs no page read;
provider failures remain errors. Contact selection can finish early with evidence.
The prompt explicitly accepts relevant employees outside the exact city or team.

`results.json` records the model proposals and `overrides` separately, and the
terminal prints executed research actions. This policy ensures an investigation,
not a guaranteed contact. It does not force the model to select an unsupported
person. No drafting prompt or message-format change is included in this fix.
