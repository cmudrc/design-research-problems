"""Use a grammar-derived battery layout as an optimizer-style starting point."""

from __future__ import annotations

import numpy

from design_research_problems import MissingOptionalDependencyError, get_problem


def _build_feasible_4s4p_state() -> object:
    """Return the same canonical 4S4P grammar state used in the battery demo.

    Returns:
        Grammar state representing a feasible 4S4P rectangular battery pack.
    """
    problem = get_problem("battery_pack_18650_series_parallel")
    state = problem.initial_state()
    state = problem.add_series_stage(state, placements=((1, 0, 0),))
    state = problem.add_series_stage(state, placements=((2, 0, 0),))
    state = problem.add_series_stage(state, placements=((3, 0, 0),))
    state = problem.add_parallel_branch(state, placements=((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0)))
    return state


def main() -> None:
    """Start from a grammar-owned 4S4P layout, then stay in the optimization API."""
    optimization_problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    state = _build_feasible_4s4p_state()
    candidate = numpy.array([float(state.series_count), float(state.parallel_count)], dtype=float)

    print(optimization_problem.metadata.problem_id)
    print(f"seed-from-grammar {state.series_count}S{state.parallel_count}P")

    try:
        seeded_evaluation = optimization_problem.evaluate(candidate)
        default_initial = optimization_problem.generate_initial_solution()
        default_evaluation = optimization_problem.evaluate(default_initial)
        solved = optimization_problem.solve(initial_solution=candidate, maxiter=25)
        solved_state = optimization_problem.decode_candidate(solved.x)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return

    print("default", int(default_initial[0]), int(default_initial[1]), bool(default_evaluation.is_feasible))
    print("seeded", round(float(seeded_evaluation.objective_value), 2), seeded_evaluation.is_feasible)
    print("solve", solved_state.series_count, solved_state.parallel_count, bool(solved.success))


if __name__ == "__main__":
    main()
