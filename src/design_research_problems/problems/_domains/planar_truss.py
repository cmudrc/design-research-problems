"""Shared backend helpers for planar truss states and evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy

from design_research_problems.problems._domains.truss_core import (
    TrussJointRecord,
    TrussLoadRecord,
    build_adjacency,
    evaluate_truss_records,
)
from design_research_problems.problems._domains.truss_core import (
    edge_key as _shared_edge_key,
)

SupportType = Literal["pinned", "roller", "free"]


@dataclass(frozen=True)
class PlanarJoint:
    """One planar joint in the shared truss state."""

    joint_id: int
    """Stable joint identifier within the state."""
    x: float
    """Planar x-coordinate."""
    y: float
    """Planar y-coordinate."""
    support_type: SupportType
    """Support condition at the joint."""


@dataclass(frozen=True)
class PlanarMember:
    """One undirected member between two joints."""

    member_id: int
    """Stable member identifier within the state."""
    start_joint_id: int
    """Identifier of the first endpoint joint."""
    end_joint_id: int
    """Identifier of the second endpoint joint."""


@dataclass(frozen=True)
class PlanarLoad:
    """One point load applied to one joint."""

    joint_id: int
    """Joint receiving the load."""
    vector: tuple[float, float, float]
    """Applied load vector."""


@dataclass(frozen=True)
class PlanarTrussState:
    """Serializable state for a planar truss topology."""

    span: float
    """Overall support-to-support span."""
    max_height: float
    """Maximum intended design envelope height."""
    joints: tuple[PlanarJoint, ...]
    """All joints currently present in the state."""
    members: tuple[PlanarMember, ...]
    """All members currently present in the state."""
    load_joint_id: int
    """Joint receiving the external design load."""
    load_vector: tuple[float, float, float]
    """Load vector applied during evaluation."""
    additional_loads: tuple[PlanarLoad, ...] = ()
    """Additional point loads applied during evaluation."""
    symmetry_axis_x: float | None = None
    """Optional x-coordinate for a vertical symmetry axis."""


@dataclass(frozen=True)
class PlanarTrussEvaluation:
    """Structured evaluation result for a planar truss state."""

    mass: float
    """Computed truss mass."""
    fos: float
    """Minimum overall factor of safety."""
    fos_buckling: float
    """Buckling factor of safety."""
    fos_yielding: float
    """Yielding factor of safety."""
    deflection: float
    """Maximum joint deflection magnitude."""
    number_of_joints: int
    """Number of joints in the evaluated state."""
    number_of_members: int
    """Number of members in the evaluated state."""
    is_feasible: bool
    """Whether the evaluated state meets the default feasibility rule."""
    failure_reason: str | None = None
    """Optional reason describing why a state is infeasible."""


def edge_key(start_joint_id: int, end_joint_id: int) -> tuple[int, int]:
    """Normalize a member edge into an undirected key.

    Args:
        start_joint_id: Identifier for start joint.
        end_joint_id: Identifier for end joint.

    Returns:
        Computed result for this callable.
    """
    return _shared_edge_key(start_joint_id, end_joint_id)


def float_matches(left: float, right: float) -> bool:
    """Return whether two coordinates should be treated as equal.

    Args:
        left: Value for ``left``.
        right: Value for ``right``.

    Returns:
        Computed result for this callable.
    """
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def point_in_collection(points: set[tuple[float, float]], x_value: float, y_value: float) -> bool:
    """Return whether one coordinate pair is already occupied.

    Args:
        points: Value for ``points``.
        x_value: Value for ``x_value``.
        y_value: Value for ``y_value``.

    Returns:
        Computed result for this callable.
    """
    return any(float_matches(px, x_value) and float_matches(py, y_value) for px, py in points)


def roofline_y(x_fraction: float, max_height: float) -> float:
    """Return the y-coordinate for a simple gable roof profile.

    Args:
        x_fraction: Value for ``x_fraction``.
        max_height: Value for ``max_height``.

    Returns:
        Computed result for this callable.
    """
    return max_height * (1.0 - abs((2.0 * x_fraction) - 1.0))


def joint_map(state: PlanarTrussState) -> dict[int, PlanarJoint]:
    """Return one ID-indexed joint lookup table.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
    return {joint.joint_id: joint for joint in state.joints}


