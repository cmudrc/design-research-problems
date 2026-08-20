Installation
============

Requires Python 3.12+.

VS Code First
-------------

For a guided editor-first path through environment creation, package install,
interpreter selection, and a first script, see :doc:`vscode_start`.

Package Install
---------------

.. code-block:: bash

   python -m pip install design-research-problems

On Windows, if ``python`` resolves to an older interpreter, use
``py -3.12 -m pip install design-research-problems`` and
``py -3.12 -m venv .venv``.

Editable Install
----------------

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e ".[dev]"

Maintainer Shortcut
-------------------

.. code-block:: bash

   make dev

Family Extras
-------------

Install only the problem-family integrations needed for your study.

.. code-block:: bash

   python -m pip install "design-research-problems[grammar]"
   python -m pip install "design-research-problems[battery]"
   python -m pip install "design-research-problems[mcp,cad]"
   python -m pip install "design-research-problems[solvers,pandas]"
   python -m pip install "design-research-problems[all]"

Optimization primitives are already available in the base install via SciPy, so
there is no separate ``opt`` extra. Use ``solvers`` for external optimization
backends or ``all`` for the broadest packaged add-on set.

When working from a source checkout, replace ``design-research-problems`` with
``.`` and add ``-e`` to install the same extras in editable mode.

Use :doc:`dependencies_and_extras` for a compact matrix and practical profile guidance.
