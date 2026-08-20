Ideation Catalog
================

The ideation catalog is a curated subset of the ``text`` problem kind. It
packages four linked tables for prompt-based human-subjects research:

- canonical prompt records,
- source-specific prompt variants,
- prompt families and lineage notes, and
- study summaries for reusable ASME-style protocols.

Use ``get_ideation_catalog()`` to inspect the
machine-readable catalog, search prompts, and export JSON, CSV, or optional
``pandas`` DataFrames.

``ideation`` is a catalog tag and study-selection concept, not a sixth
``ProblemKind``. Ideation entries keep the value ``text`` in both downstream
compatibility paths: the ``ProblemBinding.family``/``ProblemPacket.family``
path exported as ``problem_family``, and the parallel ``problem_kind`` metadata
alias.

Evidence Tiers
--------------

- ``primary_verbatim``: directly stated in accessible source text.
- ``primary_reconstructed``: reconstructed from primary source descriptions.
- ``secondary_canonical``: reusable one-line brief from a synthesis source.

The current ideation corpus includes:

- 126 prompt records with usable packaged text,
- 128 source-specific or derivative variants,
- 103 prompt families, all of which now point to at least one packaged prompt,
- 6 study summaries, and
- no stub-only family records.
