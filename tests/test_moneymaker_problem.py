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


def test_moneymaker_problem_solve_returns_feasible_reduced_coordinate_solution() -> None:
    problem = get_problem("moneymaker_hip_pump_cost_min")
    initial = problem.generate_initial_solution()
    result = problem.solve()

    assert result.success is True
    assert "Converged SciPy SLSQP baseline" in result.message
    assert result.x.shape == (10,)
    assert result.fun < problem.objective(initial)
    assert abs(problem.flow_rate_lps(result.x) - problem.target_flow_rate_lps) < 1e-9
    assert problem.max_constraint_violation(result.x) <= 1e-6


def test_moneymaker_problem_generate_initial_solution_is_deterministic() -> None:
    problem = get_problem("moneymaker_hip_pump_cost_min")
    x1 = problem.generate_initial_solution(seed=7)
    x2 = problem.generate_initial_solution(seed=7)

    assert x1.shape == (10,)
    assert numpy.allclose(x1, x2)
