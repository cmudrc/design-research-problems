"""Seed grammar problem backed by a lazy TrussMe adapter."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal, SupportsFloat, cast

import numpy

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.problems._grammar import GrammarProblem
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


@dataclass(frozen=True)
class AddJoint:
    """Add one free joint."""

    x: float
    """Planar x-coordinate for the new joint."""
    y: float
    """Planar y-coordinate for the new joint."""


@dataclass(frozen=True)
class AddMember:
    """Add one member."""

    start_joint_id: int
    """Identifier of the first endpoint joint."""
    end_joint_id: int
    """Identifier of the second endpoint joint."""


@dataclass(frozen=True)
class RemoveMember:
    """Remove one member by ID."""

    member_id: int
    """Identifier of the member to remove."""


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


class PlanarTrussSpanProblem(GrammarProblem):
    """A small topology grammar for planar truss exploration."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        span: float = 10.0,
        max_height: float = 5.0,
        load_magnitude: float = 1_000.0,
    ) -> None:
        """Initialize the seed planar truss grammar problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            span: Support-to-support span.
            max_height: Maximum design envelope height.
            load_magnitude: Downward point-load magnitude.
        """
        super().__init__(metadata=metadata, statement_markdown=statement_markdown)
        self.span = span
        self.max_height = max_height
        self.load_magnitude = load_magnitude

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest, statement_markdown: str) -> PlanarTrussSpanProblem:
        """Construct the seed grammar problem from packaged parameters.

        Args:
            manifest: Parsed packaged manifest.
            statement_markdown: Human-readable problem statement.

        Returns:
            Initialized grammar problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=statement_markdown,
            span=_coerce_float(manifest.parameters.get("span", 10.0)),
            max_height=_coerce_float(manifest.parameters.get("max_height", 5.0)),
            load_magnitude=_coerce_float(manifest.parameters.get("load_magnitude", 1_000.0)),
        )

    def initial_state(self) -> PlanarTrussState:
        """Return the canonical starting topology.

        Returns:
            Initial state containing supports, a load joint, and no members.
        """
        return PlanarTrussState(
            span=self.span,
            max_height=self.max_height,
            joints=(
                PlanarJoint(joint_id=0, x=0.0, y=0.0, support_type="pinned"),
                PlanarJoint(joint_id=1, x=self.span, y=0.0, support_type="roller"),
                PlanarJoint(joint_id=2, x=self.span / 2.0, y=self.max_height, support_type="free"),
            ),
            members=(),
            load_joint_id=2,
            load_vector=(0.0, -self.load_magnitude, 0.0),
        )

    def enumerate_actions(self, state: object) -> tuple[object, ...]:
        """Return deterministic add/remove actions.

        Args:
            state: Current grammar state.

        Returns:
            Available actions in deterministic order.
        """
        typed_state = _coerce_state(state)
        actions: list[object] = []
        candidate_points = (
            (typed_state.span * 0.25, typed_state.max_height * 0.5),
            (typed_state.span * 0.50, typed_state.max_height * 0.5),
            (typed_state.span * 0.75, typed_state.max_height * 0.5),
        )
        occupied = {(joint.x, joint.y) for joint in typed_state.joints}
        for x_value, y_value in candidate_points:
            if (x_value, y_value) not in occupied:
                actions.append(AddJoint(x=x_value, y=y_value))

        existing_edges = {_edge_key(member.start_joint_id, member.end_joint_id) for member in typed_state.members}
        joint_ids = [joint.joint_id for joint in typed_state.joints]
        for start_joint_id, end_joint_id in combinations(joint_ids, 2):
            if _edge_key(start_joint_id, end_joint_id) not in existing_edges:
                actions.append(AddMember(start_joint_id=start_joint_id, end_joint_id=end_joint_id))

        for member in typed_state.members:
            actions.append(RemoveMember(member_id=member.member_id))

        return tuple(actions)

    def apply_action(self, state: object, action: object) -> PlanarTrussState:
        """Apply one action and return a new immutable state.

        Args:
            state: Current grammar state.
            action: Action to apply.

        Returns:
            Updated grammar state.

        Raises:
            TypeError: If the action type is unsupported.
            ValueError: If the action would create an invalid state.
        """
        typed_state = _coerce_state(state)
        if isinstance(action, AddJoint):
            if any(joint.x == action.x and joint.y == action.y for joint in typed_state.joints):
                raise ValueError("Duplicate joint coordinates are not allowed.")
            next_joint_id = max((joint.joint_id for joint in typed_state.joints), default=-1) + 1
            new_joint = PlanarJoint(joint_id=next_joint_id, x=action.x, y=action.y, support_type="free")
            return PlanarTrussState(
                span=typed_state.span,
                max_height=typed_state.max_height,
                joints=tuple((*typed_state.joints, new_joint)),
                members=typed_state.members,
                load_joint_id=typed_state.load_joint_id,
                load_vector=typed_state.load_vector,
            )

        if isinstance(action, AddMember):
            if action.start_joint_id == action.end_joint_id:
                raise ValueError("Members cannot connect a joint to itself.")
            joint_ids = {joint.joint_id for joint in typed_state.joints}
            if action.start_joint_id not in joint_ids or action.end_joint_id not in joint_ids:
                raise ValueError("Members must reference existing joints.")
            edge = _edge_key(action.start_joint_id, action.end_joint_id)
            if any(_edge_key(member.start_joint_id, member.end_joint_id) == edge for member in typed_state.members):
                raise ValueError("Duplicate members are not allowed.")
            next_member_id = max((member.member_id for member in typed_state.members), default=-1) + 1
            new_member = PlanarMember(
                member_id=next_member_id,
                start_joint_id=action.start_joint_id,
                end_joint_id=action.end_joint_id,
            )
            return PlanarTrussState(
                span=typed_state.span,
                max_height=typed_state.max_height,
                joints=typed_state.joints,
                members=tuple((*typed_state.members, new_member)),
                load_joint_id=typed_state.load_joint_id,
                load_vector=typed_state.load_vector,
            )

        if isinstance(action, RemoveMember):
            if all(member.member_id != action.member_id for member in typed_state.members):
                raise ValueError("Unknown member_id.")
            return PlanarTrussState(
                span=typed_state.span,
                max_height=typed_state.max_height,
                joints=typed_state.joints,
                members=tuple(member for member in typed_state.members if member.member_id != action.member_id),
                load_joint_id=typed_state.load_joint_id,
                load_vector=typed_state.load_vector,
            )

        raise TypeError(f"Unsupported action type: {type(action)!r}")

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
