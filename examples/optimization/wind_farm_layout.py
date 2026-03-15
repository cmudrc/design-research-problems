"""Inspect the compact grid-based wind-farm layout optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    """Print one decoded layout and the baseline solver result."""
    problem = derp.get_problem("wind_farm_grid_qkp_power_max")
    initial = problem.generate_initial_solution()
    initial_state = problem.decode_candidate(initial)
    result = problem.solve()
    solved_state = problem.decode_candidate(result.x)

    print("Compact wind-farm layout benchmark")
    print("initial_selected_indices", initial_state.selected_indices)
    print("initial_expected_power_mw", round(initial_state.expected_power_mw, 4))
    print("solved_selected_indices", solved_state.selected_indices)
    print("solved_coordinates_m", solved_state.selected_coordinates_m)
    print("solved_expected_power_mw", round(solved_state.expected_power_mw, 4))
    print("success", result.success)
    print("message", result.message)


if __name__ == "__main__":
    main()
