from __future__ import annotations

from design_research_problems.problems._domains.wind_farm import (
    count_l1_spacing_violations,
    count_spacing_violations,
    create_wind_farm_layout_backend,
    decode_coordinate_vector,
    evaluate_layout_selection,
    evaluate_unrestricted_layout,
    flatten_coordinates,
    get_continuous_wind_profile,
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


def test_wind_farm_backend_evaluates_unrestricted_layout_seed() -> None:
    coordinates = (
        (43.72020044238818, 429.52248857886207),
        (111.59766943249089, 82.1459871105066),
        (221.66540225338184, 639.9506879833697),
        (308.17161590785463, 299.0038449775436),
        (443.18279529537006, 1.7620158094729277),
        (620.0350859625122, 176.3059566304521),
        (628.0066860474154, 546.3217673710446),
    )
    state = evaluate_unrestricted_layout(
        coordinates,
        direction_profile=get_continuous_wind_profile("quan_kim_2015_reduced"),
        rotor_diameter_m=77.0,
        thrust_coefficient=0.8,
        wake_expansion_coefficient=0.075,
        wake_membership_alpha=1.0,
    )
    flattened = flatten_coordinates(coordinates)

    assert flattened.shape == (14,)
    assert decode_coordinate_vector(flattened, turbine_count=7) == coordinates
    assert state.weighted_wake_deficit_mps == 0.0
    assert state.directional_overlap_counts == (0, 0, 0)
    assert count_l1_spacing_violations(coordinates, minimum_spacing_m=350.0) == 0
