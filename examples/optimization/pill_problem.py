"""Inspect a feasible seeded start and solve the pill optimization problem."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print a seeded start vector and the SciPy SLSQP baseline solution."""
    problem = derp.get_problem("pill_capsule_min_area")
    initial = problem.generate_initial_solution(seed=7)
    print(initial.shape)
    result = problem.solve(seed=3)
    print(result.message)
    print(bool(result.success), round(float(result.fun), 8))


if __name__ == "__main__":
    main()
