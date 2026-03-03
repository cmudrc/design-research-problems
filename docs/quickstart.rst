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
   print(pill.solve().fun)

   pump = get_problem("moneymaker_hip_pump_cost_min")
   result = pump.solve()
   print(result.message)
   print(pump.objective_components(result.x))

   treadle = get_problem("treadle_pump_ide_material_min")
   print(treadle.solve().message)

The grammar problem exposes a serializable starting state and a lazy `trussme`
adapter:

.. code-block:: python

   truss_problem = get_problem("planar_truss_span")
   state = truss_problem.initial_state()
   actions = truss_problem.enumerate_actions(state)
   print(len(actions))
