from __future__ import annotations

import numpy

from design_research_problems import OptimizationProblem, get_problem
from design_research_problems.problems.optimization import UnrestrictedWindFarmLayoutOptimizationProblem


def test_unrestricted_wind_farm_problem_is_registered_and_seed_is_feasible() -> None:
    problem = get_problem("wind_farm_unrestricted_deficit_min")

    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, UnrestrictedWindFarmLayoutOptimizationProblem)

    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    initial_eval = problem.evaluate(initial)

    assert initial.shape == (14,)
    assert initial_eval.is_feasible is True
    assert initial_state.weighted_wake_deficit_mps == 0.0
    assert sum(initial_state.directional_overlap_counts) == 0
    assert initial_state.minimum_l1_spacing_m > problem.minimum_l1_spacing_m


def test_unrestricted_wind_farm_baseline_returns_zero_overlap_layout() -> None:
    problem = get_problem("wind_farm_unrestricted_deficit_min")
    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)
    solved_eval = problem.evaluate(result.x)
    components = problem.objective_components(result.x)

    assert result.success is True
    assert result.x.shape == (14,)
    assert solved_eval.is_feasible is True
    assert solved_state.weighted_wake_deficit_mps == 0.0
    assert sum(solved_state.directional_overlap_counts) == 0
    assert components["spacing_violation_count"] == 0.0
    assert components["constraint_violation"] == 0.0
    assert numpy.all(result.x >= problem.bounds.lb)
    assert numpy.all(result.x <= problem.bounds.ub)
