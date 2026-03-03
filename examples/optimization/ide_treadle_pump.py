"""Inspect the packaged IDE-style treadle pump optimization benchmark."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Print the packaged baseline design and the solved design."""
    problem = get_problem("treadle_pump_ide_material_min")
    initial = problem.generate_initial_solution()
    initial_components = problem.objective_components(initial)
    result = problem.solve()
    solved_components = problem.objective_components(result.x)

    print("IDE-style treadle pump packaged benchmark")
    print(problem.metadata.title)
    print(
        "initial",
        f"flow_lps={initial_components['flow_rate_lps']:.1f}",
        f"lift_m={initial_components['lift_height_m']:.1f}",
        f"material_m3={initial_components['material_volume_m3']:.4f}",
    )
    print("solve", result.message)
    print(
        "solved",
        f"flow_lps={solved_components['flow_rate_lps']:.1f}",
        f"lift_m={solved_components['lift_height_m']:.1f}",
        f"material_m3={solved_components['material_volume_m3']:.4f}",
    )


if __name__ == "__main__":
    main()
