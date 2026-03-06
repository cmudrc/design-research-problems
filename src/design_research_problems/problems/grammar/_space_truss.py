"""Seed grammar problem for a bridge-like 3D space truss."""

from __future__ import annotations

from itertools import combinations
from typing import SupportsFloat, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.space_truss import (
    SpaceJoint,
    SpaceLoad,
    SpaceMember,
    SpaceTrussEvaluation,
    SpaceTrussState,
    build_seed_space_truss_state,
    candidate_space_truss_points,
    evaluate_space_truss_state,
)
from design_research_problems.problems._domains.truss_core import edge_key
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems._metadata import ProblemMetadata


def _coerce_float(value: object) -> float:
    """Convert a manifest parameter into ``float``.

    Args:
        value: Value for ``value``.

    Returns:
        Computed result for this callable.
    """
    return float(cast(SupportsFloat, value))


def _coerce_fractional_points_3d(raw_values: object) -> tuple[tuple[float, float, float], ...]:
    """Convert a manifest field into 3D fractional coordinate triples.

    Args:
        raw_values: Value for ``raw_values``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of 3-item coordinate triples.")
    points: list[tuple[float, float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 3:
            raise TypeError("Each candidate point must contain exactly three values.")
        x_value, y_value, z_value = raw_value
        points.append((_coerce_float(x_value), _coerce_float(y_value), _coerce_float(z_value)))
    return tuple(points)


def _coerce_state(state: object) -> SpaceTrussState:
    """Validate that an incoming state is a ``SpaceTrussState``.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    if not isinstance(state, SpaceTrussState):
        raise TypeError("state must be a SpaceTrussState")
    return state


