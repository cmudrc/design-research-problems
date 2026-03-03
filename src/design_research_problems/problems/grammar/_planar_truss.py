"""Seed grammar problem backed by a lazy TrussMe adapter."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal, SupportsFloat, cast

import numpy

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems._metadata import ProblemMetadata

SupportType = Literal["pinned", "roller", "free"]


@dataclass(frozen=True)
class PlanarJoint:
    """One planar joint in the library-owned grammar state."""

    joint_id: int
    """Stable joint identifier within the grammar state."""
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
    """Stable member identifier within the grammar state."""
    start_joint_id: int
    """Identifier of the first endpoint joint."""
    end_joint_id: int
    """Identifier of the second endpoint joint."""


@dataclass(frozen=True)
class PlanarTrussState:
    """Serializable state for the seed planar truss grammar."""

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
class PlanarLoad:
    """One point load applied to one joint."""

    joint_id: int
    """Joint receiving the load."""
    vector: tuple[float, float, float]
    """Applied load vector."""


@dataclass(frozen=True)
class PlanarTrussEvaluation:
    """Structured evaluation result for the seed grammar problem."""

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


def _import_trussme() -> Any:
    """Import ``trussme`` lazily for real grammar evaluation.

    Returns:
        Imported ``trussme`` module.

    Raises:
        MissingOptionalDependencyError: If the optional dependency is not installed.
    """
    try:
        import trussme
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "trussme is required for grammar evaluation. Install it with: pip install "
            "design-research-problems[grammar] or run: make install-trussme"
        ) from exc
    return trussme


def _edge_key(start_joint_id: int, end_joint_id: int) -> tuple[int, int]:
    """Normalize a member edge into an undirected key.

    Args:
        start_joint_id: First endpoint joint ID.
        end_joint_id: Second endpoint joint ID.

    Returns:
        Sorted endpoint pair.
    """
    if start_joint_id <= end_joint_id:
        return (start_joint_id, end_joint_id)
    return (end_joint_id, start_joint_id)


def _coerce_float(value: object) -> float:
    """Convert a manifest parameter value into ``float``.

    Args:
        value: Raw manifest value.

    Returns:
        Float-converted value.
    """
    return float(cast(SupportsFloat, value))


def _coerce_float_tuple(raw_values: object) -> tuple[float, ...]:
    """Convert a manifest value into a tuple of floats.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Tuple of float-converted values.

    Raises:
        TypeError: If the value is not a list or tuple.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of floats.")
    return tuple(_coerce_float(raw_value) for raw_value in raw_values)


