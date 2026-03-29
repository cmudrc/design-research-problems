"""Build and evaluate a simple tier-2 battery grammar state."""

from __future__ import annotations

from _battery_transition_helpers import apply_first_transition

import design_research_problems as derp


def main() -> None:
    """Nudge the seed layout with a couple of concrete pose edits and print its metrics."""

    # Load the tier-2 pose grammar and start from its deterministic vector seed.
    problem = derp.get_problem("battery_18650_t2_pose_surrogate_grammar")
    state = problem.initial_state()

    # Vector-grammar transitions already carry their next state, so we apply two
    # named local edits to move the first cell away from the default layout.
    state = apply_first_transition(problem, state, "move_cell_x")
    state = apply_first_transition(problem, state, "move_cell_y")

    evaluation = problem.evaluate(state)
    print(evaluation)


if __name__ == "__main__":
    main()
