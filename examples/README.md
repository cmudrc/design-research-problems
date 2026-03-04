# Examples

- `catalog/list_and_load.py`: list the packaged catalog and load each seed problem.
- `catalog/ideation_catalog.py`: inspect prompt, variant, family, and study counts.
- `catalog/ideation_dataframe.py`: export prompt rows to pandas when the optional extra is installed.
- `catalog/ideation_exports.py`: preview JSON and CSV prompt-index exports.
- `decision/laptop_design.py`: inspect the laptop discrete option space and best-scoring design.
- `decision/mseval_material_choice.py`: inspect one empirical MSEval material-choice benchmark.
- `text/peanut_sheller_packet.py`: render the text prompt and citation packet.
- `optimization/pill_problem.py`: sample and optionally solve the pill problem.
- `grammar/battery_pack_18650_open_ended.py`: build a 4S4P-equivalent explicit battery graph and evaluate it when `pybamm` is installed.
- `grammar/battery_pack_18650_series_parallel.py`: build the constrained rectangular 4S4P battery grammar state and evaluate it when `pybamm` is installed.
- `optimization/battery_grammar_to_optimizer.py`: seed the battery sizing optimizer from a grammar-derived 4S4P layout while staying in the optimization-family API.
- `optimization/ide_treadle_pump.py`: inspect the packaged IDE-style treadle pump baseline and solver.
- `optimization/moneymaker_hip_pump.py`: inspect the MoneyMaker Hip Pump packaged baseline and SciPy SLSQP solver.
- `optimization/pill_problem.py`: inspect a feasible seeded start and the built-in pill solver.
- `grammar/planar_truss_span.py`: build a simple truss grammar state and evaluate it when `trussme` is installed.
- `grammar/space_truss_span.py`: build a simple 3D space-truss grammar state and evaluate it when `trussme` is installed.
- `optimization/space_truss_span_mass_min.py`: inspect the packaged 3D space-truss structural optimizer and its chosen topology.
