"""Inspect the compact unrestricted wind-farm layout optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print one decoded continuous layout and the baseline solver result."""
    problem = derp.get_problem("wind_farm_unrestricted_deficit_min")
    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)

    print("Unrestricted wind-farm layout benchmark")
    print("turbine_count", problem.turbine_count)
    print("initial_weighted_wake_deficit_mps", round(initial_state.weighted_wake_deficit_mps, 6))
    print("initial_minimum_l1_spacing_m", round(initial_state.minimum_l1_spacing_m, 4))
    print("solved_weighted_wake_deficit_mps", round(solved_state.weighted_wake_deficit_mps, 6))
    print("solved_directional_overlap_counts", solved_state.directional_overlap_counts)
    print("solved_coordinates_m", solved_state.coordinates_m)
    print("success", result.success)
    print("message", result.message)


if __name__ == "__main__":
    main()
