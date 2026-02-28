"""List the packaged catalog and load each seed problem."""

from __future__ import annotations

from design_research_problems import get_problem, list_problems


def main() -> None:
    """Print the catalog IDs and the loaded class for each seed problem."""
    problem_ids = list_problems()
    print(problem_ids)
    for problem_id in problem_ids:
        problem = get_problem(problem_id)
        print(problem_id, type(problem).__name__)


if __name__ == "__main__":
    main()
