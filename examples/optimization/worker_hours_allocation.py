"""Inspect the compact competing-projects worker-hours allocation benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print one decoded baseline allocation and the greedy solver result."""
    problem = derp.get_problem("worker_hours_competing_projects_value_tracking_min")
    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)

    print("Competing-projects worker-hours benchmark")
    print("task_count", len(problem.task_names))
    print("worker_count", len(problem.worker_names))
    print("initial_tracking_error", round(initial_state.tracking_error, 4))
    print("initial_completed_tasks", initial_state.completed_task_count)
    print("solved_tracking_error", round(solved_state.tracking_error, 4))
    print("solved_inactive_hours", round(solved_state.inactive_hours, 4))
    print("solved_total_achieved_value", round(solved_state.total_achieved_value, 4))
    print("success", result.success)
    print("message", result.message)


if __name__ == "__main__":
    main()
