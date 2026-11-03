# App specs

One spec per slice of the app plan in `CLAUDE.md`. Each slice must work end to end before the
next one starts, so the specs get less detailed the further away they are. The first job of each
slice is to bring its spec up to the level of detail slice 1 has.

| Slice | Spec | Status |
|---|---|---|
| 1 | [Scoring API](01-scoring-api.md) | Ready to build once the open questions are answered |
| 2 | [Synthetic Philippine borrowers](02-synthetic-borrowers.md) | Draft |
| 3 | [Database](03-database.md) | Draft |
| 4 | [Frontend](04-frontend.md) | Draft |
| 5 | [Extras](05-extras.md) | Draft |

## How the specs relate to the other documents

- **`CLAUDE.md` hard rules** apply to every slice and are not repeated here, except where a
  rule decides a requirement.
- **`docs/decisions.md`** records *why*. A spec cites decisions (D1 to D21) and never
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