def member_lookup(state: PlanarTrussState) -> dict[tuple[int, int], PlanarMember]:
    """Return one edge-indexed member lookup table.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
    return {edge_key(member.start_joint_id, member.end_joint_id): member for member in state.members}


def mirrored_joint_id(state: PlanarTrussState, joint_id: int) -> int | None:
    """Return the mirrored joint identifier for one symmetric state.

    Args:
        state: Value for ``state``.
        joint_id: Identifier for joint.

    Returns:
        Computed result for this callable.
    """
    if state.symmetry_axis_x is None:
        return joint_id

    joints = joint_map(state)
    joint = joints.get(joint_id)
    if joint is None:
        return None

    target_x = (2.0 * state.symmetry_axis_x) - joint.x
    for candidate in state.joints:
        if float_matches(candidate.x, target_x) and float_matches(candidate.y, joint.y):
            return candidate.joint_id
    return None


def mirrored_edge(state: PlanarTrussState, edge: tuple[int, int]) -> tuple[int, int] | None:
    """Return the mirrored edge for one symmetric state.

    Args:
        state: Value for ``state``.
        edge: Value for ``edge``.

    Returns:
        Computed result for this callable.
    """
    mirrored_start = mirrored_joint_id(state, edge[0])
    mirrored_end = mirrored_joint_id(state, edge[1])
    if mirrored_start is None or mirrored_end is None:
        return None
    return edge_key(mirrored_start, mirrored_end)


def build_planar_truss_failure(state: PlanarTrussState, reason: str) -> PlanarTrussEvaluation:
    """Build a deterministic infeasible evaluation payload.

    Args:
        state: Value for ``state``.
        reason: Value for ``reason``.

    Returns:
        Computed result for this callable.
    """
    return PlanarTrussEvaluation(
        mass=0.0,
        fos=0.0,
        fos_buckling=0.0,
        fos_yielding=0.0,
        deflection=0.0,
        number_of_joints=len(state.joints),
        number_of_members=len(state.members),
        is_feasible=False,
        failure_reason=reason,
    )


def _orientation(point_a: tuple[float, float], point_b: tuple[float, float], point_c: tuple[float, float]) -> float:
    """Return the signed orientation determinant for three planar points.

    Args:
        point_a: Value for ``point_a``.
        point_b: Value for ``point_b``.
        point_c: Value for ``point_c``.

    Returns:
        Computed result for this callable.
    """
    return ((point_b[0] - point_a[0]) * (point_c[1] - point_a[1])) - (
        (point_b[1] - point_a[1]) * (point_c[0] - point_a[0])
    )


def _segments_cross(
    first_start: tuple[float, float],
    first_end: tuple[float, float],
    second_start: tuple[float, float],
    second_end: tuple[float, float],
) -> bool:
    """Return whether two open line segments intersect away from their endpoints.

    Args:
        first_start: Value for ``first_start``.
        first_end: Value for ``first_end``.
        second_start: Value for ``second_start``.
        second_end: Value for ``second_end``.

    Returns:
        Computed result for this callable.
    """
    tolerance = 1e-9
    orientation_one = _orientation(first_start, first_end, second_start)
    orientation_two = _orientation(first_start, first_end, second_end)
    orientation_three = _orientation(second_start, second_end, first_start)
    orientation_four = _orientation(second_start, second_end, first_end)
    if (
        abs(orientation_one) <= tolerance
        or abs(orientation_two) <= tolerance
        or abs(orientation_three) <= tolerance
        or abs(orientation_four) <= tolerance
    ):
        return False
    return (orientation_one > 0.0) != (orientation_two > 0.0) and (orientation_three > 0.0) != (orientation_four > 0.0)


def count_planar_member_crossings(state: PlanarTrussState) -> int:
    """Count member crossings that occur away from shared endpoints.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
    joints = joint_map(state)
    crossings = 0
    for first_index, first_member in enumerate(state.members):
        first_edge = edge_key(first_member.start_joint_id, first_member.end_joint_id)
        first_points = (
            (joints[first_edge[0]].x, joints[first_edge[0]].y),
            (joints[first_edge[1]].x, joints[first_edge[1]].y),
        )
        for second_member in state.members[first_index + 1 :]:
            second_edge = edge_key(second_member.start_joint_id, second_member.end_joint_id)
            if set(first_edge) & set(second_edge):
                continue
            second_points = (
                (joints[second_edge[0]].x, joints[second_edge[0]].y),
                (joints[second_edge[1]].x, joints[second_edge[1]].y),
            )
            if _segments_cross(first_points[0], first_points[1], second_points[0], second_points[1]):
                crossings += 1
    return crossings


