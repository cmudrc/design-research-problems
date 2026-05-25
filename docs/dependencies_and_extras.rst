Dependencies and Extras
=======================

Core Install
------------

.. code-block:: bash

   pip install design-research-problems

Editable contributor setup:

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -e ".[dev]"

Or use:

.. code-block:: bash

   make dev

Extras Matrix
-------------

.. list-table::
   :header-rows: 1

   * - Extra
     - Purpose
   * - ``grammar``
     - Truss-oriented grammar and structural workflows
   * - ``battery``
     - Battery grammar and battery optimization workflows
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

Text and decision families are suitable for lightweight setups. Grammar and
battery families are more infrastructure-sensitive because they depend on
domain-specific toolchains. MCP and CAD tasks are best when your study must
interact with an external execution environment.

Optimization primitives ship in the base install through SciPy, so there is no
separate ``opt`` extra. Use ``solvers`` for external search backends and
``all`` when you want the broadest packaged problem toolkit.

Recommended install profiles:

- lightweight catalog and text studies: base install only
- structural grammar studies: ``pip install -e ".[grammar]"``
- battery studies: ``pip install -e ".[battery]"``
- external-tool workflows: ``pip install -e ".[mcp,cad]"``
- DRAG/DERP agent workflows:
  ``pip install "design-research-agents[mcp,gemini]" "design-research-problems[mcp]"``
- broad optional-toolkit install: ``pip install -e ".[all]"``
- full local validation environment: ``make dev-full``

Release validation is exposed via ``make release-check``.
