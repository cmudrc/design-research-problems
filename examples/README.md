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
- `grammar/battery_pack_18650_open_ended.py`: build a 4S4P-equivalent explicit battery graph and evaluate it when `pybamm` is installed.
- `grammar/battery_pack_18650_series_parallel.py`: build the constrained rectangular 4S4P battery grammar state and evaluate it when `pybamm` is installed.
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
- `gui/iot_home_cooling_tk.py`: launch a Tkinter desktop GUI for interactive IoT home cooling co-design.
- `gui/truss_analysis_program_tk.py`: launch a Tkinter desktop GUI for interactive truss design with mass/FOS evaluation.
- `mcp/peanut_sheller_server.py`: spin up a local MCP stdio server and call `final_answer` through an MCP client session.
- `mcp/build123d_parametric_mounting_bracket.py`: inspect the MCP-ingested Build123d catalog problem and run a script-authored CAD evaluation through the proxied tools.

## Launching GUI Examples

From the repository root:

```bash
uv run python -m design_research_problems.gui --app iot
uv run python -m design_research_problems.gui --app truss
```
