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
- `grammar/battery_18650_t1_rectangular_surrogate_grammar.py`: inspect the tier-1 rectangular grammar baseline and its benchmark card.
- `grammar/battery_18650_t2_pose_surrogate_grammar.py`: inspect tier-2 pose-aware grammar transitions and benchmark metadata.
- `grammar/battery_18650_t3a_topology_surrogate_grammar.py`: inspect the tier-3A topology-allocation surrogate grammar and provenance.
- `grammar/battery_18650_t3b_netlist_explicit_grammar.py`: inspect the tier-3B explicit-netlist grammar behavior.
- `grammar/battery_18650_t4_thermal_hybrid_grammar.py`: inspect tier-4 grammar with hybrid thermal scoring and supported evaluator modes.
- `optimization/battery_18650_t1_rectangular_surrogate_opt.py`: inspect tier-1 optimization metrics and the default evaluation mode.
- `optimization/battery_18650_t2_pose_surrogate_opt.py`: inspect tier-2 pose-aware optimization metrics and representation metadata.
- `optimization/battery_18650_t3a_topology_surrogate_opt.py`: compare surrogate and explicit-circuit scoring on the same tier-3A candidate.
- `optimization/battery_18650_t3b_netlist_explicit_opt.py`: inspect the explicit-netlist optimization baseline with shared tier metrics.
- `optimization/battery_18650_t4_thermal_hybrid_opt.py`: compare tier-4 hybrid and explicit-circuit scoring on the same candidate.
- `optimization/battery_fast_charge_dfn_anchor_opt.py`: inspect the DFN anchor benchmark and its deterministic baseline/reference-search wording.
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
