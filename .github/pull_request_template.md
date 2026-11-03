## Summary
<!-- What changed and why, in two or three sentences. Link the decision (docs/decisions.md) if one applies. -->

## Testing
<!-- Paste what you ran and what it returned. Real output, not "tests pass". -->
- [ ] `$env:PYTHONPATH="src"; pytest -q tests` (all pass)
- [ ] Research-frozen paths touched: run on a machine with `data/raw/`: every test passed, **none skipped**
- [ ] Research-frozen paths touched: `python scripts\run_research.py` and `python scripts\run_scale_free.py`, then `git diff --exit-code results/` exits 0
- [ ] Privacy: `git status` shows nothing from `personal/` or `data/`; no new unmasked print/log in `tools/`
- [ ] Spec requirement implemented or dropped: its Status row in `docs/specs/` is updated (date, PR, evidence) and its test cites the id
- [ ] UI change: checked in a browser, screenshot with synthetic data only

```
paste output here
```

## Risk tier
<!-- High / Medium / Low from "Risk tiers" in REVIEW.md. Highest tier touched wins; when unsure, go one up. -->
Tier: 
Set by: <!-- the file that set it, e.g. src/flowscore/features/cashflow.py -->
- [ ] High only: owner ran `/security-review`

## How to revert
<!-- Usually `git revert -m 1 <merge commit>`. Say if anything else is needed (data, results, migrations). -->

## Before merge
- [ ] Every review finding answered (fixed, or replied with why not)
- [ ] CI checks green
