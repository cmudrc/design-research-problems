from __future__ import annotations

import numpy

from design_research_problems import get_problem


def test_moneymaker_problem_exposes_published_tall_tank_baseline() -> None:
    problem = get_problem("moneymaker_hip_pump_cost_min")
    baseline = problem.generate_initial_solution()
    components = problem.objective_components(baseline)

    assert baseline.shape == (10,)
    assert abs(components["flow_rate_lps"] - problem.target_flow_rate_lps) < 0.01
    assert components["tank_height_m"] == 3.0
    assert 15.0 < components["cost_usd"] < 35.0


def test_moneymaker_problem_load_data_returns_curated_cases() -> None:
    problem = get_problem("moneymaker_hip_pump_cost_min")
    dataset = problem.load_data()

    assert dataset["labels"] == (
        "published_current_tall_tank",
        "published_same_flow_min_cost_tall_tank",
        "published_max_flow_same_cost_tall_tank",
    )
    assert dataset["variables"].shape == (3, 10)
    assert numpy.allclose(dataset["flow_rate_lps"], numpy.array([0.167, 0.180, 0.220]))


def test_moneymaker_problem_generate_data_is_deterministic() -> None:
    problem = get_problem("moneymaker_hip_pump_cost_min")
    x1, y1 = problem.generate_data(n=4, seed=7)
    x2, y2 = problem.generate_data(n=4, seed=7)

    assert x1.shape == (4, 10)
    assert y1.shape == (4, 1)
    assert numpy.allclose(x1, x2)
    assert numpy.allclose(y1, y2)
