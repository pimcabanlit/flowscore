# REVIEW.md: instructions for the AI reviewer

FlowScore is a credit-risk research study plus an app. Read `CLAUDE.md` (hard rules) and
`docs/decisions.md` first. Review the diff against them. Be short and specific.

## Report as Important

These are the failures that matter here. Any instance is **Important**, never a nit.

1. **Privacy leak.** Anything from `personal/` or `data/` committed; real figures, payee names or
   account numbers in code, tests, fixtures, docs or screenshots; a new `print`/log line in
   `tools/` that outputs unmasked transaction data (use `_mask`); payee keywords added to code
   instead of `personal/category_rules.csv`; `.gitignore` loosened for `personal/`, `data/`, `.env`.
2. **Future information.** A feature that can see transactions on or after the as-of date
   (bypasses `window_slice`), or uses a field whose timing cannot be verified (D6).
3. **Research drift.** A change to `src/flowscore/features/`, `adapters/`, `schema.py`,
   `window.py`, `experiment.py`, `scripts/run_*.py` or `results/` without pasted evidence from a
   machine with Berka data: all tests passed, none skipped, and `git diff --exit-code results/`
   after `run_research.py` and `run_scale_free.py`. A deliberate result change without a new
   `docs/decisions.md` entry.
4. **Wrong numbers.** Missing values turned into 0 (`fillna(0)`, `or 0`, default 0.0) where the
   value is unknown; a new feature or financial calculation without a test with hand-worked
   expected values; a second implementation of a feature outside `features/cashflow.py`.
5. **Secrets.** Tokens, keys or DB URLs in code, config, logs or tests instead of env variables.
6. **LLM output as numbers.** An LLM producing or changing a figure instead of summarising
   verified outputs (FR-08 B). Prompts that include `personal/` data.
7. **Docs that lie.** `CLAUDE.md`, `README.md` or `docs/decisions.md` stating commands, files,
   test counts or results that the diff makes untrue.
8. **Dependencies.** Changes to `requirements*.txt` not asked for in the PR, or a new framework
   or paid service not flagged.

## How to report

- Every finding gives `file:line` evidence and one sentence on the concrete failure.
- At most **3 nits** per review. Skip style the code already does consistently.
- Never repeat a finding. A mistake made in several places is **one** finding listing every
  location.
- A bug that exists on the base branch and is not made worse by the diff is labelled
  **Pre-existing**. Report it, but it does not block the PR.
- Don't restate what the diff does; the author knows.

## Skip

Lock and generated files (`requirements-lock.txt`), test fixtures (`tests/fixtures/*.pdf`),
and committed research outputs except to check rule 3 (`results/*.csv`, `results/run_log.txt`).

## Summary

Start the summary with the PR's risk tier and the count, e.g.
`Medium · 2 Important, 1 nit`, then the findings. If there are none, write exactly
`No issues found.` after the tier.
