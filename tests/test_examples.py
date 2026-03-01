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
    assert "peanut_sheller_fu2010" in completed.stdout


@pytest.mark.examples_smoke
def test_ideation_catalog_example_runs() -> None:
    completed = _run_example("examples/catalog/ideation_catalog.py")
    assert completed.returncode == 0, completed.stderr
    assert "prompts 16" in completed.stdout


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
@pytest.mark.examples_full
def test_optimization_example_runs() -> None:
    completed = _run_example("examples/optimization/pill_problem.py")
    assert completed.returncode == 0, completed.stderr
    assert "(5, 2) (5, 1)" in completed.stdout


@pytest.mark.trussme_real
def test_grammar_example_runs_when_trussme_is_installed() -> None:
    completed = _run_example("examples/grammar/planar_truss_span.py")
    if "trussme is required for grammar evaluation" in completed.stdout:
        pytest.skip("trussme is not installed in this environment.")
    assert completed.returncode == 0, completed.stderr
