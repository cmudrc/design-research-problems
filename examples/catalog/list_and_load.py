"""List the packaged catalog, feature flags, and loaded classes."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print the catalog IDs, feature flags, and loaded class for each seed problem."""
    registry = derp.ProblemRegistry()
    problem_ids = derp.list_problems()
    print(problem_ids)
    print(registry.kind_feature_flags())
    for problem_id in problem_ids:
        problem = derp.get_problem(problem_id)
        print(problem_id, problem.metadata.feature_flags, type(problem).__name__)


if __name__ == "__main__":
    main()
