"""Build and evaluate a feasible open-ended 4S4P-equivalent battery graph."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems.grammar import AddCell


def main() -> None:
    """Build a feasible 4S4P-equivalent explicit battery graph and evaluate it."""

    # Load the open-ended battery grammar and start from its one-cell seed state.
    problem = get_problem("battery_pack_18650_open_ended")
    state = problem.initial_state()
    stage_input_terminal_id = state.pack_negative_terminal_id
    stage_output_terminal_id = state.pack_positive_terminal_id

    # First, fill out the remaining three parallel cells in stage 0. Each AddCell
    # action inserts a new physical cell and immediately ties both of its leads into
    # the existing circuit by naming the terminals it should connect to.
    for branch_index in range(1, 4):
        state = problem.apply_action(
            state,
            AddCell(
                x=0,
                y=branch_index,
                z=0,
                connect_negative_to_terminal_id=stage_input_terminal_id,
                connect_positive_to_terminal_id=stage_output_terminal_id,
            ),
        )

    # Then grow the pack stage by stage. The first cell in each new stage extends
    # the series chain and promotes its new positive lead to be the pack output.
    # The remaining three cells for that stage are added in parallel between the
    # previous stage output bus and the new stage output bus.
    for stage_index in range(1, 4):
        previous_stage_output_terminal_id = stage_output_terminal_id
        state = problem.apply_action(
            state,
            AddCell(
                x=stage_index,
                y=0,
                z=0,
                connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                use_positive_as_pack_terminal=True,
            ),
        )
        stage_output_terminal_id = state.pack_positive_terminal_id
        for branch_index in range(1, 4):
            state = problem.apply_action(
                state,
                AddCell(
                    x=stage_index,
                    y=branch_index,
                    z=0,
                    connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                    connect_positive_to_terminal_id=stage_output_terminal_id,
                ),
            )

    print(problem.metadata.problem_id)
    print(f"{len(state.cells)} cells with {len(state.connections)} interconnects")
    try:
        # The evaluator validates the explicit graph, reduces it to circuit nets, and
        # simulates the resulting pack through the shared battery backend.
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    if not evaluation.is_feasible:
        raise RuntimeError("The open-ended battery example should evaluate to a feasible design.")
    print(evaluation.topology_kind, evaluation.is_feasible, round(evaluation.design_volume, 2))


if __name__ == "__main__":
    main()
