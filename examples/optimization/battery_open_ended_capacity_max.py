"""Inspect the packaged open-ended battery capacity benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print a seeded start and a baseline solved explicit battery design."""
    problem = derp.get_problem("battery_pack_18650_open_ended_capacity_max")
    initial = problem.generate_initial_solution(seed=1)

    print("Open-ended battery packaged benchmark")
    print(problem.metadata.title)

    try:
        initial_components = problem.objective_components(initial)
        initial_violation = problem.max_constraint_violation(initial)
        result = problem.solve(maxiter=0)
        solved_components = problem.objective_components(result.x)
        solved_violation = problem.max_constraint_violation(result.x)
    except derp.MissingOptionalDependencyError as exc:
        print(exc)
        return

    print(
        "initial",
        f"cell_count={int(initial_components['cell_count'])}",
        f"connection_count={int(initial_components['connection_count'])}",
        f"delivered_capacity_ah={initial_components['delivered_capacity_ah']:.3f}",
        f"end_voltage_v={initial_components['end_voltage_v']:.3f}",
        f"design_volume_mm3={initial_components['design_volume_mm3']:.2f}",
        f"violation={initial_violation:.3g}",
    )
    print("solve", result.message)
    print(
        "solved",
        f"cell_count={int(solved_components['cell_count'])}",
        f"connection_count={int(solved_components['connection_count'])}",
        f"delivered_capacity_ah={solved_components['delivered_capacity_ah']:.3f}",
        f"end_voltage_v={solved_components['end_voltage_v']:.3f}",
        f"design_volume_mm3={solved_components['design_volume_mm3']:.2f}",
        f"violation={solved_violation:.3g}",
    )


if __name__ == "__main__":
    main()
