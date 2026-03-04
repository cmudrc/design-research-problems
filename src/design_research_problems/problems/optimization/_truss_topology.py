"""Domain-first optimization wrappers for fixed-joint planar truss topologies."""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Literal, cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.planar_truss import (
    PlanarJoint,
    PlanarTrussState,
    build_planar_truss_state_from_edges,
    build_seed_planar_truss_state,
    candidate_planar_truss_points,
    edge_key,
    enumerate_planar_truss_candidate_edges,
    expand_planar_truss_candidate_joints,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)

type _TrussObjectiveMetric = Literal["member-count", "total-length"]

_INFEASIBILITY_PENALTY_SCALE = 1_000.0


@dataclass(frozen=True)
class _TopologyAnalysis:
    """Cached deterministic graph analysis for one selected truss topology."""

    state: PlanarTrussState
    """Concrete truss state produced by the selected candidate edges."""
    member_count: int
    """Number of concrete members in the state."""
    total_member_length: float
    """Sum of all concrete member lengths."""
    active_joint_count: int
    """Number of joints required by the current active graph."""
    required_connected: bool
    """Whether the load path reaches the supports and all active joints."""
    load_degree: int
    """Graph degree at the loaded joint."""
    minimum_free_joint_degree: int | None
    """Minimum degree among active free joints other than the load joint."""
    crossing_count: int
    """Number of member crossings away from shared endpoints."""


def _coerce_float(value: object, default: float) -> float:
    """Return one manifest value as ``float`` with a fallback.

    Args:
        value: Raw manifest parameter value.
        default: Fallback value when the manifest field is missing.

    Returns:
        Float-converted parameter value.
    """
    if value is None:
        return default
    return float(cast(int | float, value))


