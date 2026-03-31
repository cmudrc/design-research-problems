design-research-problems
========================

A library of benchmark tasks for design research.

What This Library Does
----------------------

``design-research-problems`` provides structured design tasks spanning
ideation, decision-making, optimization, grammar-based design exploration, and
MCP-backed workflows. It is built for recurring research workflows where clear
metadata, reusable evaluation contracts, and domain fidelity all matter.

Stable problem metadata, packaged statements, and explicit family APIs are core
features. They make benchmarks easier to compare across agents, experiments,
and downstream analyses.

.. container:: drc-home-badges

   .. raw:: html

      <div class="drc-badge-row">
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml">
          <img alt="CI" src="https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml/badge.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/ci.yml">
          <img alt="Coverage" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/coverage.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml">
          <img alt="Examples Passing" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/examples-passing.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml">
          <img alt="Public API In Examples" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/main/.github/badges/examples-api-coverage.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml">
          <img alt="Docs" src="https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg">
        </a>
      </div>

Highlights
----------

- Packaged benchmark families for ideation, decision, optimization, grammar, and MCP-backed workflows
- Stable problem metadata and reusable family-specific APIs
- Explicit downstream metadata and evaluation contracts for experiments and analysis
- Catalog entry points for browsing and loading packaged problems
- Runnable examples spanning the major benchmark families

Typical Workflow
----------------

1. Start from a family API or a catalog entry point.
2. Load a packaged problem and inspect its metadata, statement, and structured inputs.
3. Hand the problem to agents or experiments while preserving benchmark metadata.
4. Capture outputs against the downstream metadata contract for comparison.
5. Rejoin benchmark context in downstream analysis and reporting.

.. container:: drc-home-callout

   .. note::

      **Start with** :doc:`quickstart` to load a first problem, inspect the public
      family APIs, and get the package into a reproducible local loop before
      diving into the broader catalog and reference material.

Guides
------

Learn the family model, setup flow, and benchmark-selection patterns that shape
a stable problem-research pipeline.

- :doc:`quickstart`
- :doc:`installation`
- :doc:`concepts`
- :doc:`typical_workflow`
- :doc:`downstream_metadata_contract`
- :doc:`problems/index`
- :doc:`problem_catalog/index`

Examples
--------

Browse runnable examples that show the public APIs across the major problem
families.

- :doc:`examples/index`

Reference
---------

Look up the stable import surface, rendered catalog entry points, and optional
dependency guidance for the packaged benchmark families.

- :doc:`api`
- :doc:`reference/index`
- :doc:`dependencies_and_extras`

Integration With The Ecosystem
------------------------------

The Design Research Collective maintains a modular ecosystem of libraries for
studying human and AI design behavior.

- **design-research-agents** implements AI participants, workflows, and tool-using reasoning patterns.
- **design-research-problems** provides benchmark design tasks, prompts, grammars, and evaluators.
- **design-research-analysis** analyzes the traces, event tables, and outcomes generated during studies.
- **design-research-experiments** sits above the stack as the study-design and orchestration layer, defining hypotheses, factors, conditions, replications, and artifact flows across agents, problems, and analysis.

Together these libraries support end-to-end design research pipelines, from
study design through execution and interpretation.

.. container:: drc-home-ecosystem

   .. image:: _static/ecosystem-platform.svg
      :alt: Ecosystem diagram showing experiments above agents, problems, and analysis.
      :class: dark-light drc-ecosystem-figure
      :width: 100%
      :align: center

Start Here
----------

- :doc:`quickstart`
- :doc:`installation`
- :doc:`concepts`
- :doc:`typical_workflow`
- :doc:`downstream_metadata_contract`
- :doc:`examples/index`
- :doc:`problem_catalog/index`
- :doc:`api`
- `CONTRIBUTING.md <https://github.com/cmudrc/design-research-problems/blob/main/CONTRIBUTING.md>`_

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   quickstart
   installation
   concepts
   typical_workflow
   downstream_metadata_contract
   problems/index
   problem_catalog/index

.. toctree::
   :maxdepth: 2
   :caption: Examples
   :hidden:

   examples/index

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   api
   reference/index
   dependencies_and_extras

.. toctree::
   :maxdepth: 1
   :caption: Development
   :hidden:

   CONTRIBUTING.md <https://github.com/cmudrc/design-research-problems/blob/main/CONTRIBUTING.md>
