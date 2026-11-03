# Slice 2: Synthetic Philippine borrowers

## Goal

A seeded generator produces 30 fictional Philippine borrowers. Their transactions follow the
patterns of a Philippine savings or payroll account, use the canonical schema, and are scored by
the slice 1 API. The set exists **only** to make the demo realistic (D1, hard rule 9).

## Status

One row per requirement. Statuses are `planned`, `implemented` or `dropped`.
`tests/test_spec_status.py` checks this table in CI. See "Status tracking" in
[README.md](README.md).

| Req | Status | Date | PR | Evidence |
|---|---|---|---|---|
| S2-R1 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_paydays_move_back_from_weekends_and_holidays, test_transfer_fees_follow_the_dated_schedule, test_interest_is_net_of_final_tax; sources table in src/flowscore/synthetic.py |
| S2-R2 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_borrower_set_covers_every_persona |
| S2-R3 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_borrower_set_covers_every_persona |
| S2-R4 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_same_seed_same_bytes, test_committed_files_match_the_generator |
| S2-R5 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_savings_account_never_goes_negative, test_every_account_is_valid |
| S2-R6 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_borrowers_are_clearly_fictional |
| S2-R7 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_every_account_is_valid |
| S2-R8 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_every_account_is_valid |
| S2-R9 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_every_borrower_is_scored (all 30 scored, none refused) |
| S2-R10 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_score_table_names_the_top_driver; table pasted in the PR |
| S2-R11 | implemented | 2026-11-03 | #11 | tests/test_synthetic.py::test_hand_worked_steady_account |

## In scope

- A generator module (`src/flowscore/synthetic.py`) and a script that writes canonical-schema
  CSV files for 30 borrowers in five personas.
- The personas, the patterns they follow, and the public figures behind the amounts.
- A script that scores every borrower through the API and prints the result table.
- Tests: hand-worked values, determinism, validity, and scoring with the committed model.

## Out of scope

- Default labels or outcomes. Synthetic outcomes would make any evaluation circular (D1).
- Any use of synthetic data as research evidence.
- Calibrating amounts on the owner's statements (D4). Patterns may be taken from them; amounts
  may not.
- New transaction categories. InstaPay and PESONet fees use `fee`, and the transfers use
  `transfer_in`, `transfer_out`, `rent` or `loan_payment`, so `schema.py` is untouched.
- Overdrafts. The near-zero persona runs down to zero but never below it (D23).
- Storing the borrowers in a database (slice 3) or showing them (slice 4).

## Requirements

### Generation

- **S2-R1. Patterns, not amounts.** The generator reproduces the *shape* of Philippine accounts:
  - semi-monthly payroll on the 15th and the last day of the month, moved to the previous
    working day when a payday falls on a weekend or a fixed-date national holiday (regular or
    special non-working day, plus National Heroes Day); the 13th-month pay (PD 851) arrives with
    the first December payday;
  - InstaPay and PESONet transfers with their fees: PHP 25 and PHP 50 until 2026-06-30, free from
    2026-07-01, when the big banks waived them. Each fee is its own `fee` row next to its
    transfer;
  - credit card payments, a loan payment by PESONet, rent by InstaPay, utility bills, phone load;
  - cash withdrawals in multiples of PHP 500 (sweeps in multiples of PHP 100);
  - month-end savings interest net of the 20% final tax.

  Amounts come from public sources: PSA wage and remittance statistics, the NCR wage order,
  Meralco rates and published bank fees. Each source, and each amount that is an assumption, is
  listed in the table in the module docstring of `src/flowscore/synthetic.py`.
- **S2-R2. Personas.** Five personas, each so the demo can show a different situation:
  - `steady_salaried`: semi-monthly pay from PSA daily pay figures, rent, bills, a modest card
    bill paid in full, savings that build up;
  - `card_debt`: salaried, with card payments of 35 to 50% of take-home pay and a personal loan;
  - `irregular_freelancer`: client payments of varying size, some months with none;
  - `remittance_dependent`: a monthly remittance from abroad (PSA Survey on Overseas Filipinos),
    sometimes with small cash deposits, mostly spent in cash;
  - `near_zero`: a minimum-wage earner (NCR-26) who withdraws nearly everything the day after
    each payday, so the balance runs close to zero.

  The generator does not decide the band in advance; the band is whatever the model returns.
