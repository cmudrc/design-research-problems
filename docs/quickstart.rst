Quickstart
==========

Load the package, list the seed problems, inspect feature flags, and fetch the
catalog entries:

.. code-block:: python

   from design_research_problems import ProblemRegistry, get_problem, list_problems

   registry = ProblemRegistry()
   print(list_problems())
   print(registry.kind_feature_flags())
   peanut = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
   print(peanut.render_packet(include_citation=False))

The optimization problem can be instantiated through the registry:

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

The grammar problems expose serializable starting states and a lazy `trussme`
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

The packaged desktop GUIs can be launched from the module entrypoint:

.. code-block:: bash

   python -m design_research_problems.gui --app iot
   python -m design_research_problems.gui --app truss

The IoT GUI shows a continuous room-temperature colorbar, and the truss GUI
suppresses structural evaluation while the design remains under-determined.
