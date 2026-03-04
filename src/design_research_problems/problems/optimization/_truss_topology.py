"""Engineering-centered optimization wrappers for planar and space trusses."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Literal, SupportsFloat, cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.planar_truss import (
    PlanarTrussEvaluation,
    PlanarTrussState,
    build_planar_truss_state_from_edges,
    build_seed_planar_truss_state,
    candidate_planar_truss_points,
    count_planar_member_crossings,
    enumerate_planar_truss_candidate_edges,
    evaluate_planar_truss_state,
    expand_planar_truss_candidate_joints,
)
from design_research_problems.problems._domains.planar_truss import (
    active_joint_ids as planar_active_joint_ids,
)
from design_research_problems.problems._domains.planar_truss import (
    adjacency_map as planar_adjacency_map,
)
from design_research_problems.problems._domains.space_truss import (
    SpaceTrussEvaluation,
    SpaceTrussState,
    build_seed_space_truss_state,
    build_space_truss_state_from_edges,
    candidate_space_truss_points,
    enumerate_space_truss_candidate_edges,
    evaluate_space_truss_state,
    expand_space_truss_candidate_joints,
)
from design_research_problems.problems._domains.space_truss import (
    active_joint_ids as space_active_joint_ids,
)
from design_research_problems.problems._domains.space_truss import (
    adjacency_map as space_adjacency_map,
)
from design_research_problems.problems._domains.truss_core import edge_key, reachable_joint_ids
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)

type _ObjectiveMetric = Literal["mass-min", "deflection-min", "fos-max"]
type _SupportedState = PlanarTrussState | SpaceTrussState
type _SupportedEvaluation = PlanarTrussEvaluation | SpaceTrussEvaluation

_INFEASIBILITY_PENALTY_SCALE = 1_000_000.0


@dataclass(frozen=True)
class _EngineeringAnalysis:
    """Cached graph and structural analysis for one selected topology."""

    state: _SupportedState
    """Stored state value."""
    evaluation: _SupportedEvaluation
    """Stored evaluation value."""
    required_connected: bool
    """Stored required connected value."""
    minimum_active_free_joint_degree: int | None
    """Stored minimum active free joint degree value."""
    crossing_count: int
    """Count of crossing."""


def _coerce_float(value: object, default: float) -> float:
    """Return one manifest value as ``float`` with a fallback.

    Args:
        value: Value for ``value``.
        default: Value for ``default``.

    Returns:
        Computed result for this callable.
    """
    if value is None:
        return default
    return float(cast(SupportsFloat, value))


def _coerce_optional_float(value: object) -> float | None:
    """Return one manifest value as ``float`` or ``None`` when absent.

    Args:
        value: Value for ``value``.

    Returns:
        Computed result for this callable.
    """
    if value is None:
        return None
    return float(cast(SupportsFloat, value))


def _coerce_fractional_points(raw_values: object) -> tuple[tuple[float, float], ...]:
    """Convert one manifest field into 2D fractional coordinate pairs.

    Args:
        raw_values: Value for ``raw_values``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
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
        points.append((float(cast(SupportsFloat, x_value)), float(cast(SupportsFloat, y_value))))
    return tuple(points)


def _coerce_fractional_points_3d(raw_values: object) -> tuple[tuple[float, float, float], ...]:
    """Convert one manifest field into 3D fractional coordinate triples.

    Args:
        raw_values: Value for ``raw_values``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    if raw_values is None:
        return ()
    if not isinstance(raw_values, list | tuple):
        raise TypeError("candidate_point_fractions_3d must be a list or tuple of 3-item triples.")
    points: list[tuple[float, float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 3:
            raise TypeError("Each 3D candidate point must contain exactly three numeric values.")
        x_value, y_value, z_value = raw_value
        points.append(
            (
                float(cast(SupportsFloat, x_value)),
                float(cast(SupportsFloat, y_value)),
                float(cast(SupportsFloat, z_value)),
            )
        )
    return tuple(points)


def _parse_objective_metric(value: object, *, allow_fos: bool = True) -> _ObjectiveMetric:
    """Parse and validate one supported scalar objective label.

    Args:
        value: Value for ``value``.
        allow_fos: Value for ``allow_fos``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    metric = str(value or "mass-min").strip().lower()
    allowed = {"mass-min", "deflection-min"}
    if allow_fos:
        allowed.add("fos-max")
    if metric not in allowed:
        raise ValueError(f"Unsupported truss objective metric: {metric!r}")
    return cast(_ObjectiveMetric, metric)


