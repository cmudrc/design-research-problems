"""Shared backend helpers for compact wind-farm layout problems."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import numpy
from numpy.typing import NDArray

DirectionProfile = tuple[tuple[float, float], ...]
"""Deterministic `(direction_deg, probability)` profile."""

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


__all__ = [
    "DEFAULT_WIND_DIRECTION_PROFILES",
    "DirectionProfile",
    "WindFarmLayoutBackend",
    "WindFarmLayoutState",
    "build_conflicting_pairs",
    "build_grid_coordinates",
    "build_pairwise_loss_matrix",
    "count_spacing_violations",
    "create_wind_farm_layout_backend",
    "directed_wake_loss",
    "direction_vector",
    "distance",
    "evaluate_layout_selection",
    "get_direction_profile",
]
