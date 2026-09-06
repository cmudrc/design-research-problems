Problem Paper Contributions
===========================

``design-research-problems`` can translate a packaged problem into deterministic
Background and Methods support for a later paper draft. The export preserves
problem, prompt, variant, family, study, and citation provenance without
claiming that the configured task was executed.

Collect a Component Packet
--------------------------

Use the stable catalog identifier:

.. code-block:: python

   import design_research_problems as drp

   packet = drp.collect_problem_paper_contributions(
       "ideation_peanut_shelling"
   )

The returned JSON-compatible object follows paper-contribution contract version
``0.1.0``, accepted by ``design-research-experiments``. It contains:

- configured Background and Methods contributions;
- curated references deduplicated by the existing ``Citation.key`` values;
- prompt, variant, family-lineage, and linked-study identifiers when available;
- exact ideation prompt wording and its evidence tier; and
- reporting gaps for provisional citations or incomplete linked records.

Evidence Boundary
-----------------

Every Problems contribution has ``evidence_basis="configured"`` and an empty
``evidence_refs`` list. A catalog label such as ``human-subjects-ready`` is a
task-selection property, not proof of participant recruitment, execution, or
analysis. The Methods metadata therefore reminds the downstream renderer to
obtain actual participant, timing, assignment, evaluator, and modification
details from study evidence.

Ideation Provenance
-------------------

For a problem linked to the ideation catalog, the helper follows the existing
``source_citation_keys`` and prompt relationships. It exports the selected
prompt, its source-specific variants, its family and ancestor lineage, and any
study records that directly reference those variants. It does not broaden the
selection to sibling prompts merely because they share a family.

Non-Ideation Problems
---------------------

Decision, optimization, grammar, MCP, and ordinary text problems use the same
packet shape. They receive general Background and Methods contributions from
``ProblemMetadata`` plus their curated problem citations. Decision and
optimization metadata also carries a reminder to report the variables,
objective, constraints, and evaluator settings actually used.

Downstream Aggregation
----------------------

Pass the packet to the Experiments collector as a component packet. Experiments
validates citation keys, deduplicates compatible references, and keeps the
Problems package and version as provenance. The helper generates neither a
manuscript nor observed Results claims.

See ``examples/catalog/paper_contributions.py`` for a runnable example.
