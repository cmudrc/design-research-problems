from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_example(relative_path: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, relative_path],
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
    if "optional 'design-research-problems[pandas]' extra" in completed.stdout:
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
    assert "Tools: final_answer" in completed.stdout
    assert "final_answer answer:" in completed.stdout


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
def test_open_ended_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_pack_18650_open_ended.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_pack_18650_open_ended" in completed.stdout
    if "pybamm is required for battery grammar evaluation" in completed.stdout:
        return
    assert completed.stdout.splitlines()[-1].split()[1] == "True"


@pytest.mark.examples_smoke
def test_battery_grammar_example_runs() -> None:
    completed = _run_example("examples/grammar/battery_pack_18650_series_parallel.py")
    assert completed.returncode == 0, completed.stderr
    assert "battery_pack_18650_series_parallel" in completed.stdout
    if "pybamm is required for battery grammar evaluation" in completed.stdout:
        return
    assert completed.stdout.splitlines()[-1].split()[0] == "True"


@pytest.mark.examples_smoke
def test_battery_grammar_to_optimizer_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_grammar_to_optimizer.py")
    assert completed.returncode == 0, completed.stderr
    assert "Rectangular battery packaged benchmark" in completed.stdout
    if "pybamm is required for battery grammar evaluation" in completed.stdout:
        return
    assert "initial config=" in completed.stdout
    assert "\nsolve " in completed.stdout
    assert "solved config=" in completed.stdout


@pytest.mark.examples_smoke
def test_open_ended_battery_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/battery_open_ended_capacity_max.py")
    assert completed.returncode == 0, completed.stderr
    assert "Open-ended battery packaged benchmark" in completed.stdout
    if "pybamm is required for battery grammar evaluation" in completed.stdout:
        return
    assert "initial cell_count=" in completed.stdout
    assert "\nsolve " in completed.stdout
    assert "solved cell_count=" in completed.stdout


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
def test_space_truss_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/space_truss_span_mass_min.py")
    assert completed.returncode == 0, completed.stderr
    assert "space_truss_span_mass_min" in completed.stdout
    if "trussme is required for truss evaluation" in completed.stdout:
        return
    assert "members" in completed.stdout
    assert "solve" in completed.stdout
