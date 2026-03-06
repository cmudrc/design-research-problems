"""Shared backend helpers for MATLAB Truss Analysis Program states and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy

type TrussLoadDirection = Literal["left", "down", "right", "up"]
"""Supported truss load direction labels."""


@dataclass(frozen=True)
class TrussAPJoint:
    """One joint in a planar Truss Analysis Program design."""

    joint_id: int
    """Stable joint identifier."""
    x: float
    """x coordinate in the design plane."""
    y: float
    """y coordinate in the design plane."""
    is_fixed: bool
    """Whether this joint is immutable under the grammar."""


@dataclass(frozen=True)
class TrussAPMember:
    """One undirected member between two joints."""

    member_id: int
    """Stable member identifier."""
    start_joint_id: int
    """First endpoint joint identifier."""
    end_joint_id: int
    """Second endpoint joint identifier."""
    size_index: int
    """Discrete member size index in ``[1, 10]``."""


@dataclass(frozen=True)
class TrussAPLoad:
    """One directional point load attached to a joint."""

    joint_id: int
    """Joint carrying the load."""
    direction: TrussLoadDirection
    """Load direction label."""
    magnitude_n: float
    """Load magnitude in Newtons."""


@dataclass(frozen=True)
class TrussAPState:
    """Serializable state for one truss design-session snapshot."""

    joints: tuple[TrussAPJoint, ...]
    """All joints in deterministic order."""
    members: tuple[TrussAPMember, ...]
    """All members in deterministic order."""
    loads: tuple[TrussAPLoad, ...]
    """All loads in deterministic order."""
    support_enabled: tuple[bool, bool, bool]
    """Enabled flags for support joints ``1``, ``2``, and ``3``."""
    required_support_joint_ids: tuple[int, int, int] = (1, 2, 3)
    """Support joints that must be connected for structural validity."""
    required_load_joint_ids: tuple[int, int] = (4, 5)
    """Load joints that must be connected for structural validity."""
    fos_target: float = 1.25
    """Minimum acceptable factor of safety."""
    load_magnitude_options_n: tuple[float, ...] = (50_000.0, 200_000.0, 250_000.0)
    """Discrete load magnitudes available in the original interface."""
    size_index_min: int = 1
    """Minimum member size index."""
    size_index_max: int = 10
    """Maximum member size index."""
    design_bounds: tuple[float, float, float, float] = (-6.0, 6.0, -4.0, 4.0)
    """Design-space bounds ``(x_min, x_max, y_min, y_max)``."""
    bad_zone_polygon: tuple[tuple[float, float], ...] = (
        (-1.0, 2.5),
        (-0.5, 2.5),
        (-0.5, -1.25),
        (-2.0, -1.25),
        (-2.0, -0.75),
        (-1.0, -0.75),
    )
    """Polygon used by the study's change-response phase."""
    enforce_bad_zone: bool = False
    """Whether nodes/members intersecting ``bad_zone_polygon`` are invalid."""


@dataclass(frozen=True)
class TrussAPEvaluation:
    """Structured evaluation payload for one truss design."""

    mass_kg: float
    """Total structural mass in kilograms."""
    min_fos: float
    """Minimum factor of safety across members (``0`` when undefined)."""
    is_stable: bool
    """Whether the linear solve and topology checks succeeded."""
    is_acceptable: bool
    """Whether the design satisfies the target factor of safety."""
    joint_count: int
    """Total number of joints."""
    member_count: int
    """Total number of members."""
    force_by_member_n: tuple[float, ...]
    """Axial member-force results in member order."""
    fos_by_member: tuple[float, ...] = ()
    """Per-member factor-of-safety values in member order."""
    failure_reason: str | None = None
    """Optional reason when ``is_stable`` is ``False``."""

    @property
    def is_feasible(self) -> bool:
        """Return a feasibility flag for generic computable-problem tooling.

        Returns:
            ``True`` when the truss state is structurally stable.
        """
        return self.is_stable


_FY_PA = 344.0e6
_SIZE_FACTOR = 2.0
_STEEL_E_PA = 210.0e9

