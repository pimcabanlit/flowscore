# App specs

One spec per slice of the app plan in `CLAUDE.md`. Each slice must work end to end before the
next one starts, so the specs get less detailed the further away they are. The first job of each
slice is to bring its spec up to the level of detail slice 1 has.

| Slice | Spec | Spec maturity |
|---|---|---|
| 1 | [Scoring API](01-scoring-api.md) | Implemented |
| 2 | [Synthetic Philippine borrowers](02-synthetic-borrowers.md) | Implemented |
| 3 | [Database](03-database.md) | Draft |
| 4 | [Frontend](04-frontend.md) | Draft |
| 5 | [Extras](05-extras.md) | Draft |

## How the specs relate to the other documents

- **`CLAUDE.md` hard rules** apply to every slice and are not repeated here, except where a
  rule decides a requirement.
- **`docs/decisions.md`** records *why*. A spec cites decisions (D1 to D23) and never
  contradicts them. If building a slice needs a new decision, add it to the log, then update
  the spec.
- **The original project spec** (FR numbers such as FR-08 B) is the starting point. These specs
  are narrower and win where the two differ. Each difference is named in the spec that makes it.

## Format

Every spec has the same sections:

1. **Goal**: one or two sentences on what works at the end of the slice.
2. **In scope / Out of scope**
3. **Requirements**: numbered (S1-R1, S1-R2, ...) so PRs and tests can cite them.
4. **Acceptance**: the checks that prove the slice works end to end.
5. **Risk tier**: the tier from `REVIEW.md` that the slice's PRs will carry.
6. **Open questions**: decisions the owner still has to make, each with a recommendation.
   Once answered, the answer moves into the requirements (and into `docs/decisions.md` if it is
   a lasting choice), and the question is deleted.

A requirement changes by editing the spec in the same PR that changes the behaviour.

## Status tracking

Each spec has a **Status** table near the top, with one row per requirement:

| Column | Meaning |
|---|---|
| Status | `planned`, `implemented` or `dropped` |
| Date | the day the status changed, in the PR that changed it (YYYY-MM-DD) |
| PR | the PR that implemented or dropped it, e.g. `#12` |
| Evidence | for `implemented`, the test or check that proves it; for `dropped`, the reason |

The table is updated **in the same PR** as the code, so the merged history always matches what
the code does. CI enforces this through `tests/test_spec_status.py`:

- A test that cites a requirement id (e.g. `def test_refuses_short_history():  # S1-R6`) fails CI
  until that requirement's row says `implemented` with a date, a PR number and evidence.
- Every requirement has exactly one row, and every row is well formed.

So the workflow is: write the test for the requirement and cite its id; CI goes red; fill in the
row; CI goes green. To see what is left, read the Status tables, or run
`Select-String -Path docs\specs\*.md -Pattern "\| planned \|"`.

A requirement that cannot be tested with pytest (for example "the script runs in a few
minutes") is marked `implemented` by hand, with the command output in the PR as evidence.
