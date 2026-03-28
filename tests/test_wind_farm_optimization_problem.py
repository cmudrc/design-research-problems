from __future__ import annotations

import numpy

from design_research_problems import OptimizationProblem, get_problem
from design_research_problems.problems.optimization import WindFarmLayoutOptimizationProblem


def test_wind_farm_layout_problem_is_registered_and_seed_is_feasible() -> None:
    problem = get_problem("wind_farm_grid_qkp_power_max")

    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, WindFarmLayoutOptimizationProblem)

    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    initial_eval = problem.evaluate(initial)

    assert initial.shape == (16,)
    assert initial_eval.is_feasible is True
    assert len(initial_state.selected_indices) == problem.turbine_count
    assert initial_state.expected_power_mw > 0.0


def test_wind_farm_layout_greedy_baseline_returns_fixed_count_solution() -> None:
    problem = get_problem("wind_farm_grid_qkp_power_max")
    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)

    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)
    solved_eval = problem.evaluate(result.x)
    components = problem.objective_components(result.x)

    assert result.success is True
    assert result.x.shape == (16,)
    assert solved_eval.is_feasible is True
    assert len(solved_state.selected_indices) == problem.turbine_count
    assert solved_state.expected_power_mw >= initial_state.expected_power_mw
    assert components["selected_count"] == float(problem.turbine_count)
    assert components["violation_count"] == 0.0
    assert numpy.all(result.x >= problem.bounds.lb)
    assert numpy.all(result.x <= problem.bounds.ub)
