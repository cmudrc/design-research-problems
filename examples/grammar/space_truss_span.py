"""Build and optionally evaluate a simple 3D space-truss state."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem


def main() -> None:
    """Build a simple bridge-like space truss and evaluate it when ``trussme`` is installed."""
    problem = get_problem("space_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=2, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=3, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=1)
    state = problem.add_member(state, start_joint_id=2, end_joint_id=3)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=3)
    print(problem.metadata.problem_id)
    try:
        evaluation = problem.evaluate(state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print("mass", round(evaluation.mass, 3))
    print("fos", round(evaluation.fos, 3))
    print("deflection", round(evaluation.deflection, 3))


if __name__ == "__main__":
    main()
