"""Inspect the fast-charge battery optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp
from design_research_problems import MissingOptionalDependencyError

COMMON_KEYS = (
    "charge_time_min",
    "max_plating_mol_m3",
    "max_temperature_c",
    "energy_density_wh_per_l",
    "success",
)


def main() -> None:
    problem = derp.get_problem("battery_fast_charge_cell_opt")
    initial = problem.generate_initial_solution()
    try:
        components = problem.objective_components(initial)
        result = problem.solve(maxiter=0)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print(problem.metadata.problem_id)
    print("metric-keys", ",".join(sorted(components)))
    print("initial", " ".join(f"{key}={components[key]:.6g}" for key in COMMON_KEYS))
    print("solve", result.message)


if __name__ == "__main__":
    main()
