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
  tools.py             one-request JSearch integration
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

The scaffold provides data structures, profile loading, and fictional sample
job loading, and a one-request live JSearch integration. Model calls and saving
drafts are not implemented yet. Requires Python 3.10+.

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
`linkedin_url`, `resume_path`, and `never_claim`. Resume and LinkedIn fields are
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
the first target role and first location only, using `country=ca`. All-preference
search and pagination are deferred. It never substitutes sample results.

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
The future workflow will handle retries; this function does not retry on its own.
