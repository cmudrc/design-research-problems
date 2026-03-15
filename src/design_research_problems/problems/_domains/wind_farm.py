"""Shared backend helpers for compact wind-farm layout problems."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy
from numpy.typing import NDArray

DirectionProfile = tuple[tuple[float, float], ...]
"""Deterministic `(direction_deg, probability)` profile."""

ContinuousWindProfile = tuple[tuple[float, float, float], ...]
"""Deterministic `(direction_deg, probability, wind_speed_mps)` profile."""

DEFAULT_WIND_DIRECTION_PROFILES: Final[dict[str, DirectionProfile]] = {
    "east_skewed_seed": (
        (0.0, 0.05),
        (45.0, 0.08),
        (90.0, 0.34),
        (135.0, 0.18),
        (180.0, 0.05),
        (225.0, 0.08),
        (270.0, 0.14),
        (315.0, 0.08),
    ),
    "uniform_seed": tuple((45.0 * index, 0.125) for index in range(8)),
}
"""In-package directional profiles for compact wind-farm seeds."""

DEFAULT_CONTINUOUS_WIND_PROFILES: Final[dict[str, ContinuousWindProfile]] = {
    "quan_kim_2015_reduced": (
        (30.0, 0.20, 7.0),
        (90.0, 0.16, 5.0),
        (150.0, 0.16, 5.0),
    ),
}
"""Continuous-layout directional profiles with explicit average wind speeds."""


@dataclass(frozen=True)
class WindFarmLayoutState:
    """Decoded compact wind-farm layout state."""

    selected_indices: tuple[int, ...]
    """Indices of the selected grid nodes."""
    selected_coordinates_m: tuple[tuple[float, float], ...]
    """Selected `(x, y)` coordinates in meters."""
    expected_power_mw: float
    """Expected total farm power under the compact linear-loss proxy."""
    total_wake_loss_mw: float
    """Total pairwise wake-loss estimate in megawatts."""


@dataclass(frozen=True)
class WindFarmLayoutBackend:
    """Precomputed wind-farm layout backend state shared by wrappers."""

    coordinates_m: tuple[tuple[float, float], ...]
    """Grid-node coordinates in deterministic order."""
    conflicting_pairs: tuple[tuple[int, int], ...]
    """Pairs of node indices that violate minimum spacing if both selected."""
    pairwise_loss_matrix_mw: NDArray[numpy.float64]
    """Symmetric pairwise wake-loss matrix in megawatts."""
    direction_profile_name: str
    """Stable directional-profile label."""
    direction_profile: DirectionProfile
    """Directional profile values used by the wake proxy."""


@dataclass(frozen=True)
class UnrestrictedWindFarmLayoutState:
    """Decoded state for a continuous-position wind-farm layout."""

    coordinates_m: tuple[tuple[float, float], ...]
    """Ordered turbine coordinates in meters."""
    weighted_wake_deficit_mps: float
    """Probability-weighted worst directional wind-speed deficit."""
    directional_wake_deficits_mps: tuple[float, ...]
    """Worst wake deficit for each tracked wind direction."""
    directional_overlap_counts: tuple[int, ...]
    """Number of ordered overlapping wake pairs in each direction."""
    minimum_l1_spacing_m: float
    """Smallest pairwise Manhattan spacing among all turbines."""


def get_direction_profile(direction_profile_name: str) -> DirectionProfile:
    """Return one named in-package wind-direction profile.

    Args:
        direction_profile_name: Stable profile name.

    Returns:
        Directional profile tuple.

    Raises:
        ValueError: If the profile name is unknown.
    """
    profile = DEFAULT_WIND_DIRECTION_PROFILES.get(direction_profile_name)
    if profile is None:
        raise ValueError(f"direction_profile_name must be one of {sorted(DEFAULT_WIND_DIRECTION_PROFILES)}.")
    return profile


def get_continuous_wind_profile(direction_profile_name: str) -> ContinuousWindProfile:
    """Return one named continuous-layout directional profile.

    Args:
        direction_profile_name: Stable profile name.

    Returns:
        Directional profile tuple with average wind speeds.

    Raises:
        ValueError: If the profile name is unknown.
    """
    profile = DEFAULT_CONTINUOUS_WIND_PROFILES.get(direction_profile_name)
    if profile is None:
        raise ValueError(f"direction_profile_name must be one of {sorted(DEFAULT_CONTINUOUS_WIND_PROFILES)}.")
    return profile


def build_grid_coordinates(grid_rows: int, grid_cols: int, edge_length_m: float) -> tuple[tuple[float, float], ...]:
    """Return a deterministic rectangular grid of candidate turbine coordinates.

    Args:
        grid_rows: Number of grid rows.
        grid_cols: Number of grid columns.
        edge_length_m: Side length of the square farm boundary.

    Returns:
        Grid coordinates in row-major order.

    Raises:
        ValueError: If any geometric parameter is invalid.
    """
    if grid_rows <= 0 or grid_cols <= 0:
        raise ValueError("grid_rows and grid_cols must be positive.")
    if edge_length_m <= 0.0:
        raise ValueError("edge_length_m must be positive.")

    x_spacing = edge_length_m / max(1, grid_cols - 1)
    y_spacing = edge_length_m / max(1, grid_rows - 1)
    coordinates: list[tuple[float, float]] = []
    for row_index in range(grid_rows):
        for col_index in range(grid_cols):
            coordinates.append((col_index * x_spacing, row_index * y_spacing))
    return tuple(coordinates)


def flatten_coordinates(coordinates_m: tuple[tuple[float, float], ...]) -> NDArray[numpy.float64]:
    """Flatten one ordered coordinate tuple into a solver vector."""
    flattened: list[float] = []
    for x_coord, y_coord in coordinates_m:
        flattened.extend((x_coord, y_coord))
    return numpy.array(flattened, dtype=float)


def decode_coordinate_vector(
    variables: NDArray[numpy.float64],
    *,
    turbine_count: int,
) -> tuple[tuple[float, float], ...]:
    """Decode one flat coordinate vector into ordered `(x, y)` pairs."""
    candidate = numpy.array(variables, dtype=float, copy=False)
    expected_shape = (2 * turbine_count,)
    if candidate.shape != expected_shape:
        raise ValueError(f"variables must match the flattened wind layout shape {expected_shape}.")
    return tuple((float(candidate[2 * index]), float(candidate[(2 * index) + 1])) for index in range(turbine_count))


def build_conflicting_pairs(
    coordinates_m: tuple[tuple[float, float], ...],
    minimum_spacing_m: float,
) -> tuple[tuple[int, int], ...]:
    """Return all node pairs that violate the minimum-spacing threshold.

    Args:
        coordinates_m: Candidate grid coordinates.
        minimum_spacing_m: Hard spacing threshold.

    Returns:
        Sorted conflicting index pairs.

    Raises:
        ValueError: If ``minimum_spacing_m`` is invalid.
    """
    if minimum_spacing_m <= 0.0:
        raise ValueError("minimum_spacing_m must be positive.")

    pairs: list[tuple[int, int]] = []
    for index_i, point_i in enumerate(coordinates_m[:-1]):
        for index_j, point_j in enumerate(coordinates_m[index_i + 1 :], start=index_i + 1):
            if distance(point_i, point_j) + 1e-9 < minimum_spacing_m:
                pairs.append((index_i, index_j))
    return tuple(pairs)


def count_l1_spacing_violations(
    coordinates_m: tuple[tuple[float, float], ...],
    *,
    minimum_spacing_m: float,
) -> int:
    """Count how many turbine pairs violate a Manhattan-spacing threshold."""
    if minimum_spacing_m <= 0.0:
        raise ValueError("minimum_spacing_m must be positive.")
    count = 0
    for index_i, point_i in enumerate(coordinates_m[:-1]):
        for point_j in coordinates_m[index_i + 1 :]:
            if l1_distance(point_i, point_j) + 1e-9 < minimum_spacing_m:
                count += 1
    return count


def minimum_l1_spacing(coordinates_m: tuple[tuple[float, float], ...]) -> float:
    """Return the smallest pairwise Manhattan spacing for one layout."""
    if len(coordinates_m) < 2:
        return math.inf
    minimum = math.inf
    for index_i, point_i in enumerate(coordinates_m[:-1]):
        for point_j in coordinates_m[index_i + 1 :]:
            minimum = min(minimum, l1_distance(point_i, point_j))
    return minimum


def build_pairwise_loss_matrix(
    coordinates_m: tuple[tuple[float, float], ...],
    *,
    direction_profile: DirectionProfile,
    rotor_diameter_m: float,
    wake_expansion_coefficient: float,
    pairwise_loss_scale_mw: float,
) -> NDArray[numpy.float64]:
    """Return a symmetric pairwise wake-loss matrix for the candidate grid.

    Args:
        coordinates_m: Candidate grid coordinates.
        direction_profile: Directional wake profile.
        rotor_diameter_m: Rotor diameter used by the wake proxy.
        wake_expansion_coefficient: Linear wake-cone expansion rate.
        pairwise_loss_scale_mw: Peak pairwise wake-loss scale.

    Returns:
        Symmetric wake-loss matrix in megawatts.

    Raises:
        ValueError: If any wake parameter is invalid.
    """
    if rotor_diameter_m <= 0.0:
        raise ValueError("rotor_diameter_m must be positive.")
    if wake_expansion_coefficient < 0.0:
        raise ValueError("wake_expansion_coefficient must be nonnegative.")
    if pairwise_loss_scale_mw <= 0.0:
        raise ValueError("pairwise_loss_scale_mw must be positive.")

    matrix = numpy.zeros((len(coordinates_m), len(coordinates_m)), dtype=float)
    for index_i, point_i in enumerate(coordinates_m[:-1]):
        for index_j, point_j in enumerate(coordinates_m[index_i + 1 :], start=index_i + 1):
            loss = directed_wake_loss(
                point_i,
                point_j,
                direction_profile=direction_profile,
                rotor_diameter_m=rotor_diameter_m,
                wake_expansion_coefficient=wake_expansion_coefficient,
                pairwise_loss_scale_mw=pairwise_loss_scale_mw,
            ) + directed_wake_loss(
                point_j,
                point_i,
                direction_profile=direction_profile,
                rotor_diameter_m=rotor_diameter_m,
                wake_expansion_coefficient=wake_expansion_coefficient,
                pairwise_loss_scale_mw=pairwise_loss_scale_mw,
            )
            matrix[index_i, index_j] = loss
            matrix[index_j, index_i] = loss
    return matrix


def wake_speed_deficit_mps(
    downwind_distance_m: float,
    *,
    rotor_diameter_m: float,
    thrust_coefficient: float,
    wake_expansion_coefficient: float,
    wind_speed_mps: float,
) -> float:
    """Return the Jensen-style wind-speed deficit used by the 2015 MILP paper."""
    if downwind_distance_m <= 0.0:
        return 0.0
    if rotor_diameter_m <= 0.0:
        raise ValueError("rotor_diameter_m must be positive.")
    if not 0.0 <= thrust_coefficient <= 1.0:
        raise ValueError("thrust_coefficient must lie in [0, 1].")
    if wake_expansion_coefficient < 0.0:
        raise ValueError("wake_expansion_coefficient must be nonnegative.")
    if wind_speed_mps <= 0.0:
        raise ValueError("wind_speed_mps must be positive.")

    expanded_diameter = rotor_diameter_m + (2.0 * wake_expansion_coefficient * downwind_distance_m)
    retained_speed_fraction = max(0.0, 1.0 - (thrust_coefficient * rotor_diameter_m**2 / expanded_diameter**2))
    return float(wind_speed_mps * (1.0 - math.sqrt(retained_speed_fraction)))


def directed_wake_deficit_mps(
    point_i: tuple[float, float],
    point_j: tuple[float, float],
    *,
    direction_deg: float,
    wind_speed_mps: float,
    rotor_diameter_m: float,
    thrust_coefficient: float,
    wake_expansion_coefficient: float,
    wake_membership_alpha: float,
) -> float:
    """Return the directional wake deficit from one turbine to another."""
    if not 0.0 <= wake_membership_alpha <= 1.0:
        raise ValueError("wake_membership_alpha must lie in [0, 1].")

    delta_x = point_j[0] - point_i[0]
    delta_y = point_j[1] - point_i[1]
    direction_x, direction_y = direction_vector(direction_deg)
    downwind_distance = (delta_x * direction_x) + (delta_y * direction_y)
    if downwind_distance <= 0.0:
        return 0.0

    lateral_distance = abs((-direction_y * delta_x) + (direction_x * delta_y))
    wake_half_width = (wake_expansion_coefficient * downwind_distance) + (
        (1.0 - wake_membership_alpha) * 0.5 * rotor_diameter_m
    )
    if lateral_distance > wake_half_width + 1e-9:
        return 0.0
    return wake_speed_deficit_mps(
        downwind_distance,
        rotor_diameter_m=rotor_diameter_m,
        thrust_coefficient=thrust_coefficient,
        wake_expansion_coefficient=wake_expansion_coefficient,
        wind_speed_mps=wind_speed_mps,
    )


def create_wind_farm_layout_backend(
    *,
    grid_rows: int,
    grid_cols: int,
    edge_length_m: float,
    minimum_spacing_m: float,
    rotor_diameter_m: float,
    wake_expansion_coefficient: float,
    pairwise_loss_scale_mw: float,
    direction_profile_name: str,
) -> WindFarmLayoutBackend:
    """Build the reusable backend bundle for one compact wind-farm instance.

    Args:
        grid_rows: Number of grid rows.
        grid_cols: Number of grid columns.
        edge_length_m: Side length of the square farm boundary.
        minimum_spacing_m: Hard spacing threshold.
        rotor_diameter_m: Rotor diameter used by the wake proxy.
        wake_expansion_coefficient: Linear wake-cone expansion rate.
        pairwise_loss_scale_mw: Peak pairwise wake-loss scale.
        direction_profile_name: Stable profile name.

    Returns:
        Shared backend bundle with geometry and wake precomputes.
    """
    coordinates_m = build_grid_coordinates(grid_rows, grid_cols, edge_length_m)
    direction_profile = get_direction_profile(direction_profile_name)
    return WindFarmLayoutBackend(
        coordinates_m=coordinates_m,
        conflicting_pairs=build_conflicting_pairs(coordinates_m, minimum_spacing_m),
        pairwise_loss_matrix_mw=build_pairwise_loss_matrix(
            coordinates_m,
            direction_profile=direction_profile,
            rotor_diameter_m=rotor_diameter_m,
            wake_expansion_coefficient=wake_expansion_coefficient,
            pairwise_loss_scale_mw=pairwise_loss_scale_mw,
        ),
        direction_profile_name=direction_profile_name,
        direction_profile=direction_profile,
    )


def evaluate_unrestricted_layout(
    coordinates_m: tuple[tuple[float, float], ...],
    *,
    direction_profile: ContinuousWindProfile,
    rotor_diameter_m: float,
    thrust_coefficient: float,
    wake_expansion_coefficient: float,
    wake_membership_alpha: float,
) -> UnrestrictedWindFarmLayoutState:
    """Evaluate one continuous wind-farm layout under the compact 2015 proxy."""
    directional_penalties: list[float] = []
    overlap_counts: list[int] = []
    weighted_penalty = 0.0
    for direction_deg, probability, wind_speed_mps in direction_profile:
        worst_deficit = 0.0
        overlap_count = 0
        for index_i, point_i in enumerate(coordinates_m):
            for index_j, point_j in enumerate(coordinates_m):
                if index_i == index_j:
                    continue
                deficit = directed_wake_deficit_mps(
                    point_i,
                    point_j,
                    direction_deg=direction_deg,
                    wind_speed_mps=wind_speed_mps,
                    rotor_diameter_m=rotor_diameter_m,
                    thrust_coefficient=thrust_coefficient,
                    wake_expansion_coefficient=wake_expansion_coefficient,
                    wake_membership_alpha=wake_membership_alpha,
                )
                if deficit <= 0.0:
                    continue
                overlap_count += 1
                worst_deficit = max(worst_deficit, deficit)
        directional_penalties.append(worst_deficit)
        overlap_counts.append(overlap_count)
        weighted_penalty += probability * worst_deficit

    return UnrestrictedWindFarmLayoutState(
        coordinates_m=coordinates_m,
        weighted_wake_deficit_mps=weighted_penalty,
        directional_wake_deficits_mps=tuple(directional_penalties),
        directional_overlap_counts=tuple(overlap_counts),
        minimum_l1_spacing_m=minimum_l1_spacing(coordinates_m),
    )


def evaluate_layout_selection(
    selected_indices: tuple[int, ...],
    *,
    coordinates_m: tuple[tuple[float, float], ...],
    pairwise_loss_matrix_mw: NDArray[numpy.float64],
    base_power_mw: float,
) -> WindFarmLayoutState:
    """Evaluate one selected turbine subset under the compact wake proxy.

    Args:
        selected_indices: Chosen grid-node indices.
        coordinates_m: Candidate grid coordinates.
        pairwise_loss_matrix_mw: Symmetric wake-loss matrix.
        base_power_mw: Stand-alone turbine power estimate.

    Returns:
        Decoded layout state with compact power metrics.
    """
    total_wake_loss = 0.0
    for offset, index_i in enumerate(selected_indices):
        for index_j in selected_indices[offset + 1 :]:
            total_wake_loss += float(pairwise_loss_matrix_mw[index_i, index_j])
    return WindFarmLayoutState(
        selected_indices=selected_indices,
        selected_coordinates_m=tuple(coordinates_m[index] for index in selected_indices),
        expected_power_mw=(base_power_mw * len(selected_indices)) - total_wake_loss,
        total_wake_loss_mw=total_wake_loss,
    )


def count_spacing_violations(
    selected_indices: tuple[int, ...],
    conflicting_pairs: tuple[tuple[int, int], ...],
) -> int:
    """Count how many conflicting node pairs are simultaneously selected.

    Args:
        selected_indices: Selected grid-node indices.
        conflicting_pairs: Pairs that violate the spacing rule.

    Returns:
        Number of spacing-rule violations.
    """
    selected_set = set(selected_indices)
    return sum(1 for index_i, index_j in conflicting_pairs if index_i in selected_set and index_j in selected_set)


def directed_wake_loss(
    point_i: tuple[float, float],
    point_j: tuple[float, float],
    *,
    direction_profile: DirectionProfile,
    rotor_diameter_m: float,
    wake_expansion_coefficient: float,
    pairwise_loss_scale_mw: float,
) -> float:
    """Return the directional wake loss from one upstream candidate to another.

    Args:
        point_i: Upstream point.
        point_j: Downstream candidate point.
        direction_profile: Directional wake profile.
        rotor_diameter_m: Rotor diameter used by the wake proxy.
        wake_expansion_coefficient: Linear wake-cone expansion rate.
        pairwise_loss_scale_mw: Peak pairwise wake-loss scale.

    Returns:
        Direction-weighted wake loss in megawatts.
    """
    delta_x = point_j[0] - point_i[0]
    delta_y = point_j[1] - point_i[1]
    total_loss = 0.0
    for direction_deg, probability in direction_profile:
        direction_x, direction_y = direction_vector(direction_deg)
        downwind_distance = (delta_x * direction_x) + (delta_y * direction_y)
        if downwind_distance <= 0.0:
            continue
        lateral_distance = abs((-direction_y * delta_x) + (direction_x * delta_y))
        wake_radius = (0.5 * rotor_diameter_m) + (wake_expansion_coefficient * downwind_distance)
        if wake_radius <= 0.0 or lateral_distance >= wake_radius:
            continue
        lateral_factor = max(0.0, 1.0 - (lateral_distance / wake_radius))
        downwind_factor = rotor_diameter_m / (rotor_diameter_m + downwind_distance)
        total_loss += probability * pairwise_loss_scale_mw * lateral_factor * downwind_factor
    return total_loss


def direction_vector(direction_deg: float) -> tuple[float, float]:
    """Return the `(x, y)` unit vector for one wind direction in degrees."""
    radians = math.radians(direction_deg)
    return (math.sin(radians), math.cos(radians))


def distance(point_i: tuple[float, float], point_j: tuple[float, float]) -> float:
    """Return Euclidean distance between two planar points."""
    return math.hypot(point_j[0] - point_i[0], point_j[1] - point_i[1])


def l1_distance(point_i: tuple[float, float], point_j: tuple[float, float]) -> float:
    """Return Manhattan distance between two planar points."""
    return abs(point_j[0] - point_i[0]) + abs(point_j[1] - point_i[1])


__all__ = [
    "DEFAULT_CONTINUOUS_WIND_PROFILES",
    "DEFAULT_WIND_DIRECTION_PROFILES",
    "ContinuousWindProfile",
    "DirectionProfile",
    "UnrestrictedWindFarmLayoutState",
    "WindFarmLayoutBackend",
    "WindFarmLayoutState",
    "build_conflicting_pairs",
    "build_grid_coordinates",
    "build_pairwise_loss_matrix",
    "count_l1_spacing_violations",
    "count_spacing_violations",
    "create_wind_farm_layout_backend",
    "decode_coordinate_vector",
    "directed_wake_deficit_mps",
    "directed_wake_loss",
    "direction_vector",
    "distance",
    "evaluate_layout_selection",
    "evaluate_unrestricted_layout",
    "flatten_coordinates",
    "get_continuous_wind_profile",
    "get_direction_profile",
    "l1_distance",
    "minimum_l1_spacing",
    "wake_speed_deficit_mps",
]
