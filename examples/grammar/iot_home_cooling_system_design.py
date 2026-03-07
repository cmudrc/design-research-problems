"""Build and evaluate a small IoT home cooling-system design."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Create a simple IoT network and evaluate lifecycle and thermal metrics."""
    problem = derp.get_problem("iot_home_cooling_system_design")
    state = problem.initial_state()
    transitions = problem.enumerate_transitions(state)

    state = problem.add_processor(state, x=-8.708087, y=29.342105)
    state = problem.add_sensor(state, dm_name="d0", x=3.651551, y=26.568279)
    state = problem.add_cooler(state, dm_name="d0", x=6.947455, y=35.999289, btus=10_000.0, cfm=200.0)

    evaluation = problem.evaluate(state)
    print(problem.metadata.problem_id)
    print("initial-transition-count", len(transitions))
    print("product-count", len(state.products))
    print("link-count", len(state.links))
    print("total-cost", round(evaluation.total_cost, 3))
    print("peak-temp-c", round(evaluation.peak_temp_c, 3))
    print("capital-cost", round(evaluation.capital_cost, 3))
    print("operation-cost", round(evaluation.operation_cost, 3))


if __name__ == "__main__":
    main()
