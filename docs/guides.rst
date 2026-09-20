Guides
======

``design-research-problems`` is the benchmark-task layer of the
CMU Design Research Collective design-research ecosystem. It owns packaged task
definitions, metadata, statements, evaluators, and task-specific assets.

Primary Path
------------

1. :doc:`installation` — create a supported Python environment and choose extras.
2. :doc:`quickstart` — load and inspect a problem using the base install.
3. :doc:`concepts` and :doc:`typical_workflow` — learn the kind model and handoff flow.
4. :doc:`examples/index` — run examples across the packaged problem kinds.
5. :doc:`api` — confirm the compatibility-guaranteed import surface.

Catalog and Integration Guides
------------------------------

- :doc:`catalog_guide` provides a curated problem-selection path.
- :doc:`problems/index` explains the five public problem kinds.
- :doc:`problem_catalog/index` is the generated problem-by-problem inventory.
- :doc:`downstream_metadata_contract` defines the orchestration compatibility mapping.
- :doc:`paper_contributions` exports citation-backed problem context for paper drafting.
- :doc:`vscode_start` provides an editor-first setup and debugging path.
- :doc:`dependencies_and_extras` maps optional integrations to install profiles.

Compatibility and Ecosystem
---------------------------

The curated top-level API and downstream metadata contract are the public
compatibility boundary. The integration module derives both
``ProblemBinding.family`` and the parallel ``problem_kind`` metadata alias from
``ProblemMetadata.kind``. Experiments copies the binding's ``family`` into
``problem_family``. Ideation is a catalog subset of ``text``, not a sixth
problem kind.

- `design-research-agents <https://cmudrc.github.io/design-research-agents/>`_ owns participant execution.
- `design-research-experiments <https://cmudrc.github.io/design-research-experiments/>`_ owns study design and orchestration.
- `design-research-analysis <https://cmudrc.github.io/design-research-analysis/>`_ owns validation and downstream analysis.

.. toctree::
   :maxdepth: 1
   :hidden:

   installation
   quickstart
   concepts
   typical_workflow
   catalog_guide
   downstream_metadata_contract
   paper_contributions
   vscode_start
   dependencies_and_extras
