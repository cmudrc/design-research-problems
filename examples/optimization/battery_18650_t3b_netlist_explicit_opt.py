"""Inspect the T3B explicit-netlist battery optimization benchmark."""

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
    problem = derp.get_problem("battery_18650_t3b_netlist_explicit_opt")
    initial = problem.generate_initial_solution(seed=3)
    components = problem.objective_components(initial)
    provenance = problem.evaluation_provenance(initial)
    result = problem.solve(maxiter=5)
    print(problem.metadata.problem_id)
    print("evaluation-mode", provenance.evaluation_mode)
    print("metric-keys", ",".join(sorted(components)))
    print("initial", " ".join(f"{key}={components[key]:.3f}" for key in COMMON_KEYS))
    print("solve", result.message)


if __name__ == "__main__":
    main()
