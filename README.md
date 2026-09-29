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

_TODO — coming once v0.1 lands._
