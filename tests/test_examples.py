from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_example(relative_path: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, relative_path, *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.examples_smoke
def test_catalog_example_runs() -> None:
    completed = _run_example("examples/catalog/list_and_load.py")
    assert completed.returncode == 0, completed.stderr
    assert "ideation_peanut_shelling_fu_cagan_kotovsky_2010" in completed.stdout


@pytest.mark.examples_smoke
def test_ideation_catalog_example_runs() -> None:
    completed = _run_example("examples/catalog/ideation_catalog.py")
    assert completed.returncode == 0, completed.stderr
    assert "prompts 40" in completed.stdout


@pytest.mark.examples_smoke
def test_ideation_export_example_runs() -> None:
    completed = _run_example("examples/catalog/ideation_exports.py")
    assert completed.returncode == 0, completed.stderr
    assert "prompt_id,problem_id,family_id,canonical_brief,evidence_tier,status,tags" in completed.stdout


@pytest.mark.examples_smoke
def test_ideation_dataframe_example_runs() -> None:
    completed = _run_example("examples/catalog/ideation_dataframe.py")
    assert completed.returncode == 0, completed.stderr
    if "Install it with: pip install design-research-problems[pandas]" in completed.stdout:
        pytest.skip("pandas is not installed in this environment.")
    assert "prompt_id" in completed.stdout


@pytest.mark.examples_smoke
def test_text_example_runs() -> None:
    completed = _run_example("examples/text/peanut_sheller_packet.py")
    assert completed.returncode == 0, completed.stderr
    assert "Device to shell peanuts" in completed.stdout


@pytest.mark.examples_smoke
def test_mcp_example_runs() -> None:
    completed = _run_example("examples/mcp/peanut_sheller_server.py")
    assert completed.returncode == 0, completed.stderr
    if "Install the optional MCP dependency with:" in completed.stdout:
        pytest.skip("mcp is not installed in this environment.")
    assert "Problem id: ideation_peanut_shelling_fu_cagan_kotovsky_2010" in completed.stdout
    assert "Tool count: 1" in completed.stdout
    assert "Tools: submit_final" in completed.stdout
    assert "submit_final answer:" in completed.stdout


@pytest.mark.examples_smoke
def test_mcp_build123d_example_runs() -> None:
    completed = _run_example("examples/mcp/build123d_parametric_mounting_bracket.py")
    assert completed.returncode == 0, completed.stderr
    if "Install the optional MCP dependency with:" in completed.stdout:
        pytest.skip("mcp is not installed in this environment.")
    if "build123d backend startup failed:" in completed.stdout:
        pytest.skip("build123d backend could not be started in this environment.")
    assert "Problem id: mcp_build123d_parametric_mounting_bracket" in completed.stdout
    assert "Tool count:" in completed.stdout
    assert "backend_status" in completed.stdout
    assert "evaluate_scripted_part" in completed.stdout
    assert "describe_last_script_result" in completed.stdout
    assert "Resources: problem://design-brief" in completed.stdout
    assert "submit_final answer:" in completed.stdout


@pytest.mark.examples_smoke
def test_decision_laptop_example_runs() -> None:
    completed = _run_example("examples/decision/laptop_design.py")
    assert completed.returncode == 0, completed.stderr
    assert "decision_laptop_design_profit_maximization" in completed.stdout
    assert "candidate-count 3125" in completed.stdout
    assert "top-three" in completed.stdout


@pytest.mark.examples_smoke
def test_decision_mseval_example_runs() -> None:
    completed = _run_example("examples/decision/mseval_material_choice.py")
    assert completed.returncode == 0, completed.stderr
    assert "decision_mseval_safety_helmet_lightweight" in completed.stdout
    assert "candidate-count 9" in completed.stdout
    assert "best Composite" in completed.stdout


@pytest.mark.examples_smoke
@pytest.mark.examples_full
def test_ide_treadle_pump_example_runs() -> None:
    completed = _run_example("examples/optimization/ide_treadle_pump.py")
    assert completed.returncode == 0, completed.stderr
    assert "IDE-style treadle pump packaged benchmark" in completed.stdout
    assert "initial flow_lps=" in completed.stdout
    assert "violation=" in completed.stdout
    assert "Converged SciPy SLSQP baseline" in completed.stdout
    assert "solved flow_lps=2.500" in completed.stdout


@pytest.mark.examples_smoke
@pytest.mark.examples_full
def test_pill_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/pill_problem.py")
    assert completed.returncode == 0, completed.stderr
    assert "(2,)" in completed.stdout
    assert "Converged SciPy SLSQP baseline" in completed.stdout


@pytest.mark.examples_smoke
@pytest.mark.examples_full
def test_moneymaker_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/moneymaker_hip_pump.py")
    assert completed.returncode == 0, completed.stderr
    assert "MoneyMaker Hip Pump humanitarian water-lifting benchmark" in completed.stdout
    assert "Converged SciPy SLSQP baseline" in completed.stdout


@pytest.mark.examples_smoke
def test_gmpb_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/gmpb_dynamic_problem.py")
    assert completed.returncode == 0, completed.stderr
    assert "gmpb_default_dynamic_min" in completed.stdout
    assert "before env=0 evals=0" in completed.stdout
    assert "after env=0 evals=1" in completed.stdout


@pytest.mark.examples_smoke
def test_t1_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_18650_t1_series_parallel_grammar.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t1_series_parallel_grammar" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t2_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_18650_t2_layout_grammar.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t2_layout_grammar" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t3_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_18650_t3_topology_grammar.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t3_topology_grammar" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t4_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_18650_t4_thermal_grammar.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t4_thermal_grammar" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t1_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_18650_t1_series_parallel_opt.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t1_series_parallel_opt" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t2_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_18650_t2_layout_opt.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t2_layout_opt" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t3_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_18650_t3_topology_opt.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t3_topology_opt" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_t4_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_18650_t4_thermal_opt.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_18650_t4_thermal_opt" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.examples_smoke
def test_fast_charge_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_fast_charge_cell_opt.py")
    assert completed.returncode == 0, completed.stderr
    if "Install it with: pip install design-research-problems[battery]" in completed.stdout:
        pytest.skip("pybamm is not installed in this environment.")
    assert "battery_fast_charge_cell_opt" in completed.stdout
    assert "metric-keys" in completed.stdout


@pytest.mark.trussme_real
def test_grammar_example_runs_when_trussme_is_installed() -> None:
    completed = _run_example("examples/grammar/planar_truss_span.py")
    if "trussme is required for truss evaluation" in completed.stdout:
        pytest.skip("trussme is not installed in this environment.")
    assert completed.returncode == 0, completed.stderr


@pytest.mark.examples_smoke
def test_space_truss_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/space_truss_span.py")
    assert completed.returncode == 0, completed.stderr
    assert "space_truss_span" in completed.stdout
    if "trussme is required for truss evaluation" in completed.stdout:
        return
    assert "mass" in completed.stdout
    assert "fos" in completed.stdout
    assert "deflection" in completed.stdout


@pytest.mark.examples_smoke
def test_iot_home_cooling_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/iot_home_cooling_system_design.py")
    assert completed.returncode == 0, completed.stderr
    assert "iot_home_cooling_system_design" in completed.stdout
    assert "total-cost" in completed.stdout
    assert "peak-temp-c" in completed.stdout


@pytest.mark.examples_smoke
def test_truss_ap_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/truss_analysis_program_design.py")
    assert completed.returncode == 0, completed.stderr
    assert "truss_analysis_program_design" in completed.stdout
    assert "mass-kg" in completed.stdout
    assert "min-fos" in completed.stdout


@pytest.mark.examples_smoke
def test_space_truss_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/space_truss_span_mass_min.py")
    assert completed.returncode == 0, completed.stderr
    assert "space_truss_span_mass_min" in completed.stdout
    if "trussme is required for truss evaluation" in completed.stdout:
        return
    assert "members" in completed.stdout
    assert "solve" in completed.stdout
