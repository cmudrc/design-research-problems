Dependencies and Extras
=======================

The project keeps runtime dependencies small and layers family-specific
integrations behind extras.

Core Install
------------

.. code-block:: bash

   pip install design-research-problems

Runtime dependencies:

- ``gmpb``
- ``numpy``
- ``scipy``

Development Install
-------------------

.. code-block:: bash

   make dev

This installs linting, typing, tests, docs, and release-check tooling.

Reproducible Install
--------------------

.. code-block:: bash

   make repro REPRO_EXTRAS="dev"

The frozen install uses ``uv.lock`` and pinned interpreter ``3.12.12``.

Extras Matrix
-------------

.. list-table::
   :header-rows: 1

   * - Extra
     - Purpose
     - Key packages
   * - ``grammar``
     - Truss grammar evaluation and structural truss optimization benchmarks
     - ``trussme``
   * - ``battery``
     - Battery grammar evaluation and battery optimization benchmarks
     - ``pybamm``
   * - ``mcp``
     - MCP export/ingestion problem workflows
     - ``mcp``
   * - ``cad``
     - Build123d CAD backend for MCP CAD problems
     - ``build123d``
   * - ``solvers``
     - External optimization backends for selected problems
     - ``nevergrad``, ``pymoo``
   * - ``pandas``
     - DataFrame export helpers for ideation catalog workflows
     - ``pandas``
   * - ``opt``
     - Compatibility extra for SciPy optimization dependency
     - ``scipy``
   * - ``dev``
     - Contributor tooling and quality checks
     - ``pytest``, ``ruff``, ``mypy``, ``sphinx``, ``build``, ``twine``

Recommended Profiles
--------------------

- Fast contributor loop: ``make dev``
- Truss workflows: ``pip install -e ".[grammar]"`` or ``make dev-truss``
- Battery workflows: ``pip install -e ".[battery]"`` or ``make dev-battery``
- MCP CAD workflows: ``pip install -e ".[mcp,cad]"``
- Extra solver coverage: ``pip install -e ".[solvers]"``
- Full optional local verification: ``make dev-full``

Maintainer Release Baseline
---------------------------

Use this flow before tagging a release:

1. Use Python ``3.12.12`` (from ``.python-version``).
2. Regenerate lock data: ``make lock``.
3. Verify frozen install and checks: ``make repro REPRO_EXTRAS="dev"`` and ``make ci``.
4. Build release artifacts and validate metadata: ``make release-check``.
5. Commit lock/dependency updates before tagging.

Notes
-----

- Truss grammar evaluation and structural truss optimization require ``trussme``.
- Battery grammar evaluation requires a supported ``pybamm`` install; there is no packaged battery-evaluation fallback.
- Open-ended battery optimization prefers ``pymoo``, then ``nevergrad``, then the built-in deterministic local-search baseline.
