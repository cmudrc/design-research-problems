"""Inspect the packaged laptop design decision problem."""

from __future__ import annotations

from heapq import nlargest

from design_research_problems import get_problem


def main() -> None:
    """Print a compact summary aligned with the empirical-choice decision demo."""
    problem = get_problem("decision_laptop_design_profit_maximization")
    top_three = nlargest(3, problem.iter_option_evaluations(), key=lambda evaluation: evaluation.objective_value)
    best = top_three[0]

    print(problem.metadata.problem_id)
    print("objective", problem.objective_specs[0].key)
    print("candidate-count", problem.option_count)
    print("best", round(best.objective_value, 6), dict(best.option.values))
    print(
        "top-three",
        [(round(entry.objective_value, 6), dict(entry.option.values)) for entry in top_three],
    )


if __name__ == "__main__":
    main()
