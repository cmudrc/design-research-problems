"""Grammar problem for MATLAB Truss Analysis Program design mechanics."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import SupportsFloat, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.truss_ap import (
    TrussAPEvaluation,
    TrussAPJoint,
    TrussAPLoad,
    TrussAPMember,
    TrussAPState,
    TrussLoadDirection,
    build_default_truss_ap_state,
    clear_truss_load,
    evaluate_truss_ap_state,
    resolve_truss_load,
    truss_member_exists,
)
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems._metadata import ProblemMetadata


def _coerce_float(value: object) -> float:
    """Convert one manifest value into ``float``.

    Args:
        value: Raw manifest value.

    Returns:
        Float-converted value.
    """
    return float(cast(SupportsFloat, value))


def _coerce_int(value: object) -> int:
    """Convert one manifest value into ``int``.

    Args:
        value: Raw manifest value.

    Returns:
        Int-converted value.
    """
    return int(cast(int, value))


def _coerce_bool(value: object) -> bool:
    """Convert one manifest value into ``bool``.

    Args:
        value: Raw manifest value.

    Returns:
        Bool-converted value.
    """
    return bool(value)


def _coerce_points(raw_values: object) -> tuple[tuple[float, float], ...]:
    """Convert a manifest value into ``(x, y)`` point pairs.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Tuple of coordinate pairs.

    Raises:
        TypeError: If any point is invalid.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of 2-item coordinate pairs.")
    points: list[tuple[float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 2:
            raise TypeError("Each candidate point must contain exactly two values.")
        x_value, y_value = raw_value
        points.append((_coerce_float(x_value), _coerce_float(y_value)))
    return tuple(points)


def _coerce_float_tuple(raw_values: object) -> tuple[float, ...]:
    """Convert a manifest value into a tuple of floats.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Float tuple.

    Raises:
        TypeError: If the value is not a sequence.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of floats.")
    return tuple(_coerce_float(value) for value in raw_values)


def _coerce_state(state: object) -> TrussAPState:
    """Validate that an incoming state is a ``TrussAPState``.

    Args:
        state: Arbitrary object supplied by callers.

    Returns:
        Validated state.

    Raises:
        TypeError: If ``state`` is invalid.
    """
    if not isinstance(state, TrussAPState):
        raise TypeError("state must be a TrussAPState")
    return state


def _point_key(x_value: float, y_value: float) -> tuple[float, float]:
    """Return canonical occupancy key for one coordinate.

    Args:
        x_value: x coordinate.
        y_value: y coordinate.

    Returns:
        Occupancy key tuple.
    """
    return (x_value, y_value)


def _edge_key(joint_a: int, joint_b: int) -> tuple[int, int]:
    """Return canonical undirected edge key.

    Args:
        joint_a: First joint identifier.
        joint_b: Second joint identifier.

    Returns:
        Sorted edge key.
    """
    return (joint_a, joint_b) if joint_a < joint_b else (joint_b, joint_a)


def _joint_id_set(state: TrussAPState) -> set[int]:
    """Return the current joint identifier set for one state.

    Args:
        state: Input truss state.

    Returns:
        Joint IDs present in the state.
    """
    return {joint.joint_id for joint in state.joints}


class TrussAPGrammarProblem(GrammarProblem[TrussAPState, TrussAPEvaluation]):
    """Bounded grammar over MATLAB Truss Analysis Program design mechanics."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        candidate_points: tuple[tuple[float, float], ...] = (),
        max_editable_joints: int = 16,
        default_member_size_index: int = 5,
        load_magnitude_options_n: tuple[float, ...] = (50_000.0, 200_000.0, 250_000.0),
        enable_bad_zone: bool = False,
    ) -> None:
        """Initialize the Truss AP grammar problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            candidate_points: Finite candidate coordinates for editable joints.
            max_editable_joints: Cap on editable joints.
            default_member_size_index: Default size index for new members.
            load_magnitude_options_n: Allowed load magnitudes for load edits.
            enable_bad_zone: Whether to enforce restricted-zone constraints.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.candidate_points = candidate_points
        self.max_editable_joints = max_editable_joints
        self.default_member_size_index = default_member_size_index
        self.load_magnitude_options_n = load_magnitude_options_n
        self.enable_bad_zone = enable_bad_zone

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> TrussAPGrammarProblem:
        """Construct the grammar problem from packaged parameters.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized grammar problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            candidate_points=_coerce_points(manifest.parameters.get("candidate_points", ())),
            max_editable_joints=_coerce_int(manifest.parameters.get("max_editable_joints", 16)),
            default_member_size_index=_coerce_int(manifest.parameters.get("default_member_size_index", 5)),
            load_magnitude_options_n=_coerce_float_tuple(
                manifest.parameters.get("load_magnitude_options_n", (50_000.0, 200_000.0, 250_000.0))
            ),
            enable_bad_zone=_coerce_bool(manifest.parameters.get("enable_bad_zone", False)),
        )

    def initial_state(self) -> TrussAPState:
        """Return the canonical truss seed state.

        Returns:
            Seed truss state.
        """
        return replace(
            build_default_truss_ap_state(),
            load_magnitude_options_n=self.load_magnitude_options_n,
            enforce_bad_zone=self.enable_bad_zone,
        )

    def evaluate(self, state: TrussAPState) -> TrussAPEvaluation:
        """Evaluate one truss design state.

        Args:
            state: Current design state.

        Returns:
            Structural evaluation metrics.
        """
        typed_state = _coerce_state(state)
        return evaluate_truss_ap_state(typed_state)

    def enumerate_transitions(self, state: TrussAPState) -> tuple[GrammarTransition[TrussAPState], ...]:
        """Return deterministic legal transitions for one truss state.

        Args:
            state: Current design state.

        Returns:
            Deterministic legal transitions.
        """
        typed_state = _coerce_state(state)
        transitions: list[GrammarTransition[TrussAPState]] = []
        occupied = {_point_key(joint.x, joint.y) for joint in typed_state.joints}
        editable_joints = tuple(joint for joint in typed_state.joints if not joint.is_fixed)

        if len(editable_joints) < self.max_editable_joints:
            for x_value, y_value in self.candidate_points:
                if _point_key(x_value, y_value) in occupied:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="add_joint",
                        parameters=(("x", x_value), ("y", y_value)),
                        next_state=self.add_joint(typed_state, x=x_value, y=y_value),
                    )
                )

        for joint in editable_joints:
            for x_value, y_value in self.candidate_points:
                key = _point_key(x_value, y_value)
                if key == _point_key(joint.x, joint.y):
                    continue
                if key in occupied:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="move_joint",
                        parameters=(("joint_id", joint.joint_id), ("x", x_value), ("y", y_value)),
                        next_state=self.move_joint(typed_state, joint_id=joint.joint_id, x=x_value, y=y_value),
                    )
                )

        for joint in editable_joints:
            transitions.append(
                GrammarTransition(
                    rule_name="delete_joint",
                    parameters=(("joint_id", joint.joint_id),),
                    next_state=self.delete_joint(typed_state, joint_id=joint.joint_id),
                )
            )

        existing_edges = {_edge_key(member.start_joint_id, member.end_joint_id) for member in typed_state.members}
        joint_ids = sorted(joint.joint_id for joint in typed_state.joints)
        for start_joint_id, end_joint_id in combinations(joint_ids, 2):
            edge = _edge_key(start_joint_id, end_joint_id)
            if edge in existing_edges:
                continue
            transitions.append(
                GrammarTransition(
                    rule_name="add_member",
                    parameters=(
                        ("start_joint_id", start_joint_id),
                        ("end_joint_id", end_joint_id),
                        ("size_index", self.default_member_size_index),
                    ),
                    next_state=self.add_member(
                        typed_state,
                        start_joint_id=start_joint_id,
                        end_joint_id=end_joint_id,
                        size_index=self.default_member_size_index,
                    ),
                )
            )

        for member in typed_state.members:
            transitions.append(
                GrammarTransition(
                    rule_name="delete_member",
                    parameters=(("member_id", member.member_id),),
                    next_state=self.delete_member(typed_state, member_id=member.member_id),
                )
            )
            if member.size_index > typed_state.size_index_min:
                transitions.append(
                    GrammarTransition(
                        rule_name="set_member_size",
                        parameters=(("member_id", member.member_id), ("size_index", member.size_index - 1)),
                        next_state=self.set_member_size(
                            typed_state,
                            member_id=member.member_id,
                            size_index=member.size_index - 1,
                        ),
                    )
                )
            if member.size_index < typed_state.size_index_max:
                transitions.append(
                    GrammarTransition(
                        rule_name="set_member_size",
                        parameters=(("member_id", member.member_id), ("size_index", member.size_index + 1)),
                        next_state=self.set_member_size(
                            typed_state,
                            member_id=member.member_id,
                            size_index=member.size_index + 1,
                        ),
                    )
                )

        for support_slot, _support_joint_id in enumerate(typed_state.required_support_joint_ids, start=1):
            enabled = typed_state.support_enabled[support_slot - 1]
            transitions.append(
                GrammarTransition(
                    rule_name="set_support_enabled",
                    parameters=(("support_id", support_slot), ("enabled", not enabled)),
                    next_state=self.set_support_enabled(typed_state, support_id=support_slot, enabled=not enabled),
                )
            )

        load_lookup = {(load.joint_id, load.direction): load.magnitude_n for load in typed_state.loads}
        for joint_id in sorted(joint.joint_id for joint in typed_state.joints):
            for direction in ("left", "down", "right", "up"):
                current = load_lookup.get((joint_id, direction))
                for magnitude in typed_state.load_magnitude_options_n:
                    if current == magnitude:
                        continue
                    transitions.append(
                        GrammarTransition(
                            rule_name="set_load",
                            parameters=(
                                ("joint_id", joint_id),
                                ("direction", direction),
                                ("magnitude_n", magnitude),
                            ),
                            next_state=self.set_load(
                                typed_state,
                                joint_id=joint_id,
                                direction=direction,
                                magnitude_n=magnitude,
                            ),
                        )
                    )
                if current is not None:
                    transitions.append(
                        GrammarTransition(
                            rule_name="clear_load",
                            parameters=(("joint_id", joint_id), ("direction", direction)),
                            next_state=self.clear_load(
                                typed_state,
                                joint_id=joint_id,
                                direction=direction,
                            ),
                        )
                    )

        return tuple(transitions)

    def add_joint(self, state: TrussAPState, *, x: float, y: float) -> TrussAPState:
        """Add one editable joint.

        Args:
            state: Current state.
            x: Joint x coordinate.
            y: Joint y coordinate.

        Returns:
            Updated state with one new editable joint.

        Raises:
            ValueError: If placement is invalid.
        """
        typed_state = _coerce_state(state)
        editable_count = sum(1 for joint in typed_state.joints if not joint.is_fixed)
        if editable_count >= self.max_editable_joints:
            raise ValueError("Maximum editable-joint count reached.")

        x_min, x_max, y_min, y_max = typed_state.design_bounds
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            raise ValueError("Joint must lie inside the design bounds.")

        if any(_point_key(joint.x, joint.y) == _point_key(x, y) for joint in typed_state.joints):
            raise ValueError("A joint already exists at those coordinates.")

        next_joint_id = max((joint.joint_id for joint in typed_state.joints), default=0) + 1
        joints = (*typed_state.joints, TrussAPJoint(joint_id=next_joint_id, x=x, y=y, is_fixed=False))
        return replace(typed_state, joints=joints)

    def move_joint(self, state: TrussAPState, *, joint_id: int, x: float, y: float) -> TrussAPState:
        """Move one editable joint.

        Args:
            state: Current state.
            joint_id: Target joint identifier.
            x: New x coordinate.
            y: New y coordinate.

        Returns:
            Updated state with one moved joint.

        Raises:
            ValueError: If move is invalid.
        """
        typed_state = _coerce_state(state)
        target_index = next(
            (index for index, joint in enumerate(typed_state.joints) if joint.joint_id == joint_id),
            None,
        )
        if target_index is None:
            raise ValueError("Unknown joint ID.")

        target = typed_state.joints[target_index]
        if target.is_fixed:
            raise ValueError("Fixed joints cannot be moved.")

        x_min, x_max, y_min, y_max = typed_state.design_bounds
        if not (x_min <= x <= x_max and y_min <= y <= y_max):
            raise ValueError("Joint must lie inside the design bounds.")

        for index, joint in enumerate(typed_state.joints):
            if index == target_index:
                continue
            if _point_key(joint.x, joint.y) == _point_key(x, y):
                raise ValueError("A joint already exists at those coordinates.")

        joints = list(typed_state.joints)
        joints[target_index] = replace(target, x=x, y=y)
        return replace(typed_state, joints=tuple(joints))

    def delete_joint(self, state: TrussAPState, *, joint_id: int) -> TrussAPState:
        """Delete one editable joint and its dependent elements.

        Args:
            state: Current state.
            joint_id: Target joint identifier.

        Returns:
            Updated state with the joint removed.

        Raises:
            ValueError: If the joint is unknown or fixed.
        """
        typed_state = _coerce_state(state)
        target = next((joint for joint in typed_state.joints if joint.joint_id == joint_id), None)
        if target is None:
            raise ValueError("Unknown joint ID.")
        if target.is_fixed:
            raise ValueError("Fixed joints cannot be deleted.")

        joints = tuple(joint for joint in typed_state.joints if joint.joint_id != joint_id)
        members = tuple(
            member
            for member in typed_state.members
            if member.start_joint_id != joint_id and member.end_joint_id != joint_id
        )
        loads = tuple(load for load in typed_state.loads if load.joint_id != joint_id)
        return replace(typed_state, joints=joints, members=members, loads=loads)

    def add_member(
        self,
        state: TrussAPState,
        *,
        start_joint_id: int,
        end_joint_id: int,
        size_index: int,
    ) -> TrussAPState:
        """Add one member between two joints.

        Args:
            state: Current state.
            start_joint_id: First endpoint joint ID.
            end_joint_id: Second endpoint joint ID.
            size_index: Member size index in ``[1, 10]``.

        Returns:
            Updated state with one additional member.

        Raises:
            ValueError: If inputs are invalid.
        """
        typed_state = _coerce_state(state)
        if start_joint_id == end_joint_id:
            raise ValueError("Members cannot connect a joint to itself.")

        joint_lookup = {joint.joint_id: joint for joint in typed_state.joints}
        start = joint_lookup.get(start_joint_id)
        end = joint_lookup.get(end_joint_id)
        if start is None or end is None:
            raise ValueError("Members must reference existing joints.")

        if truss_member_exists(typed_state.members, start_joint_id, end_joint_id):
            raise ValueError("That member already exists.")

        if not (typed_state.size_index_min <= size_index <= typed_state.size_index_max):
            raise ValueError("Member size index is out of bounds.")

        if _point_key(start.x, start.y) == _point_key(end.x, end.y):
            raise ValueError("Members cannot have zero length.")

        next_member_id = max((member.member_id for member in typed_state.members), default=0) + 1
        members = (
            *typed_state.members,
            TrussAPMember(
                member_id=next_member_id,
                start_joint_id=start_joint_id,
                end_joint_id=end_joint_id,
                size_index=size_index,
            ),
        )
        return replace(typed_state, members=members)

    def delete_member(self, state: TrussAPState, *, member_id: int) -> TrussAPState:
        """Delete one member by identifier.

        Args:
            state: Current state.
            member_id: Target member identifier.

        Returns:
            Updated state without the target member.

        Raises:
            ValueError: If member is unknown.
        """
        typed_state = _coerce_state(state)
        if not any(member.member_id == member_id for member in typed_state.members):
            raise ValueError("Unknown member ID.")
        members = tuple(member for member in typed_state.members if member.member_id != member_id)
        return replace(typed_state, members=members)

    def set_member_size(self, state: TrussAPState, *, member_id: int, size_index: int) -> TrussAPState:
        """Set one member's discrete size index.

        Args:
            state: Current state.
            member_id: Target member identifier.
            size_index: New size index in ``[1, 10]``.

        Returns:
            Updated state with one resized member.

        Raises:
            ValueError: If inputs are invalid.
        """
        typed_state = _coerce_state(state)
        if not (typed_state.size_index_min <= size_index <= typed_state.size_index_max):
            raise ValueError("Member size index is out of bounds.")

        members = list(typed_state.members)
        target_index = next((index for index, member in enumerate(members) if member.member_id == member_id), None)
        if target_index is None:
            raise ValueError("Unknown member ID.")

        members[target_index] = replace(members[target_index], size_index=size_index)
        return replace(typed_state, members=tuple(members))

    def set_support_enabled(self, state: TrussAPState, *, support_id: int, enabled: bool) -> TrussAPState:
        """Enable or disable one support joint.

        Args:
            state: Current state.
            support_id: 1-based support slot identifier.
            enabled: Whether to enable that support.

        Returns:
            Updated state with toggled support settings.

        Raises:
            ValueError: If support ID is invalid.
        """
        typed_state = _coerce_state(state)
        support_count = len(typed_state.support_enabled)
        if support_id < 1 or support_id > support_count:
            raise ValueError(f"support_id must be between 1 and {support_count}.")

        support_enabled = list(typed_state.support_enabled)
        support_enabled[support_id - 1] = bool(enabled)
        return replace(typed_state, support_enabled=cast(tuple[bool, bool, bool], tuple(support_enabled)))

    def set_load(
        self,
        state: TrussAPState,
        *,
        joint_id: int,
        direction: TrussLoadDirection,
        magnitude_n: float,
    ) -> TrussAPState:
        """Set one directional point load at one joint.

        Args:
            state: Current state.
            joint_id: Target joint identifier.
            direction: Load direction.
            magnitude_n: Load magnitude in Newtons.

        Returns:
            Updated state with set load.

        Raises:
            ValueError: If load settings are invalid.
        """
        typed_state = _coerce_state(state)
        if joint_id not in _joint_id_set(typed_state):
            raise ValueError("Unknown joint ID.")
        if direction not in {"left", "down", "right", "up"}:
            raise ValueError("direction must be one of left/down/right/up.")
        if magnitude_n not in typed_state.load_magnitude_options_n:
            raise ValueError("Unsupported load magnitude.")
        return resolve_truss_load(
            typed_state,
            joint_id=joint_id,
            direction=direction,
            magnitude_n=magnitude_n,
        )

    def clear_load(self, state: TrussAPState, *, joint_id: int, direction: TrussLoadDirection) -> TrussAPState:
        """Remove one directional load from one joint.

        Args:
            state: Current state.
            joint_id: Target joint identifier.
            direction: Target direction.

        Returns:
            Updated state without the target load.

        Raises:
            ValueError: If joint or direction is invalid.
        """
        typed_state = _coerce_state(state)
        if joint_id not in _joint_id_set(typed_state):
            raise ValueError("Unknown joint ID.")
        if direction not in {"left", "down", "right", "up"}:
            raise ValueError("direction must be one of left/down/right/up.")
        return clear_truss_load(typed_state, joint_id=joint_id, direction=direction)


__all__ = [
    "TrussAPEvaluation",
    "TrussAPGrammarProblem",
    "TrussAPJoint",
    "TrussAPLoad",
    "TrussAPMember",
    "TrussAPState",
]
