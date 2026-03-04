"""Internal shared helpers for planar and space truss backends."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Any, Literal

import numpy

from design_research_problems._exceptions import MissingOptionalDependencyError

SupportType = Literal["pinned", "roller", "free"]
Axis = Literal["x", "y", "z"]


@dataclass(frozen=True)
class TrussJointRecord:
    """Internal evaluator record for one joint."""

    joint_id: int
    """Identifier for joint."""
    coordinates: tuple[float, float, float]
    """Stored coordinates value."""
    support_type: SupportType
    """Stored support type value."""
    roller_axis: Axis = "y"
    """Stored roller axis value."""


@dataclass(frozen=True)
class TrussLoadRecord:
    """Internal evaluator record for one point load."""

    joint_id: int
    """Identifier for joint."""
    vector: tuple[float, float, float]
    """Stored vector value."""


@dataclass(frozen=True)
class TrussAnalysisMetrics:
    """Internal structural metrics extracted from ``trussme``."""

    mass: float
    """Stored mass value."""
    fos: float
    """Stored fos value."""
    fos_buckling: float
    """Stored fos buckling value."""
    fos_yielding: float
    """Stored fos yielding value."""
    deflection: float
    """Stored deflection value."""


def edge_key(start_joint_id: int, end_joint_id: int) -> tuple[int, int]:
    """Normalize one undirected edge key.

    Args:
        start_joint_id: Identifier for start joint.
        end_joint_id: Identifier for end joint.

    Returns:
        Computed result for this callable.
    """
    if start_joint_id <= end_joint_id:
        return (start_joint_id, end_joint_id)
    return (end_joint_id, start_joint_id)


def import_trussme(required_for: str = "truss evaluation") -> Any:
    """Import ``trussme`` lazily with a consistent optional-dependency error.

    Args:
        required_for: Value for ``required_for``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    try:
        import trussme
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            f"trussme is required for {required_for}. Install it with: pip install "
            "design-research-problems[grammar] or run: make install-trussme"
        ) from exc
    return trussme


def reachable_joint_ids(adjacency: dict[int, set[int]], start_joint_id: int) -> set[int]:
    """Return the reachable connected component from one start joint.

    Args:
        adjacency: Value for ``adjacency``.
        start_joint_id: Identifier for start joint.

    Returns:
        Computed result for this callable.
    """
    frontier = [start_joint_id]
    reachable: set[int] = set()
    while frontier:
        current = frontier.pop()
        if current in reachable:
            continue
        reachable.add(current)
        frontier.extend(neighbor for neighbor in adjacency.get(current, ()) if neighbor not in reachable)
    return reachable


def build_adjacency(
    joint_ids: set[int],
    members: tuple[tuple[int, int], ...],
) -> dict[int, set[int]]:
    """Return an undirected adjacency map for the supplied joints and members.

    Args:
        joint_ids: Value for ``joint_ids``.
        members: Value for ``members``.

    Returns:
        Computed result for this callable.
    """
    adjacency: dict[int, set[int]] = {joint_id: set() for joint_id in joint_ids}
    for start_joint_id, end_joint_id in members:
        adjacency[start_joint_id].add(end_joint_id)
        adjacency[end_joint_id].add(start_joint_id)
    return adjacency


def evaluate_truss_records(
    joints: tuple[TrussJointRecord, ...],
    members: tuple[tuple[int, int], ...],
    load: TrussLoadRecord,
    additional_loads: tuple[TrussLoadRecord, ...] = (),
    *,
    out_of_plane_axis: Axis | None = None,
) -> TrussAnalysisMetrics:
    """Build, analyze, and summarize one truss via ``trussme``.

    Args:
        joints: Value for ``joints``.
        members: Value for ``members``.
        load: Value for ``load``.
        additional_loads: Value for ``additional_loads``.
        out_of_plane_axis: Value for ``out_of_plane_axis``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    trussme = import_trussme()
    truss = trussme.Truss()
    index_map: dict[int, int] = {}
    for joint in sorted(joints, key=lambda item: item.joint_id):
        coordinates = list(joint.coordinates)
        if joint.support_type == "pinned":
            index = truss.add_pinned_joint(coordinates)
        elif joint.support_type == "roller":
            index = truss.add_roller_joint(coordinates, constrained_axis=joint.roller_axis)
        else:
            index = truss.add_free_joint(coordinates)
        index_map[joint.joint_id] = index

    if out_of_plane_axis is not None:
        truss.add_out_of_plane_support(out_of_plane_axis)

    for start_joint_id, end_joint_id in members:
        truss.add_member(index_map[start_joint_id], index_map[end_joint_id])

    truss.set_load(index_map[load.joint_id], list(load.vector))
    for additional_load in additional_loads:
        truss.set_load(index_map[additional_load.joint_id], list(additional_load.vector))

    try:
        with warnings.catch_warnings():
            # TrussMe emits a benign divide-by-zero RuntimeWarning when a
            # member carries zero axial force, which corresponds to an infinite
            # factor of safety for that member. Keep the metrics while
            # suppressing the noisy external warning.
            warnings.filterwarnings(
                "ignore",
                message="divide by zero encountered in scalar divide",
                category=RuntimeWarning,
                module=r"trussme\.components",
            )
            truss.analyze()
            mass = float(truss.mass)
            fos = float(truss.fos)
            fos_buckling = float(truss.fos_buckling)
            fos_yielding = float(truss.fos_yielding)
            deflection = float(truss.deflection)
    except numpy.linalg.LinAlgError:
        raise

    return TrussAnalysisMetrics(
        mass=mass,
        fos=fos,
        fos_buckling=fos_buckling,
        fos_yielding=fos_yielding,
        deflection=deflection,
    )


__all__ = [
    "Axis",
    "SupportType",
    "TrussAnalysisMetrics",
    "TrussJointRecord",
    "TrussLoadRecord",
    "build_adjacency",
    "edge_key",
    "evaluate_truss_records",
    "import_trussme",
    "reachable_joint_ids",
]
