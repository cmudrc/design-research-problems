from __future__ import annotations

from design_research_problems.problems._domains.wind_farm import (
    count_spacing_violations,
    create_wind_farm_layout_backend,
    evaluate_layout_selection,
)


def test_wind_farm_backend_builds_expected_compact_grid_bundle() -> None:
    backend = create_wind_farm_layout_backend(
        grid_rows=4,
        grid_cols=4,
        edge_length_m=960.0,
        minimum_spacing_m=450.0,
        rotor_diameter_m=80.0,
        wake_expansion_coefficient=0.075,
        pairwise_loss_scale_mw=0.42,
        direction_profile_name="east_skewed_seed",
    )

    assert len(backend.coordinates_m) == 16
    assert len(backend.conflicting_pairs) == 24
    assert backend.pairwise_loss_matrix_mw.shape == (16, 16)
    assert backend.direction_profile_name == "east_skewed_seed"


def test_wind_farm_backend_evaluates_layouts_and_detects_spacing_conflicts() -> None:
    backend = create_wind_farm_layout_backend(
        grid_rows=4,
        grid_cols=4,
        edge_length_m=960.0,
        minimum_spacing_m=450.0,
        rotor_diameter_m=80.0,
        wake_expansion_coefficient=0.075,
        pairwise_loss_scale_mw=0.42,
        direction_profile_name="east_skewed_seed",
    )

    solved_state = evaluate_layout_selection(
        (1, 7, 8, 14),
        coordinates_m=backend.coordinates_m,
        pairwise_loss_matrix_mw=backend.pairwise_loss_matrix_mw,
        base_power_mw=1.5,
    )
    conflicting_count = count_spacing_violations((0, 1), backend.conflicting_pairs)

    assert solved_state.selected_indices == (1, 7, 8, 14)
    assert solved_state.expected_power_mw == 6.0
    assert solved_state.total_wake_loss_mw == 0.0
    assert conflicting_count == 1
