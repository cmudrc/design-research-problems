"""Inspect the packaged IDE-style treadle pump optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print a seeded start and the solved design."""
    problem = derp.get_problem("treadle_pump_ide_material_min")
    initial = problem.generate_initial_solution(seed=1)
    initial_components = problem.objective_components(initial)
    initial_violation = problem.max_constraint_violation(initial)
    result = problem.solve()
    solved_components = problem.objective_components(result.x)
    solved_violation = problem.max_constraint_violation(result.x)

    print("IDE-style treadle pump packaged benchmark")
    print(problem.metadata.title)
    print(
        "initial",
        f"flow_lps={initial_components['flow_rate_lps']:.3f}",
        f"lift_m={initial_components['lift_height_m']:.3f}",
        f"material_m3={initial_components['material_volume_m3']:.6f}",
        f"violation={initial_violation:.3g}",
    )
    print("solve", result.message)
    print(
        "solved",
        f"flow_lps={solved_components['flow_rate_lps']:.3f}",
        f"lift_m={solved_components['lift_height_m']:.3f}",
        f"material_m3={solved_components['material_volume_m3']:.6f}",
        f"violation={solved_violation:.3g}",
    )


if __name__ == "__main__":
    main()
