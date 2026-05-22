Installation
============

Package Install
---------------

.. code-block:: bash

   pip install design-research-problems

Editable Install
----------------

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   pip install -e ".[dev]"

Maintainer Shortcut
-------------------

.. code-block:: bash

   make dev

Family Extras
-------------

Install only the problem-family integrations needed for your study.

.. code-block:: bash

   pip install -e ".[grammar]"
   pip install -e ".[battery]"
   pip install -e ".[mcp,cad]"
   pip install -e ".[solvers,pandas]"
   pip install -e ".[all]"

Optimization primitives are already available in the base install via SciPy, so
there is no separate ``opt`` extra. Use ``solvers`` for external optimization
backends or ``all`` for the broadest packaged add-on set.

Use :doc:`dependencies_and_extras` for a compact matrix and practical profile guidance.
