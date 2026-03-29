"""Shared finite-cylinder geometry helpers for battery-cell layout models."""

from __future__ import annotations

import math
from dataclasses import dataclass

_PARALLEL_ALIGNMENT_TOLERANCE = 1.0e-3
_DISTANCE_TOLERANCE_MM = 1.0e-9


@dataclass(frozen=True)
class FiniteCylinder:
    """Finite cylinder represented by a center point and unit axis."""

    center_mm: tuple[float, float, float]
    """Cylinder center in millimeters."""
    axis_unit_vector: tuple[float, float, float]
    """Normalized cylinder axis."""
    radius_mm: float
    """Cylinder radius."""
    half_length_mm: float
    """Half the cylinder length."""


@dataclass(frozen=True)
class CylinderDistanceSummary:
    """Derived clearance metrics between two finite cylinders."""

    clearance_true_mm: float
    """Minimum surface-to-surface clearance, negative when the solids overlap."""
    gap_radial_mm: float | None
    """Side-wall gap for nearly parallel cylinders, when defined."""
    gap_axial_mm: float | None
    """End-cap gap for nearly parallel cylinders, when defined."""
    closest_points: tuple[tuple[float, float, float], tuple[float, float, float]]
    """Approximate closest surface points on both cylinders."""
    classification: str
    """One of ``radial``, ``axial``, ``skew``, or ``overlap``."""


def axis_unit_vector_from_euler(
    angle_x_deg: float,
    angle_y_deg: float,
    angle_z_deg: float,
) -> tuple[float, float, float]:
    """Return the unit cylinder axis implied by XYZ Euler angles.

    Args:
        angle_x_deg: Rotation about the x-axis in degrees.
        angle_y_deg: Rotation about the y-axis in degrees.
        angle_z_deg: Rotation about the z-axis in degrees.

    Returns:
        Unit axis vector for the rotated cylinder centerline.
    """
    angle_x = math.radians(angle_x_deg)
    angle_y = math.radians(angle_y_deg)
    angle_z = math.radians(angle_z_deg)

    x_value = 0.0
    y_value = 0.0
    z_value = 1.0

    cos_x = math.cos(angle_x)
    sin_x = math.sin(angle_x)
    y_rot = (y_value * cos_x) - (z_value * sin_x)
    z_rot = (y_value * sin_x) + (z_value * cos_x)
    x_rot = x_value

    cos_y = math.cos(angle_y)
    sin_y = math.sin(angle_y)
    x_rot2 = (x_rot * cos_y) + (z_rot * sin_y)
    z_rot2 = (-x_rot * sin_y) + (z_rot * cos_y)
    y_rot2 = y_rot

    cos_z = math.cos(angle_z)
    sin_z = math.sin(angle_z)
    x_rot3 = (x_rot2 * cos_z) - (y_rot2 * sin_z)
    y_rot3 = (x_rot2 * sin_z) + (y_rot2 * cos_z)
    z_rot3 = z_rot2

    norm = math.sqrt((x_rot3 * x_rot3) + (y_rot3 * y_rot3) + (z_rot3 * z_rot3))
    if norm <= _DISTANCE_TOLERANCE_MM:
        return (0.0, 0.0, 1.0)
    return (x_rot3 / norm, y_rot3 / norm, z_rot3 / norm)


def min_distance_between_cylinders(
    first: FiniteCylinder,
    second: FiniteCylinder,
) -> CylinderDistanceSummary:
    """Return clearance metrics between two finite cylinders.

    The helper distinguishes axial and radial gaps for nearly parallel cylinders
    and falls back to a skew-line approximation for general orientations.

    Args:
        first: First finite cylinder.
        second: Second finite cylinder.

    Returns:
        Cylinder clearance summary.
    """
    first_axis = _normalize_vector(first.axis_unit_vector)
    second_axis = _normalize_vector(second.axis_unit_vector)
    axis_alignment = abs(_dot(first_axis, second_axis))
    if 1.0 - axis_alignment <= _PARALLEL_ALIGNMENT_TOLERANCE:
        return _parallel_cylinder_distance(first, second, first_axis, second_axis)
    return _skew_cylinder_distance(first, second, first_axis, second_axis)