def evaluate_planar_truss_state(state: PlanarTrussState) -> PlanarTrussEvaluation:
    """Evaluate one state with the lazy TrussMe adapter.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    try:
        if not state.members:
            evaluate_truss_records(
                tuple(
                    TrussJointRecord(
                        joint_id=joint.joint_id,
                        coordinates=(joint.x, joint.y, 0.0),
                        support_type=joint.support_type,
                    )
                    for joint in state.joints
                ),
                (),
                TrussLoadRecord(joint_id=state.load_joint_id, vector=state.load_vector),
                tuple(),
                out_of_plane_axis="z",
            )
            return build_planar_truss_failure(state, "At least one member is required.")

        metrics = evaluate_truss_records(
            tuple(
                TrussJointRecord(
                    joint_id=joint.joint_id,
                    coordinates=(joint.x, joint.y, 0.0),
                    support_type=joint.support_type,
                )
                for joint in state.joints
            ),
            tuple(
                edge_key(member.start_joint_id, member.end_joint_id)
                for member in sorted(state.members, key=lambda item: item.member_id)
            ),
            TrussLoadRecord(joint_id=state.load_joint_id, vector=state.load_vector),
            tuple(TrussLoadRecord(joint_id=load.joint_id, vector=load.vector) for load in state.additional_loads),
            out_of_plane_axis="z",
        )
        fos = metrics.fos
        return PlanarTrussEvaluation(
            mass=metrics.mass,
            fos=fos,
            fos_buckling=metrics.fos_buckling,
            fos_yielding=metrics.fos_yielding,
            deflection=metrics.deflection,
            number_of_joints=len(state.joints),
            number_of_members=len(state.members),
            is_feasible=fos >= 1.0,
            failure_reason=None,
        )
    except numpy.linalg.LinAlgError as exc:
        return build_planar_truss_failure(state, f"Linear solve failed: {exc}")
    except (IndexError, ValueError, KeyError) as exc:
        return build_planar_truss_failure(state, str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard for optional integration.
        from design_research_problems._exceptions import MissingOptionalDependencyError

        if isinstance(exc, MissingOptionalDependencyError):
            raise
        return build_planar_truss_failure(state, f"{type(exc).__name__}: {exc}")


__all__ = [
    "PlanarJoint",
    "PlanarLoad",
    "PlanarMember",
    "PlanarTrussEvaluation",
    "PlanarTrussState",
    "SupportType",
    "build_planar_truss_failure",
    "count_planar_member_crossings",
    "edge_key",
    "evaluate_planar_truss_state",
    "float_matches",
    "joint_map",
    "member_lookup",
    "mirrored_edge",
    "mirrored_joint_id",
    "point_in_collection",
    "roofline_y",
]


def build_seed_planar_truss_state(
    span: float,
    max_height: float,
    load_magnitude: float,
    *,
    roof_load_x_fractions: tuple[float, ...] = (),
    enforce_symmetry: bool = False,
) -> PlanarTrussState:
    """Build the canonical zero-member planar truss seed state.

    Args:
        span: Support-to-support span.
        max_height: Maximum intended design envelope height.
        load_magnitude: Downward point-load magnitude.
        roof_load_x_fractions: Optional roofline load locations as span fractions.
        enforce_symmetry: Whether the state should record a vertical symmetry axis.

    Returns:
        Seed state containing the supports, one or more loaded joints, and no members.
    """
    joints: list[PlanarJoint] = [
        PlanarJoint(joint_id=0, x=0.0, y=0.0, support_type="pinned"),
        PlanarJoint(joint_id=1, x=span, y=0.0, support_type="roller"),
    ]
    if roof_load_x_fractions:
        load_joint_ids: list[int] = []
        for index, x_fraction in enumerate(roof_load_x_fractions, start=2):
            joints.append(
                PlanarJoint(
                    joint_id=index,
                    x=span * x_fraction,
                    y=roofline_y(x_fraction, max_height),
                    support_type="free",
                )
            )
            load_joint_ids.append(index)
        load_value = load_magnitude / float(len(load_joint_ids))
        load_vector = (0.0, -load_value, 0.0)
        additional_loads = tuple(PlanarLoad(joint_id=joint_id, vector=load_vector) for joint_id in load_joint_ids[1:])
        load_joint_id = load_joint_ids[0]
    else:
        joints.append(PlanarJoint(joint_id=2, x=span / 2.0, y=max_height, support_type="free"))
        load_joint_id = 2
        load_vector = (0.0, -load_magnitude, 0.0)
        additional_loads = ()

    return PlanarTrussState(
        span=span,
        max_height=max_height,
        joints=tuple(joints),
        members=(),
        load_joint_id=load_joint_id,
        load_vector=load_vector,
        additional_loads=additional_loads,
        symmetry_axis_x=span / 2.0 if enforce_symmetry else None,
    )


def candidate_planar_truss_points(
    state: PlanarTrussState,
    *,
    candidate_point_fractions: tuple[tuple[float, float], ...] = (),
) -> tuple[tuple[float, float], ...]:
    """Return the deterministic candidate interior joint coordinates.

    Args:
        state: Base truss state that defines the span and height scaling.
        candidate_point_fractions: Optional span- and height-fraction pairs.

    Returns:
        Candidate interior joint coordinates in deterministic order.
    """
    if candidate_point_fractions:
        return tuple(
            (state.span * x_fraction, state.max_height * y_fraction)
            for x_fraction, y_fraction in candidate_point_fractions
        )
    return (
        (state.span * 0.25, state.max_height * 0.5),
        (state.span * 0.50, state.max_height * 0.5),
        (state.span * 0.75, state.max_height * 0.5),
    )


def expand_planar_truss_candidate_joints(
    state: PlanarTrussState,
    candidate_points: tuple[tuple[float, float], ...],
) -> PlanarTrussState:
    """Return a state with all deterministic candidate joints inserted.

    Args:
        state: Base truss state to extend.
        candidate_points: Candidate interior joint coordinates.

    Returns:
        State containing the original joints plus any admissible candidate joints.
    """
    joints = list(state.joints)
    occupied = {(joint.x, joint.y) for joint in joints}
    next_joint_id = max((joint.joint_id for joint in joints), default=-1) + 1

    if state.symmetry_axis_x is None:
        for x_value, y_value in candidate_points:
            if point_in_collection(occupied, x_value, y_value):
                continue
            joints.append(PlanarJoint(joint_id=next_joint_id, x=x_value, y=y_value, support_type="free"))
            occupied.add((x_value, y_value))
            next_joint_id += 1
        return PlanarTrussState(
            span=state.span,
            max_height=state.max_height,
            joints=tuple(joints),
            members=state.members,
            load_joint_id=state.load_joint_id,
            load_vector=state.load_vector,
            additional_loads=state.additional_loads,
            symmetry_axis_x=state.symmetry_axis_x,
        )

    processed_points: list[tuple[float, float]] = []
    assert state.symmetry_axis_x is not None
    for x_value, y_value in candidate_points:
        if any(float_matches(px, x_value) and float_matches(py, y_value) for px, py in processed_points):
            continue
        if float_matches(x_value, state.symmetry_axis_x):
            processed_points.append((x_value, y_value))
            if point_in_collection(occupied, x_value, y_value):
                continue
            joints.append(PlanarJoint(joint_id=next_joint_id, x=x_value, y=y_value, support_type="free"))
            occupied.add((x_value, y_value))
            next_joint_id += 1
            continue

        mirrored_x = (2.0 * state.symmetry_axis_x) - x_value
        processed_points.append((x_value, y_value))
        processed_points.append((mirrored_x, y_value))
        if point_in_collection(occupied, x_value, y_value) or point_in_collection(occupied, mirrored_x, y_value):
            continue
        left_x, right_x = sorted((x_value, mirrored_x))
        joints.append(PlanarJoint(joint_id=next_joint_id, x=left_x, y=y_value, support_type="free"))
        joints.append(PlanarJoint(joint_id=next_joint_id + 1, x=right_x, y=y_value, support_type="free"))
        occupied.add((left_x, y_value))
        occupied.add((right_x, y_value))
        next_joint_id += 2

    return PlanarTrussState(
        span=state.span,
        max_height=state.max_height,
        joints=tuple(joints),
        members=state.members,
        load_joint_id=state.load_joint_id,
        load_vector=state.load_vector,
        additional_loads=state.additional_loads,
        symmetry_axis_x=state.symmetry_axis_x,
    )


def enumerate_planar_truss_candidate_edges(state: PlanarTrussState) -> tuple[tuple[int, int], ...]:
    """Return the canonical candidate member edges for one fixed joint set.

    Args:
        state: Truss state whose joints define the candidate topology space.

    Returns:
        Canonical undirected member edges in deterministic order.
    """
    existing_edges = set(member_lookup(state))
    joint_ids = sorted(joint.joint_id for joint in state.joints)
    candidate_edges: list[tuple[int, int]] = []
    for index, start_joint_id in enumerate(joint_ids):
        for end_joint_id in joint_ids[index + 1 :]:
            edge = edge_key(start_joint_id, end_joint_id)
            if edge in existing_edges:
                continue
            if state.symmetry_axis_x is not None:
                mirrored = mirrored_edge(state, edge)
                if mirrored is None:
                    continue
                if edge != min(edge, mirrored):
                    continue
                if mirrored != edge and mirrored in existing_edges:
                    continue
            candidate_edges.append(edge)
    return tuple(candidate_edges)


def build_planar_truss_state_from_edges(
    base_state: PlanarTrussState,
    selected_edges: tuple[tuple[int, int], ...],
) -> PlanarTrussState:
    """Build a concrete truss state from a fixed joint set and selected edges.

    Args:
        base_state: Fixed-joint state that supplies joints, loads, and symmetry.
        selected_edges: Canonical undirected edges selected for inclusion.

    Returns:
        New state with deterministically numbered members.

    Raises:
        ValueError: If a selected edge references missing joints or violates symmetry requirements.
    """
    joint_ids = {joint.joint_id for joint in base_state.joints}
    included_edges = {edge_key(member.start_joint_id, member.end_joint_id) for member in base_state.members}
    for raw_edge in selected_edges:
        edge = edge_key(raw_edge[0], raw_edge[1])
        if edge[0] not in joint_ids or edge[1] not in joint_ids:
            raise ValueError("Selected edges must reference existing joints.")
        included_edges.add(edge)
        if base_state.symmetry_axis_x is None:
            continue
        mirrored = mirrored_edge(base_state, edge)
        if mirrored is None:
            raise ValueError("Symmetric truss states require mirrored joints for every selected edge.")
        included_edges.add(mirrored)

    ordered_edges = tuple(sorted(included_edges))
    retained_joint_ids = {joint.joint_id for joint in base_state.joints if joint.support_type != "free"} | {
        base_state.load_joint_id
    }
    retained_joint_ids.update(load.joint_id for load in base_state.additional_loads)
    for edge in ordered_edges:
        retained_joint_ids.update(edge)
    joints = tuple(joint for joint in base_state.joints if joint.joint_id in retained_joint_ids)
    members = tuple(
        PlanarMember(
            member_id=member_id,
            start_joint_id=edge[0],
            end_joint_id=edge[1],
        )
        for member_id, edge in enumerate(ordered_edges)
    )
    return PlanarTrussState(
        span=base_state.span,
        max_height=base_state.max_height,
        joints=joints,
        members=members,
        load_joint_id=base_state.load_joint_id,
        load_vector=base_state.load_vector,
        additional_loads=base_state.additional_loads,
        symmetry_axis_x=base_state.symmetry_axis_x,
    )


__all__ += [
    "build_planar_truss_state_from_edges",
    "build_seed_planar_truss_state",
    "candidate_planar_truss_points",
    "enumerate_planar_truss_candidate_edges",
    "expand_planar_truss_candidate_joints",
]


def active_joint_ids(state: PlanarTrussState) -> set[int]:
    """Return the joint IDs touched by supports, the load joint, or active members.

    Args:
        state: Planar truss state to inspect.

    Returns:
        Set of joint IDs that participate in the active load path.
    """
    active_ids = {joint.joint_id for joint in state.joints if joint.support_type != "free"} | {state.load_joint_id}
    for member in state.members:
        active_ids.add(member.start_joint_id)
        active_ids.add(member.end_joint_id)
    return active_ids


def adjacency_map(state: PlanarTrussState) -> dict[int, set[int]]:
    """Return an undirected adjacency map for the state's members.

    Args:
        state: Planar truss state to inspect.

    Returns:
        Mapping of joint IDs to neighboring joint IDs.
    """
    joint_ids = {joint.joint_id for joint in state.joints}
    edges = tuple(edge_key(member.start_joint_id, member.end_joint_id) for member in state.members)
    return build_adjacency(joint_ids, edges)


__all__ += ["active_joint_ids", "adjacency_map"]
