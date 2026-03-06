"""Build and evaluate a feasible constrained rectangular 4S4P battery pack."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem


def main() -> None:
    """Build the constrained feasible 4S4P case and evaluate it when ``pybamm`` is installed.

    Raises:
        RuntimeError: If the constructed example pack evaluates as infeasible.
    """

    # Load the constrained rectangular battery grammar and start from its 1S1P seed pack.
    problem = get_problem("battery_pack_18650_series_parallel")
    state = problem.initial_state()

    # Add three more series stages. In this grammar each add_series_stage call must
    # provide one placement for every existing parallel branch, which is one cell at
    # a time while the pack is still 1P.
    state = problem.add_series_stage(state, placements=((1, 0, 0),))
    state = problem.add_series_stage(state, placements=((2, 0, 0),))
    state = problem.add_series_stage(state, placements=((3, 0, 0),))

    # Add three more parallel branches. Once the pack is 4S, each add_parallel_branch
    # call must provide one placement for every series stage, so each edit adds a
    # full new branch of four cells.
    state = problem.add_parallel_branch(state, placements=((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0)))

    print(problem.metadata.problem_id)
    print(f"{state.series_count}S{state.parallel_count}P with {len(state.cells)} cells")
    try:
        # The packaged evaluator checks the rectangular topology, translates it into
        # the shared explicit circuit backend, and then runs the battery simulation.
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    if not evaluation.is_feasible:
        raise RuntimeError("The constrained battery example should evaluate to a feasible design.")
    print(evaluation.is_feasible, round(evaluation.design_volume, 2))


if __name__ == "__main__":
    main()
