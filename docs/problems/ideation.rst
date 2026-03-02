Ideation Catalog
================

The ideation catalog packages four linked tables for prompt-based human-subjects
research:

- canonical prompt records,
- source-specific prompt variants,
- prompt families and lineage notes, and
- study summaries for reusable ASME-style protocols.

Use ``get_ideation_catalog()`` to inspect the
machine-readable catalog, search prompts, and export JSON, CSV, or optional
``pandas`` DataFrames.

Evidence Tiers
--------------

- ``primary_verbatim``: directly stated in accessible source text.
- ``primary_reconstructed``: reconstructed from primary source descriptions.
- ``secondary_canonical``: reusable one-line brief from a synthesis source.

The current ideation corpus includes:

- 40 prompt records with usable packaged text,
- 40 source-specific or derivative variants,
- 22 prompt families, all of which now point to at least one packaged prompt,
- 6 study summaries, and
- no stub-only family records.
