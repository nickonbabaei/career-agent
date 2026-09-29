# AGENTS.md

Instructions for the coding agent working in this repo (Codex, Claude Code, etc.).

## Start here
1. Read `SPEC.md` before writing any code. It is the source of truth for
   scope, architecture, and product decisions.
2. Read `README.md` for the pipeline and roadmap.

## Architecture
Fixed workflow backbone — the steps are known and always the same:

```
find jobs → relevance filter → research role/company → match background → draft → human review → send
```

- A small agent loop is allowed ONLY inside the research step
  (company/hiring-team lookup), where the steps can't be fixed in advance.
- Relevance filtering is a single model call (classifier), not a loop.
- If you're tempted to add an agent loop somewhere else, justify it in the
  SPEC decisions log first.

## Hard rules
- NEVER invent user experience. Drafts draw ONLY from
  `profile/profile.yaml`, the resume, and LinkedIn data. If it's not in the
  profile, the agent may not claim it.
- NOTHING sends without explicit per-message human approval. The approval
  gate is load-bearing; don't route around it.
- `profile/profile.yaml` and resumes are gitignored — never commit real
  user data. Work against `profile.yaml.example`.
- Tool contracts: every tool declares its inputs, outputs, and failure
  behavior. On failure: retry once, then skip the role, log the reason,
  continue the run. Never silently swallow errors.
- Spec before code: product decisions get written to the SPEC decisions log
  FIRST, then implemented.

## Conventions
- v0.1 is CLI: profile config → job search → relevance filter → drafts
  saved for review. No web UI yet (that's `server/`, v0.2).
- Job discovery via a third-party job API. No hand-rolled LinkedIn scraper
  (ToS risk).
- Keep the agent runtime small. Production-readiness lives in the spec,
  evals, observability, and approval gates — not in loop cleverness.
- Every change to drafting behavior must be checked against `evals/`
  before merging.
