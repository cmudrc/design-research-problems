"""Build and optionally evaluate a simple tier-3B battery grammar state."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Build a small 2S2P explicit netlist and evaluate it when PyBaMM is installed."""

    # Load the explicit-netlist grammar and start from its one-cell seed state.
    problem = derp.get_problem("battery_18650_t3b_netlist_explicit_grammar")
    state = problem.initial_state()

    # First add a parallel mate across the seed cell, then append a second
    # series stage with one cell per branch to build a simple 2S2P pack.
    stage_output_terminal_id = state.pack_positive_terminal_id
    state = problem.add_cell(
        state,
        x=0,
        y=1,
        z=0,
        connect_negative_to_terminal_id=state.pack_negative_terminal_id,
        connect_positive_to_terminal_id=stage_output_terminal_id,
    )
    state = problem.add_cell(
        state,
        x=1,
        y=0,
        z=0,
        connect_negative_to_terminal_id=stage_output_terminal_id,
        use_positive_as_pack_terminal=True,
    )
    state = problem.add_cell(
        state,
        x=1,
        y=1,
        z=0,
        connect_negative_to_terminal_id=stage_output_terminal_id,
        connect_positive_to_terminal_id=state.pack_positive_terminal_id,
    )

    try:
        evaluation = problem.evaluate(state)
    except derp.MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation)


if __name__ == "__main__":
    main()
