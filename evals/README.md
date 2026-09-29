# evals/

Draft-quality evaluation: the thing that proves the agent's output is good,
not just generated.

## What's here (v0.3 target)
- `rubric.md` — what makes a good outreach draft: grounded in the profile,
  specific to the role, correct tone, zero invented claims.
- `cases/` — regression cases: (posting + profile) → expected draft
  properties. Every prompt or tool change must pass these.
- `judge.py` — LLM judge scoring drafts against the rubric.

## Rule
No change to drafting behavior merges without running evals and reporting
the delta. Gaps in the evals become gaps in the product.
