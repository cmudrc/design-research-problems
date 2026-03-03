"""Shared backend helpers for planar truss states and evaluation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Literal

import numpy

from design_research_problems._exceptions import MissingOptionalDependencyError

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
    """Normalize a member edge into an undirected key."""
    if start_joint_id <= end_joint_id:
        return (start_joint_id, end_joint_id)
    return (end_joint_id, start_joint_id)


def float_matches(left: float, right: float) -> bool:
    """Return whether two coordinates should be treated as equal."""
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def point_in_collection(points: set[tuple[float, float]], x_value: float, y_value: float) -> bool:
    """Return whether one coordinate pair is already occupied."""
    return any(float_matches(px, x_value) and float_matches(py, y_value) for px, py in points)


def roofline_y(x_fraction: float, max_height: float) -> float:
    """Return the y-coordinate for a simple gable roof profile."""
    return max_height * (1.0 - abs((2.0 * x_fraction) - 1.0))


def joint_map(state: PlanarTrussState) -> dict[int, PlanarJoint]:
    """Return one ID-indexed joint lookup table."""
    return {joint.joint_id: joint for joint in state.joints}


def member_lookup(state: PlanarTrussState) -> dict[tuple[int, int], PlanarMember]:
    """Return one edge-indexed member lookup table."""
    return {edge_key(member.start_joint_id, member.end_joint_id): member for member in state.members}


def mirrored_joint_id(state: PlanarTrussState, joint_id: int) -> int | None:
    """Return the mirrored joint identifier for one symmetric state."""
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
    """Return the mirrored edge for one symmetric state."""
    mirrored_start = mirrored_joint_id(state, edge[0])
    mirrored_end = mirrored_joint_id(state, edge[1])
    if mirrored_start is None or mirrored_end is None:
        return None
    return edge_key(mirrored_start, mirrored_end)


def build_planar_truss_failure(state: PlanarTrussState, reason: str) -> PlanarTrussEvaluation:
    """Build a deterministic infeasible evaluation payload."""
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


def _import_trussme() -> Any:
    """Import ``trussme`` lazily for real planar-truss evaluation."""
    try:
        import trussme
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "trussme is required for grammar evaluation. Install it with: pip install "
            "design-research-problems[grammar] or run: make install-trussme"
        ) from exc
    return trussme


def evaluate_planar_truss_state(state: PlanarTrussState) -> PlanarTrussEvaluation:
    """Evaluate one state with the lazy TrussMe adapter."""
    if not state.members:
        return build_planar_truss_failure(state, "At least one member is required.")

    try:
        trussme = _import_trussme()
        truss = trussme.Truss()
        index_map: dict[int, int] = {}
        for joint in sorted(state.joints, key=lambda item: item.joint_id):
            coordinates = [joint.x, joint.y, 0.0]
            if joint.support_type == "pinned":
                index = truss.add_pinned_joint(coordinates)
            elif joint.support_type == "roller":
                index = truss.add_roller_joint(coordinates)
            else:
                index = truss.add_free_joint(coordinates)
            index_map[joint.joint_id] = index

        truss.add_out_of_plane_support("z")
        for member in sorted(state.members, key=lambda item: item.member_id):
            truss.add_member(index_map[member.start_joint_id], index_map[member.end_joint_id])

        truss.set_load(index_map[state.load_joint_id], list(state.load_vector))
        for load in state.additional_loads:
            truss.set_load(index_map[load.joint_id], list(load.vector))
        truss.analyze()
        fos = float(truss.fos)
        return PlanarTrussEvaluation(
            mass=float(truss.mass),
            fos=fos,
            fos_buckling=float(truss.fos_buckling),
            fos_yielding=float(truss.fos_yielding),
            deflection=float(truss.deflection),
            number_of_joints=len(state.joints),
            number_of_members=len(state.members),
            is_feasible=fos >= 1.0,
            failure_reason=None,
        )
    except numpy.linalg.LinAlgError as exc:
        return build_planar_truss_failure(state, f"Linear solve failed: {exc}")
    except (IndexError, ValueError, KeyError) as exc:
        return build_planar_truss_failure(state, str(exc))
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:  # pragma: no cover - defensive guard for optional integration.
        return build_planar_truss_failure(state, f"{type(exc).__name__}: {exc}")


__all__ = [
    "PlanarJoint",
    "PlanarLoad",
    "PlanarMember",
    "PlanarTrussEvaluation",
    "PlanarTrussState",
    "SupportType",
    "build_planar_truss_failure",
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
