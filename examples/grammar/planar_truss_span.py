"""Build and optionally evaluate a simple truss state."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Build a simple triangular state and evaluate it when ``trussme`` is installed."""

    # Load the planar truss grammar and start from its seed state, which already
    # includes the fixed support joints and one free top joint.
    problem = derp.get_problem("planar_truss_span")
    state = problem.initial_state()

    # Apply three rule methods to connect the top joint to both supports and then
    # close the base edge. Together these edits build the minimal triangle.
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=1)
    try:
        # The evaluator converts the serializable grammar state into a fresh truss
        # model for analysis and returns the resulting performance metrics.
        evaluation = problem.evaluate(state)
    except derp.MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation)


if __name__ == "__main__":
    main()