def _parallel_cylinder_distance(
    first: FiniteCylinder,
    second: FiniteCylinder,
    first_axis: tuple[float, float, float],
    second_axis: tuple[float, float, float],
) -> CylinderDistanceSummary:
    """Return clearance metrics for nearly parallel cylinders."""
    center_delta = _sub(second.center_mm, first.center_mm)
    axial_offset_mm = abs(_dot(center_delta, first_axis))
    radial_delta = _sub(center_delta, _scale(first_axis, _dot(center_delta, first_axis)))
    radial_center_distance_mm = _norm(radial_delta)

    radial_overlap_mm = (first.radius_mm + second.radius_mm) - radial_center_distance_mm
    axial_overlap_mm = (first.half_length_mm + second.half_length_mm) - axial_offset_mm
    gap_radial_mm = max(0.0, -radial_overlap_mm)
    gap_axial_mm = max(0.0, -axial_overlap_mm)

    if radial_overlap_mm > 0.0 and axial_overlap_mm > 0.0:
        classification = "overlap"
        clearance_true_mm = -min(radial_overlap_mm, axial_overlap_mm)
    elif gap_axial_mm <= _DISTANCE_TOLERANCE_MM and gap_radial_mm > _DISTANCE_TOLERANCE_MM:
        classification = "radial"
        clearance_true_mm = gap_radial_mm
    elif gap_radial_mm <= _DISTANCE_TOLERANCE_MM and gap_axial_mm > _DISTANCE_TOLERANCE_MM:
        classification = "axial"
        clearance_true_mm = gap_axial_mm
    else:
        classification = "skew"
        clearance_true_mm = math.sqrt((gap_radial_mm**2) + (gap_axial_mm**2))

    closest_points = _parallel_closest_surface_points(
        first=first,
        second=second,
        first_axis=first_axis,
        second_axis=second_axis,
        radial_delta=radial_delta,
        classification=classification,
    )
    return CylinderDistanceSummary(
        clearance_true_mm=clearance_true_mm,
        gap_radial_mm=gap_radial_mm,
        gap_axial_mm=gap_axial_mm,
        closest_points=closest_points,
        classification=classification,
    )


