from __future__ import annotations

import numpy

from design_research_problems import get_problem


def test_ide_treadle_problem_exposes_zone_i_baseline() -> None:
    problem = get_problem("treadle_pump_ide_material_min")
    baseline = problem.generate_initial_solution()
    components = problem.objective_components(baseline)

    assert baseline.shape == (4,)
    assert abs(components["flow_rate_lps"] - problem.target_flow_rate_lps) < 1e-6
    assert abs(components["lift_height_m"] - problem.target_lift_height_m) < 1e-5
    assert 0.002 < components["material_volume_m3"] < 0.01


def test_ide_treadle_problem_solve_returns_feasible_solution() -> None:
    problem = get_problem("treadle_pump_ide_material_min")
    initial = problem.generate_initial_solution()
    result = problem.solve()

    assert result.success is True
    assert "Converged SciPy SLSQP baseline" in result.message
    assert result.x.shape == (4,)
    assert result.fun <= problem.objective(initial)
    assert abs(problem.flow_rate_lps(result.x) - problem.target_flow_rate_lps) < 1e-9
    assert abs(problem.lift_height_m(result.x) - problem.target_lift_height_m) < 1e-9
    assert problem.max_constraint_violation(result.x) <= 1e-6


def test_ide_treadle_problem_generate_initial_solution_is_deterministic() -> None:
    problem = get_problem("treadle_pump_ide_material_min")
    x1 = problem.generate_initial_solution(seed=7)
    x2 = problem.generate_initial_solution(seed=7)

    assert x1.shape == (4,)
    assert numpy.allclose(x1, x2)
