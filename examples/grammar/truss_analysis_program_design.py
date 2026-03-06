"""Build and evaluate a truss design using Truss Analysis Program mechanics."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Create a feasible truss and print key evaluation metrics."""
    problem = get_problem("truss_analysis_program_design")
    state = problem.initial_state()

    state = problem.add_joint(state, x=-3.446939, y=1.847708)
    state = problem.add_joint(state, x=-0.410204, y=1.835182)
    state = problem.add_joint(state, x=2.834694, y=1.860235)

    for start_joint_id, end_joint_id in (
        (1, 4),
        (4, 2),
        (2, 5),
        (5, 3),
        (1, 6),
        (6, 4),
        (4, 7),
        (7, 2),
        (2, 8),
        (8, 5),
        (6, 7),
        (7, 8),
    ):
        state = problem.add_member(state, start_joint_id=start_joint_id, end_joint_id=end_joint_id, size_index=8)

    evaluation = problem.evaluate(state)
    print(problem.metadata.problem_id)
    print("joint-count", evaluation.joint_count)
    print("member-count", evaluation.member_count)
    print("mass-kg", round(evaluation.mass_kg, 3))
    print("min-fos", round(evaluation.min_fos, 3))
    print("is-stable", evaluation.is_stable)
    print("is-acceptable", evaluation.is_acceptable)


if __name__ == "__main__":
    main()
