Run An Example In VS Code
=========================

Use this page when you want to try ``design-research-problems`` in VS Code.
Choose the installed-package path for a first user workflow, or the source
checkout path when you want to run the repository's checked-in examples and
development checks.

The checked-in ``examples/`` directory lives in the repository source. Do not
assume those files are present inside the PyPI wheel.

Requirements
------------

- Python 3.12 or newer. Maintainer workflows target the version in
  ``.python-version``.
- VS Code with the Python extension.
- A VS Code integrated terminal.

Installed Package From PyPI
---------------------------

Open an empty folder in VS Code, then create and activate a virtual
environment from ``Terminal > New Terminal``.

On macOS or Linux:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install design-research-problems

On Windows PowerShell:

.. code-block:: powershell

   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install design-research-problems

Run ``Python: Select Interpreter`` from the command palette and choose the
interpreter inside ``.venv``. If VS Code does not list it, enter the interpreter
path manually:

- macOS/Linux: ``.venv/bin/python``
- Windows: ``.venv\Scripts\python.exe``

Create ``problems_example.py`` in the workspace folder:

.. code-block:: python

   import design_research_problems as derp

   print(f"Catalog size: {len(derp.list_problems())}")
   problem = derp.get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(problem.render_brief(include_citation=False))

Run the file with VS Code's ``Run Python File`` action, or run:

.. code-block:: bash

   python problems_example.py

Source Checkout For Repository Examples
---------------------------------------

Use this path when you want the checked-in examples, docs, tests, and optional
development tooling.

.. code-block:: bash

   git clone https://github.com/cmudrc/design-research-problems.git
   cd design-research-problems
   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -e ".[dev]"

Equivalent maintainer shortcut:

.. code-block:: bash

   make dev

Run the compact deterministic example path from the integrated terminal:

.. code-block:: bash

   make examples-smoke
   python examples/catalog/list_and_load.py
   python examples/catalog/public_api_tour.py

First Development Checks
------------------------

Run the checks from VS Code's integrated terminal:

.. code-block:: bash

   make test
   make qa
   make docs-check

``make qa`` runs linting, formatting checks, type checks, and tests. Run
``make coverage`` before merge when changing tested behavior.

Optional Backends
-----------------

The base install covers text, decision, catalog, and SciPy-backed optimization
workflows. Install optional extras only for workflows that need them:

.. code-block:: bash

   python -m pip install -e ".[grammar]"
   python -m pip install -e ".[battery]"
   python -m pip install -e ".[mcp,cad]"
   python -m pip install -e ".[solvers,pandas]"

Use ``make dev-full`` only when you need the broadest local validation
environment.

Troubleshooting
---------------

- If VS Code imports fail but the terminal works, reselect the ``.venv``
  interpreter and reload the window.
- If ``make`` uses the wrong Python, activate ``.venv`` in the terminal or run
  ``PYTHON=.venv/bin/python make test``.
- If Windows activation is blocked, switch the terminal profile to Command
  Prompt and run ``.\.venv\Scripts\activate.bat``.
- If an optional backend import is missing, install the matching family extra
  rather than ``all`` unless you need broad validation coverage.
- Avoid committing generated runtime output under ``artifacts/``,
  ``docs/_build/``, or local virtual environment directories.