- **S2-R3. Borrower set.** 30 borrowers, 6 per persona, `SYN-001` to `SYN-030`. Each has 12 full
  months of history, from 2025-10-01 to 2026-09-30, and an assessment date of 2026-10-01. The
  parameters of each borrower (pay, shares of spending, opening balance) are drawn from a
  random stream seeded by (seed, borrower number), so borrowers within a persona differ and
  adding a borrower never changes another.
- **S2-R4. Deterministic.** The same seed produces byte-identical output, and the seed is a
  script argument (`--seed`, default 2026). The committed files equal the generator's output
  for the default seed; a test regenerates them and compares bytes.
- **S2-R5. Savings account rules.** The balance never goes below zero. A flexible debit (cash,
  card purchase, phone load) is cut to what the account holds. A fixed payment (rent, bills,
  card, loan) that the account cannot cover is skipped, as a declined payment would be.

### Output

- **S2-R6. Clearly fictional.** IDs are `SYN-nnn`, names are `Demo Borrower nn`, and every
  borrower record carries `synthetic: true`. There is no payee or description column at all.
  The generator reads nothing: not `personal/`, not `data/`. Generated files go to
  `demo/synthetic/`, which is committed because it holds no private data.
- **S2-R7. Format.** `demo/synthetic/borrowers.csv` holds `borrower_id`, `display_name`,
  `persona`, `synthetic`, `history_start`, `as_of`, `generator_version` and `seed`.
  `demo/synthetic/transactions.csv` holds `borrower_id` followed by the canonical columns from
  `schema.py`. Amounts have two decimals, an absent debit or credit is an empty cell (never 0),
  and line endings are LF on every platform.
- **S2-R8. Valid.** Every account passes `schema.validate()`, uses only categories from
  `schema.CATEGORIES`, has dates in `[history_start, as_of)`, and has a running balance that
  equals the previous balance plus the credit minus the debit, to the centavo. Transaction ids
  sort in chronological order, so same-day ties keep the statement's order.

### Scoring

- **S2-R9. Scorable.** A test posts every borrower to `POST /api/v1/assessments/score` with the
  committed model and pins the status of each. A borrower that is refused for being out of range
  is listed in that test and reported in the PR, not hidden. That outcome is itself a finding
  about D21's range check.
- **S2-R10. Result table.** `scripts/score_synthetic_borrowers.py` prints a Markdown table of
  borrower, persona, status, percentile, band, top SHAP driver (largest absolute contribution,
  with its sign) and out-of-range flags.

### Tests

- **S2-R11. Hand-worked values.** For a steady salaried profile with round, known parameters, a
  test checks every row over two months: the payday dates (including a weekend and a holiday
  move), the 13th-month pay, the fee rows, the monthly totals and the running balance; and that
  the same profile pays no fee after 2026-07-01.

## Acceptance

1. `python scripts\generate_synthetic_borrowers.py` writes `demo/synthetic/`, and running it again
   changes no byte (`git diff --exit-code demo/`).
2. `python scripts\score_synthetic_borrowers.py` scores every borrower through the API and prints
   the table of persona, band and top SHAP driver. The table is pasted into the PR, along with
   the test output.

## Risk tier

**Medium.** The slice adds a module under `src/flowscore/` outside the research-frozen paths, two
scripts, demo data and tests. It becomes High if it touches `features/` or `schema.py`, for
example to add a category.

## Findings from the first run

- All 30 borrowers are scored; none is refused, so D21's range check holds for these patterns.
- The personas spread across the bands: `near_zero` and most `card_debt` borrowers land in
  `higher` relative risk, `steady_salaried` and `remittance_dependent` mostly in `lower`.
- `min_balance_to_income` is the top SHAP driver for most borrowers. The model leans on the
  balance cushion, so the demo shows fewer distinct drivers than the personas were meant to.
  Remittance dependence itself is invisible to the D21 features (a transfer in counts as
  income like any other), which is why those borrowers look lower risk when they keep a cushion.
  This is a property of the model, not something to tune the personas around (S2-R2).

## Decisions taken in this slice

Recorded as D23 in `docs/decisions.md`: no new categories, 30 borrowers, a near-zero persona
instead of an overdraft, a dated fee schedule, and committed demo data.