def _coerce_fractional_points(raw_values: object) -> tuple[tuple[float, float], ...]:
    """Convert a manifest value into fractional point pairs.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Tuple of two-item ``(x, y)`` coordinate pairs.

    Raises:
        TypeError: If the value is not a sequence of two-item coordinate pairs.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of 2-item coordinate pairs.")
    pairs: list[tuple[float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 2:
            raise TypeError("Each candidate point must contain exactly two values.")
        x_value, y_value = raw_value
        pairs.append((_coerce_float(x_value), _coerce_float(y_value)))
    return tuple(pairs)


def _float_matches(left: float, right: float) -> bool:
    """Return whether two coordinates should be treated as equal.

    Args:
        left: First coordinate value.
        right: Second coordinate value.

    Returns:
        True when the coordinates are effectively equal.
    """
    return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)


def _point_in_collection(points: set[tuple[float, float]], x_value: float, y_value: float) -> bool:
    """Return whether one coordinate pair is already occupied.

    Args:
        points: Existing occupied coordinates.
        x_value: Candidate x-coordinate.
        y_value: Candidate y-coordinate.

    Returns:
        True when one occupied point matches the candidate coordinates.
    """
    return any(_float_matches(px, x_value) and _float_matches(py, y_value) for px, py in points)


def _roofline_y(x_fraction: float, max_height: float) -> float:
    """Return the y-coordinate for a simple gable roof profile.

    Args:
        x_fraction: Horizontal location expressed as a span fraction.
        max_height: Peak roof height.

    Returns:
        Roofline y-coordinate at the requested horizontal location.
    """
    return max_height * (1.0 - abs((2.0 * x_fraction) - 1.0))


def _coerce_state(state: object) -> PlanarTrussState:
    """Validate that an incoming state is a ``PlanarTrussState``.

    Args:
        state: Arbitrary object supplied by the caller.

    Returns:
        The validated grammar state.

    Raises:
        TypeError: If the object is not a ``PlanarTrussState``.
    """
    if not isinstance(state, PlanarTrussState):
        raise TypeError("state must be a PlanarTrussState")
    return state


def _joint_map(state: PlanarTrussState) -> dict[int, PlanarJoint]:
    """Return one ID-indexed joint lookup table.

    Args:
        state: Grammar state to index.

    Returns:
        Mapping of joint IDs to joint records.
    """
    return {joint.joint_id: joint for joint in state.joints}


def _member_lookup(state: PlanarTrussState) -> dict[tuple[int, int], PlanarMember]:
    """Return one edge-indexed member lookup table.

    Args:
        state: Grammar state to index.

    Returns:
        Mapping of normalized member edges to member records.
    """
    return {_edge_key(member.start_joint_id, member.end_joint_id): member for member in state.members}


def _mirrored_joint_id(state: PlanarTrussState, joint_id: int) -> int | None:
    """Return the mirrored joint identifier for one symmetric state.

    Args:
        state: Grammar state that may enforce symmetry.
        joint_id: Joint identifier to mirror.

    Returns:
        Mirrored joint ID, the original ID for non-symmetric states, or ``None`` if unmatched.
    """
    if state.symmetry_axis_x is None:
        return joint_id

    joints = _joint_map(state)
    joint = joints.get(joint_id)
    if joint is None:
        return None

    target_x = (2.0 * state.symmetry_axis_x) - joint.x
    for candidate in state.joints:
        if _float_matches(candidate.x, target_x) and _float_matches(candidate.y, joint.y):
            return candidate.joint_id
    return None


def _mirrored_edge(state: PlanarTrussState, edge: tuple[int, int]) -> tuple[int, int] | None:
    """Return the mirrored edge for one symmetric state.

    Args:
        state: Grammar state that may enforce symmetry.
        edge: Normalized member edge to mirror.

    Returns:
        Mirrored normalized edge, or ``None`` if a mirrored joint cannot be found.
    """
    mirrored_start = _mirrored_joint_id(state, edge[0])
    mirrored_end = _mirrored_joint_id(state, edge[1])
    if mirrored_start is None or mirrored_end is None:
        return None
    return _edge_key(mirrored_start, mirrored_end)


class PlanarTrussSpanProblem(GrammarProblem[PlanarTrussState, PlanarTrussEvaluation]):
    """A small topology grammar for planar truss exploration."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        span: float = 10.0,
        max_height: float = 5.0,
        load_magnitude: float = 1_000.0,
        roof_load_x_fractions: tuple[float, ...] = (),
        candidate_point_fractions: tuple[tuple[float, float], ...] = (),
        enforce_symmetry: bool = False,
    ) -> None:
        """Initialize the seed planar truss grammar problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            span: Support-to-support span.
            max_height: Maximum design envelope height.
            load_magnitude: Downward point-load magnitude.
            roof_load_x_fractions: Optional roofline load locations as span fractions.
            candidate_point_fractions: Optional interior joint locations as span and height fractions.
            enforce_symmetry: Whether edits should preserve left-right symmetry.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.span = span
        self.max_height = max_height
        self.load_magnitude = load_magnitude
        self.roof_load_x_fractions = roof_load_x_fractions
        self.candidate_point_fractions = candidate_point_fractions
        self.enforce_symmetry = enforce_symmetry

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> PlanarTrussSpanProblem:
        """Construct the seed grammar problem from packaged parameters.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized grammar problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            span=_coerce_float(manifest.parameters.get("span", 10.0)),
            max_height=_coerce_float(manifest.parameters.get("max_height", 5.0)),
            load_magnitude=_coerce_float(manifest.parameters.get("load_magnitude", 1_000.0)),
            roof_load_x_fractions=_coerce_float_tuple(manifest.parameters.get("roof_load_x_fractions", ())),
            candidate_point_fractions=_coerce_fractional_points(
                manifest.parameters.get("candidate_point_fractions", ())
            ),
            enforce_symmetry=bool(manifest.parameters.get("enforce_symmetry", False)),
        )

    def initial_state(self) -> PlanarTrussState:
        """Return the canonical starting topology.

        Returns:
            Initial state containing supports, a load joint, and no members.
        """
        joints: list[PlanarJoint] = [
            PlanarJoint(joint_id=0, x=0.0, y=0.0, support_type="pinned"),
            PlanarJoint(joint_id=1, x=self.span, y=0.0, support_type="roller"),
        ]

        if self.roof_load_x_fractions:
            load_joint_ids: list[int] = []
            for index, x_fraction in enumerate(self.roof_load_x_fractions, start=2):
                joints.append(
                    PlanarJoint(
                        joint_id=index,
                        x=self.span * x_fraction,
                        y=_roofline_y(x_fraction, self.max_height),
                        support_type="free",
                    )
                )
                load_joint_ids.append(index)
            load_value = self.load_magnitude / float(len(load_joint_ids))
            load_vector = (0.0, -load_value, 0.0)
            additional_loads = tuple(
                PlanarLoad(joint_id=joint_id, vector=load_vector) for joint_id in load_joint_ids[1:]
            )
            load_joint_id = load_joint_ids[0]
        else:
            joints.append(PlanarJoint(joint_id=2, x=self.span / 2.0, y=self.max_height, support_type="free"))
            load_joint_id = 2
            load_vector = (0.0, -self.load_magnitude, 0.0)
            additional_loads = ()

        return PlanarTrussState(
            span=self.span,
            max_height=self.max_height,
            joints=tuple(joints),
            members=(),
            load_joint_id=load_joint_id,
            load_vector=load_vector,
            additional_loads=additional_loads,
            symmetry_axis_x=self.span / 2.0 if self.enforce_symmetry else None,
        )

    def _candidate_points(self, state: PlanarTrussState) -> tuple[tuple[float, float], ...]:
        """Return the configured candidate interior joint coordinates.

        Args:
            state: Current grammar state.

        Returns:
            Candidate interior joint coordinates in deterministic order.
        """
        if self.candidate_point_fractions:
            return tuple(
                (state.span * x_fraction, state.max_height * y_fraction)
                for x_fraction, y_fraction in self.candidate_point_fractions
            )
        return (
            (state.span * 0.25, state.max_height * 0.5),
            (state.span * 0.50, state.max_height * 0.5),
            (state.span * 0.75, state.max_height * 0.5),
        )

    def enumerate_transitions(self, state: PlanarTrussState) -> tuple[GrammarTransition[PlanarTrussState], ...]:
        """Return deterministic add/remove transitions.

        Args:
            state: Current grammar state.

        Returns:
            Fully specified legal transitions in deterministic order.
        """
        typed_state = _coerce_state(state)
        transitions: list[GrammarTransition[PlanarTrussState]] = []
        candidate_points = self._candidate_points(typed_state)
        occupied = {(joint.x, joint.y) for joint in typed_state.joints}
        if typed_state.symmetry_axis_x is None:
            for x_value, y_value in candidate_points:
                if not _point_in_collection(occupied, x_value, y_value):
                    transitions.append(
                        GrammarTransition(
                            rule_name="add_joint",
                            parameters=(("x", x_value), ("y", y_value)),
                            next_state=self.add_joint(typed_state, x=x_value, y=y_value),
                        )
                    )
        else:
            processed_points: set[tuple[float, float]] = set()
            for x_value, y_value in candidate_points:
                if any(_float_matches(px, x_value) and _float_matches(py, y_value) for px, py in processed_points):
                    continue
                if _float_matches(x_value, typed_state.symmetry_axis_x):
                    processed_points.add((x_value, y_value))
                    if not _point_in_collection(occupied, x_value, y_value):
                        transitions.append(
                            GrammarTransition(
                                rule_name="add_joint",
                                parameters=(("x", x_value), ("y", y_value)),
                                next_state=self.add_joint(typed_state, x=x_value, y=y_value),
                            )
                        )
                    continue

                mirrored_x = (2.0 * typed_state.symmetry_axis_x) - x_value
                processed_points.add((x_value, y_value))
                processed_points.add((mirrored_x, y_value))
                if _point_in_collection(occupied, x_value, y_value) or _point_in_collection(
                    occupied, mirrored_x, y_value
                ):
                    continue
                left_x, right_x = sorted((x_value, mirrored_x))
                transitions.append(
                    GrammarTransition(
                        rule_name="add_joint_pair",
                        parameters=(
                            ("left_x", left_x),
                            ("left_y", y_value),
                            ("right_x", right_x),
                            ("right_y", y_value),
                        ),
                        next_state=self.add_joint_pair(
                            typed_state,
                            left_x=left_x,
                            left_y=y_value,
                            right_x=right_x,
                            right_y=y_value,
                        ),
                    )
                )

        existing_edges = {_edge_key(member.start_joint_id, member.end_joint_id) for member in typed_state.members}
        joint_ids = [joint.joint_id for joint in typed_state.joints]
        for start_joint_id, end_joint_id in combinations(joint_ids, 2):
            edge = _edge_key(start_joint_id, end_joint_id)
            if edge in existing_edges:
                continue
            if typed_state.symmetry_axis_x is not None:
                mirrored_edge = _mirrored_edge(typed_state, edge)
                if mirrored_edge is None:
                    continue
                if edge != min(edge, mirrored_edge):
                    continue
                if mirrored_edge != edge and mirrored_edge in existing_edges:
                    continue
            transitions.append(
                GrammarTransition(
                    rule_name="add_member",
                    parameters=(("start_joint_id", edge[0]), ("end_joint_id", edge[1])),
                    next_state=self.add_member(
                        typed_state,
                        start_joint_id=edge[0],
                        end_joint_id=edge[1],
                    ),
                )
            )

        for member in typed_state.members:
            if typed_state.symmetry_axis_x is not None:
                edge = _edge_key(member.start_joint_id, member.end_joint_id)
                mirrored_edge = _mirrored_edge(typed_state, edge)
                if mirrored_edge is None:
                    continue
                if edge != min(edge, mirrored_edge):
                    continue
            transitions.append(
                GrammarTransition(
                    rule_name="remove_member",
                    parameters=(("member_id", member.member_id),),
                    next_state=self.remove_member(typed_state, member_id=member.member_id),
                )
            )

        return tuple(transitions)

    def add_joint(self, state: PlanarTrussState, *, x: float, y: float) -> PlanarTrussState:
        """Add one free joint and return the new immutable state.

        Args:
            state: Current grammar state.
            x: Planar x-coordinate for the new joint.
            y: Planar y-coordinate for the new joint.

        Returns:
            Updated grammar state.

        Raises:
            ValueError: If the action would create an invalid state.
        """
        typed_state = _coerce_state(state)
        if typed_state.symmetry_axis_x is not None and not _float_matches(x, typed_state.symmetry_axis_x):
            raise ValueError("Symmetric states can only add single joints on the symmetry axis.")
        if any(joint.x == x and joint.y == y for joint in typed_state.joints):
            raise ValueError("Duplicate joint coordinates are not allowed.")
        next_joint_id = max((joint.joint_id for joint in typed_state.joints), default=-1) + 1
        new_joint = PlanarJoint(joint_id=next_joint_id, x=x, y=y, support_type="free")
        return PlanarTrussState(
            span=typed_state.span,
            max_height=typed_state.max_height,
            joints=tuple((*typed_state.joints, new_joint)),
            members=typed_state.members,
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
            symmetry_axis_x=typed_state.symmetry_axis_x,
        )

    def add_joint_pair(
        self,
        state: PlanarTrussState,
        *,
        left_x: float,
        left_y: float,
        right_x: float,
        right_y: float,
    ) -> PlanarTrussState:
        """Add one mirrored pair of joints and return the new immutable state."""
        typed_state = _coerce_state(state)
        if typed_state.symmetry_axis_x is None:
            raise ValueError("AddJointPair requires a symmetric state.")
        expected_mirror_x = (2.0 * typed_state.symmetry_axis_x) - left_x
        if not _float_matches(expected_mirror_x, right_x) or not _float_matches(left_y, right_y):
            raise ValueError("AddJointPair coordinates must mirror across the symmetry axis.")
        occupied = {(joint.x, joint.y) for joint in typed_state.joints}
        if any(
            _point_in_collection(occupied, x_value, y_value)
            for x_value, y_value in ((left_x, left_y), (right_x, right_y))
        ):
            raise ValueError("Duplicate joint coordinates are not allowed.")
        next_joint_id = max((joint.joint_id for joint in typed_state.joints), default=-1) + 1
        new_left_joint = PlanarJoint(joint_id=next_joint_id, x=left_x, y=left_y, support_type="free")
        new_right_joint = PlanarJoint(
            joint_id=next_joint_id + 1,
            x=right_x,
            y=right_y,
            support_type="free",
        )
        return PlanarTrussState(
            span=typed_state.span,
            max_height=typed_state.max_height,
            joints=tuple((*typed_state.joints, new_left_joint, new_right_joint)),
            members=typed_state.members,
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
            symmetry_axis_x=typed_state.symmetry_axis_x,
        )

    def add_member(
        self,
        state: PlanarTrussState,
        *,
        start_joint_id: int,
        end_joint_id: int,
    ) -> PlanarTrussState:
        """Add one member and return the new immutable state."""
        typed_state = _coerce_state(state)
        if start_joint_id == end_joint_id:
            raise ValueError("Members cannot connect a joint to itself.")
        joint_ids = {joint.joint_id for joint in typed_state.joints}
        if start_joint_id not in joint_ids or end_joint_id not in joint_ids:
            raise ValueError("Members must reference existing joints.")
        edge = _edge_key(start_joint_id, end_joint_id)
        existing_lookup = _member_lookup(typed_state)
        if edge in existing_lookup:
            raise ValueError("Duplicate members are not allowed.")
        next_member_id = max((member.member_id for member in typed_state.members), default=-1) + 1
        edges_to_add = [edge]
        if typed_state.symmetry_axis_x is not None:
            mirrored_edge = _mirrored_edge(typed_state, edge)
            if mirrored_edge is None:
                raise ValueError("Symmetric states require mirrored joints before adding members.")
            if mirrored_edge in existing_lookup:
                raise ValueError("Duplicate members are not allowed.")
            if mirrored_edge != edge:
                edges_to_add.append(mirrored_edge)
        new_members = tuple(
            PlanarMember(
                member_id=next_member_id + index,
                start_joint_id=member_edge[0],
                end_joint_id=member_edge[1],
            )
            for index, member_edge in enumerate(edges_to_add)
        )
        return PlanarTrussState(
            span=typed_state.span,
            max_height=typed_state.max_height,
            joints=typed_state.joints,
            members=tuple((*typed_state.members, *new_members)),
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
            symmetry_axis_x=typed_state.symmetry_axis_x,
        )

    def remove_member(self, state: PlanarTrussState, *, member_id: int) -> PlanarTrussState:
        """Remove one member and its mirrored counterpart when symmetry is enforced."""
        typed_state = _coerce_state(state)
        existing_lookup = _member_lookup(typed_state)
        target_member = next((member for member in typed_state.members if member.member_id == member_id), None)
        if target_member is None:
            raise ValueError("Unknown member_id.")
        removable_edges = {_edge_key(target_member.start_joint_id, target_member.end_joint_id)}
        if typed_state.symmetry_axis_x is not None:
            mirrored_edge = _mirrored_edge(typed_state, next(iter(removable_edges)))
            if mirrored_edge is None:
                raise ValueError("Symmetric states require mirrored joints before removing members.")
            if mirrored_edge in existing_lookup:
                removable_edges.add(mirrored_edge)
        return PlanarTrussState(
            span=typed_state.span,
            max_height=typed_state.max_height,
            joints=typed_state.joints,
            members=tuple(
                member
                for member in typed_state.members
                if _edge_key(member.start_joint_id, member.end_joint_id) not in removable_edges
            ),
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
            symmetry_axis_x=typed_state.symmetry_axis_x,
        )

    def evaluate(self, state: object) -> PlanarTrussEvaluation:
        """Evaluate one state with the lazy TrussMe adapter.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Structured evaluation metrics and feasibility status.

        Raises:
            MissingOptionalDependencyError: If ``trussme`` is not installed.
        """
        typed_state = _coerce_state(state)
        if not typed_state.members:
            return self._failure(typed_state, "At least one member is required.")

        try:
            trussme = _import_trussme()
            truss = trussme.Truss()
            index_map: dict[int, int] = {}
            for joint in sorted(typed_state.joints, key=lambda item: item.joint_id):
                coordinates = [joint.x, joint.y, 0.0]
                if joint.support_type == "pinned":
                    index = truss.add_pinned_joint(coordinates)
                elif joint.support_type == "roller":
                    index = truss.add_roller_joint(coordinates)
                else:
                    index = truss.add_free_joint(coordinates)
                index_map[joint.joint_id] = index

            truss.add_out_of_plane_support("z")
            for member in sorted(typed_state.members, key=lambda item: item.member_id):
                truss.add_member(index_map[member.start_joint_id], index_map[member.end_joint_id])

            truss.set_load(index_map[typed_state.load_joint_id], list(typed_state.load_vector))
            for load in typed_state.additional_loads:
                truss.set_load(index_map[load.joint_id], list(load.vector))
            truss.analyze()
            fos = float(truss.fos)
            return PlanarTrussEvaluation(
                mass=float(truss.mass),
                fos=fos,
                fos_buckling=float(truss.fos_buckling),
                fos_yielding=float(truss.fos_yielding),
                deflection=float(truss.deflection),
                number_of_joints=len(typed_state.joints),
                number_of_members=len(typed_state.members),
                is_feasible=fos >= 1.0,
                failure_reason=None,
            )
        except numpy.linalg.LinAlgError as exc:
            return self._failure(typed_state, f"Linear solve failed: {exc}")
        except (IndexError, ValueError, KeyError) as exc:
            return self._failure(typed_state, str(exc))
        except MissingOptionalDependencyError:
            raise
        except Exception as exc:  # pragma: no cover - defensive guard for optional integration.
            return self._failure(typed_state, f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _failure(state: PlanarTrussState, reason: str) -> PlanarTrussEvaluation:
        """Build a deterministic infeasible evaluation payload.

        Args:
            state: Grammar state that failed evaluation.
            reason: Human-readable failure reason.

        Returns:
            Infeasible evaluation result with zeroed metrics.
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
