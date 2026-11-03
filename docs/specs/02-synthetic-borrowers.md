# Slice 2: Synthetic Philippine borrowers

## Goal

A seeded generator produces a set of fictional Philippine borrowers. Their transactions look
like real Philippine bank activity, follow the canonical schema, and can be scored by the
slice 1 API. The set exists **only** to make the demo realistic (D1, hard rule 9).

## In scope

- A generator script that writes canonical-schema CSV files for a fixed set of personas.
- The personas and the patterns they follow.
- Checks that every generated account passes `schema.validate()` and gets a response from the
  scoring API.

## Out of scope

- Default labels or outcomes. Synthetic outcomes would make any evaluation circular (D1).
- Any use of synthetic data as research evidence.
- Calibrating amounts on the owner's statements (D4). Patterns may be taken from them; amounts
  may not.

## Requirements

- **S2-R1. Patterns, not amounts.** The generator reproduces the *shape* of Philippine accounts:
  - semi-monthly payroll on the 15th and the last day of the month, moved to the previous
    working day when a payday falls on a weekend;
  - InstaPay and PESONet transfers, with their fees;
  - credit card payments, rent, utility bills and phone load;
  - cash withdrawals.

  Amounts come from public sources, such as PSA wage statistics and published bank fees. Each
  source is cited in the script's docstring.
- **S2-R2. Personas.** The generator covers at least these personas:
  - steady salaried;
  - salaried with high card debt;
  - irregular freelancer or gig income;
  - remittance-dependent;
  - an account that goes into overdraft or runs close to zero.

  Each persona exists so the demo can show a different risk band and different SHAP drivers.
  The generator does not decide the band in advance; the band is whatever the model returns.
- **S2-R3. Deterministic.** The same seed produces byte-identical output, and the seed is a
  script argument.
- **S2-R4. Clearly fictional.** Names, IDs and payees are obviously made up, and every borrower
  record carries `synthetic: true`. Generated files go to `demo/synthetic/`, which is committed
  because it holds no private data.
- **S2-R5. Valid and scorable.** A test checks that every account passes `schema.validate()`
  and gets `status: "scored"` from the scoring endpoint. A persona that is refused for being
  out of range is reported, not hidden. That outcome is itself a finding about D21's range
  check.
- **S2-R6. Tests.** For one persona with known parameters, a test checks hand-worked
  expectations: the payday dates, the monthly totals, and that the running balance stays
  consistent.

## Acceptance

Running the generator, then scoring every persona through the API, produces a table of
persona, band and top SHAP driver. The table is pasted into the PR, along with the test output.

## Risk tier

**Medium.** The slice adds new scripts, data and tests. It becomes High if it touches
`features/` or `schema.py`, for example to add a category.

## Open questions

1. **Should new categories be added for InstaPay or PESONet fees?**
   *Recommendation:* no. They map to the existing `fee` and `transfer_in`/`transfer_out`
   categories, which leaves `schema.py` (High tier) untouched.
2. **How many borrowers should there be?**
   *Recommendation:* about 30, a few per persona, which is enough for the borrower list and
   portfolio views in later slices.
