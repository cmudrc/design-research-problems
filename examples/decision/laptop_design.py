"""Inspect the packaged laptop design decision problem."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Print a compact summary aligned with the empirical-choice decision demo."""
    problem = get_problem("decision_laptop_design_profit_maximization")
    top_three = problem.rank_evaluations()[:3]
    best = problem.best_evaluation()

    print(problem.metadata.problem_id)
    print("objective", problem.objective_specs[0].key)
    print("candidate-kind", problem.candidate_kind)
    print("candidate-count", problem.candidate_count)
    print("best", round(best.objective_value, 6), best.candidate_label)
    print(
        "top-three",
        [(round(entry.objective_value, 6), entry.candidate_label) for entry in top_three],
    )


if __name__ == "__main__":
    main()
