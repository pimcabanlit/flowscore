# Slice 4: Frontend

## Goal

A web app over the slice 3 API with three views: a borrower list, a cash-flow view for one
borrower, and an assessment page that shows the risk band and its SHAP explanation.

## Status

One row per requirement. Statuses are `planned`, `implemented` or `dropped`.
`tests/test_spec_status.py` checks this table in CI. See "Status tracking" in
[README.md](README.md).

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S4-R1 | planned | | | |
| S4-R2 | planned | | | |
| S4-R3 | planned | | | |
| S4-R4 | planned | | | |
| S4-R5 | planned | | | |

## In scope

Next.js App Router with TypeScript in strict mode, Tailwind and shadcn/ui, and `/api/v1`
rewrites to the FastAPI backend. The slice covers the three pages above, using synthetic
borrowers only.

## Out of scope

Statement upload or PDF parsing (D19), portfolio analytics and the LLM narrative (slice 5),
and editing settings.

## Requirements (draft)

- **S4-R1. Borrower list.** Shows each borrower's name, their latest band and its as-of date,
  and a "synthetic" badge.
- **S4-R2. Cash-flow view.** Shows monthly inflow and outflow with the running balance, and
  marks the 3-month window used by the latest assessment. Every figure comes from the API; the
  frontend computes nothing (hard rule 4).
- **S4-R3. Assessment page.** Shows:
  - the band and percentile;
  - one SHAP bar per feature, labelled in plain language ("Balance relative to income"), with
    the raw value next to it;
  - missing and out-of-range features, each shown with a reason;
  - the D21 notice, always visible and never hidden behind a tooltip.

  There is no probability-of-default number on the page.
- **S4-R4. Refused assessments** show why the borrower was refused and which features were out
  of range, instead of an empty page.
- **S4-R5. UI evidence.** Each UI PR includes a screenshot made with synthetic data, as
  `CLAUDE.md` requires.

## Acceptance (draft)

From the borrower list, open a synthetic borrower, see their cash flow, and open their
assessment. The band, SHAP bars, flags and notice match the API response.

## Risk tier

**Medium** in general. Anything that changes what a number means on screen is reviewed as
High.

## Open questions

1. **Should the frontend live in the same repo?**
   *Recommendation:* yes, in `frontend/`, next to `backend/`, so a single PR can change the API
   and its view together.
