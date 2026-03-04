"""Shared backend helpers for 3D space truss states and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy

from design_research_problems.problems._domains.truss_core import (
    Axis,
    SupportType,
    TrussJointRecord,
    TrussLoadRecord,
    build_adjacency,
    edge_key,
    evaluate_truss_records,
)


@dataclass(frozen=True)
class SpaceJoint:
    """One 3D joint in the shared space-truss state."""

    joint_id: int
    x: float
    y: float
    z: float
    support_type: SupportType


@dataclass(frozen=True)
class SpaceMember:
    """One undirected member between two space joints."""

    member_id: int
    start_joint_id: int
    end_joint_id: int


@dataclass(frozen=True)
class SpaceLoad:
    """One point load applied to one space-truss joint."""

    joint_id: int
    vector: tuple[float, float, float]


@dataclass(frozen=True)
class SpaceTrussState:
    """Serializable state for a 3D space truss."""

    span: float
    width: float
    max_height: float
    joints: tuple[SpaceJoint, ...]
    members: tuple[SpaceMember, ...]
    load_joint_id: int
    load_vector: tuple[float, float, float]
    additional_loads: tuple[SpaceLoad, ...] = ()


@dataclass(frozen=True)
class SpaceTrussEvaluation:
    """Structured evaluation result for a 3D space truss."""

    mass: float
    fos: float
    fos_buckling: float
    fos_yielding: float
    deflection: float
    number_of_joints: int
    number_of_members: int
    is_feasible: bool
    failure_reason: str | None = None


def build_space_truss_failure(state: SpaceTrussState, reason: str) -> SpaceTrussEvaluation:
    """Build a deterministic infeasible 3D evaluation payload."""
    return SpaceTrussEvaluation(
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


def build_seed_space_truss_state(
    span: float,
    width: float,
    max_height: float,
    load_magnitude: float,
) -> SpaceTrussState:
    """Build the canonical bridge-like 3D seed state."""
    half_width = width / 2.0
    joints = (
        SpaceJoint(joint_id=0, x=0.0, y=-half_width, z=0.0, support_type="pinned"),
        SpaceJoint(joint_id=1, x=0.0, y=half_width, z=0.0, support_type="roller"),
        SpaceJoint(joint_id=2, x=span, y=-half_width, z=0.0, support_type="roller"),
        SpaceJoint(joint_id=3, x=span, y=half_width, z=0.0, support_type="roller"),
        SpaceJoint(joint_id=4, x=span / 2.0, y=0.0, z=max_height, support_type="free"),
    )
    return SpaceTrussState(
        span=span,
        width=width,
        max_height=max_height,
        joints=joints,
        members=(),
        load_joint_id=4,
        load_vector=(0.0, 0.0, -load_magnitude),
        additional_loads=(),
    )


def candidate_space_truss_points(
    state: SpaceTrussState,
    *,
    candidate_point_fractions_3d: tuple[tuple[float, float, float], ...] = (),
) -> tuple[tuple[float, float, float], ...]:
    """Return the deterministic interior candidate-joint coordinates."""
    if candidate_point_fractions_3d:
        half_width = state.width / 2.0
        return tuple(
            (state.span * x_fraction, half_width * y_fraction, state.max_height * z_fraction)
            for x_fraction, y_fraction, z_fraction in candidate_point_fractions_3d
        )
    half_width = state.width / 2.0
    return (
        (state.span * 0.25, -half_width, state.max_height * 0.5),
        (state.span * 0.25, half_width, state.max_height * 0.5),
        (state.span * 0.75, -half_width, state.max_height * 0.5),
        (state.span * 0.75, half_width, state.max_height * 0.5),
    )


def expand_space_truss_candidate_joints(
    state: SpaceTrussState,
    candidate_points: tuple[tuple[float, float, float], ...],
) -> SpaceTrussState:
    """Return a state with deterministic candidate joints inserted."""
    joints = list(state.joints)
    occupied = {(joint.x, joint.y, joint.z) for joint in joints}
    next_joint_id = max((joint.joint_id for joint in joints), default=-1) + 1
    for x_value, y_value, z_value in candidate_points:
        point = (x_value, y_value, z_value)
        if point in occupied:
            continue
        joints.append(SpaceJoint(joint_id=next_joint_id, x=x_value, y=y_value, z=z_value, support_type="free"))
        occupied.add(point)
        next_joint_id += 1
    return SpaceTrussState(
        span=state.span,
        width=state.width,
        max_height=state.max_height,
        joints=tuple(joints),
        members=state.members,
        load_joint_id=state.load_joint_id,
        load_vector=state.load_vector,
        additional_loads=state.additional_loads,
    )


def enumerate_space_truss_candidate_edges(state: SpaceTrussState) -> tuple[tuple[int, int], ...]:
    """Return the canonical candidate member edges for one fixed 3D joint set."""
    existing_edges = {edge_key(member.start_joint_id, member.end_joint_id) for member in state.members}
    joint_ids = sorted(joint.joint_id for joint in state.joints)
    candidate_edges: list[tuple[int, int]] = []
    for index, start_joint_id in enumerate(joint_ids):
        for end_joint_id in joint_ids[index + 1 :]:
            edge = edge_key(start_joint_id, end_joint_id)
            if edge in existing_edges:
                continue
            candidate_edges.append(edge)
    return tuple(candidate_edges)


def build_space_truss_state_from_edges(
    base_state: SpaceTrussState,
    selected_edges: tuple[tuple[int, int], ...],
) -> SpaceTrussState:
    """Build a concrete 3D state from a fixed joint set and selected edges."""
    joint_ids = {joint.joint_id for joint in base_state.joints}
    included_edges = {edge_key(member.start_joint_id, member.end_joint_id) for member in base_state.members}
    for raw_edge in selected_edges:
        edge = edge_key(raw_edge[0], raw_edge[1])
        if edge[0] not in joint_ids or edge[1] not in joint_ids:
            raise ValueError("Selected edges must reference existing joints.")
        included_edges.add(edge)

    ordered_edges = tuple(sorted(included_edges))
    retained_joint_ids = {joint.joint_id for joint in base_state.joints if joint.support_type != "free"} | {
        base_state.load_joint_id
    }
    retained_joint_ids.update(load.joint_id for load in base_state.additional_loads)
    for edge in ordered_edges:
        retained_joint_ids.update(edge)
    joints = tuple(joint for joint in base_state.joints if joint.joint_id in retained_joint_ids)
    members = tuple(
        SpaceMember(member_id=member_id, start_joint_id=edge[0], end_joint_id=edge[1])
        for member_id, edge in enumerate(ordered_edges)
    )
    return SpaceTrussState(
        span=base_state.span,
        width=base_state.width,
        max_height=base_state.max_height,
        joints=joints,
        members=members,
        load_joint_id=base_state.load_joint_id,
        load_vector=base_state.load_vector,
        additional_loads=base_state.additional_loads,
    )


def _space_roller_axis(joint: SpaceJoint, state: SpaceTrussState) -> Axis:
    """Return a deterministic roller axis for one support joint.

    Args:
        joint: Support joint to classify.
        state: Space-truss state containing the joint.

    Returns:
        Axis label used when translating the joint into the shared truss-core
        records.
    """
    del state
    if joint.joint_id in {1, 2}:
        return "z"
    return "y"


def evaluate_space_truss_state(state: SpaceTrussState) -> SpaceTrussEvaluation:
    """Evaluate one 3D state with the lazy TrussMe adapter.

    Args:
        state: Space-truss state to evaluate.

    Returns:
        Structural evaluation or failure record for ``state``.

    Raises:
        design_research_problems.MissingOptionalDependencyError: If the optional
            real evaluator dependency is unavailable.
    """
    if not state.joints:
        return build_space_truss_failure(state, "At least one joint is required.")

    joint_records = tuple(
        TrussJointRecord(
            joint_id=joint.joint_id,
            coordinates=(joint.x, joint.y, joint.z),
            support_type=joint.support_type,
            roller_axis=_space_roller_axis(joint, state),
        )
        for joint in state.joints
    )
    member_pairs = tuple(
        edge_key(member.start_joint_id, member.end_joint_id)
        for member in sorted(state.members, key=lambda item: item.member_id)
    )
    load = TrussLoadRecord(joint_id=state.load_joint_id, vector=state.load_vector)
    additional_loads = tuple(
        TrussLoadRecord(joint_id=load_value.joint_id, vector=load_value.vector) for load_value in state.additional_loads
    )
    try:
        metrics = evaluate_truss_records(joint_records, member_pairs, load, additional_loads)
        return SpaceTrussEvaluation(
            mass=metrics.mass,
            fos=metrics.fos,
            fos_buckling=metrics.fos_buckling,
            fos_yielding=metrics.fos_yielding,
            deflection=metrics.deflection,
            number_of_joints=len(state.joints),
            number_of_members=len(state.members),
            is_feasible=metrics.fos >= 1.0,
            failure_reason=None,
        )
    except numpy.linalg.LinAlgError as exc:
        return build_space_truss_failure(state, f"Linear solve failed: {exc}")
    except (IndexError, ValueError, KeyError) as exc:
        return build_space_truss_failure(state, str(exc))
    except Exception as exc:  # pragma: no cover - defensive optional integration guard.
        from design_research_problems._exceptions import MissingOptionalDependencyError

        if isinstance(exc, MissingOptionalDependencyError):
            raise
        return build_space_truss_failure(state, f"{type(exc).__name__}: {exc}")


def active_joint_ids(state: SpaceTrussState) -> set[int]:
    """Return the joint IDs touched by supports, the load joint, or active members.

    Args:
        state: Space truss state to inspect.

    Returns:
        Set of joint IDs that participate in the active load path.
    """
    active_ids = {joint.joint_id for joint in state.joints if joint.support_type != "free"} | {state.load_joint_id}
    for member in state.members:
        active_ids.add(member.start_joint_id)
        active_ids.add(member.end_joint_id)
    return active_ids


def adjacency_map(state: SpaceTrussState) -> dict[int, set[int]]:
    """Return an undirected adjacency map for the state's members.

    Args:
        state: Space truss state to inspect.

    Returns:
        Mapping of joint IDs to neighboring joint IDs.
    """
    joint_ids = {joint.joint_id for joint in state.joints}
    edges = tuple(edge_key(member.start_joint_id, member.end_joint_id) for member in state.members)
    return build_adjacency(joint_ids, edges)


__all__ = [
    "SpaceJoint",
    "SpaceLoad",
    "SpaceMember",
    "SpaceTrussEvaluation",
    "SpaceTrussState",
    "active_joint_ids",
    "adjacency_map",
    "build_seed_space_truss_state",
    "build_space_truss_failure",
    "build_space_truss_state_from_edges",
    "candidate_space_truss_points",
    "enumerate_space_truss_candidate_edges",
    "evaluate_space_truss_state",
    "expand_space_truss_candidate_joints",
]
