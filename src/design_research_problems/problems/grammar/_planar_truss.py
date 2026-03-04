"""Seed grammar problem backed by a lazy TrussMe adapter."""

from __future__ import annotations

from itertools import combinations
from typing import SupportsFloat, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.planar_truss import (
    PlanarJoint,
    PlanarLoad,
    PlanarMember,
    PlanarTrussEvaluation,
    PlanarTrussState,
)
from design_research_problems.problems._domains.planar_truss import (
    edge_key as _edge_key,
)
from design_research_problems.problems._domains.planar_truss import (
    evaluate_planar_truss_state as _evaluate_planar_truss_state,
)
from design_research_problems.problems._domains.planar_truss import (
    float_matches as _float_matches,
)
from design_research_problems.problems._domains.planar_truss import (
    member_lookup as _member_lookup,
)
from design_research_problems.problems._domains.planar_truss import (
    mirrored_edge as _mirrored_edge,
)
from design_research_problems.problems._domains.planar_truss import (
    point_in_collection as _point_in_collection,
)
from design_research_problems.problems._domains.planar_truss import (
    roofline_y as _roofline_y,
)
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems._metadata import ProblemMetadata


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
        """Add one mirrored pair of joints and return the new immutable state.

        Args:
            state: Current grammar state.
            left_x: X-coordinate for the left-side joint.
            left_y: Y-coordinate for the left-side joint.
            right_x: X-coordinate for the mirrored right-side joint.
            right_y: Y-coordinate for the mirrored right-side joint.

        Returns:
            Updated grammar state.

        Raises:
            ValueError: If the action would violate symmetry or reuse coordinates.
        """
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
        """Add one member and return the new immutable state.

        Args:
            state: Current grammar state.
            start_joint_id: First joint connected by the member.
            end_joint_id: Second joint connected by the member.

        Returns:
            Updated grammar state.

        Raises:
            ValueError: If the member is invalid, duplicated, or breaks symmetry.
        """
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
        """Remove one member and its mirrored counterpart when symmetry is enforced.

        Args:
            state: Current grammar state.
            member_id: Identifier of the member to remove.

        Returns:
            Updated grammar state.

        Raises:
            ValueError: If the target member is missing or the symmetric state is inconsistent.
        """
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
        return _evaluate_planar_truss_state(typed_state)
