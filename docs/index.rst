design-research-problems
========================

The benchmark-task layer for reproducible design research.

What This Library Does
----------------------

``design-research-problems`` owns structured task definitions, metadata,
statements, evaluators, and packaged assets across five ``ProblemKind`` values:
text, decision, optimization, grammar, and MCP. The ideation catalog is a
curated subset of the text family.

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
          <img alt="Coverage" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/coverage.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml">
          <img alt="Examples Passing" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-passing.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/examples.yml">
          <img alt="API in Examples" src="https://raw.githubusercontent.com/cmudrc/design-research-problems/HEAD/.github/badges/examples-api-coverage.svg">
        </a>
        <a class="drc-badge-link" href="https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml">
          <img alt="Docs" src="https://github.com/cmudrc/design-research-problems/actions/workflows/docs-pages.yml/badge.svg">
        </a>
        <a class="drc-badge-link" href="https://pypi.org/project/design-research-problems/">
          <img alt="PyPI Version" src="https://img.shields.io/pypi/v/design-research-problems.svg">
        </a>
        <a class="drc-badge-link" href="https://pypi.org/project/design-research-problems/">
          <img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/design-research-problems.svg">
        </a>
      </div>

Quality Signals
---------------

- ``Coverage`` reports total line coverage for the default deterministic test
  suite; CI requires at least 95%.
- ``Examples Passing`` reports checked-in example scripts that execute
  successfully in the examples workflow.
- ``API in Examples`` reports curated top-level ``__all__`` exports referenced
  by runnable examples. ``N/N`` means every supported top-level export appears
  in at least one example, and CI requires 100%.

Run ``make coverage``, ``make examples-test``, and ``make examples-coverage``
to reproduce these checks locally.

Highlights
----------

- Packaged benchmark families for text, decision, optimization, grammar, and MCP-backed workflows
- A linked ideation metadata catalog within the text family
- Stable problem metadata and reusable family-specific APIs
- A study-facing integration seam in ``design_research_problems.integration`` for orchestration layers
- Explicit downstream metadata and evaluation contracts for experiments and analysis
- Citation-backed Background and Methods contributions for downstream paper drafts
- Catalog entry points for browsing and loading packaged problems
- Runnable examples spanning the major benchmark families

Typical Workflow
----------------

1. Start from a family API or a catalog entry point.
2. Load a packaged problem and inspect its metadata, statement, and structured inputs.
3. Let the experiments layer resolve the problem through
   ``design_research_problems.integration.resolve_problem_binding(...)``, invoke
   an agent, and preserve benchmark metadata.
4. Capture outputs against the downstream metadata contract for comparison.
5. Rejoin benchmark context in downstream analysis and reporting.

.. container:: drc-home-callout

   .. note::

      **New here?** Follow :doc:`guides` for the shared install → quickstart →
      concepts/workflow → examples → API path. Use :doc:`catalog_guide` when
      you are ready to choose among packaged tasks.

Guides
------

Learn the family model, setup flow, and benchmark-selection patterns that shape
a stable problem-research pipeline.

- :doc:`guides`
- :doc:`installation`
- :doc:`quickstart`
- :doc:`concepts`
- :doc:`typical_workflow`

Examples
--------

Browse runnable examples that show the public APIs across the major problem
families.

- :doc:`examples/index`

Reference
---------

Look up the stable import surface, rendered catalog entry points, and optional
dependency guidance for the packaged benchmark families.

- :doc:`reference/index`

Integration With The Ecosystem
------------------------------

The CMU Design Research Collective design-research ecosystem is a modular set of
libraries for studying human and AI design behavior.

- `design-research-agents <https://cmudrc.github.io/design-research-agents/>`_ owns executable AI participants, workflows, and tool-using reasoning patterns.
- **design-research-problems** (this package) owns benchmark tasks, prompts, grammars, metadata, and evaluators.
- `design-research-experiments <https://cmudrc.github.io/design-research-experiments/>`_
  owns study design and coordinates artifact flows across packages.
- `design-research-analysis <https://cmudrc.github.io/design-research-analysis/>`_ validates and analyzes the resulting traces, event tables, and outcomes.

Together these libraries support end-to-end design research pipelines, from
study design through execution and interpretation.

The figure shows two complementary views: control responsibility and runtime
artifact flow. Neither view is a package-install order. See the umbrella
`compatibility matrix <https://cmudrc.github.io/design-research/compatibility.html>`_
for the component versions tested together.

.. container:: drc-home-ecosystem

   .. image:: _static/ecosystem-platform.svg
      :alt: Two-view diagram showing the control topology and runtime data flow across Problems, Agents, Experiments, and Analysis.
      :class: dark-light drc-ecosystem-figure
      :width: 100%
      :align: center

Start Here
----------

- :doc:`installation`
- :doc:`quickstart`
- :doc:`concepts`
- :doc:`typical_workflow`
- :doc:`examples/index`
- :doc:`api`
- :doc:`guides`
- :doc:`problem_catalog/index`
- `CONTRIBUTING.md <https://github.com/cmudrc/design-research-problems/blob/HEAD/CONTRIBUTING.md>`_

.. toctree::
   :maxdepth: 2
   :caption: Guides
   :hidden:

   guides

.. toctree::
   :maxdepth: 2
   :caption: Problems and Catalog
   :hidden:

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

   reference/index

.. toctree::
   :maxdepth: 1
   :caption: Development
   :hidden:

   automation_baseline
   CONTRIBUTING.md <https://github.com/cmudrc/design-research-problems/blob/HEAD/CONTRIBUTING.md>
