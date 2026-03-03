"""Build and optionally evaluate a simple truss state."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems.grammar import AddMember


def main() -> None:
    """Build a simple triangular state and evaluate it when ``trussme`` is installed."""

    # Load the planar truss grammar and start from its seed state, which already
    # includes the fixed support joints and one free top joint.
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()

    # Apply three AddMember actions to connect the top joint to both supports and
    # then close the base edge. Together these actions build the minimal triangle.
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=1, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=1))
    try:
        # The evaluator converts the serializable grammar state into a fresh truss
        # model for analysis and returns the resulting performance metrics.
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation)


if __name__ == "__main__":
    main()
