# Slice 4: Frontend

## Goal

A web app over the slice 3 API with three views: a borrower list, a cash-flow view for one
borrower, and an assessment page that shows the relative risk band and its SHAP explanation.
Every figure on screen comes from the API, and nothing on screen reads as a probability of
default or an absolute risk level (D21, D22).

## Status

One row per requirement. Statuses are `planned`, `implemented` or `dropped`.
`tests/test_spec_status.py` checks this table in CI. See "Status tracking" in
[README.md](README.md).

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S4-R1 | implemented | 2026-11-03 | #15 | browser check in #15 (borrower list screenshot); `npm run check` |
| S4-R2 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_cashflow_endpoint; browser check in #15 |
| S4-R3 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_notice_comes_from_the_api_and_is_never_a_tooltip; browser check in #15 |
| S4-R4 | implemented | 2026-11-03 | #15 | browser check in #15 (refused assessment screenshot) |
| S4-R5 | implemented | 2026-11-03 | #15 | screenshots in #15, synthetic borrowers only |
| S4-R6 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_monthly_summary_is_hand_worked and 3 more |
| S4-R7 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_every_model_feature_has_one_plain_label |
| S4-R8 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_frontend_never_shows_a_probability_or_an_absolute_label |
| S4-R9 | implemented | 2026-11-03 | #15 | tests/test_frontend_api.py::test_assess_demo_borrowers_runs_twice_without_duplicates; browser check in #15 |
| S4-R10 | implemented | 2026-11-03 | #15 | `npm run check` (typecheck, lint, build) output in #15 |
| S4-R11 | implemented | 2026-11-03 | #15 | browser check in #15 (API stopped, unknown borrower) |
| S4-R12 | implemented | 2026-11-03 | #15 | browser check in #15 (keyboard path, token contrast ratios, 375 px width, Impeccable detector) |

## In scope

Next.js App Router with TypeScript in strict mode, Tailwind and shadcn/ui conventions, and
`/api/v1` rewrites to the FastAPI backend, in `frontend/` next to `backend/` (D25). The slice
covers the three pages above, the two read endpoints they need, and a way to fill the demo
database with assessments, using synthetic borrowers only.

## Out of scope

Statement upload or PDF parsing (D19), portfolio analytics and the LLM narrative (slice 5),
editing settings, sign-in (the API has none yet; D24), and a frontend job in CI (D25: a
workflow change is High tier and gets its own PR).

## Requirements

### Pages

- **S4-R1. Borrower list** (`/`). One row per borrower: display name, a "Synthetic" badge, the
  latest band in relative words ("Higher relative risk"), its percentile and as-of date, and the
  history the database covers. A borrower without an assessment says "Not assessed" (never a
  blank or a zero band). A refused latest assessment says "Refused" (S4-R4). Each row links to
  the borrower page.
- **S4-R2. Cash-flow view** (`/borrowers/{id}`). Monthly money in and money out as bars, the
  end-of-day running balance as a line, and the 3-month window of the latest assessment shaded
  and labelled with its dates. A table under the chart gives the same monthly figures. A month
  the stored history does not fully cover is drawn and listed as "not covered", never as zero.
  Every figure comes from `GET /api/v1/borrowers/{id}/cashflow` (S4-R6); the frontend only
  formats numbers, it computes none (hard rule 4).
- **S4-R3. Assessment page** (`/assessments/{id}`). Shows:
  - the band in relative words and the percentile among the Berka reference borrowers, on a
    0 to 100 strip with the band cut-offs from the response marked;
  - one SHAP bar per feature, labelled in plain language from the glossary (S4-R7), with the
    raw value next to it and the direction in words ("towards higher relative risk");
  - missing and out-of-range features, each with its reason: a missing feature names the
    training median the model used in its place; an out-of-range feature shows its value and
    the training range;
  - the observation window (`window_start` to the day before `as_of`) and the model version;
  - the D21 notice, rendered from the response's `notice` field, always visible and never
    hidden behind a tooltip.

  There is no probability-of-default number on the page (S4-R8).
