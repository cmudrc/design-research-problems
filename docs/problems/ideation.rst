Ideation Catalog
================

The ideation catalog packages four linked tables for prompt-based human-subjects
research:

- canonical prompt records,
- source-specific prompt variants,
- prompt families and lineage notes, and
- study summaries for reusable ASME-style protocols.

Use :func:`design_research_problems.get_ideation_catalog` to inspect the
machine-readable catalog, search prompts, and export JSON, CSV, or optional
``pandas`` DataFrames.

Evidence Tiers
--------------

- ``primary_verbatim``: directly stated in accessible source text.
- ``primary_reconstructed``: reconstructed from primary source descriptions.
- ``secondary_canonical``: reusable one-line brief from a synthesis source.
- ``family_stub``: family metadata without a packaged prompt statement.
- ``placeholder``: reserved entry that still needs source completion.

The current ideation corpus includes:

- 12 canonical one-line prompts from the design-studies reuse synthesis,
- 3 ASME study-specific prompts,
- 2 primary task framings from Goldschmidt and Smolkov (2006),
- the legacy detailed ``peanut_sheller_fu2010`` prompt as a linked variant,
- 14 cataloged prompt families (CAT-A through CAT-N), and
- additional family records needed to cover the non-overlapping canonical briefs.
