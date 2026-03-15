from __future__ import annotations

import numpy

from design_research_problems import OptimizationProblem, get_problem
from design_research_problems.problems.optimization import CompetingProjectsWorkerHoursProblem


def test_worker_hours_problem_is_registered_and_initial_plan_is_feasible() -> None:
    problem = get_problem("worker_hours_competing_projects_value_tracking_min")

    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, CompetingProjectsWorkerHoursProblem)

    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    initial_eval = problem.evaluate(initial)

    assert initial.shape == (2400,)
    assert initial_eval.is_feasible is True
    assert initial_state.completed_task_count == 0
    assert initial_state.total_achieved_value > 0.0
    assert initial_state.total_achieved_value < initial_state.total_target_value
    assert initial_state.total_target_value > 0.0


def test_worker_hours_greedy_baseline_improves_tracking_error() -> None:
    problem = get_problem("worker_hours_competing_projects_value_tracking_min")
    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    initial_components = problem.objective_components(initial)

    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)
    solved_eval = problem.evaluate(result.x)
    solved_components = problem.objective_components(result.x)

    assert result.success is True
    assert result.x.shape == (2400,)
    assert solved_eval.is_feasible is True
    assert solved_state.tracking_error < initial_state.tracking_error
    assert solved_components["tracking_error"] < initial_components["tracking_error"]
    assert solved_state.total_achieved_value >= initial_state.total_achieved_value
    assert numpy.all(result.x >= problem.bounds.lb)
    assert numpy.all(result.x <= problem.bounds.ub)
