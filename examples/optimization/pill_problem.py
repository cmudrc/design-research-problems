"""Sample and optionally solve the pill optimization problem."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem


def main() -> None:
    """Sample the pill problem and solve it when SciPy is available."""
    problem = get_problem("pill_capsule_min_area")
    x, y = problem.generate_data(n=5, seed=7)
    print(x.shape, y.shape)
    try:
        result = problem.solve(seed=3)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(bool(result.success), round(float(result.fun), 8))


if __name__ == "__main__":
    main()
