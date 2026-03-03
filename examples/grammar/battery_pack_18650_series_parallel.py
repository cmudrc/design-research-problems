"""Build and evaluate a simple 4S4P battery-pack grammar state."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems.grammar import AddParallelBranch, AddSeriesStage


def main() -> None:
    """Build a small feasible-looking state and evaluate it when ``pybamm`` is installed."""

    problem = get_problem("battery_pack_18650_series_parallel")
    state = problem.initial_state()
    state = problem.apply_action(state, AddSeriesStage(placements=((1, 0, 0),)))
    state = problem.apply_action(state, AddSeriesStage(placements=((2, 0, 0),)))
    state = problem.apply_action(state, AddSeriesStage(placements=((3, 0, 0),)))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0))))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0))))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0))))

    print(problem.metadata.problem_id)
    print(f"{state.series_count}S{state.parallel_count}P with {len(state.cells)} cells")
    try:
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation.is_feasible, round(evaluation.design_volume, 2))


if __name__ == "__main__":
    main()