class _BinaryTrussEngineeringOptimizationProblem(OptimizationProblem):
    """Shared deterministic binary edge-selection optimizer for structural trusses."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str,
        resource_bundle: PackageResourceBundle | None,
        *,
        base_state: _SupportedState,
        candidate_edges: tuple[tuple[int, int], ...],
        objective_metric: _ObjectiveMetric,
        minimum_fos: float | None,
        maximum_deflection: float | None,
        maximum_mass: float | None,
        state_builder: Callable[[Any, tuple[tuple[int, int], ...]], _SupportedState],
        evaluator: Callable[[Any], _SupportedEvaluation],
        active_joint_ids_fn: Callable[[Any], set[int]],
        adjacency_fn: Callable[[Any], dict[int, set[int]]],
        crossing_count_fn: Callable[[Any], int] | None = None,
    ) -> None:
        """Initialize the shared structural truss optimizer.

        Args:
            metadata: Value for ``metadata``.
            statement_markdown: Value for ``statement_markdown``.
            resource_bundle: Value for ``resource_bundle``.
            base_state: Value for ``base_state``.
            candidate_edges: Value for ``candidate_edges``.
            objective_metric: Value for ``objective_metric``.
            minimum_fos: Value for ``minimum_fos``.
            maximum_deflection: Value for ``maximum_deflection``.
            maximum_mass: Value for ``maximum_mass``.
            state_builder: Value for ``state_builder``.
            evaluator: Value for ``evaluator``.
            active_joint_ids_fn: Value for ``active_joint_ids_fn``.
            adjacency_fn: Value for ``adjacency_fn``.
            crossing_count_fn: Value for ``crossing_count_fn``.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.objective_metric = objective_metric
        self.minimum_fos = minimum_fos
        self.maximum_deflection = maximum_deflection
        self.maximum_mass = maximum_mass
        self._base_state = base_state
        self._candidate_edges = candidate_edges
        self._state_builder = state_builder
        self._evaluator = evaluator
        self._active_joint_ids = active_joint_ids_fn
        self._adjacency = adjacency_fn
        self._crossing_count = crossing_count_fn
        self._analysis_cache: dict[tuple[int, ...], _EngineeringAnalysis] = {}

        variable_count = len(self._candidate_edges)
        self.bounds = Bounds(
            lb=numpy.zeros(variable_count, dtype=float),
            ub=numpy.ones(variable_count, dtype=float),
        )

        constraints: list[ConstraintDefinition] = [
            ConstraintDefinition(kind="ineq", evaluate=self._support_connectivity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._free_joint_degree_margin),
        ]
        if self._crossing_count is not None:
            constraints.append(ConstraintDefinition(kind="ineq", evaluate=self._crossing_margin))
        if self.minimum_fos is not None:
            constraints.append(ConstraintDefinition(kind="ineq", evaluate=self._minimum_fos_margin))
        if self.maximum_deflection is not None:
            constraints.append(ConstraintDefinition(kind="ineq", evaluate=self._maximum_deflection_margin))
        if self.maximum_mass is not None:
            constraints.append(ConstraintDefinition(kind="ineq", evaluate=self._maximum_mass_margin))
        self.constraints = constraints

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the all-off binary starting point.

        Args:
            seed: Value for ``seed``.

        Returns:
            Computed result for this callable.
        """
        del seed
        return numpy.array(self._seed_bits(), dtype=float)

    def _seed_bits(self) -> tuple[int, ...]:
        """Return the deterministic default binary seed bits.

        Returns:
            Computed result for this callable.
        """
        return tuple(0 for _ in self._candidate_edges)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the structural objective plus a large infeasibility penalty.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Penalized scalar objective value for ``variables``.
        """
        analysis = self._analysis_from_variables(variables)
        if self.objective_metric == "mass-min":
            base_objective = float(analysis.evaluation.mass)
        elif self.objective_metric == "deflection-min":
            base_objective = float(analysis.evaluation.deflection)
        else:
            base_objective = -float(analysis.evaluation.fos)
        return base_objective + (_INFEASIBILITY_PENALTY_SCALE * self.constraint_violation(variables))

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 512,
    ) -> OptimizationResult:
        """Enumerate binary topologies in deterministic neighborhood order.

        Args:
            initial_solution: Optional binary design vector used as the anchor
                topology.
            seed: Unused placeholder to preserve the shared optimization
                interface.
            maxiter: Maximum number of candidate topologies to enumerate.

        Returns:
            Best available baseline optimization result within the enumeration
            budget.
        """
        del seed
        if initial_solution is None:
            anchor = self.generate_initial_solution()
        else:
            anchor = self._normalize_vector(initial_solution)
        anchor_bits = self._bit_tuple(anchor)
        budget = max(1, maxiter)
        candidate_bits = self._candidate_bits(anchor_bits, limit=budget)
        best_bits = candidate_bits[0]
        best_score = math.inf
        evaluations = 0
        for bits in candidate_bits:
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
                "Enumerated structural truss topologies and found a feasible baseline "
                f"(mass {best_analysis.evaluation.mass:.3f}, fos {best_analysis.evaluation.fos:.3f}, "
                f"deflection {best_analysis.evaluation.deflection:.3f})."
            )
        else:
            message = (
                "Enumerated structural truss topologies and returned the best-effort design "
                f"(max violation {best_violation:.3g})."
            )
        return OptimizationResult(
            x=best_vector.copy(),
            fun=self.objective(best_vector),
            success=best_violation <= 1e-9,
            message=message,
            nit=len(candidate_bits),
            nfev=evaluations,
        )

    def _candidate_bits(self, anchor_bits: tuple[int, ...], *, limit: int) -> tuple[tuple[int, ...], ...]:
        """Return at most ``limit`` candidates in increasing Hamming-distance order.

        Args:
            anchor_bits: Binary anchor topology used as the enumeration center.
            limit: Maximum number of bit patterns to return.

        Returns:
            Candidate bit tuples ordered by increasing Hamming distance.
        """
        bit_count = len(anchor_bits)
        candidates: list[tuple[int, ...]] = []
        for distance in range(bit_count + 1):
            for indices in combinations(range(bit_count), distance):
                bits = list(anchor_bits)
                for index in indices:
                    bits[index] = 1 - bits[index]
                candidates.append(tuple(bits))
                if len(candidates) >= limit:
                    return tuple(candidates)
        return tuple(candidates)

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return one clipped vector with the expected binary dimension.

        Args:
            variables: Candidate design vector to normalize.

        Returns:
            Clipped floating-point vector with the expected binary shape.

        Raises:
            ValueError: If ``variables`` does not match the candidate-edge
                dimensionality.
        """
        normalized = numpy.array(variables, dtype=float, copy=True)
        expected_shape = (len(self._candidate_edges),)
        if normalized.shape != expected_shape:
            raise ValueError(f"Expected a {expected_shape[0]}-variable design vector, received {normalized.shape!r}.")
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _bit_tuple(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        """Return the rounded binary tuple represented by one design vector.

        Args:
            variables: Candidate design vector to round into bits.

        Returns:
            Rounded binary bit tuple for ``variables``.
        """
        normalized = self._normalize_vector(variables)
        return tuple(1 if float(value) >= 0.5 else 0 for value in normalized)

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> _SupportedState:
        """Build one concrete truss state from a binary design vector.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Concrete planar or space-truss state represented by ``variables``.
        """
        return self._analysis_from_variables(variables).state

    def _state_from_variables(self, variables: NDArray[numpy.float64]) -> _SupportedState:
        """Build one concrete truss state from a binary design vector.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Concrete planar or space-truss state represented by ``variables``.
        """
        return self.decode_candidate(variables)

    def _analysis_from_variables(self, variables: NDArray[numpy.float64]) -> _EngineeringAnalysis:
        """Return cached graph and structural analysis for one design vector.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Cached or newly computed engineering analysis for ``variables``.
        """
        return self._analysis_from_bits(self._bit_tuple(variables))

    def _analysis_from_bits(self, bits: tuple[int, ...]) -> _EngineeringAnalysis:
        """Return cached graph and structural analysis for one bit tuple.

        Args:
            bits: Binary topology bit tuple.

        Returns:
            Cached or newly computed engineering analysis for ``bits``.
        """
        cached = self._analysis_cache.get(bits)
        if cached is not None:
            return cached

        selected_edges = tuple(self._candidate_edges[index] for index, include_edge in enumerate(bits) if include_edge)
        state = self._state_builder(self._base_state, selected_edges)
        adjacency = self._adjacency(state)
        active_joint_ids = self._active_joint_ids(state)
        reachable = reachable_joint_ids(adjacency, state.load_joint_id)
        required_connected = active_joint_ids.issubset(reachable)
        joint_lookup = {joint.joint_id: joint for joint in state.joints}
        free_joint_degrees = [
            len(adjacency[joint_id])
            for joint_id in active_joint_ids
            if joint_id != state.load_joint_id and joint_lookup[joint_id].support_type == "free"
        ]
        evaluation = self._evaluator(state)
        analysis = _EngineeringAnalysis(
            state=state,
            evaluation=evaluation,
            required_connected=required_connected,
            minimum_active_free_joint_degree=min(free_joint_degrees, default=None),
            crossing_count=0 if self._crossing_count is None else self._crossing_count(state),
        )
        self._analysis_cache[bits] = analysis
        return analysis

    def _support_connectivity_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return a binary margin for required graph connectivity.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Positive value when the required active joints are connected.
        """
        return 1.0 if self._analysis_from_variables(variables).required_connected else -1.0

    def _free_joint_degree_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimum active free-joint degree margin above one.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Signed degree margin for the active free joints.
        """
        minimum_degree = self._analysis_from_variables(variables).minimum_active_free_joint_degree
        if minimum_degree is None:
            return 1.0
        return float(minimum_degree - 1)

    def _crossing_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the non-crossing margin for planar topologies.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Non-crossing margin for the planar topology encoded by ``variables``.
        """
        return float(-self._analysis_from_variables(variables).crossing_count)

    def _minimum_fos_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining factor-of-safety margin.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Remaining factor-of-safety margin for ``variables``.
        """
        assert self.minimum_fos is not None
        return float(self._analysis_from_variables(variables).evaluation.fos - self.minimum_fos)

    def _maximum_deflection_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining maximum-deflection margin.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Remaining deflection margin for ``variables``.
        """
        assert self.maximum_deflection is not None
        return float(self.maximum_deflection - self._analysis_from_variables(variables).evaluation.deflection)

    def _maximum_mass_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining maximum-mass margin.

        Args:
            variables: Candidate binary design vector.

        Returns:
            Remaining mass margin for ``variables``.
        """
        assert self.maximum_mass is not None
        return float(self.maximum_mass - self._analysis_from_variables(variables).evaluation.mass)


class PlanarTrussEngineeringOptimizationProblem(_BinaryTrussEngineeringOptimizationProblem):
    """Binary structural optimization over a fixed-joint planar truss scaffold."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        span: float = 10.0,
        max_height: float = 5.0,
        load_magnitude: float = 1_000.0,
        candidate_point_fractions: tuple[tuple[float, float], ...] = (),
        enforce_symmetry: bool = False,
        objective_metric: _ObjectiveMetric = "mass-min",
        minimum_fos: float | None = 1.0,
        maximum_deflection: float | None = 0.20,
        maximum_mass: float | None = None,
    ) -> None:
        """Initialize one packaged engineer-centered planar truss optimization instance.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            span: Support span for the seed truss.
            max_height: Maximum allowable truss height.
            load_magnitude: Downward load applied at the load joint.
            candidate_point_fractions: Fractional coordinates for optional
                interior candidate joints.
            enforce_symmetry: Whether to restrict the scaffold to a symmetric
                joint layout.
            objective_metric: Structural metric optimized by the baseline.
            minimum_fos: Optional minimum factor-of-safety threshold.
            maximum_deflection: Optional maximum deflection threshold.
            maximum_mass: Optional maximum mass threshold.
        """
        self.span = span
        self.max_height = max_height
        self.load_magnitude = load_magnitude
        self.candidate_point_fractions = candidate_point_fractions
        self.enforce_symmetry = enforce_symmetry
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
        base_state = expand_planar_truss_candidate_joints(seed_state, candidate_points)
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            base_state=base_state,
            candidate_edges=enumerate_planar_truss_candidate_edges(base_state),
            objective_metric=objective_metric,
            minimum_fos=minimum_fos,
            maximum_deflection=maximum_deflection,
            maximum_mass=maximum_mass,
            state_builder=build_planar_truss_state_from_edges,
            evaluator=evaluate_planar_truss_state,
            active_joint_ids_fn=planar_active_joint_ids,
            adjacency_fn=planar_adjacency_map,
            crossing_count_fn=count_planar_member_crossings,
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> PlanarTrussEngineeringOptimizationProblem:
        """Construct one packaged planar truss optimization instance from manifest data.

        Args:
            manifest: Parsed problem manifest.

        Returns:
            Loaded planar truss engineering optimization problem.
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
            minimum_fos=_coerce_optional_float(manifest.parameters.get("minimum_fos")),
            maximum_deflection=_coerce_optional_float(manifest.parameters.get("maximum_deflection")),
            maximum_mass=_coerce_optional_float(manifest.parameters.get("maximum_mass")),
        )

    def _seed_bits(self) -> tuple[int, ...]:
        """Return a simple triangular load path as the default planar seed.

        Returns:
            Default planar seed bit tuple.
        """
        seed_edges = {edge_key(0, 1), edge_key(0, 2), edge_key(1, 2)}
        return tuple(1 if edge in seed_edges else 0 for edge in self._candidate_edges)


class SpaceTrussEngineeringOptimizationProblem(_BinaryTrussEngineeringOptimizationProblem):
    """Binary structural optimization over a fixed-joint 3D space-truss scaffold."""

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
        objective_metric: _ObjectiveMetric = "mass-min",
        minimum_fos: float | None = 1.0,
        maximum_deflection: float | None = 0.20,
    ) -> None:
        """Initialize one packaged engineer-centered space-truss optimization instance.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            span: Support span for the seed truss.
            width: Lateral width of the seed truss.
            max_height: Maximum allowable truss height.
            load_magnitude: Downward load applied at the load joint.
            candidate_point_fractions_3d: Fractional coordinates for optional
                interior candidate joints.
            objective_metric: Structural metric optimized by the baseline.
            minimum_fos: Optional minimum factor-of-safety threshold.
            maximum_deflection: Optional maximum deflection threshold.
        """
        self.span = span
        self.width = width
        self.max_height = max_height
        self.load_magnitude = load_magnitude
        self.candidate_point_fractions_3d = candidate_point_fractions_3d
        seed_state = build_seed_space_truss_state(
            span=self.span,
            width=self.width,
            max_height=self.max_height,
            load_magnitude=self.load_magnitude,
        )
        candidate_points = candidate_space_truss_points(
            seed_state,
            candidate_point_fractions_3d=self.candidate_point_fractions_3d,
        )
        base_state = expand_space_truss_candidate_joints(seed_state, candidate_points)
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            base_state=base_state,
            candidate_edges=enumerate_space_truss_candidate_edges(base_state),
            objective_metric=objective_metric,
            minimum_fos=minimum_fos,
            maximum_deflection=maximum_deflection,
            maximum_mass=None,
            state_builder=build_space_truss_state_from_edges,
            evaluator=evaluate_space_truss_state,
            active_joint_ids_fn=space_active_joint_ids,
            adjacency_fn=space_adjacency_map,
            crossing_count_fn=None,
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> SpaceTrussEngineeringOptimizationProblem:
        """Construct one packaged 3D space-truss optimization instance from manifest data.

        Args:
            manifest: Parsed problem manifest.

        Returns:
            Loaded space-truss engineering optimization problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            span=_coerce_float(manifest.parameters.get("span"), 10.0),
            width=_coerce_float(manifest.parameters.get("width"), 4.0),
            max_height=_coerce_float(manifest.parameters.get("max_height"), 5.0),
            load_magnitude=_coerce_float(manifest.parameters.get("load_magnitude"), 1_000.0),
            candidate_point_fractions_3d=_coerce_fractional_points_3d(
                manifest.parameters.get("candidate_point_fractions_3d")
            ),
            objective_metric=_parse_objective_metric(manifest.parameters.get("objective_metric"), allow_fos=False),
            minimum_fos=_coerce_optional_float(manifest.parameters.get("minimum_fos")),
            maximum_deflection=_coerce_optional_float(manifest.parameters.get("maximum_deflection")),
        )

    def _seed_bits(self) -> tuple[int, ...]:
        """Return a bridge-like braced pyramid as the default 3D seed.

        Returns:
            Default space-truss seed bit tuple.
        """
        seed_edges = {
            edge_key(0, 4),
            edge_key(1, 4),
            edge_key(2, 4),
            edge_key(3, 4),
            edge_key(0, 1),
            edge_key(2, 3),
            edge_key(0, 2),
            edge_key(1, 3),
            edge_key(0, 3),
            edge_key(1, 2),
        }
        return tuple(1 if edge in seed_edges else 0 for edge in self._candidate_edges)


__all__ = [
    "PlanarTrussEngineeringOptimizationProblem",
    "SpaceTrussEngineeringOptimizationProblem",
]
