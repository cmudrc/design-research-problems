"""Inspect one MSEval empirical material-selection decision problem."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Print a compact summary aligned with the laptop decision demo."""
    problem = get_problem("decision_mseval_safety_helmet_lightweight")
    top_three = problem.rank_choices()[:3]
    best = top_three[0]

    print(problem.metadata.problem_id)
    print("objective", problem.objective_specs[0].key)
    print("candidate-count", len(problem.choice_options))
    print("best", best.choice_label, round(best.objective_value, 6))
    print(
        "top-three",
        [(entry.choice_label, round(entry.objective_value, 6)) for entry in top_three],
    )


if __name__ == "__main__":
    main()
