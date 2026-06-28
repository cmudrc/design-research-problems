VS Code Start
=============

Use this path when opening ``design-research-problems`` in VS Code for the
first time. The commands are repo-local and assume Python 3.12 or newer.

Requirements
------------

- Python 3.12 or newer. Maintainer workflows target the version in
  ``.python-version``.
- VS Code with the Python extension.
- ``make`` available in the integrated terminal.
- Optional: ``uv`` for faster virtual environment and package installs.

Open the Repository
-------------------

Open the repository root folder in VS Code, not the parent ecosystem folder. The
root should contain ``pyproject.toml``, ``Makefile``, ``src/``, ``tests/``, and
``examples/``.

Create an Environment
---------------------

Standard library setup:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate

On Windows PowerShell, use:

.. code-block:: powershell

   py -3.12 -m venv .venv
   .venv\Scripts\Activate.ps1

With ``uv``:

.. code-block:: bash

   uv venv --python 3.12
   source .venv/bin/activate

Install Development Dependencies
--------------------------------

Use the maintainer shortcut:

.. code-block:: bash

   make dev

Equivalent ``pip`` command:

.. code-block:: bash

   python -m pip install --upgrade pip setuptools wheel
   python -m pip install -e ".[dev]"

Equivalent ``uv`` command:

.. code-block:: bash

   uv pip install -e ".[dev]"

Install optional extras only when the problem family or backend needs them:

.. code-block:: bash

   python -m pip install -e ".[grammar]"
   python -m pip install -e ".[battery]"
   python -m pip install -e ".[mcp,cad]"
   python -m pip install -e ".[solvers,pandas]"

Use ``make dev-full`` when you need the broadest local validation environment.

Select the VS Code Interpreter
------------------------------

Run ``Python: Select Interpreter`` from the command palette and choose the
interpreter inside ``.venv``. If VS Code does not list it, enter the interpreter
path manually:

- macOS/Linux: ``.venv/bin/python``
- Windows: ``.venv\Scripts\python.exe``

First Checks
------------

Run the checks from VS Code's integrated terminal:

.. code-block:: bash

   make test
   make qa
   make docs-check

``make qa`` runs linting, formatting checks, type checks, and tests. Run
``make coverage`` before merge when changing tested behavior.

Problem Families And Optional Backends
--------------------------------------

The base install covers text, decision, catalog, and SciPy-backed optimization
workflows. Install optional extras only for workflows that need them:

- ``grammar`` for truss-oriented grammar and structural workflows.
- ``battery`` for battery grammar and battery optimization workflows.
- ``mcp,cad`` for MCP-backed CAD task workflows.
- ``solvers,pandas`` for external optimizer backends and tabular exports.

External simulators and solver toolchains should stay out of the default setup
unless the issue or example explicitly requires them.

Deterministic Examples
----------------------

Run the compact deterministic example path from the integrated terminal:

.. code-block:: bash

   make examples-smoke

To run catalog examples directly:

.. code-block:: bash

   PYTHONPATH=src python examples/catalog/list_and_load.py
   PYTHONPATH=src python examples/catalog/public_api_tour.py

Troubleshooting
---------------

- If VS Code imports fail but the terminal works, reselect the ``.venv``
  interpreter and reload the window.
- If ``make`` uses the wrong Python, activate ``.venv`` in the terminal or run
  ``PYTHON=.venv/bin/python make test``.
- If Windows activation is blocked, enable script execution for the current
  user or use the VS Code Python extension's environment activation.
- If an optional backend import is missing, install the matching family extra
  rather than ``all`` unless you need broad validation coverage.
- Avoid committing generated runtime output under ``artifacts/``,
  ``docs/_build/``, or local virtual environment directories.
