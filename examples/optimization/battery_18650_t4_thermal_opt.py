"""Inspect tier-4 battery optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp

COMMON_KEYS = (
    "cell_count",
    "connection_count",
    "cost_usd",
    "design_volume_mm3",
    "max_temperature_c",
    "voltage_v",
    "capacity_ah",
    "current_limit_a",
    "min_clearance_mm",
)


def main() -> None:
    problem = derp.get_problem("battery_18650_t4_thermal_opt")
    initial = problem.generate_initial_solution(seed=4)
    components = problem.objective_components(initial)
    result = problem.solve(maxiter=10)
    solved = problem.objective_components(result.x)
    print(problem.metadata.problem_id)
    print("metric-keys", ",".join(sorted(components)))
    print("initial", " ".join(f"{key}={components[key]:.3f}" for key in COMMON_KEYS))
    print("solve", result.message)
    print("solved", " ".join(f"{key}={solved[key]:.3f}" for key in COMMON_KEYS))


if __name__ == "__main__":
    main()
