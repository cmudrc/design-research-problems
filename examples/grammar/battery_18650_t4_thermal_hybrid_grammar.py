"""Build and optionally evaluate a simple tier-4 battery grammar state."""

from __future__ import annotations

from _battery_transition_helpers import apply_first_transition

import design_research_problems as derp


def main() -> None:
    """Apply topology, pose, and thermal edits, then evaluate when PyBaMM is installed."""

    # Load the tier-4 thermal grammar and start from the deterministic seed.
    problem = derp.get_problem("battery_18650_t4_thermal_hybrid_grammar")
    state = problem.initial_state()

    # Use one topology edit, one pose edit, and one thermal tuning edit so the
    # example touches each part of the tier-4 representation.
    state = apply_first_transition(problem, state, "adjust_cell_count")
    state = apply_first_transition(problem, state, "move_cell_x")
    state = apply_first_transition(problem, state, "tune_cooling_coefficient")

    try:
        evaluation = problem.evaluate(state)
    except derp.MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation)


if __name__ == "__main__":
    main()