def _parallel_closest_surface_points(
    *,
    first: FiniteCylinder,
    second: FiniteCylinder,
    first_axis: tuple[float, float, float],
    second_axis: tuple[float, float, float],
    radial_delta: tuple[float, float, float],
    classification: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return approximate closest surface points for nearly parallel cylinders."""
    radial_norm = _norm(radial_delta)
    radial_direction = (
        _any_perpendicular(first_axis)
        if radial_norm <= _DISTANCE_TOLERANCE_MM
        else _scale(
            radial_delta,
            1.0 / radial_norm,
        )
    )
    center_delta = _sub(second.center_mm, first.center_mm)
    second_center_projection = _dot(center_delta, first_axis)
    overlap_low = max(-first.half_length_mm, second_center_projection - second.half_length_mm)
    overlap_high = min(first.half_length_mm, second_center_projection + second.half_length_mm)
    if overlap_low <= overlap_high:
        first_axis_offset = 0.5 * (overlap_low + overlap_high)
    else:
        first_axis_offset = min(first.half_length_mm, max(-first.half_length_mm, second_center_projection))
    second_axis_offset = min(
        second.half_length_mm,
        max(-second.half_length_mm, first_axis_offset - second_center_projection),
    )
    first_axis_point = _add(first.center_mm, _scale(first_axis, first_axis_offset))
    second_axis_point = _add(second.center_mm, _scale(second_axis, second_axis_offset))
    if classification == "axial":
        return (first_axis_point, second_axis_point)
    return (
        _add(first_axis_point, _scale(radial_direction, first.radius_mm)),
        _sub(second_axis_point, _scale(radial_direction, second.radius_mm)),
    )


def _skew_cylinder_distance(
    first: FiniteCylinder,
    second: FiniteCylinder,
    first_axis: tuple[float, float, float],
    second_axis: tuple[float, float, float],
) -> CylinderDistanceSummary:
    """Return clearance metrics for non-parallel cylinders."""
    first_start = _sub(first.center_mm, _scale(first_axis, first.half_length_mm))
    first_end = _add(first.center_mm, _scale(first_axis, first.half_length_mm))
    second_start = _sub(second.center_mm, _scale(second_axis, second.half_length_mm))
    second_end = _add(second.center_mm, _scale(second_axis, second.half_length_mm))
    first_axis_point, second_axis_point = _segment_closest_points(
        first_start,
        first_end,
        second_start,
        second_end,
    )
    axis_distance_mm = _norm(_sub(second_axis_point, first_axis_point))
    surface_clearance_mm = axis_distance_mm - (first.radius_mm + second.radius_mm)
    direction = (
        _any_perpendicular(first_axis)
        if axis_distance_mm <= _DISTANCE_TOLERANCE_MM
        else _scale(_sub(second_axis_point, first_axis_point), 1.0 / axis_distance_mm)
    )
    classification = "skew" if surface_clearance_mm >= 0.0 else "overlap"
    return CylinderDistanceSummary(
        clearance_true_mm=surface_clearance_mm,
        gap_radial_mm=None,
        gap_axial_mm=None,
        closest_points=(
            _add(first_axis_point, _scale(direction, first.radius_mm)),
            _sub(second_axis_point, _scale(direction, second.radius_mm)),
        ),
        classification=classification,
    )


def _segment_closest_points(
    point_a0: tuple[float, float, float],
    point_a1: tuple[float, float, float],
    point_b0: tuple[float, float, float],
    point_b1: tuple[float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return the closest points between two finite 3D line segments."""
    u_vector = _sub(point_a1, point_a0)
    v_vector = _sub(point_b1, point_b0)
    w_vector = _sub(point_a0, point_b0)
    a_value = _dot(u_vector, u_vector)
    b_value = _dot(u_vector, v_vector)
    c_value = _dot(v_vector, v_vector)
    d_value = _dot(u_vector, w_vector)
    e_value = _dot(v_vector, w_vector)
    denominator = (a_value * c_value) - (b_value * b_value)

    s_numerator = denominator
    s_denominator = denominator
    t_numerator = denominator
    t_denominator = denominator

    if denominator <= _DISTANCE_TOLERANCE_MM:
        s_numerator = 0.0
        s_denominator = 1.0
        t_numerator = e_value
        t_denominator = c_value
    else:
        s_numerator = (b_value * e_value) - (c_value * d_value)
        t_numerator = (a_value * e_value) - (b_value * d_value)
        if s_numerator < 0.0:
            s_numerator = 0.0
            t_numerator = e_value
            t_denominator = c_value
        elif s_numerator > s_denominator:
            s_numerator = s_denominator
            t_numerator = e_value + b_value
            t_denominator = c_value

    if t_numerator < 0.0:
        t_numerator = 0.0
        if (-d_value) < 0.0:
            s_numerator = 0.0
        elif (-d_value) > a_value:
            s_numerator = s_denominator
        else:
            s_numerator = -d_value
            s_denominator = a_value
    elif t_numerator > t_denominator:
        t_numerator = t_denominator
        if (-d_value + b_value) < 0.0:
            s_numerator = 0.0
        elif (-d_value + b_value) > a_value:
            s_numerator = s_denominator
        else:
            s_numerator = -d_value + b_value
            s_denominator = a_value

    s_coordinate = 0.0 if abs(s_numerator) <= _DISTANCE_TOLERANCE_MM else s_numerator / s_denominator
    t_coordinate = 0.0 if abs(t_numerator) <= _DISTANCE_TOLERANCE_MM else t_numerator / t_denominator
    return (
        _add(point_a0, _scale(u_vector, s_coordinate)),
        _add(point_b0, _scale(v_vector, t_coordinate)),
    )


def _any_perpendicular(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    """Return one deterministic unit vector perpendicular to ``vector``."""
    x_value, y_value, z_value = vector
    perpendicular = (0.0, -z_value, y_value) if abs(x_value) < abs(y_value) else (-z_value, 0.0, x_value)
    return _normalize_vector(perpendicular)


def _normalize_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    """Return a normalized vector."""
    norm = _norm(vector)
    if norm <= _DISTANCE_TOLERANCE_MM:
        return (0.0, 0.0, 1.0)
    return (vector[0] / norm, vector[1] / norm, vector[2] / norm)


def _dot(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> float:
    """Return the 3D dot product."""
    return (first[0] * second[0]) + (first[1] * second[1]) + (first[2] * second[2])


def _norm(vector: tuple[float, float, float]) -> float:
    """Return the Euclidean norm."""
    return math.sqrt(_dot(vector, vector))


def _add(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Return vector addition."""
    return (first[0] + second[0], first[1] + second[1], first[2] + second[2])


def _sub(
    first: tuple[float, float, float],
    second: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Return vector subtraction."""
    return (first[0] - second[0], first[1] - second[1], first[2] - second[2])


def _scale(
    vector: tuple[float, float, float],
    scalar: float,
) -> tuple[float, float, float]:
    """Return scalar multiplication."""
    return (vector[0] * scalar, vector[1] * scalar, vector[2] * scalar)


__all__ = [
    "CylinderDistanceSummary",
    "FiniteCylinder",
    "axis_unit_vector_from_euler",
    "min_distance_between_cylinders",
]
