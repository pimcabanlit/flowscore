# Synthetic demo borrowers

**Fictional. Demo only.** 30 made-up Philippine borrowers (`SYN-001` to `SYN-030`, "Demo
Borrower nn") with 12 months of transactions each, for the app demo. They have no outcomes and
are never evidence for a research question (D1, D23). No row comes from anyone's statements:
the patterns follow Philippine banking (semi-monthly payroll, InstaPay and PESONet fees, 13th
month pay, remittances) and the amounts come from public figures listed in
`src/flowscore_demo/synthetic.py`.

- `borrowers.csv`: one row per borrower, with `persona` and `synthetic = true`.
- `transactions.csv`: `borrower_id` plus the canonical schema columns.

Regenerate with `python scripts\generate_synthetic_borrowers.py` (byte-identical for the same
seed; `tests/test_synthetic.py` checks the committed files). Spec:
`docs/specs/02-synthetic-borrowers.md`.