class SpaceTrussSpanProblem(GrammarProblem[SpaceTrussState, SpaceTrussEvaluation]):
    """A bounded 3D truss grammar with explicit joint and member edits."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        span: float = 10.0,
        width: float = 4.0,
        max_height: float = 5.0,
        load_magnitude: float = 1_000.0,
        candidate_point_fractions_3d: tuple[tuple[float, float, float], ...] = (),
    ) -> None:
        """Initialize the packaged 3D space-truss grammar problem.

        Args:
            metadata: Value for ``metadata``.
            statement_markdown: Value for ``statement_markdown``.
            resource_bundle: Value for ``resource_bundle``.
            span: Value for ``span``.
            width: Value for ``width``.
            max_height: Value for ``max_height``.
            load_magnitude: Value for ``load_magnitude``.
            candidate_point_fractions_3d: Value for ``candidate_point_fractions_3d``.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.span = span
        self.width = width
        self.max_height = max_height
        self.load_magnitude = load_magnitude
        self.candidate_point_fractions_3d = candidate_point_fractions_3d

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> SpaceTrussSpanProblem:
        """Construct the grammar problem from packaged parameters.

        Args:
            manifest: Value for ``manifest``.

        Returns:
            Computed result for this callable.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            span=_coerce_float(manifest.parameters.get("span", 10.0)),
            width=_coerce_float(manifest.parameters.get("width", 4.0)),
            max_height=_coerce_float(manifest.parameters.get("max_height", 5.0)),
            load_magnitude=_coerce_float(manifest.parameters.get("load_magnitude", 1_000.0)),
            candidate_point_fractions_3d=_coerce_fractional_points_3d(
                manifest.parameters.get(
                    "candidate_point_fractions_3d",
                    (
                        (0.25, -1.0, 0.5),
                        (0.25, 1.0, 0.5),
                        (0.75, -1.0, 0.5),
                        (0.75, 1.0, 0.5),
                    ),
                )
            ),
        )

    def initial_state(self) -> SpaceTrussState:
        """Return the canonical bridge-like 3D seed state.

        Returns:
            Computed result for this callable.
        """
        return build_seed_space_truss_state(
            span=self.span,
            width=self.width,
            max_height=self.max_height,
            load_magnitude=self.load_magnitude,
        )

    def _candidate_points(self, state: SpaceTrussState) -> tuple[tuple[float, float, float], ...]:
        """Return the configured candidate interior joint coordinates.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        return candidate_space_truss_points(
            state,
            candidate_point_fractions_3d=self.candidate_point_fractions_3d,
        )

    def enumerate_transitions(self, state: SpaceTrussState) -> tuple[GrammarTransition[SpaceTrussState], ...]:
        """Return deterministic add/remove transitions for the current 3D state.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        typed_state = _coerce_state(state)
        transitions: list[GrammarTransition[SpaceTrussState]] = []
        occupied = {(joint.x, joint.y, joint.z) for joint in typed_state.joints}
        for x_value, y_value, z_value in self._candidate_points(typed_state):
            if (x_value, y_value, z_value) in occupied:
                continue
            transitions.append(
                GrammarTransition(
                    rule_name="add_joint",
                    parameters=(("x", x_value), ("y", y_value), ("z", z_value)),
                    next_state=self.add_joint(typed_state, x=x_value, y=y_value, z=z_value),
                )
            )

        existing_edges = {edge_key(member.start_joint_id, member.end_joint_id) for member in typed_state.members}
        for start_joint_id, end_joint_id in combinations(sorted(joint.joint_id for joint in typed_state.joints), 2):
            edge = edge_key(start_joint_id, end_joint_id)
            if edge in existing_edges:
                continue
            transitions.append(
                GrammarTransition(
                    rule_name="add_member",
                    parameters=(("start_joint_id", start_joint_id), ("end_joint_id", end_joint_id)),
                    next_state=self.add_member(
                        typed_state,
                        start_joint_id=start_joint_id,
                        end_joint_id=end_joint_id,
                    ),
                )
            )

        for member in typed_state.members:
            transitions.append(
                GrammarTransition(
                    rule_name="remove_member",
                    parameters=(("member_id", member.member_id),),
                    next_state=self.remove_member(typed_state, member_id=member.member_id),
                )
            )
        return tuple(transitions)

    def add_joint(self, state: SpaceTrussState, *, x: float, y: float, z: float) -> SpaceTrussState:
        """Insert one new free joint inside the configured envelope.

        Args:
            state: Value for ``state``.
            x: Value for ``x``.
            y: Value for ``y``.
            z: Value for ``z``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        if not (0.0 <= x <= typed_state.span):
            raise ValueError("x must lie within the configured span.")
        half_width = typed_state.width / 2.0
        if not (-half_width <= y <= half_width):
            raise ValueError("y must lie within the configured lateral envelope.")
        if not (0.0 <= z <= typed_state.max_height):
            raise ValueError("z must lie within the configured height envelope.")
        if any(joint.x == x and joint.y == y and joint.z == z for joint in typed_state.joints):
            raise ValueError("A joint already exists at those coordinates.")
        next_joint_id = max((joint.joint_id for joint in typed_state.joints), default=-1) + 1
        joints = (*typed_state.joints, SpaceJoint(joint_id=next_joint_id, x=x, y=y, z=z, support_type="free"))
        return SpaceTrussState(
            span=typed_state.span,
            width=typed_state.width,
            max_height=typed_state.max_height,
            joints=joints,
            members=typed_state.members,
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
        )

    def add_member(
        self,
        state: SpaceTrussState,
        *,
        start_joint_id: int,
        end_joint_id: int,
    ) -> SpaceTrussState:
        """Insert one new member between two existing joints.

        Args:
            state: Value for ``state``.
            start_joint_id: Identifier for start joint.
            end_joint_id: Identifier for end joint.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        edge = edge_key(start_joint_id, end_joint_id)
        if edge[0] == edge[1]:
            raise ValueError("Members cannot connect a joint to itself.")
        joint_ids = {joint.joint_id for joint in typed_state.joints}
        if edge[0] not in joint_ids or edge[1] not in joint_ids:
            raise ValueError("Members must reference existing joints.")
        if any(edge_key(member.start_joint_id, member.end_joint_id) == edge for member in typed_state.members):
            raise ValueError("That member already exists.")
        next_member_id = max((member.member_id for member in typed_state.members), default=-1) + 1
        members = (
            *typed_state.members,
            SpaceMember(member_id=next_member_id, start_joint_id=edge[0], end_joint_id=edge[1]),
        )
        return SpaceTrussState(
            span=typed_state.span,
            width=typed_state.width,
            max_height=typed_state.max_height,
            joints=typed_state.joints,
            members=members,
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
        )

    def remove_member(self, state: SpaceTrussState, *, member_id: int) -> SpaceTrussState:
        """Remove one existing member by identifier.

        Args:
            state: Value for ``state``.
            member_id: Identifier for member.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        members = tuple(member for member in typed_state.members if member.member_id != member_id)
        if len(members) == len(typed_state.members):
            raise ValueError(f"Unknown member_id: {member_id}")
        renumbered = tuple(
            SpaceMember(
                member_id=index,
                start_joint_id=member.start_joint_id,
                end_joint_id=member.end_joint_id,
            )
            for index, member in enumerate(members)
        )
        return SpaceTrussState(
            span=typed_state.span,
            width=typed_state.width,
            max_height=typed_state.max_height,
            joints=typed_state.joints,
            members=renumbered,
            load_joint_id=typed_state.load_joint_id,
            load_vector=typed_state.load_vector,
            additional_loads=typed_state.additional_loads,
        )

    def evaluate(self, state: SpaceTrussState) -> SpaceTrussEvaluation:
        """Evaluate one 3D space-truss state.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        return evaluate_space_truss_state(_coerce_state(state))


__all__ = [
    "SpaceJoint",
    "SpaceLoad",
    "SpaceMember",
    "SpaceTrussEvaluation",
    "SpaceTrussSpanProblem",
    "SpaceTrussState",
]
