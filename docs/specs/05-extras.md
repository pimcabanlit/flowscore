# Slice 5: Extras

## Goal

Add portfolio analytics, a grounded LLM narrative for each assessment, and a settings page.
This slice is an outline only. Write a full spec once slice 4 works.

## In scope (outline)

- **Portfolio analytics.** Show band counts, the most common SHAP drivers across borrowers,
  and the share of borrowers with out-of-range flags, computed over stored assessments.
- **LLM narrative.** Write a short plain-language summary of a stored assessment. It follows
  the original spec's FR-08 B and hard rule 5:
  - the LLM receives only the stored, verified output: band, percentile, SHAP values, flags
    and notice;
  - it may summarise that output, but never produces or changes a number;
  - every number in the narrative is checked against the input, and a narrative that fails the
    check is not shown.

  All LLM calls go through one model-manager module, and the key comes from an environment
  variable.
- **Settings.** Choose the active model version from the registry and view model metadata
  read-only.

## Out of scope

Vintage and migration analysis (there is no outcome history), prompts that contain any data
from `personal/`, and LLM-driven decisions.

## Risk tier

**High** for the LLM prompts and tools. **Medium** for the rest.

## Open questions

1. **Which LLM provider should be used, at what cost?** This must be flagged before adding it
   (hard rule 10).
2. **Should the narrative be generated when an assessment is scored, or when someone asks for
   it?**
   *Recommendation:* on request. Store it with its prompt version, so stored narratives can be
   reproduced.