def _coerce_fractional_points(raw_values: object) -> tuple[tuple[float, float], ...]:
    """Convert one manifest field into fractional point pairs.

    Args:
        raw_values: Raw manifest parameter value.

    Returns:
        Tuple of ``(x_fraction, y_fraction)`` pairs.

    Raises:
        TypeError: If the value is not a sequence of two-item numeric pairs.
    """
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list | tuple):
        raise TypeError("candidate_point_fractions must be a list or tuple of 2-item pairs.")
    points: list[tuple[float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 2:
            raise TypeError("Each candidate point must contain exactly two numeric values.")
        x_value, y_value = raw_value
        points.append((float(cast(int | float, x_value)), float(cast(int | float, y_value))))
    return tuple(points)


def _parse_objective_metric(value: object) -> _TrussObjectiveMetric:
    """Parse one supported scalar objective label.

    Args:
        value: Raw manifest parameter value.

    Returns:
        Validated objective label.

    Raises:
        ValueError: If the value does not name a supported truss objective.
    """
    metric = str(value or "member-count").strip().lower()
    if metric not in {"member-count", "total-length"}:
        raise ValueError(f"Unsupported truss objective metric: {metric!r}")
    return cast(_TrussObjectiveMetric, metric)


def _orientation(point_a: tuple[float, float], point_b: tuple[float, float], point_c: tuple[float, float]) -> float:
    """Return the signed orientation determinant for three planar points.

    Args:
        point_a: First point.
        point_b: Second point.
        point_c: Third point.

    Returns:
        Signed orientation determinant.
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
    """Return whether two open line segments intersect.

    Args:
        first_start: First segment start point.
        first_end: First segment end point.
        second_start: Second segment start point.
        second_end: Second segment end point.

    Returns:
        ``True`` when the segments cross at a non-endpoint interior point.
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


class PlanarTrussTopologyOptimizationProblem(OptimizationProblem):
    """Binary optimization over domain-defined candidate truss members."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        span: float = 10.0,
        max_height: float = 5.0,
        load_magnitude: float = 1_000.0,
        candidate_point_fractions: tuple[tuple[float, float], ...] = (),
        enforce_symmetry: bool = False,
        objective_metric: _TrussObjectiveMetric = "member-count",
    ) -> None:
        """Initialize one packaged truss topology optimization instance.

        Args:
            metadata: Shared packaged metadata for the optimization entry.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            span: Support-to-support span.
            max_height: Maximum design envelope height.
            load_magnitude: Downward point-load magnitude.
            candidate_point_fractions: Optional fractional interior candidate joint coordinates.
            enforce_symmetry: Whether selected members should preserve left-right symmetry.
            objective_metric: Scalar objective used to rank feasible topologies.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.span = span
        self.max_height = max_height
        self.load_magnitude = load_magnitude
        self.candidate_point_fractions = candidate_point_fractions
        self.enforce_symmetry = enforce_symmetry
        self.objective_metric = objective_metric

        seed_state = build_seed_planar_truss_state(
            span=self.span,
            max_height=self.max_height,
            load_magnitude=self.load_magnitude,
            enforce_symmetry=self.enforce_symmetry,
        )
        candidate_points = candidate_planar_truss_points(
            seed_state,
            candidate_point_fractions=self.candidate_point_fractions,
        )
        self._base_state = expand_planar_truss_candidate_joints(seed_state, candidate_points)
        self._candidate_edges = enumerate_planar_truss_candidate_edges(self._base_state)
        variable_count = len(self._candidate_edges)
        self.bounds = Bounds(
            lb=numpy.zeros(variable_count, dtype=float),
            ub=numpy.ones(variable_count, dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._support_connectivity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._load_degree_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._free_joint_degree_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._maxwell_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._crossing_margin),
        ]
        self._analysis_cache: dict[tuple[int, ...], _TopologyAnalysis] = {}

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> PlanarTrussTopologyOptimizationProblem:
        """Construct one packaged optimization instance from manifest data.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized optimization problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            span=_coerce_float(manifest.parameters.get("span"), 10.0),
            max_height=_coerce_float(manifest.parameters.get("max_height"), 5.0),
            load_magnitude=_coerce_float(manifest.parameters.get("load_magnitude"), 1_000.0),
            candidate_point_fractions=_coerce_fractional_points(manifest.parameters.get("candidate_point_fractions")),
            enforce_symmetry=bool(manifest.parameters.get("enforce_symmetry", False)),
            objective_metric=_parse_objective_metric(manifest.parameters.get("objective_metric")),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the all-off binary starting point.

        Args:
            seed: Optional random seed. Unused by the deterministic baseline.

        Returns:
            Zero vector with one binary variable per candidate edge.
        """
        del seed
        return numpy.zeros(len(self._candidate_edges), dtype=float)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the penalized scalar objective for one topology.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Penalized scalar objective value.
        """
        analysis = self._analysis_from_variables(variables)
        if self.objective_metric == "member-count":
            base_objective = float(analysis.member_count)
        else:
            base_objective = analysis.total_member_length
        return base_objective + (_INFEASIBILITY_PENALTY_SCALE * self.constraint_violation(variables))

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 512,
    ) -> OptimizationResult:
        """Enumerate binary topologies in deterministic neighborhood order.

        Args:
            initial_solution: Optional binary-like anchor vector.
            seed: Optional random seed. Unused by the deterministic baseline.
            maxiter: Maximum number of candidate bitmasks to evaluate.

        Returns:
            Best enumerated candidate and its baseline optimization summary.
        """
        del seed
        if initial_solution is None:
            anchor = self.generate_initial_solution()
        else:
            anchor = self._normalize_vector(initial_solution)
        anchor_bits = self._bit_tuple(anchor)

        candidate_bits = sorted(
            product((0, 1), repeat=len(self._candidate_edges)),
            key=lambda bits: (
                sum(1 for index, bit in enumerate(bits) if bit != anchor_bits[index]),
                sum(bits),
                tuple(index for index, bit in enumerate(bits) if bit),
            ),
        )
        budget = max(1, min(maxiter, len(candidate_bits)))

        best_bits = candidate_bits[0]
        best_score = math.inf
        evaluations = 0
        for bits in candidate_bits[:budget]:
            candidate = numpy.array(bits, dtype=float)
            score = self.objective(candidate)
            evaluations += 1
            if score < best_score:
                best_score = score
                best_bits = bits

        best_vector = numpy.array(best_bits, dtype=float)
        best_violation = self.max_constraint_violation(best_vector)
        best_analysis = self._analysis_from_bits(best_bits)
        if best_violation <= 1e-9:
            message = (
                "Enumerated binary planar-truss topologies and found a feasible design "
                f"with {best_analysis.member_count} members."
            )
        else:
            message = (
                "Enumerated binary planar-truss topologies and returned the best-effort design "
                f"(max violation {best_violation:.3g})."
            )
        return OptimizationResult(
            x=best_vector.copy(),
            fun=self.objective(best_vector),
            success=best_violation <= 1e-9,
            message=message,
            nit=budget,
            nfev=evaluations,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return one clipped vector with the expected binary dimension.

        Args:
            variables: Candidate design vector.

        Returns:
            Clipped float vector.

        Raises:
            ValueError: If the vector shape does not match the candidate edge set.
        """
        normalized = numpy.array(variables, dtype=float, copy=True)
        expected_shape = (len(self._candidate_edges),)
        if normalized.shape != expected_shape:
            raise ValueError(f"Expected a {expected_shape[0]}-variable design vector, received {normalized.shape!r}.")
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _bit_tuple(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        """Return the rounded binary tuple represented by one design vector.

        Args:
            variables: Candidate design vector.

        Returns:
            Tuple of ``0`` and ``1`` bits.
        """
        normalized = self._normalize_vector(variables)
        return tuple(1 if float(value) >= 0.5 else 0 for value in normalized)

    def _state_from_variables(self, variables: NDArray[numpy.float64]) -> PlanarTrussState:
        """Build one concrete truss state from a binary design vector.

        Args:
            variables: Candidate design vector.

        Returns:
            Concrete truss state using the shared planar-truss primitives.
        """
        return self._analysis_from_variables(variables).state

    def _analysis_from_variables(self, variables: NDArray[numpy.float64]) -> _TopologyAnalysis:
        """Return cached graph analysis for one design vector.

        Args:
            variables: Candidate design vector.

        Returns:
            Cached deterministic graph analysis.
        """
        return self._analysis_from_bits(self._bit_tuple(variables))

    def _analysis_from_bits(self, bits: tuple[int, ...]) -> _TopologyAnalysis:
        """Return cached graph analysis for one binary bit tuple.

        Args:
            bits: Binary candidate edge-selection tuple.

        Returns:
            Cached deterministic graph analysis.
        """
        cached = self._analysis_cache.get(bits)
        if cached is not None:
            return cached

        selected_edges = tuple(self._candidate_edges[index] for index, include_edge in enumerate(bits) if include_edge)
        state = build_planar_truss_state_from_edges(self._base_state, selected_edges)
        analysis = self._analyze_state(state)
        self._analysis_cache[bits] = analysis
        return analysis

    def _analyze_state(self, state: PlanarTrussState) -> _TopologyAnalysis:
        """Compute deterministic graph metrics for one concrete topology.

        Args:
            state: Concrete truss state.

        Returns:
            Derived graph analysis metrics.
        """
        joint_lookup = {joint.joint_id: joint for joint in state.joints}
        adjacency: dict[int, set[int]] = {joint.joint_id: set() for joint in state.joints}
        active_joint_ids = {joint.joint_id for joint in state.joints if joint.support_type != "free"} | {
            state.load_joint_id
        }
        total_member_length = 0.0
        for member in state.members:
            adjacency[member.start_joint_id].add(member.end_joint_id)
            adjacency[member.end_joint_id].add(member.start_joint_id)
            active_joint_ids.add(member.start_joint_id)
            active_joint_ids.add(member.end_joint_id)
            total_member_length += self._member_length(
                joint_lookup[member.start_joint_id],
                joint_lookup[member.end_joint_id],
            )

        reachable: set[int] = set()
        frontier = [state.load_joint_id]
        while frontier:
            current = frontier.pop()
            if current in reachable:
                continue
            reachable.add(current)
            frontier.extend(neighbor for neighbor in adjacency[current] if neighbor not in reachable)
        required_connected = active_joint_ids.issubset(reachable)

        free_joint_degrees = [
            len(adjacency[joint_id])
            for joint_id in active_joint_ids
            if joint_id != state.load_joint_id and joint_lookup[joint_id].support_type == "free"
        ]
        minimum_free_joint_degree = min(free_joint_degrees, default=None)
        crossing_count = self._count_crossings(state, joint_lookup)
        return _TopologyAnalysis(
            state=state,
            member_count=len(state.members),
            total_member_length=total_member_length,
            active_joint_count=len(active_joint_ids),
            required_connected=required_connected,
            load_degree=len(adjacency[state.load_joint_id]),
            minimum_free_joint_degree=minimum_free_joint_degree,
            crossing_count=crossing_count,
        )

    def _member_length(self, start_joint: PlanarJoint, end_joint: PlanarJoint) -> float:
        """Return the Euclidean length of one member.

        Args:
            start_joint: First member endpoint.
            end_joint: Second member endpoint.

        Returns:
            Euclidean member length.
        """
        return math.dist((start_joint.x, start_joint.y), (end_joint.x, end_joint.y))

    def _count_crossings(self, state: PlanarTrussState, joints: dict[int, PlanarJoint]) -> int:
        """Count member crossings that occur away from shared endpoints.

        Args:
            state: Concrete truss state.
            joints: Joint lookup keyed by joint ID.

        Returns:
            Number of pairwise crossings.
        """
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

    def _support_connectivity_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return a binary margin for required graph connectivity.

        Args:
            variables: Candidate design vector.

        Returns:
            ``1`` when the active topology is connected, otherwise ``-1``.
        """
        return 1.0 if self._analysis_from_variables(variables).required_connected else -1.0

    def _load_degree_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the load-joint degree margin.

        Args:
            variables: Candidate design vector.

        Returns:
            Load-joint degree minus the required minimum of two.
        """
        return float(self._analysis_from_variables(variables).load_degree - 2)

    def _free_joint_degree_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimum active free-joint degree margin.

        Args:
            variables: Candidate design vector.

        Returns:
            Minimum degree margin across active free joints, or ``0`` when none are active.
        """
        minimum_degree = self._analysis_from_variables(variables).minimum_free_joint_degree
        if minimum_degree is None:
            return 0.0
        return float(minimum_degree - 2)

    def _maxwell_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the planar-truss Maxwell-rule margin.

        Args:
            variables: Candidate design vector.

        Returns:
            Member-count margin above ``2j - 3`` for the active joint set.
        """
        analysis = self._analysis_from_variables(variables)
        required_member_count = max((2 * analysis.active_joint_count) - 3, 0)
        return float(analysis.member_count - required_member_count)

    def _crossing_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the non-crossing margin for the selected topology.

        Args:
            variables: Candidate design vector.

        Returns:
            Negative crossing count so any crossing creates an inequality violation.
        """
        return float(-self._analysis_from_variables(variables).crossing_count)


__all__ = ["PlanarTrussTopologyOptimizationProblem"]
