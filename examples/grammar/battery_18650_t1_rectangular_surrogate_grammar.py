"""Build and evaluate a simple tier-1 battery grammar state."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Grow the seed state into a small 2S2P pack and print its metrics."""

    # Load the tier-1 rectangular grammar and start from the bundled 1S1P seed.
    problem = derp.get_problem("battery_18650_t1_rectangular_surrogate_grammar")
    state = problem.initial_state()

    # First add one parallel branch beside the seed cell, then append a second
    # series stage with one cell per branch to build a minimal 2S2P layout.
    state = problem.add_parallel_branch(state, placements=((0, 1, 0),))
    state = problem.add_series_stage(state, placements=((1, 0, 0), (1, 1, 0)))

    # The evaluator reports the shared battery-tier metric contract.
    evaluation = problem.evaluate(state)
    print(evaluation)


if __name__ == "__main__":
    main()
