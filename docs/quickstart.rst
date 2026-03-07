Quickstart
==========

Requires Python 3.12+ and assumes you are working from the repository root.

Create and activate a virtual environment:

.. code-block:: bash

   python -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip

Path A: Installed package (fastest)
-----------------------------------

Use this when you want the shortest path to catalog exploration from PyPI.

1. Install the base package:

.. code-block:: bash

   pip install design-research-problems

2. (Optional) install family-specific extras:

.. code-block:: bash

   pip install "design-research-problems[grammar]"      # truss grammar + structural optimization
   pip install "design-research-problems[battery]"      # battery grammar + battery optimization
   pip install "design-research-problems[mcp,cad]"      # MCP export/ingestion + Build123d backend
   pip install "design-research-problems[solvers]"      # external optimization backends
   pip install "design-research-problems[pandas]"       # DataFrame exports for ideation catalog

3. List the catalog and inspect one text problem:

.. code-block:: python

   from design_research_problems import ProblemRegistry, get_problem, list_problems

   registry = ProblemRegistry()
   print(list_problems())
   print(registry.kind_feature_flags())
   peanut = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(peanut.render_brief(include_citation=False))

Path B: Editable repository checkout
------------------------------------

Use this when you are developing or validating local changes.

1. Install editable package + dev tooling:

.. code-block:: bash

   make dev

2. (Optional) install integration dependencies:

.. code-block:: bash

   make dev-truss
   make dev-battery
   # or install everything:
   make dev-full

3. Run one catalog example:

.. code-block:: bash

   PYTHONPATH=src python examples/catalog/list_and_load.py

4. Launch the packaged desktop GUIs:

.. code-block:: bash

   python -m design_research_problems.gui --app iot
   python -m design_research_problems.gui --app truss

Problem-family snippets
-----------------------

Optimization problems can be instantiated and solved directly:

.. code-block:: python

   pill = get_problem("pill_capsule_min_area")
   print(pill.generate_initial_solution(seed=7))
   print(pill.evaluate(pill.generate_initial_solution(seed=7)).is_feasible)
   print(pill.solve().fun)

   pump = get_problem("moneymaker_hip_pump_cost_min")
   result = pump.solve()
   print(result.message)
   print(pump.objective_components(result.x))

   treadle = get_problem("treadle_pump_ide_material_min")
   print(treadle.solve().message)

Grammar problems expose serializable starting states and a lazy ``trussme``
adapter:

.. code-block:: python

   truss_problem = get_problem("planar_truss_span")
   state = truss_problem.initial_state()
   state = truss_problem.add_member(state, start_joint_id=0, end_joint_id=2)
   print(len(truss_problem.enumerate_transitions(state)))

The constrained battery grammar exposes explicit cell placements and group-wise
series or parallel edits:

.. code-block:: python

   battery_problem = get_problem("battery_pack_18650_series_parallel")
   battery_state = battery_problem.initial_state()
   battery_state = battery_problem.add_series_stage(battery_state, placements=((1, 0, 0),))
   print(
       battery_state.series_count,
       battery_state.parallel_count,
       len(battery_problem.enumerate_transitions(battery_state)),
   )

The open-ended battery grammar starts from a single cell and exposes explicit
netlist edits:

.. code-block:: python

   open_battery_problem = get_problem("battery_pack_18650_open_ended")
   open_battery_state = open_battery_problem.initial_state()
   open_battery_state = open_battery_problem.add_cell(
       open_battery_state,
       x=1,
       y=0,
       z=0,
       connect_negative_to_terminal_id=open_battery_state.pack_positive_terminal_id,
       use_positive_as_pack_terminal=True,
   )
   print(
       len(open_battery_state.cells),
       len(open_battery_state.connections),
       len(open_battery_problem.enumerate_transitions(open_battery_state)),
   )

Checks and Docs
---------------

.. code-block:: bash

   make test
   make docs-check
   make docs-build

Next Steps
----------

- Install profiles and release checks: :doc:`dependencies_and_extras`
- Family-level API and behavior guide: :doc:`problems/index`
- Full generated problem-by-problem inventory: :doc:`problem_catalog/index`
- Runnable example inventory: :doc:`examples/index`
- Supported top-level exports: :doc:`api`
