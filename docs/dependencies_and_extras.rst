Dependencies and Extras
=======================

Core Install
------------

.. code-block:: bash

   python -m pip install design-research-problems

Editable contributor setup:

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"

Or use:

.. code-block:: bash

   make dev

Maintainer Release Baseline
---------------------------

1. Use Python ``3.12`` from ``.python-version``.
2. Install maintainer dependencies with ``make dev``.
3. Run the automated CI baseline with ``make ci``.
4. Build the public documentation with ``make docs-build``.
5. When links or navigation changed, run ``make docs-linkcheck``.
6. Build and validate distributions with ``make release-check``.
7. Commit the reviewed release metadata and documentation, then tag and publish.

``make release-check`` builds the source distribution and wheel and runs
``twine check`` against both artifacts.

Extras Matrix
-------------

.. list-table::
   :header-rows: 1

   * - Extra
     - Purpose
   * - ``grammar``
     - ``trussme``-backed planar and 3D truss structural evaluation
   * - ``battery``
     - PyBaMM-backed battery-fidelity modes
   * - ``mcp``
     - MCP-backed task workflows
   * - ``cad``
     - Build123d-backed CAD workflows
   * - ``solvers``
     - External optimization backends beyond the base SciPy install
   * - ``pandas``
     - DataFrame exports for catalog/ideation data
   * - ``all``
     - Convenience bundle for the currently useful optional integrations
   * - ``dev``
     - Contributor tooling

The base install supports text and decision problems, generic grammar
transitions, and analytic-surrogate battery paths. Add ``grammar`` when a study
uses ``trussme`` for real planar or 3D truss structural evaluation. Add
``battery`` when a protocol selects PyBaMM-backed battery-fidelity modes. MCP
and CAD tasks are best when your study must interact with an external execution
environment.

Optimization primitives ship in the base install through SciPy, so there is no
separate ``opt`` extra. Use ``solvers`` for external search backends and
``all`` when you want the broadest packaged problem toolkit.

Recommended install profiles:

- lightweight catalog and text studies: base install only
- ``trussme``-backed planar or 3D truss evaluation:
  ``python -m pip install "design-research-problems[grammar]"``
- PyBaMM-backed battery-fidelity studies:
  ``python -m pip install "design-research-problems[battery]"``
- external-tool workflows:
  ``python -m pip install "design-research-problems[mcp,cad]"``
- DRAG/DERP agent workflows:
  ``python -m pip install "design-research-agents[mcp]" "design-research-problems[mcp]"``
- broad optional-toolkit install:
  ``python -m pip install "design-research-problems[all]"``
- full local validation environment: ``make dev-full``

From a source checkout, replace ``design-research-problems`` with ``.`` and
add ``-e``. Add ``dev`` only when you also need contributor tooling.

Release validation is exposed via ``make release-check``.
