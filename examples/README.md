# Examples

Install `design-research-problems[solvers]` if you want the open-ended battery
optimizer example to use the optional `pymoo` or `nevergrad` solver backends.

- `catalog/list_and_load.py`: list the packaged catalog and load each seed problem.
- `catalog/ideation_catalog.py`: inspect prompt, variant, family, and study counts.
- `catalog/ideation_dataframe.py`: export prompt rows to pandas when the optional extra is installed.
- `catalog/ideation_exports.py`: preview JSON and CSV prompt-index exports.
- `decision/laptop_design.py`: inspect the laptop discrete option space and best-scoring design.
- `decision/mseval_material_choice.py`: inspect one empirical MSEval material-choice benchmark.
- `text/peanut_sheller_packet.py`: render the text prompt and citation packet.
- `optimization/pill_problem.py`: sample and optionally solve the pill problem.
- `grammar/battery_18650_t1_series_parallel_grammar.py`: inspect the tier-1 rectangular battery grammar baseline.
- `grammar/battery_18650_t2_layout_grammar.py`: inspect tier-2 pose-aware battery grammar transitions and metrics.
- `grammar/battery_18650_t3_topology_grammar.py`: inspect tier-3 explicit topology battery grammar behavior.
- `grammar/battery_18650_t4_thermal_grammar.py`: inspect tier-4 battery grammar with thermal-system tuning actions.
- `optimization/battery_18650_t1_series_parallel_opt.py`: inspect tier-1 optimization metrics and solver output.
- `optimization/battery_18650_t2_layout_opt.py`: inspect tier-2 pose-aware optimization metrics and solver output.
- `optimization/battery_18650_t3_topology_opt.py`: inspect tier-3 topology-aware optimization metrics and solver output.
- `optimization/battery_18650_t4_thermal_opt.py`: inspect tier-4 thermal-system optimization metrics and solver output.
- `grammar/iot_home_cooling_system_design.py`: build a small IoT home cooling network and evaluate lifecycle and thermal metrics.
- `grammar/truss_analysis_program_design.py`: build a truss using MATLAB Truss Analysis Program mechanics and inspect mass/FOS results.
- `optimization/battery_grammar_to_optimizer.py`: inspect the packaged rectangular battery sizing optimizer with a seeded start and solved design.
- `optimization/battery_open_ended_capacity_max.py`: inspect the packaged open-ended battery co-design optimizer with a seeded explicit graph and a baseline solved design.
- `optimization/ide_treadle_pump.py`: inspect the packaged IDE-style treadle pump baseline and solver.
- `optimization/moneymaker_hip_pump.py`: inspect the MoneyMaker Hip Pump packaged baseline and SciPy SLSQP solver.
- `optimization/pill_problem.py`: inspect a feasible seeded start and the built-in pill solver.
- `grammar/planar_truss_span.py`: build a simple truss grammar state and evaluate it when `trussme` is installed.
- `grammar/space_truss_span.py`: build a simple 3D space-truss grammar state and evaluate it when `trussme` is installed.
- `optimization/space_truss_span_mass_min.py`: inspect the packaged 3D space-truss structural optimizer and its chosen topology.
- `mcp/peanut_sheller_server.py`: spin up a local MCP stdio server and call `submit_final` through an MCP client session.
- `mcp/build123d_parametric_mounting_bracket.py`: inspect the MCP-ingested Build123d catalog problem and run a script-authored CAD evaluation through the proxied tools.