- **S4-R4. Refused assessments** show why the borrower was refused (more than half of the
  features outside the training range, D21) and which features were out of range, with their
  values and ranges, instead of an empty page or a band.
- **S4-R5. UI evidence.** Each UI PR includes screenshots made with synthetic data only, as
  `CLAUDE.md` requires.

### Backend support

- **S4-R6. Monthly cash-flow summary.** `GET /api/v1/borrowers/{id}/cashflow` returns, per
  calendar month the history touches: money in (all credits), money out (all debits), net,
  closing balance and transaction count; the end-of-day balance of each day with transactions;
  and the window of the latest assessment (`null` if none). A month not fully covered by the
  stored batches has `null` figures and `covered: false`. Sums are exact (Decimal). This is a
  display summary in `backend/app/transactions/summary.py`, not a model feature: it never
  feeds the model, and `features/cashflow.py` is untouched (D25). Hand-worked tests.
- **S4-R7. Plain-language labels.** `GET /api/v1/features/glossary` returns a label, a short
  description and a unit for each feature in `SCALE_FREE_FEATURES`, from
  `backend/app/features/glossary.py`. Stored assessments also return `window_start`, and
  `GET /api/v1/health` returns the artifact's band cut-offs for the percentile strip. What a
  number means on screen is decided in the backend, where pytest and review read it.

### Guards

- **S4-R8. Relative wording only.** Bands are written "Lower / Middle / Higher relative risk"
  among Berka reference borrowers. No source file in `frontend/src` contains an absolute label
  ("high risk", "low risk"), "probability", "probability of default" or "PD". A pytest scan
  enforces it in CI.
- **S4-R9. Demo assessments.** The borrower page offers "Run assessment" when the borrower has
  none, posting `as_of` = the borrower's `history_end` from the API.
  `scripts/assess_demo_borrowers.py` does the same for every borrower without an assessment,
  through the API, and changes nothing on a second run.

### Build and quality

- **S4-R10. Stack and wiring.** `frontend/` is Next.js (App Router) with TypeScript `strict`,
  Tailwind CSS, shadcn/ui conventions (CVA, `clsx`, `tailwind-merge`) and Lucide icons, fonts
  through `next/font`. The browser calls `/api/v1/*` on its own origin and Next.js rewrites it
  to `FLOWSCORE_API_URL` (default `http://127.0.0.1:8000`); server components call the same
  URL. Server components by default; client components only for the "Run assessment" button.
  `npm run check` (typecheck, lint, production build) passes. Charts are hand-written SVG, so
  there is no chart library (D25).
- **S4-R11. States.** Every page has a loading state, a "no such borrower/assessment" page,
  and an error page that says what failed and how to recover (start the API; set
  `FLOWSCORE_DATABASE_URL`; run the seed script), without a stack trace.
- **S4-R12. Accessibility and layout.** Keyboard focus is visible on every link and button;
  text meets WCAG AA contrast; each chart has a text equivalent (the monthly table, the SHAP
  values as text); colour is never the only carrier of meaning (bands are words, SHAP direction
  is words); the pages work at 375 px wide without horizontal page scroll; motion respects
  `prefers-reduced-motion`.

## Acceptance

From the borrower list, open a synthetic borrower, see their cash flow with the window marked,
and open their assessment. The band, percentile, SHAP bars, flags and notice match the API
response, and the browser check in the PR shows it, with screenshots of a scored and a refused
assessment.

## Risk tier

**Medium** in general. Anything that changes what a number means on screen is reviewed as
High: the glossary (`backend/app/features/glossary.py`), the band wording, and the cash-flow
summary rules.

## Open questions

None left. The draft's question 1 (same repo?) is answered by D25: yes, in `frontend/`.
