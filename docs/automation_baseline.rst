Docs Automation Baseline
========================

This page documents the shared docs and CI baseline for
``design-research-problems``.

The problems repo shares the common module-repo docs baseline with the rest of
the family, but it also owns one repo-specific generator: the public problem
catalog. This page clarifies where the shared baseline ends and where
problem-catalog-specific automation begins.

Shared Module Baseline
----------------------

.. list-table::
   :header-rows: 1

   * - Concern
     - Local utility
     - Workflow owner
     - Baseline expectation
   * - Docs consistency
     - ``scripts/check_docs_consistency.py``
     - ``ci.yml``
     - README, docs landing pages, examples, and generated catalog entry points stay aligned.
   * - Docstring policy
     - ``scripts/check_google_docstrings.py``
     - ``ci.yml``
     - Public APIs, scripts, and examples stay on the shared docstring policy.
   * - Coverage badge
     - ``scripts/generate_coverage_badge.py``
     - ``ci.yml``
     - Coverage badge stays synchronized with the enforced repo quality floor.
   * - Example docs generation
     - ``scripts/generate_example_docs.py``
     - ``examples.yml``
     - Checked-in examples remain represented in the published docs.
   * - Example reporting
     - ``scripts/generate_examples_metrics.py`` and ``scripts/generate_examples_badges.py``
     - ``examples.yml``
     - Example pass/fail and public-API coverage badges use the shared family format.

Workflow Responsibilities
-------------------------

- ``ci.yml`` owns lint, type, test, docs-consistency, docstring, and coverage-oriented checks.
- ``examples.yml`` owns example execution, generated example docs, and example-derived badge metrics.
- ``docs-pages.yml`` owns the published docs build.
- ``workflow.yml`` remains the aggregate maintainer workflow entry point.

Problem-Catalog-Specific Automation
-----------------------------------

``design-research-problems`` also owns one repo-specific generator that is not
part of the generic shared baseline:

- ``scripts/generate_problem_catalog_docs.py``

That generator produces the full packaged-problem catalog under
``docs/problem_catalog/``. It is intentionally a problems-only utility because
no other repo exposes a comparable public inventory of benchmark entries.

The shared baseline vs repo-specific split is therefore:

- Shared baseline: docs checks, badges, examples, and docs publishing.
- Problems-specific utility: generated catalog pages and the curation layer that explains how to browse them.

When To Update This Page
------------------------

Refresh this page whenever workflow ownership changes or when a new docs,
examples, badge, or catalog-generation utility becomes part of the expected
maintainer flow.
