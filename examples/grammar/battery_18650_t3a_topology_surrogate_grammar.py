"""Build and evaluate a simple tier-3A battery grammar state."""

from __future__ import annotations

from _battery_transition_helpers import apply_first_transition

import design_research_problems as derp


def main() -> None:
    """Apply a few topology edits to the seed state and print its metrics."""

    # Load the topology-allocation grammar and start from its seed vector.
    problem = derp.get_problem("battery_18650_t3a_topology_surrogate_grammar")
    state = problem.initial_state()

    # Apply one cell-count edit, one series-count edit, and one stage-slot edit
    # so the example touches the topology-specific part of the representation.
    state = apply_first_transition(problem, state, "adjust_cell_count")
    state = apply_first_transition(problem, state, "adjust_series_count")
    state = apply_first_transition(problem, state, "adjust_first_cell_stage_slot")

    evaluation = problem.evaluate(state)
    print(evaluation)


if __name__ == "__main__":
    main()