_OUTER_DIAMETER_M = numpy.asarray([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float) / 100.0
_WALL_THICKNESS_M = _OUTER_DIAMETER_M / 15.0
_SECTION_AREA_M2 = (
    numpy.pi * (_OUTER_DIAMETER_M / 2.0) ** 2 - numpy.pi * (_OUTER_DIAMETER_M / 2.0 - _WALL_THICKNESS_M) ** 2
)
_SECTION_INERTIA_M4 = numpy.pi * (_OUTER_DIAMETER_M**4 - (_OUTER_DIAMETER_M - 2.0 * _WALL_THICKNESS_M) ** 4) / 64.0
_LINEAR_MASS_KG_PER_M = _SECTION_AREA_M2 * 7870.0

_DIRECTION_TO_SLOT: dict[TrussLoadDirection, int] = {
    "left": 1,
    "down": 2,
    "right": 3,
    "up": 4,
}

_SLOT_TO_DIRECTION: dict[int, TrussLoadDirection] = {
    1: "left",
    2: "down",
    3: "right",
    4: "up",
}


def _edge_key(joint_a: int, joint_b: int) -> tuple[int, int]:
    """Return canonical undirected member key for two joint IDs.

    Args:
        joint_a: First joint identifier.
        joint_b: Second joint identifier.

    Returns:
        Sorted edge key.
    """
    return (joint_a, joint_b) if joint_a < joint_b else (joint_b, joint_a)


def _point_in_polygon(x_value: float, y_value: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    """Return whether a point lies inside or on one polygon.

    Args:
        x_value: Point x coordinate.
        y_value: Point y coordinate.
        polygon: Polygon vertices in order.

    Returns:
        ``True`` when the point lies inside or on the polygon.
    """
    inside = False
    count = len(polygon)
    for index in range(count):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % count]
        cross = (x_value - x0) * (y1 - y0) - (y_value - y0) * (x1 - x0)
        if (
            abs(cross) < 1e-12
            and min(x0, x1) - 1e-12 <= x_value <= max(x0, x1) + 1e-12
            and min(y0, y1) - 1e-12 <= y_value <= max(y0, y1) + 1e-12
        ):
            return True

        intersects = (y0 > y_value) != (y1 > y_value)
        if not intersects:
            continue
        if abs(y1 - y0) < 1e-12:
            continue
        x_at_y = x0 + (y_value - y0) * (x1 - x0) / (y1 - y0)
        if x_value < x_at_y:
            inside = not inside
    return inside


def _segments_intersect(
    ax0: float,
    ay0: float,
    ax1: float,
    ay1: float,
    bx0: float,
    by0: float,
    bx1: float,
    by1: float,
) -> bool:
    """Return whether two line segments intersect.

    Args:
        ax0: Segment A start x.
        ay0: Segment A start y.
        ax1: Segment A end x.
        ay1: Segment A end y.
        bx0: Segment B start x.
        by0: Segment B start y.
        bx1: Segment B end x.
        by1: Segment B end y.

    Returns:
        ``True`` when segments intersect or touch.
    """

    def orientation(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> float:
        return (qy - py) * (rx - qx) - (qx - px) * (ry - qy)

    def on_segment(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> bool:
        return min(px, rx) - 1e-12 <= qx <= max(px, rx) + 1e-12 and min(py, ry) - 1e-12 <= qy <= max(py, ry) + 1e-12

    o1 = orientation(ax0, ay0, ax1, ay1, bx0, by0)
    o2 = orientation(ax0, ay0, ax1, ay1, bx1, by1)
    o3 = orientation(bx0, by0, bx1, by1, ax0, ay0)
    o4 = orientation(bx0, by0, bx1, by1, ax1, ay1)

    if o1 * o2 < 0 and o3 * o4 < 0:
        return True

    if abs(o1) < 1e-12 and on_segment(ax0, ay0, bx0, by0, ax1, ay1):
        return True
    if abs(o2) < 1e-12 and on_segment(ax0, ay0, bx1, by1, ax1, ay1):
        return True
    if abs(o3) < 1e-12 and on_segment(bx0, by0, ax0, ay0, bx1, by1):
        return True
    return abs(o4) < 1e-12 and on_segment(bx0, by0, ax1, ay1, bx1, by1)


def _segment_intersects_polygon(
    start: tuple[float, float],
    end: tuple[float, float],
    polygon: tuple[tuple[float, float], ...],
) -> bool:
    """Return whether a segment intersects or lies within a polygon.

    Args:
        start: Segment start point.
        end: Segment end point.
        polygon: Polygon vertices.

    Returns:
        ``True`` when the segment intersects or lies in the polygon.
    """
    if _point_in_polygon(start[0], start[1], polygon) or _point_in_polygon(end[0], end[1], polygon):
        return True

    for index in range(len(polygon)):
        p0 = polygon[index]
        p1 = polygon[(index + 1) % len(polygon)]
        if _segments_intersect(start[0], start[1], end[0], end[1], p0[0], p0[1], p1[0], p1[1]):
            return True
    return False


def build_default_truss_ap_state() -> TrussAPState:
    """Build the canonical seed state for Truss Analysis Program mechanics.

    Returns:
        Seed state with required joints, loads, and no members.
    """
    joints = (
        TrussAPJoint(joint_id=1, x=-5.0, y=0.0, is_fixed=True),
        TrussAPJoint(joint_id=2, x=1.0, y=0.0, is_fixed=True),
        TrussAPJoint(joint_id=3, x=5.0, y=0.0, is_fixed=True),
        TrussAPJoint(joint_id=4, x=-2.0, y=0.0, is_fixed=True),
        TrussAPJoint(joint_id=5, x=3.0, y=0.0, is_fixed=True),
    )
    loads = (
        TrussAPLoad(joint_id=4, direction="down", magnitude_n=200_000.0),
        TrussAPLoad(joint_id=5, direction="down", magnitude_n=200_000.0),
    )
    return TrussAPState(
        joints=joints,
        members=(),
        loads=loads,
        support_enabled=(True, True, True),
    )


def truss_member_exists(members: tuple[TrussAPMember, ...], joint_a: int, joint_b: int) -> bool:
    """Return whether an undirected member already exists.

    Args:
        members: Existing members.
        joint_a: First joint identifier.
        joint_b: Second joint identifier.

    Returns:
        ``True`` when a member already connects the two joints.
    """
    edge = _edge_key(joint_a, joint_b)
    return any(_edge_key(member.start_joint_id, member.end_joint_id) == edge for member in members)


def _load_lookup(state: TrussAPState) -> dict[tuple[int, int], float]:
    """Build a lookup from ``(joint_id, slot)`` to load magnitude.

    Args:
        state: Input truss state.

    Returns:
        Load magnitude mapping for all explicit directional loads.
    """
    lookup: dict[tuple[int, int], float] = {}
    for load in state.loads:
        slot = _DIRECTION_TO_SLOT.get(load.direction)
        if slot is None:
            continue
        lookup[(load.joint_id, slot)] = load.magnitude_n
    return lookup


def _degree_by_joint(state: TrussAPState) -> dict[int, int]:
    """Return member degree counts per joint.

    Args:
        state: Input truss state.

    Returns:
        Mapping from joint ID to degree count.
    """
    degree = {joint.joint_id: 0 for joint in state.joints}
    for member in state.members:
        if member.start_joint_id in degree:
            degree[member.start_joint_id] += 1
        if member.end_joint_id in degree:
            degree[member.end_joint_id] += 1
    return degree


def _calculate_mass(state: TrussAPState) -> float:
    """Compute truss mass from member lengths and discrete section choices.

    Args:
        state: Input truss state.

    Returns:
        Total mass in kilograms.
    """
    joint_lookup = {joint.joint_id: joint for joint in state.joints}
    mass = 0.0
    for member in state.members:
        start = joint_lookup.get(member.start_joint_id)
        end = joint_lookup.get(member.end_joint_id)
        if start is None or end is None:
            continue
        if not (1 <= member.size_index <= len(_LINEAR_MASS_KG_PER_M)):
            continue
        length = float(numpy.hypot(end.x - start.x, end.y - start.y))
        mass += length * _LINEAR_MASS_KG_PER_M[member.size_index - 1]
    return float(mass)


def _invalid_evaluation(state: TrussAPState, reason: str) -> TrussAPEvaluation:
    """Build one standardized invalid truss evaluation payload.

    Args:
        state: Input truss state.
        reason: Human-readable invalidity reason.

    Returns:
        Infeasible evaluation with zero FOS and empty force results.
    """
    return TrussAPEvaluation(
        mass_kg=_calculate_mass(state),
        min_fos=0.0,
        is_stable=False,
        is_acceptable=False,
        joint_count=len(state.joints),
        member_count=len(state.members),
        force_by_member_n=(),
        fos_by_member=(),
        failure_reason=reason,
    )


def _validate_state_shape(state: TrussAPState) -> str | None:
    """Validate state fields that can trigger runtime solver failures.

    Args:
        state: Input truss state.

    Returns:
        ``None`` when valid, otherwise one failure reason string.
    """
    if len(state.required_support_joint_ids) != 3:
        return "Exactly three required support joints are expected."
    if len(state.support_enabled) != len(state.required_support_joint_ids):
        return "support_enabled length must match required_support_joint_ids length."

    joint_ids = {joint.joint_id for joint in state.joints}
    for load in state.loads:
        if load.direction not in _DIRECTION_TO_SLOT:
            return "Load directions must be one of left/down/right/up."
        if load.joint_id not in joint_ids:
            return "Loads must reference existing joints."
        if not numpy.isfinite(load.magnitude_n):
            return "Load magnitudes must be finite."

    seen_members: set[tuple[int, int]] = set()
    for member in state.members:
        if member.start_joint_id == member.end_joint_id:
            return "Members cannot connect a joint to itself."
        if member.start_joint_id not in joint_ids or member.end_joint_id not in joint_ids:
            return "Members must reference existing joints."
        if not (state.size_index_min <= member.size_index <= state.size_index_max):
            return "Member size index is out of bounds."
        if not (1 <= member.size_index <= len(_SECTION_AREA_M2)):
            return "Member size index exceeds the available section table."

        edge = _edge_key(member.start_joint_id, member.end_joint_id)
        if edge in seen_members:
            return "Duplicate members between the same joints are not allowed."
        seen_members.add(edge)

    return None


def _evaluate_st_solver(
    state: TrussAPState,
) -> tuple[bool, tuple[float, ...], tuple[float, ...], str | None]:
    """Solve the structural model and compute member forces/FOS.

    Args:
        state: Input truss state.

    Returns:
        Tuple ``(stable, forces, fos_values, failure_reason)``.
    """
    joint_lookup = {joint.joint_id: joint for joint in state.joints}
    joint_ids = tuple(sorted(joint_lookup))
    id_to_index = {joint_id: index for index, joint_id in enumerate(joint_ids)}
    member_count = len(state.members)
    joint_count = len(joint_ids)

    if member_count == 0:
        return (False, (), (), "At least one member is required.")

    coord = numpy.zeros((3, joint_count), dtype=float)
    for joint_id, index in id_to_index.items():
        joint = joint_lookup[joint_id]
        coord[:, index] = numpy.asarray((joint.x, joint.y, 0.0), dtype=float)

    re_matrix = numpy.zeros((3, joint_count), dtype=float)
    re_matrix[2, :] = 1.0

    support_settings = state.support_enabled
    support_joint_ids = state.required_support_joint_ids
    if support_settings[0] and support_joint_ids[0] in id_to_index:
        re_matrix[:, id_to_index[support_joint_ids[0]]] = numpy.asarray((1.0, 1.0, 1.0), dtype=float)
    if support_settings[1] and support_joint_ids[1] in id_to_index:
        re_matrix[:, id_to_index[support_joint_ids[1]]] = numpy.asarray((0.0, 1.0, 1.0), dtype=float)
    if support_settings[2] and support_joint_ids[2] in id_to_index:
        re_matrix[:, id_to_index[support_joint_ids[2]]] = numpy.asarray((1.0, 1.0, 1.0), dtype=float)

    load_lookup = _load_lookup(state)
    load = numpy.zeros((3, joint_count), dtype=float)
    for joint_id in joint_ids:
        index = id_to_index[joint_id]
        left = load_lookup.get((joint_id, 1), 0.0)
        down = load_lookup.get((joint_id, 2), 0.0)
        right = load_lookup.get((joint_id, 3), 0.0)
        up = load_lookup.get((joint_id, 4), 0.0)
        load[0, index] = right - left
        load[1, index] = up - down

    dof_count = 3 * joint_count
    stiffness = numpy.zeros((dof_count, dof_count), dtype=float)
    tj = numpy.zeros((3, member_count), dtype=float)
    areas = numpy.zeros(member_count, dtype=float)
    inertias = numpy.zeros(member_count, dtype=float)
    member_lengths = numpy.zeros(member_count, dtype=float)
    con = numpy.zeros((2, member_count), dtype=int)

    for member_index, member in enumerate(state.members):
        if not (1 <= member.size_index <= len(_SECTION_AREA_M2)):
            return (False, (), (), "Member size index exceeds the available section table.")
        start_index = id_to_index.get(member.start_joint_id)
        end_index = id_to_index.get(member.end_joint_id)
        if start_index is None or end_index is None:
            return (False, (), (), "Members must reference existing joints.")

        con[:, member_index] = numpy.asarray((start_index, end_index), dtype=int)

        start = coord[:, start_index]
        end = coord[:, end_index]
        c_vec = end - start
        length = float(numpy.linalg.norm(c_vec))
        member_lengths[member_index] = length
        if length <= 0.0:
            return (False, (), (), "Members cannot have zero length.")

        t_vec = c_vec / length
        s_matrix = numpy.outer(t_vec, t_vec)
        area = _SECTION_AREA_M2[member.size_index - 1]
        inertia = _SECTION_INERTIA_M4[member.size_index - 1]
        areas[member_index] = area
        inertias[member_index] = inertia

        g_value = _STEEL_E_PA * area / length
        tj[:, member_index] = g_value * t_vec

        block = g_value * numpy.block([[s_matrix, -s_matrix], [-s_matrix, s_matrix]])
        dof = [
            3 * start_index,
            3 * start_index + 1,
            3 * start_index + 2,
            3 * end_index,
            3 * end_index + 1,
            3 * end_index + 2,
        ]
        for row_idx in range(6):
            for col_idx in range(6):
                stiffness[dof[row_idx], dof[col_idx]] += block[row_idx, col_idx]

    displacement_mask = (1.0 - re_matrix).reshape(-1)
    free_dofs = numpy.flatnonzero(displacement_mask)
    displacement = displacement_mask.copy()
    rhs = load.reshape(-1)

    if free_dofs.size == 0:
        return (False, (), (), "No unconstrained DOFs available for solve.")

    reduced = stiffness[numpy.ix_(free_dofs, free_dofs)]
    stable = True
    reciprocal_condition = 0.0
    try:
        reciprocal_condition = 1.0 / float(numpy.linalg.cond(reduced))
    except numpy.linalg.LinAlgError:
        reciprocal_condition = 0.0

    if reciprocal_condition < numpy.finfo(float).eps:
        stable = False

    try:
        displacement[free_dofs] = numpy.linalg.lstsq(reduced, rhs[free_dofs], rcond=None)[0]
    except numpy.linalg.LinAlgError:
        return (False, (), (), "Structural solve failed.")

    displacement_matrix = displacement.reshape(3, joint_count)
    force = numpy.sum(
        tj * (displacement_matrix[:, con[1, :]] - displacement_matrix[:, con[0, :]]),
        axis=0,
    )

    fos_values = numpy.zeros(member_count, dtype=float)
    for member_index in range(member_count):
        member_force = force[member_index]
        if member_force < 0.0:
            buckling = abs(
                (numpy.pi**2 * _STEEL_E_PA * inertias[member_index] / (member_lengths[member_index] ** 2))
                / member_force
            )
            yield_limit = abs(areas[member_index] * _FY_PA / member_force)
            fos_values[member_index] = min(buckling, yield_limit)
        else:
            fos_values[member_index] = (
                numpy.inf if member_force == 0.0 else (areas[member_index] * _FY_PA / member_force)
            )

    if numpy.isnan(fos_values).any():
        return (False, tuple(float(value) for value in force), (), "Computed FOS contains NaN values.")

    return (
        stable,
        tuple(float(value) for value in force),
        tuple(float(value) for value in fos_values),
        "Structural matrix is singular or nearly singular." if not stable else None,
    )


def evaluate_truss_ap_state(state: TrussAPState) -> TrussAPEvaluation:
    """Evaluate one truss state with MATLAB parity mechanics.

    Args:
        state: Input truss state.

    Returns:
        Deterministic structural metrics for the design.
    """
    invalid_reason = _validate_state_shape(state)
    if invalid_reason is not None:
        return _invalid_evaluation(state, invalid_reason)

    joint_ids = [joint.joint_id for joint in state.joints]
    if len(joint_ids) != len(set(joint_ids)):
        return _invalid_evaluation(state, "Joint IDs must be unique.")

    if state.enforce_bad_zone:
        for joint in state.joints:
            if joint.is_fixed:
                continue
            if _point_in_polygon(joint.x, joint.y, state.bad_zone_polygon):
                return _invalid_evaluation(state, "A movable joint is inside the restricted zone.")
        lookup = {joint.joint_id: joint for joint in state.joints}
        for member in state.members:
            start = lookup.get(member.start_joint_id)
            end = lookup.get(member.end_joint_id)
            if start is None or end is None:
                continue
            if _segment_intersects_polygon((start.x, start.y), (end.x, end.y), state.bad_zone_polygon):
                return _invalid_evaluation(state, "A member intersects the restricted zone.")

    degree = _degree_by_joint(state)
    if not all(degree.get(joint_id, 0) > 0 for joint_id in state.required_support_joint_ids):
        return _invalid_evaluation(state, "All required support joints must connect to at least one member.")

    if not all(degree.get(joint_id, 0) > 0 for joint_id in state.required_load_joint_ids):
        return _invalid_evaluation(state, "All required load joints must connect to at least one member.")

    stable, forces, fos_values, failure_reason = _evaluate_st_solver(state)
    min_fos = min(fos_values) if fos_values else 0.0
    return TrussAPEvaluation(
        mass_kg=_calculate_mass(state),
        min_fos=float(min_fos),
        is_stable=stable,
        is_acceptable=stable and min_fos >= state.fos_target,
        joint_count=len(state.joints),
        member_count=len(state.members),
        force_by_member_n=forces,
        fos_by_member=fos_values,
        failure_reason=failure_reason,
    )


def resolve_truss_load(
    state: TrussAPState,
    *,
    joint_id: int,
    direction: TrussLoadDirection,
    magnitude_n: float,
) -> TrussAPState:
    """Return a state with one load value set for one joint/direction pair.

    Args:
        state: Input state.
        joint_id: Target joint identifier.
        direction: Direction slot to set.
        magnitude_n: New load magnitude in Newtons.

    Returns:
        Updated state with the target load replaced or inserted.
    """
    retained = [load for load in state.loads if not (load.joint_id == joint_id and load.direction == direction)]
    retained.append(TrussAPLoad(joint_id=joint_id, direction=direction, magnitude_n=magnitude_n))
    retained.sort(key=lambda entry: (entry.joint_id, _DIRECTION_TO_SLOT[entry.direction]))
    return replace(state, loads=tuple(retained))


def clear_truss_load(state: TrussAPState, *, joint_id: int, direction: TrussLoadDirection) -> TrussAPState:
    """Return a state with one load removed for one joint/direction pair.

    Args:
        state: Input state.
        joint_id: Target joint identifier.
        direction: Target direction.

    Returns:
        Updated state without the target load.
    """
    loads = tuple(load for load in state.loads if not (load.joint_id == joint_id and load.direction == direction))
    return replace(state, loads=loads)


__all__ = [
    "TrussAPEvaluation",
    "TrussAPJoint",
    "TrussAPLoad",
    "TrussAPMember",
    "TrussAPState",
    "TrussLoadDirection",
    "build_default_truss_ap_state",
    "clear_truss_load",
    "evaluate_truss_ap_state",
    "resolve_truss_load",
    "truss_member_exists",
]
