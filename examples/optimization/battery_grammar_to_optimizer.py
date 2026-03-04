"""Bridge the rectangular battery grammar to its optimization-family sibling."""

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
    """Compare one explicit grammar design to the optimization-family wrapper."""
    grammar_problem = get_problem("battery_pack_18650_series_parallel")
    optimization_problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    state = _build_feasible_4s4p_state()
    candidate = numpy.array([float(state.series_count), float(state.parallel_count)], dtype=float)

    print(grammar_problem.metadata.problem_id)
    print(optimization_problem.metadata.problem_id)
    print(f"bridge {state.series_count}S{state.parallel_count}P")

    try:
        grammar_evaluation = grammar_problem.evaluate(state)
        optimization_evaluation = optimization_problem.evaluate(candidate)
        solved = optimization_problem.solve(maxiter=25)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return

    print("grammar", round(grammar_evaluation.design_cost, 2), grammar_evaluation.is_feasible)
    print("optimizer", round(float(optimization_evaluation.objective_value), 2), optimization_evaluation.is_feasible)
    print("solve", int(solved.x[0]), int(solved.x[1]), bool(solved.success))


if __name__ == "__main__":
    main()
