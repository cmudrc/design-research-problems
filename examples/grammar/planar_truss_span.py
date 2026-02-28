"""Build and optionally evaluate a simple truss state."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems.grammar import AddMember


def main() -> None:
    """Build a simple triangular state and evaluate it when ``trussme`` is installed."""
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=1, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=1))
    try:
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(evaluation)


if __name__ == "__main__":
    main()
