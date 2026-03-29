from __future__ import annotations

import numpy

from design_research_problems.problems._domains.personnel_allocation import (
    build_manager_baseline_plan,
    build_value_tracking_plan,
    create_competing_projects_backend,
    simulate_competing_projects_plan,
)


def test_personnel_allocation_backend_builds_expected_case_bundle() -> None:
    backend = create_competing_projects_backend(horizon_days=60)

    assert backend.variable_shape == (60, 5, 8)
    assert backend.variable_count == 2400
    assert backend.target_value_by_day.shape == (60, 8)
    assert backend.task_names[0] == "Project 1 - Phase 1"
    assert backend.worker_names[-1] == "Worker E"
    assert backend.target_value_by_day[0, 0] > 0.0
    assert backend.target_value_by_day[0, 1] == 0.0


def test_personnel_allocation_heuristics_improve_on_empty_plan() -> None:
    backend = create_competing_projects_backend(horizon_days=60)

    empty = numpy.zeros(backend.variable_count, dtype=float)
    baseline = build_manager_baseline_plan(backend)
    greedy = build_value_tracking_plan(backend)
    empty_sim = simulate_competing_projects_plan(empty, backend=backend)
    baseline_sim = simulate_competing_projects_plan(baseline, backend=backend)
    greedy_sim = simulate_competing_projects_plan(greedy, backend=backend)

    assert baseline.shape == (backend.variable_count,)
    assert greedy.shape == (backend.variable_count,)
    assert baseline_sim.tracking_error < empty_sim.tracking_error
    assert greedy_sim.tracking_error < empty_sim.tracking_error
    assert greedy_sim.daily_value_by_task.shape == (60, 8)
    assert numpy.all(greedy_sim.daily_hours >= 0.0)
    assert greedy_sim.inactive_hours >= 0.0
