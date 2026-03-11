"""Tiered 18650 battery optimization ladder with progressive design freedom."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    BatteryThermalPriors,
    interpolate_total_resistance,
    load_18650_thermal_priors,
)
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    MIN_SPACING_MM,
    BatteryRequirements,
)
from design_research_problems.problems._domains.battery_tier_metrics import (
    BatteryObjectiveWeights,
    BatteryTierMetrics,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
    bounded_pattern_search,
)
from design_research_problems.problems.grammar._battery_problem_base import (
    parse_battery_backend_config,
    parse_battery_requirements,
)
from design_research_problems.problems.optimization._battery_grid import BatteryGridSizingProblem
from design_research_problems.problems.optimization._battery_oriented_layout import BatteryOrientedLayoutProblem

_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_DEFAULT_AMBIENT_TEMPERATURE_C = 25.0
_DEFAULT_MAX_TEMPERATURE_C = 60.0
_DEFAULT_COOLING_COEFFICIENT = 18.0
_DEFAULT_PASSIVE_COOLING = 1.0
_THERMAL_MODEL_LUMPED = "lumped"
_THERMAL_MODEL_MULTI_NODE = "multi_node_2node"
_DEFAULT_THERMAL_MODEL = _THERMAL_MODEL_MULTI_NODE


@dataclass(frozen=True)
class Tier2DecodedCandidate:
    """Decoded tier-2 candidate."""

    series_count: int
    """Rounded series-stage count."""
    parallel_count: int
    """Rounded parallel-branch count."""
    cell_count: int
    """Derived cell count ``series_count * parallel_count``."""


@dataclass(frozen=True)
class Tier3DecodedCandidate:
    """Decoded tier-3 candidate."""

    cell_count: int
    """Active cell count."""
    series_count: int
    """Requested series stage count."""
    stage_counts: tuple[int, ...]
    """Population assigned to each series stage."""


@dataclass(frozen=True)
class Tier4DecodedCandidate:
    """Decoded tier-4 candidate."""

    base: Tier3DecodedCandidate
    """Underlying topology decode."""
    cooling_coefficient_w_per_m2k: float
    """Candidate-specific convective cooling coefficient."""
    passive_cooling_w_per_k: float
    """Candidate-specific baseline thermal conductance."""
    ambient_temperature_c: float
    """Candidate-specific ambient temperature."""


@dataclass(frozen=True)
class Tier4ThermalDiagnostics:
    """Detailed tier-4 thermal diagnostics for non-contract reporting."""

    thermal_model: str
    """Thermal model used for the evaluation."""
    max_core_temperature_c: float
    """Maximum core temperature across all active cells."""
    max_surface_temperature_c: float
    """Maximum surface-node temperature across all active cells."""
    coolant_temperature_c: float
    """Coolant/jig node temperature."""
    max_core_surface_delta_c: float
    """Largest core-to-surface delta across active cells."""


@dataclass(frozen=True)
class _Tier4NodeThermalSolution:
    """Internal thermal-network solution payload for one candidate."""

    max_core_temperature_c: float
    max_surface_temperature_c: float
    coolant_temperature_c: float
    max_core_surface_delta_c: float


def _thermal_peak_temperature_c(
    *,
    cell_count: int,
    parallel_equivalent: float,
    surface_area_mm2: float,
    load_current_a: float,
    cooling_coefficient_w_per_m2k: float,
    passive_cooling_w_per_k: float,
    ambient_temperature_c: float,
) -> float:
    """Return one steady-state thermal proxy."""
    if cell_count <= 0:
        return float(ambient_temperature_c)
    per_cell_current = load_current_a / max(parallel_equivalent, 1.0e-9)
    total_heat_w = float(cell_count) * (per_cell_current**2) * CELL_SPEC_18650.internal_resistance_ohm
    cooling_area_m2 = surface_area_mm2 * 1.0e-6
    cooling_conductance = max(passive_cooling_w_per_k, 1.0e-9) + (cooling_coefficient_w_per_m2k * cooling_area_m2)
    return float(ambient_temperature_c + (total_heat_w / max(cooling_conductance, 1.0e-9)))


def _score_metrics(
    *,
    metrics: BatteryTierMetrics,
    requirements: BatteryRequirements,
    max_cell_count: int,
    max_temperature_c: float,
    ambient_temperature_c: float,
    weights: BatteryObjectiveWeights,
    total_violation: float,
) -> float:
    """Return weighted scalar objective plus infeasibility penalty."""
    max_pack_volume = max(
        requirements.max_width_mm * requirements.max_depth_mm * requirements.max_height_mm,
        1.0,
    )
    volume_term = metrics.design_volume_mm3 / max_pack_volume
    cost_term = metrics.cell_count / max(float(max_cell_count), 1.0)
    thermal_span = max(max_temperature_c - ambient_temperature_c, 1.0)
    temperature_term = (metrics.max_temperature_c - ambient_temperature_c) / thermal_span
    penalty = _INFEASIBILITY_PENALTY_SCALE * total_violation
    return (
        (weights.volume * volume_term) + (weights.cost * cost_term) + (weights.temperature * temperature_term) + penalty
    )


class Battery18650Tier1SeriesParallelOptimizationProblem(BatteryGridSizingProblem):
    """Tier-1 optimizer: choose only ``S`` and ``P`` with canonical layout/wiring."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        backend_config: BatteryBackendConfig | None = None,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_w_per_m2k: float = _DEFAULT_COOLING_COEFFICIENT,
        passive_cooling_w_per_k: float = _DEFAULT_PASSIVE_COOLING,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
    ) -> None:
        """Initialize tier-1 series-parallel optimization."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
            backend_config=backend_config,
        )
        self.objective_weights = objective_weights or BatteryObjectiveWeights(volume=0.20, cost=0.65, temperature=0.15)
        self.cooling_coefficient_w_per_m2k = float(cooling_coefficient_w_per_m2k)
        self.passive_cooling_w_per_k = max(1.0e-9, float(passive_cooling_w_per_k))
        self.ambient_temperature_c = float(ambient_temperature_c)
        self.maximum_temperature_c = max(float(maximum_temperature_c), self.ambient_temperature_c + 1.0)
        self.load_current_a = (
            float(self.requirements.minimum_current_a) if load_current_a is None else float(load_current_a)
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier1SeriesParallelOptimizationProblem:
        """Construct one tier-1 optimizer from manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            backend_config=parse_battery_backend_config(manifest),
            objective_weights=BatteryObjectiveWeights.from_mapping(
                parameters.get("objective_weights"),
                default_volume=0.20,
                default_cost=0.65,
                default_temperature=0.15,
            ),
            cooling_coefficient_w_per_m2k=float(
                cast(float, parameters.get("cooling_coefficient_w_per_m2k", _DEFAULT_COOLING_COEFFICIENT))
            ),
            passive_cooling_w_per_k=float(
                cast(float, parameters.get("passive_cooling_w_per_k", _DEFAULT_PASSIVE_COOLING))
            ),
            ambient_temperature_c=float(
                cast(float, parameters.get("ambient_temperature_c", _DEFAULT_AMBIENT_TEMPERATURE_C))
            ),
            maximum_temperature_c=float(
                cast(float, parameters.get("maximum_temperature_c", _DEFAULT_MAX_TEMPERATURE_C))
            ),
            load_current_a=cast(float | None, parameters.get("load_current_a")),
        )

    def _connection_count(self, series_count: int, parallel_count: int) -> int:
        """Return canonical connection count for rectangular ``SxP`` bus wiring."""
        return max(0, series_count + 1) * max(0, parallel_count - 1)

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        """Return tier-1 metrics for one candidate vector."""
        evaluation = self._evaluation_from_variables(variables)
        state = self.decode_candidate(variables)
        peak_temperature = _thermal_peak_temperature_c(
            cell_count=evaluation.cell_count,
            parallel_equivalent=float(state.parallel_count),
            surface_area_mm2=evaluation.surface_area,
            load_current_a=self.load_current_a,
            cooling_coefficient_w_per_m2k=self.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=self.passive_cooling_w_per_k,
            ambient_temperature_c=self.ambient_temperature_c,
        )
        return BatteryTierMetrics(
            cell_count=float(evaluation.cell_count),
            connection_count=float(self._connection_count(state.series_count, state.parallel_count)),
            cost_usd=float(evaluation.design_cost),
            design_volume_mm3=float(evaluation.design_volume),
            max_temperature_c=peak_temperature,
            voltage_v=float(evaluation.design_voltage),
            capacity_ah=float(evaluation.design_capacity),
            current_limit_a=float(evaluation.analytic_current_limit),
            min_clearance_mm=float(MIN_SPACING_MM),
            is_feasible=bool(evaluation.is_feasible),
            failure_reason=evaluation.failure_reason,
        )

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the shared battery metric contract for one candidate."""
        return self._metrics_from_variables(variables).as_dict()

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the weighted tier-1 scalar objective."""
        normalized = self._normalize_vector(variables)
        metrics = self._metrics_from_variables(normalized)
        return _score_metrics(
            metrics=metrics,
            requirements=self.requirements,
            max_cell_count=self._max_series_count() * self._max_parallel_count(),
            max_temperature_c=self.maximum_temperature_c,
            ambient_temperature_c=self.ambient_temperature_c,
            weights=self.objective_weights,
            total_violation=self.constraint_violation(normalized),
        )


class _TierOrientedOptimizationBase(OptimizationProblem):
    """Shared oriented-layout helper for tier-2 through tier-4 optimizers."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        minimum_spacing_mm: float = MIN_SPACING_MM,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_w_per_m2k: float = _DEFAULT_COOLING_COEFFICIENT,
        passive_cooling_w_per_k: float = _DEFAULT_PASSIVE_COOLING,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
    ) -> None:
        """Store shared tiered-layout optimization configuration."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.requirements = requirements or BatteryRequirements(
            target_voltage_v=14.8,
            minimum_capacity_ah=10.0,
            minimum_current_a=60.0,
            max_width_mm=500.0,
            max_depth_mm=500.0,
            max_height_mm=250.0,
            voltage_tolerance_v=0.1,
        )
        self.max_cell_count = max(1, int(max_cell_count))
        self.minimum_spacing_mm = max(0.0, float(minimum_spacing_mm))
        self.objective_weights = objective_weights or BatteryObjectiveWeights(volume=0.45, cost=0.35, temperature=0.20)
        self.cooling_coefficient_w_per_m2k = float(cooling_coefficient_w_per_m2k)
        self.passive_cooling_w_per_k = max(1.0e-9, float(passive_cooling_w_per_k))
        self.ambient_temperature_c = float(ambient_temperature_c)
        self.maximum_temperature_c = max(float(maximum_temperature_c), self.ambient_temperature_c + 1.0)
        self.load_current_a = (
            float(self.requirements.minimum_current_a) if load_current_a is None else float(load_current_a)
        )
        # Internal geometry helper with the complex rotated-cylinder clearance model.
        self._pose_helper = BatteryOrientedLayoutProblem(
            metadata=metadata,
            requirements=self.requirements,
            max_cell_count=self.max_cell_count,
            minimum_spacing_mm=self.minimum_spacing_mm,
            cooling_coefficient_w_per_m2k=self.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=self.passive_cooling_w_per_k,
            ambient_temperature_c=self.ambient_temperature_c,
            maximum_temperature_c=self.maximum_temperature_c,
            load_current_a=self.load_current_a,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return a clipped candidate vector with expected shape."""
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != self.bounds.lb.shape:
            raise ValueError(
                f"Expected a {self.bounds.lb.shape[0]}-variable design vector, received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _pose_helper_evaluation(
        self,
        *,
        active_cell_count: int,
        pose_variables: NDArray[numpy.float64],
    ) -> Any:
        """Return the oriented geometry summary from the shared pose helper."""
        helper_vector = numpy.zeros(1 + (6 * self.max_cell_count), dtype=float)
        helper_vector[0] = float(max(1, min(active_cell_count, self.max_cell_count)))
        helper_vector[1 : 1 + (6 * self.max_cell_count)] = pose_variables[: 6 * self.max_cell_count]
        return self._pose_helper._evaluation_from_variables(helper_vector)

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the shared battery metric contract."""
        return self._metrics_from_variables(variables).as_dict()

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return weighted scalar objective with infeasibility penalty."""
        normalized = self._normalize_vector(variables)
        metrics = self._metrics_from_variables(normalized)
        return _score_metrics(
            metrics=metrics,
            requirements=self.requirements,
            max_cell_count=self.max_cell_count,
            max_temperature_c=self.maximum_temperature_c,
            ambient_temperature_c=self.ambient_temperature_c,
            weights=self.objective_weights,
            total_violation=self.constraint_violation(normalized),
        )

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 80,
    ) -> OptimizationResult:
        """Run deterministic bounded local search for tiered layout problems."""
        start = (
            self.generate_initial_solution(seed=seed)
            if initial_solution is None
            else self._normalize_vector(initial_solution)
        )
        if maxiter <= 0:
            best = self._normalize_vector(start)
            max_violation = self.max_constraint_violation(best)
            return OptimizationResult(
                x=best,
                fun=self.objective(best),
                success=max_violation <= 1.0e-9,
                message="Evaluated one tiered battery candidate.",
                nit=0,
                nfev=1,
            )
        search = bounded_pattern_search(
            objective=self.objective,
            lower_bounds=self.bounds.lb,
            upper_bounds=self.bounds.ub,
            initial_solution=start,
            maxiter=maxiter,
            initial_step_fraction=0.08,
            minimum_step_fraction=1.0e-3,
        )
        best = self._normalize_vector(search.x)
        max_violation = self.max_constraint_violation(best)
        return OptimizationResult(
            x=best,
            fun=self.objective(best),
            success=max_violation <= 1.0e-9,
            message=(
                "Evaluated tiered battery layouts and found a feasible design."
                if max_violation <= 1.0e-9
                else "Evaluated tiered battery layouts and returned a best-effort design."
            ),
            nit=search.nit,
            nfev=search.nfev + 1,
        )

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        """Return tier-specific metric payload for one candidate."""
        raise NotImplementedError

    def _width_margin(self, variables: NDArray[numpy.float64]) -> float:
        volume_mm3 = float(self._metrics_from_variables(variables).design_volume_mm3)
        return float(self.requirements.max_width_mm - (volume_mm3 ** (1.0 / 3.0)))

    def _depth_margin(self, variables: NDArray[numpy.float64]) -> float:
        evaluation = self._pose_for_margin(variables)
        return self.requirements.max_depth_mm - float(evaluation.design_depth_mm)

    def _height_margin(self, variables: NDArray[numpy.float64]) -> float:
        evaluation = self._pose_for_margin(variables)
        return self.requirements.max_height_mm - float(evaluation.design_height_mm)

    def _voltage_margin(self, variables: NDArray[numpy.float64]) -> float:
        metrics = self._metrics_from_variables(variables)
        return self.requirements.voltage_tolerance_v - abs(metrics.voltage_v - self.requirements.target_voltage_v)

    def _capacity_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).capacity_ah - self.requirements.minimum_capacity_ah

    def _current_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).current_limit_a - self.requirements.minimum_current_a

    def _clearance_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).min_clearance_mm

    def _minimum_spacing_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).min_clearance_mm - self.minimum_spacing_mm

    def _temperature_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self.maximum_temperature_c - self._metrics_from_variables(variables).max_temperature_c

    def _pose_for_margin(self, variables: NDArray[numpy.float64]) -> Any:
        """Return pose-helper evaluation for geometric envelope margins."""
        normalized = self._normalize_vector(variables)
        active_count, pose_variables = self._active_count_and_pose_variables(normalized)
        return self._pose_helper_evaluation(active_cell_count=active_count, pose_variables=pose_variables)

    def _active_count_and_pose_variables(self, variables: NDArray[numpy.float64]) -> tuple[int, NDArray[numpy.float64]]:
        """Return active cell count and flattened pose variables for helper evaluation."""
        raise NotImplementedError


class Battery18650Tier2LayoutOptimizationProblem(_TierOrientedOptimizationBase):
    """Tier-2 optimizer: rectangular topology plus full cell pose freedom."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        minimum_spacing_mm: float = MIN_SPACING_MM,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_w_per_m2k: float = _DEFAULT_COOLING_COEFFICIENT,
        passive_cooling_w_per_k: float = _DEFAULT_PASSIVE_COOLING,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
    ) -> None:
        """Initialize tier-2 optimization."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
            max_cell_count=max_cell_count,
            minimum_spacing_mm=minimum_spacing_mm,
            objective_weights=objective_weights or BatteryObjectiveWeights(volume=0.45, cost=0.35, temperature=0.20),
            cooling_coefficient_w_per_m2k=cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=passive_cooling_w_per_k,
            ambient_temperature_c=ambient_temperature_c,
            maximum_temperature_c=maximum_temperature_c,
            load_current_a=load_current_a,
        )
        self.max_series_count = self.max_cell_count
        self.max_parallel_count = self.max_cell_count
        lower = numpy.zeros(2 + (6 * self.max_cell_count), dtype=float)
        upper = numpy.zeros(2 + (6 * self.max_cell_count), dtype=float)
        lower[0:2] = (1.0, 1.0)
        upper[0:2] = (float(self.max_series_count), float(self.max_parallel_count))
        for index in range(self.max_cell_count):
            offset = 2 + (6 * index)
            lower[offset : offset + 6] = (0.0, 0.0, 0.0, -180.0, -180.0, -180.0)
            upper[offset : offset + 6] = (
                self.requirements.max_width_mm,
                self.requirements.max_depth_mm,
                self.requirements.max_height_mm,
                180.0,
                180.0,
                180.0,
            )
        self.bounds = Bounds(lb=lower, ub=upper)
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._width_margin_from_pose),
            ConstraintDefinition(kind="ineq", evaluate=self._depth_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._height_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._cell_budget_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._current_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._clearance_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._minimum_spacing_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._temperature_margin),
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier2LayoutOptimizationProblem:
        """Construct one tier-2 optimizer from manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, parameters.get("max_cell_count", 24))),
            minimum_spacing_mm=float(cast(float, parameters.get("minimum_spacing_mm", MIN_SPACING_MM))),
            objective_weights=BatteryObjectiveWeights.from_mapping(
                parameters.get("objective_weights"),
                default_volume=0.45,
                default_cost=0.35,
                default_temperature=0.20,
            ),
            cooling_coefficient_w_per_m2k=float(
                cast(float, parameters.get("cooling_coefficient_w_per_m2k", _DEFAULT_COOLING_COEFFICIENT))
            ),
            passive_cooling_w_per_k=float(
                cast(float, parameters.get("passive_cooling_w_per_k", _DEFAULT_PASSIVE_COOLING))
            ),
            ambient_temperature_c=float(
                cast(float, parameters.get("ambient_temperature_c", _DEFAULT_AMBIENT_TEMPERATURE_C))
            ),
            maximum_temperature_c=float(
                cast(float, parameters.get("maximum_temperature_c", _DEFAULT_MAX_TEMPERATURE_C))
            ),
            load_current_a=cast(float | None, parameters.get("load_current_a")),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return deterministic or seeded tier-2 initial candidate."""
        baseline_series = max(1, round(self.requirements.target_voltage_v / CELL_SPEC_18650.nominal_voltage_v))
        baseline_parallel = max(
            1,
            math.ceil(
                max(
                    self.requirements.minimum_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah,
                    self.requirements.minimum_current_a
                    / (CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c),
                )
            ),
        )
        candidate = numpy.zeros_like(self.bounds.lb)
        candidate[0] = float(min(self.max_series_count, baseline_series))
        candidate[1] = float(min(self.max_parallel_count, baseline_parallel))
        helper_initial = self._pose_helper.generate_initial_solution(seed=seed)
        candidate[2:] = helper_initial[1:]
        return self._normalize_vector(candidate)

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> Tier2DecodedCandidate:
        """Decode one tier-2 candidate."""
        normalized = self._normalize_vector(variables)
        series_count = round(float(normalized[0]))
        parallel_count = round(float(normalized[1]))
        return Tier2DecodedCandidate(
            series_count=series_count,
            parallel_count=parallel_count,
            cell_count=series_count * parallel_count,
        )

    def _active_count_and_pose_variables(self, variables: NDArray[numpy.float64]) -> tuple[int, NDArray[numpy.float64]]:
        decoded = self.decode_candidate(variables)
        return (decoded.cell_count, numpy.array(variables[2:], dtype=float, copy=False))

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        normalized = self._normalize_vector(variables)
        decoded = self.decode_candidate(normalized)
        helper = self._pose_helper_evaluation(
            active_cell_count=decoded.cell_count,
            pose_variables=numpy.array(normalized[2:], dtype=float, copy=False),
        )
        voltage_v = float(decoded.series_count) * CELL_SPEC_18650.nominal_voltage_v
        capacity_ah = float(decoded.parallel_count) * CELL_SPEC_18650.nominal_capacity_ah
        current_limit_a = (
            float(decoded.parallel_count) * CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
        )
        connection_count = float(max(0, decoded.series_count + 1) * max(0, decoded.parallel_count - 1))
        max_temperature_c = _thermal_peak_temperature_c(
            cell_count=decoded.cell_count,
            parallel_equivalent=float(max(decoded.parallel_count, 1)),
            surface_area_mm2=float(helper.surface_area_mm2),
            load_current_a=self.load_current_a,
            cooling_coefficient_w_per_m2k=self.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=self.passive_cooling_w_per_k,
            ambient_temperature_c=self.ambient_temperature_c,
        )
        return BatteryTierMetrics(
            cell_count=float(decoded.cell_count),
            connection_count=connection_count,
            cost_usd=float(decoded.cell_count) * CELL_SPEC_18650.unit_cost_usd,
            design_volume_mm3=float(helper.design_volume_mm3),
            max_temperature_c=max_temperature_c,
            voltage_v=voltage_v,
            capacity_ah=capacity_ah,
            current_limit_a=current_limit_a,
            min_clearance_mm=float(helper.minimum_surface_clearance_mm),
            is_feasible=True,
        )

    def _width_margin_from_pose(self, variables: NDArray[numpy.float64]) -> float:
        evaluation = self._pose_for_margin(variables)
        return self.requirements.max_width_mm - float(evaluation.design_width_mm)

    def _cell_budget_margin(self, variables: NDArray[numpy.float64]) -> float:
        return float(self.max_cell_count - self.decode_candidate(variables).cell_count)


class Battery18650Tier3TopologyOptimizationProblem(_TierOrientedOptimizationBase):
    """Tier-3 optimizer: variable cell count, stage topology, and full poses."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        minimum_spacing_mm: float = MIN_SPACING_MM,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_w_per_m2k: float = _DEFAULT_COOLING_COEFFICIENT,
        passive_cooling_w_per_k: float = _DEFAULT_PASSIVE_COOLING,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
    ) -> None:
        """Initialize tier-3 optimization."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
            max_cell_count=max_cell_count,
            minimum_spacing_mm=minimum_spacing_mm,
            objective_weights=objective_weights or BatteryObjectiveWeights(volume=0.40, cost=0.30, temperature=0.30),
            cooling_coefficient_w_per_m2k=cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=passive_cooling_w_per_k,
            ambient_temperature_c=ambient_temperature_c,
            maximum_temperature_c=maximum_temperature_c,
            load_current_a=load_current_a,
        )
        # Decision vector:
        #   [cell_count, series_count, (x,y,z,ax,ay,az,stage_slot)*max_cell_count]
        lower = numpy.zeros(2 + (7 * self.max_cell_count), dtype=float)
        upper = numpy.zeros(2 + (7 * self.max_cell_count), dtype=float)
        lower[0:2] = (1.0, 1.0)
        upper[0:2] = (float(self.max_cell_count), float(self.max_cell_count))
        for index in range(self.max_cell_count):
            offset = 2 + (7 * index)
            lower[offset : offset + 7] = (0.0, 0.0, 0.0, -180.0, -180.0, -180.0, 0.0)
            upper[offset : offset + 7] = (
                self.requirements.max_width_mm,
                self.requirements.max_depth_mm,
                self.requirements.max_height_mm,
                180.0,
                180.0,
                180.0,
                float(self.max_cell_count - 1),
            )
        self.bounds = Bounds(lb=lower, ub=upper)
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._width_margin_from_pose),
            ConstraintDefinition(kind="ineq", evaluate=self._depth_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._height_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._current_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._clearance_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._minimum_spacing_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._temperature_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._stage_completeness_margin),
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier3TopologyOptimizationProblem:
        """Construct one tier-3 optimizer from manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, parameters.get("max_cell_count", 24))),
            minimum_spacing_mm=float(cast(float, parameters.get("minimum_spacing_mm", MIN_SPACING_MM))),
            objective_weights=BatteryObjectiveWeights.from_mapping(
                parameters.get("objective_weights"),
                default_volume=0.40,
                default_cost=0.30,
                default_temperature=0.30,
            ),
            cooling_coefficient_w_per_m2k=float(
                cast(float, parameters.get("cooling_coefficient_w_per_m2k", _DEFAULT_COOLING_COEFFICIENT))
            ),
            passive_cooling_w_per_k=float(
                cast(float, parameters.get("passive_cooling_w_per_k", _DEFAULT_PASSIVE_COOLING))
            ),
            ambient_temperature_c=float(
                cast(float, parameters.get("ambient_temperature_c", _DEFAULT_AMBIENT_TEMPERATURE_C))
            ),
            maximum_temperature_c=float(
                cast(float, parameters.get("maximum_temperature_c", _DEFAULT_MAX_TEMPERATURE_C))
            ),
            load_current_a=cast(float | None, parameters.get("load_current_a")),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return deterministic or seeded tier-3 initial candidate."""
        baseline_series = max(1, round(self.requirements.target_voltage_v / CELL_SPEC_18650.nominal_voltage_v))
        baseline_parallel = max(
            1,
            math.ceil(
                max(
                    self.requirements.minimum_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah,
                    self.requirements.minimum_current_a
                    / (CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c),
                )
            ),
        )
        cell_count = min(self.max_cell_count, baseline_series * baseline_parallel)
        candidate = numpy.zeros_like(self.bounds.lb)
        candidate[0] = float(cell_count)
        candidate[1] = float(min(baseline_series, cell_count))
        helper_initial = self._pose_helper.generate_initial_solution(seed=seed)
        for index in range(self.max_cell_count):
            source = 1 + (6 * index)
            target = 2 + (7 * index)
            candidate[target : target + 6] = helper_initial[source : source + 6]
            candidate[target + 6] = float(index % max(1, int(candidate[1])))
        return self._normalize_vector(candidate)

    def _decode(self, variables: NDArray[numpy.float64]) -> Tier3DecodedCandidate:
        normalized = self._normalize_vector(variables)
        cell_count = round(float(normalized[0]))
        series_count = round(float(normalized[1]))
        series_count = max(1, min(series_count, cell_count))
        stage_counts = [0 for _ in range(series_count)]
        for cell_index in range(cell_count):
            offset = 2 + (7 * cell_index)
            stage_slot = round(float(normalized[offset + 6]))
            stage_slot = max(0, min(stage_slot, series_count - 1))
            stage_counts[stage_slot] += 1
        return Tier3DecodedCandidate(
            cell_count=cell_count,
            series_count=series_count,
            stage_counts=tuple(stage_counts),
        )

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> Tier3DecodedCandidate:
        """Decode one tier-3 candidate."""
        return self._decode(variables)

    def _active_count_and_pose_variables(self, variables: NDArray[numpy.float64]) -> tuple[int, NDArray[numpy.float64]]:
        normalized = self._normalize_vector(variables)
        decoded = self._decode(normalized)
        pose_values = numpy.zeros(6 * self.max_cell_count, dtype=float)
        for index in range(self.max_cell_count):
            source = 2 + (7 * index)
            target = 6 * index
            pose_values[target : target + 6] = normalized[source : source + 6]
        return (decoded.cell_count, pose_values)

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        normalized = self._normalize_vector(variables)
        decoded = self._decode(normalized)
        active_count, pose_values = self._active_count_and_pose_variables(normalized)
        helper = self._pose_helper_evaluation(active_cell_count=active_count, pose_variables=pose_values)
        min_stage_population = min(decoded.stage_counts, default=0)
        voltage_v = float(decoded.series_count) * CELL_SPEC_18650.nominal_voltage_v
        capacity_ah = float(min_stage_population) * CELL_SPEC_18650.nominal_capacity_ah
        current_limit_a = (
            float(min_stage_population) * CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
        )
        connection_count = float(
            sum(max(0, count - 1) for count in decoded.stage_counts) + max(0, decoded.series_count - 1)
        )
        max_temperature_c = _thermal_peak_temperature_c(
            cell_count=decoded.cell_count,
            parallel_equivalent=float(max(min_stage_population, 1)),
            surface_area_mm2=float(helper.surface_area_mm2),
            load_current_a=self.load_current_a,
            cooling_coefficient_w_per_m2k=self.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=self.passive_cooling_w_per_k,
            ambient_temperature_c=self.ambient_temperature_c,
        )
        return BatteryTierMetrics(
            cell_count=float(decoded.cell_count),
            connection_count=connection_count,
            cost_usd=float(decoded.cell_count) * CELL_SPEC_18650.unit_cost_usd,
            design_volume_mm3=float(helper.design_volume_mm3),
            max_temperature_c=max_temperature_c,
            voltage_v=voltage_v,
            capacity_ah=capacity_ah,
            current_limit_a=current_limit_a,
            min_clearance_mm=float(helper.minimum_surface_clearance_mm),
            is_feasible=True,
            failure_reason=None if min_stage_population > 0 else "At least one series stage is empty.",
        )

    def _stage_completeness_margin(self, variables: NDArray[numpy.float64]) -> float:
        return float(min(self._decode(variables).stage_counts, default=0))

    def _width_margin_from_pose(self, variables: NDArray[numpy.float64]) -> float:
        evaluation = self._pose_for_margin(variables)
        return self.requirements.max_width_mm - float(evaluation.design_width_mm)


class Battery18650Tier4ThermalOptimizationProblem(Battery18650Tier3TopologyOptimizationProblem):
    """Tier-4 optimizer: tier-3 freedom plus thermal-system design variables."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        minimum_spacing_mm: float = MIN_SPACING_MM,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_bounds: tuple[float, float] = (5.0, 50.0),
        passive_cooling_bounds: tuple[float, float] = (0.1, 10.0),
        ambient_temperature_bounds: tuple[float, float] = (5.0, 45.0),
        thermal_model: str = _DEFAULT_THERMAL_MODEL,
        thermal_neighbor_clearance_mm: float = 8.0,
        thermal_contact_decay_mm: float = 2.0,
        thermal_contact_resistance_k_per_w: float = 2.5,
        thermal_flow_shadowing_factor: float = 0.25,
        thermal_airflow_axis: str = "x",
        thermal_reference_soc: float = 0.5,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
    ) -> None:
        """Initialize tier-4 optimization."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
            max_cell_count=max_cell_count,
            minimum_spacing_mm=minimum_spacing_mm,
            objective_weights=objective_weights or BatteryObjectiveWeights(volume=0.35, cost=0.25, temperature=0.40),
            cooling_coefficient_w_per_m2k=0.0,
            passive_cooling_w_per_k=1.0,
            ambient_temperature_c=25.0,
            maximum_temperature_c=maximum_temperature_c,
            load_current_a=load_current_a,
        )
        self._thermal_priors: BatteryThermalPriors = load_18650_thermal_priors()
        self.thermal_model = self._coerce_thermal_model(thermal_model)
        self.thermal_neighbor_clearance_mm = max(0.0, float(thermal_neighbor_clearance_mm))
        self.thermal_contact_decay_mm = max(1.0e-6, float(thermal_contact_decay_mm))
        self.thermal_contact_resistance_k_per_w = max(1.0e-6, float(thermal_contact_resistance_k_per_w))
        self.thermal_flow_shadowing_factor = float(numpy.clip(thermal_flow_shadowing_factor, 0.0, 1.0))
        self.thermal_airflow_axis = self._coerce_airflow_axis(thermal_airflow_axis)
        self.thermal_reference_soc = float(numpy.clip(thermal_reference_soc, 0.0, 1.0))
        cell_radius_m = (CELL_SPEC_18650.diameter_mm / 2.0) * 1.0e-3
        cell_length_m = CELL_SPEC_18650.length_mm * 1.0e-3
        self._single_cell_surface_area_m2 = (2.0 * math.pi * cell_radius_m * cell_length_m) + (
            2.0 * math.pi * (cell_radius_m**2)
        )
        self._latest_thermal_diagnostics: Tier4ThermalDiagnostics | None = None
        self.cooling_coefficient_bounds = (
            float(cooling_coefficient_bounds[0]),
            float(cooling_coefficient_bounds[1]),
        )
        self.passive_cooling_bounds = (
            float(passive_cooling_bounds[0]),
            float(passive_cooling_bounds[1]),
        )
        self.ambient_temperature_bounds = (
            float(ambient_temperature_bounds[0]),
            float(ambient_temperature_bounds[1]),
        )
        base_lb = self.bounds.lb
        base_ub = self.bounds.ub
        self.bounds = Bounds(
            lb=numpy.concatenate(
                [
                    base_lb,
                    numpy.array(
                        [
                            self.cooling_coefficient_bounds[0],
                            self.passive_cooling_bounds[0],
                            self.ambient_temperature_bounds[0],
                        ],
                        dtype=float,
                    ),
                ]
            ),
            ub=numpy.concatenate(
                [
                    base_ub,
                    numpy.array(
                        [
                            self.cooling_coefficient_bounds[1],
                            self.passive_cooling_bounds[1],
                            self.ambient_temperature_bounds[1],
                        ],
                        dtype=float,
                    ),
                ]
            ),
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier4ThermalOptimizationProblem:
        """Construct one tier-4 optimizer from manifest data."""
        parameters = manifest.parameters
        cooling_bounds = cast(
            dict[str, float], parameters.get("cooling_coefficient_bounds", {"lower": 5.0, "upper": 50.0})
        )
        passive_bounds = cast(dict[str, float], parameters.get("passive_cooling_bounds", {"lower": 0.1, "upper": 10.0}))
        ambient_bounds = cast(
            dict[str, float], parameters.get("ambient_temperature_bounds", {"lower": 5.0, "upper": 45.0})
        )
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, parameters.get("max_cell_count", 24))),
            minimum_spacing_mm=float(cast(float, parameters.get("minimum_spacing_mm", MIN_SPACING_MM))),
            objective_weights=BatteryObjectiveWeights.from_mapping(
                parameters.get("objective_weights"),
                default_volume=0.35,
                default_cost=0.25,
                default_temperature=0.40,
            ),
            cooling_coefficient_bounds=(
                float(cooling_bounds.get("lower", 5.0)),
                float(cooling_bounds.get("upper", 50.0)),
            ),
            passive_cooling_bounds=(
                float(passive_bounds.get("lower", 0.1)),
                float(passive_bounds.get("upper", 10.0)),
            ),
            ambient_temperature_bounds=(
                float(ambient_bounds.get("lower", 5.0)),
                float(ambient_bounds.get("upper", 45.0)),
            ),
            thermal_model=str(cast(str, parameters.get("thermal_model", _DEFAULT_THERMAL_MODEL))),
            thermal_neighbor_clearance_mm=float(cast(float, parameters.get("thermal_neighbor_clearance_mm", 8.0))),
            thermal_contact_decay_mm=float(cast(float, parameters.get("thermal_contact_decay_mm", 2.0))),
            thermal_contact_resistance_k_per_w=float(
                cast(float, parameters.get("thermal_contact_resistance_k_per_w", 2.5))
            ),
            thermal_flow_shadowing_factor=float(cast(float, parameters.get("thermal_flow_shadowing_factor", 0.25))),
            thermal_airflow_axis=str(cast(str, parameters.get("thermal_airflow_axis", "x"))),
            thermal_reference_soc=float(cast(float, parameters.get("thermal_reference_soc", 0.5))),
            maximum_temperature_c=float(
                cast(float, parameters.get("maximum_temperature_c", _DEFAULT_MAX_TEMPERATURE_C))
            ),
            load_current_a=cast(float | None, parameters.get("load_current_a")),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return deterministic or seeded tier-4 initial candidate."""
        base = super().generate_initial_solution(seed=seed)
        candidate = numpy.zeros_like(self.bounds.lb)
        candidate[: base.shape[0]] = base
        candidate[-3:] = numpy.array(
            [
                sum(self.cooling_coefficient_bounds) / 2.0,
                sum(self.passive_cooling_bounds) / 2.0,
                sum(self.ambient_temperature_bounds) / 2.0,
            ],
            dtype=float,
        )
        return self._normalize_vector(candidate)

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return clipped tier-4 vectors, accepting full or base tier-3 shapes."""
        normalized = numpy.array(variables, dtype=float, copy=True)
        full_dimension = self.bounds.lb.shape[0]
        base_dimension = full_dimension - 3
        if normalized.shape == (full_dimension,):
            lb = self.bounds.lb
            ub = self.bounds.ub
        elif normalized.shape == (base_dimension,):
            lb = self.bounds.lb[:-3]
            ub = self.bounds.ub[:-3]
        else:
            raise ValueError(
                f"Expected a {base_dimension}- or {full_dimension}-variable design vector, "
                f"received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, lb, ub), dtype=float, copy=False)

    def _thermal_parameters_from_variables(self, variables: NDArray[numpy.float64]) -> tuple[float, float, float]:
        normalized = self._normalize_vector(variables)
        if normalized.shape[0] != self.bounds.lb.shape[0]:
            raise ValueError("Tier-4 thermal parameters require the full tier-4 design vector.")
        return (
            float(normalized[-3]),
            float(normalized[-2]),
            float(normalized[-1]),
        )

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> Tier3DecodedCandidate:
        """Decode one tier-4 candidate into the shared tier-3 topology summary."""
        normalized = self._normalize_vector(variables)
        return super().decode_candidate(normalized[:-3])

    def decode_thermal_candidate(self, variables: NDArray[numpy.float64]) -> Tier4DecodedCandidate:
        """Decode one tier-4 candidate including thermal-system variables."""
        normalized = self._normalize_vector(variables)
        base = super().decode_candidate(normalized[:-3])
        cooling, passive, ambient = self._thermal_parameters_from_variables(normalized)
        return Tier4DecodedCandidate(
            base=base,
            cooling_coefficient_w_per_m2k=cooling,
            passive_cooling_w_per_k=passive,
            ambient_temperature_c=ambient,
        )

    def _active_count_and_pose_variables(self, variables: NDArray[numpy.float64]) -> tuple[int, NDArray[numpy.float64]]:
        normalized = self._normalize_vector(variables)
        base = normalized if normalized.shape[0] == self.bounds.lb.shape[0] - 3 else normalized[:-3]
        return super()._active_count_and_pose_variables(base)

    def _decode(self, variables: NDArray[numpy.float64]) -> Tier3DecodedCandidate:
        normalized = self._normalize_vector(variables)
        base = normalized if normalized.shape[0] == self.bounds.lb.shape[0] - 3 else normalized[:-3]
        return super()._decode(base)

    def _coerce_thermal_model(self, thermal_model: str) -> str:
        model = thermal_model.strip().lower()
        if model not in {_THERMAL_MODEL_LUMPED, _THERMAL_MODEL_MULTI_NODE}:
            raise ValueError(
                "Tier-4 thermal_model must be one of "
                f"{_THERMAL_MODEL_LUMPED!r} or {_THERMAL_MODEL_MULTI_NODE!r}, received {thermal_model!r}."
            )
        return model

    def _coerce_airflow_axis(self, axis: str) -> str:
        value = axis.strip().lower()
        if value not in {"x", "y", "z"}:
            raise ValueError(f"Tier-4 thermal_airflow_axis must be one of 'x', 'y', 'z', received {axis!r}.")
        return value

    def _effective_parallel_and_resistance(self, decoded: Tier3DecodedCandidate) -> tuple[float, float]:
        min_stage_population = min(decoded.stage_counts, default=0)
        parallel_equivalent = float(max(min_stage_population, 1))
        effective_resistance = interpolate_total_resistance(self._thermal_priors, self.thermal_reference_soc)
        return (parallel_equivalent, effective_resistance)

    def _airflow_shadow_factors(self, cells: tuple[Any, ...]) -> list[float]:
        if not cells:
            return []
        axis_accessor = {
            "x": lambda cell: float(cell.x_mm),
            "y": lambda cell: float(cell.y_mm),
            "z": lambda cell: float(cell.z_mm),
        }[self.thermal_airflow_axis]
        coordinates = [axis_accessor(cell) for cell in cells]
        minimum = min(coordinates)
        maximum = max(coordinates)
        span = max(maximum - minimum, 1.0e-9)
        factors: list[float] = []
        for coordinate in coordinates:
            position = (coordinate - minimum) / span
            factor = 1.0 - (self.thermal_flow_shadowing_factor * position)
            factors.append(float(max(0.1, min(1.0, factor))))
        return factors

    def _pairwise_contact_conductances(self, cells: tuple[Any, ...]) -> dict[tuple[int, int], float]:
        conductances: dict[tuple[int, int], float] = {}
        for first_index in range(len(cells)):
            first = cells[first_index]
            for second_index in range(first_index + 1, len(cells)):
                second = cells[second_index]
                center_distance = math.sqrt(
                    ((float(first.x_mm) - float(second.x_mm)) ** 2)
                    + ((float(first.y_mm) - float(second.y_mm)) ** 2)
                    + ((float(first.z_mm) - float(second.z_mm)) ** 2)
                )
                clearance_mm = center_distance - CELL_SPEC_18650.diameter_mm
                if clearance_mm > self.thermal_neighbor_clearance_mm:
                    continue
                coupling = (1.0 / self.thermal_contact_resistance_k_per_w) * math.exp(
                    -max(clearance_mm, 0.0) / self.thermal_contact_decay_mm
                )
                if coupling <= 0.0:
                    continue
                conductances[(first_index, second_index)] = float(coupling)
        return conductances

    def _solve_lumped_thermal_network(
        self,
        *,
        cell_count: int,
        per_cell_heat_w: float,
        cooling_coefficient_w_per_m2k: float,
        passive_cooling_w_per_k: float,
        ambient_temperature_c: float,
        total_surface_area_mm2: float,
    ) -> _Tier4NodeThermalSolution:
        if cell_count <= 0:
            return _Tier4NodeThermalSolution(
                max_core_temperature_c=ambient_temperature_c,
                max_surface_temperature_c=ambient_temperature_c,
                coolant_temperature_c=ambient_temperature_c,
                max_core_surface_delta_c=0.0,
            )
        total_heat_w = float(cell_count) * per_cell_heat_w
        cooling_area_m2 = max(total_surface_area_mm2, 0.0) * 1.0e-6
        base_path_conductance = 1.0 / (
            (1.0 / max(self._thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9))
            + (1.0 / max(self._thermal_priors.jig_to_ambient_conductance_w_per_k, 1.0e-9))
        )
        cooling_conductance = (
            max(passive_cooling_w_per_k, 1.0e-9)
            + max(cooling_coefficient_w_per_m2k, 0.0) * cooling_area_m2
            + base_path_conductance
        )
        coolant_conductance = (
            max(passive_cooling_w_per_k, 1.0e-9) + self._thermal_priors.jig_to_ambient_conductance_w_per_k
        )
        max_core_temperature_c = float(ambient_temperature_c + (total_heat_w / max(cooling_conductance, 1.0e-9)))
        coolant_temperature_c = float(ambient_temperature_c + (total_heat_w / max(coolant_conductance, 1.0e-9)))
        return _Tier4NodeThermalSolution(
            max_core_temperature_c=max_core_temperature_c,
            max_surface_temperature_c=max_core_temperature_c,
            coolant_temperature_c=coolant_temperature_c,
            max_core_surface_delta_c=max(0.0, max_core_temperature_c - coolant_temperature_c),
        )

    def _solve_multi_node_thermal_network(
        self,
        *,
        decoded: Tier3DecodedCandidate,
        cells: tuple[Any, ...],
        per_cell_heat_w: float,
        cooling_coefficient_w_per_m2k: float,
        passive_cooling_w_per_k: float,
        ambient_temperature_c: float,
    ) -> _Tier4NodeThermalSolution:
        cell_count = int(decoded.cell_count)
        if cell_count <= 0:
            return _Tier4NodeThermalSolution(
                max_core_temperature_c=ambient_temperature_c,
                max_surface_temperature_c=ambient_temperature_c,
                coolant_temperature_c=ambient_temperature_c,
                max_core_surface_delta_c=0.0,
            )

        node_count = (2 * cell_count) + 1
        matrix = numpy.zeros((node_count, node_count), dtype=float)
        vector = numpy.zeros(node_count, dtype=float)
        coolant_index = 2 * cell_count
        thermal_contact = self._pairwise_contact_conductances(cells)
        shadow_factors = self._airflow_shadow_factors(cells)
        core_surface_conductance = max(2.0 * self._thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9)
        base_surface_coolant_conductance = max(2.0 * self._thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9)

        for cell_index in range(cell_count):
            core_index = cell_index
            surface_index = cell_count + cell_index
            matrix[core_index, core_index] += core_surface_conductance
            matrix[core_index, surface_index] -= core_surface_conductance
            vector[core_index] += per_cell_heat_w

            matrix[surface_index, core_index] -= core_surface_conductance
            matrix[surface_index, surface_index] += core_surface_conductance
            surface_coolant_conductance = base_surface_coolant_conductance + (
                max(cooling_coefficient_w_per_m2k, 0.0) * self._single_cell_surface_area_m2 * shadow_factors[cell_index]
            )
            matrix[surface_index, surface_index] += surface_coolant_conductance
            matrix[surface_index, coolant_index] -= surface_coolant_conductance
            matrix[coolant_index, coolant_index] += surface_coolant_conductance
            matrix[coolant_index, surface_index] -= surface_coolant_conductance

        for (first_index, second_index), conductance in thermal_contact.items():
            surface_first = cell_count + first_index
            surface_second = cell_count + second_index
            matrix[surface_first, surface_first] += conductance
            matrix[surface_second, surface_second] += conductance
            matrix[surface_first, surface_second] -= conductance
            matrix[surface_second, surface_first] -= conductance

        coolant_to_ambient = (
            max(passive_cooling_w_per_k, 1.0e-9) + self._thermal_priors.jig_to_ambient_conductance_w_per_k
        )
        matrix[coolant_index, coolant_index] += coolant_to_ambient
        vector[coolant_index] += coolant_to_ambient * ambient_temperature_c

        try:
            temperatures = numpy.linalg.solve(matrix, vector)
        except numpy.linalg.LinAlgError:
            temperatures = numpy.linalg.lstsq(matrix, vector, rcond=None)[0]

        core_temperatures = temperatures[:cell_count]
        surface_temperatures = temperatures[cell_count : 2 * cell_count]
        coolant_temperature = float(temperatures[coolant_index])
        core_surface_deltas = core_temperatures - surface_temperatures
        max_core_surface_delta = max(0.0, float(numpy.max(core_surface_deltas)))
        return _Tier4NodeThermalSolution(
            max_core_temperature_c=float(numpy.max(core_temperatures)),
            max_surface_temperature_c=float(numpy.max(surface_temperatures)),
            coolant_temperature_c=coolant_temperature,
            max_core_surface_delta_c=max_core_surface_delta,
        )

    def _solve_thermal_network(
        self,
        *,
        decoded: Tier3DecodedCandidate,
        pose_evaluation: Any,
        cooling_coefficient_w_per_m2k: float,
        passive_cooling_w_per_k: float,
        ambient_temperature_c: float,
    ) -> _Tier4NodeThermalSolution:
        parallel_equivalent, effective_resistance = self._effective_parallel_and_resistance(decoded)
        per_cell_current = self.load_current_a / max(parallel_equivalent, 1.0e-9)
        per_cell_heat_w = (per_cell_current**2) * max(effective_resistance, 1.0e-9)
        if self.thermal_model == _THERMAL_MODEL_LUMPED:
            return self._solve_lumped_thermal_network(
                cell_count=decoded.cell_count,
                per_cell_heat_w=per_cell_heat_w,
                cooling_coefficient_w_per_m2k=cooling_coefficient_w_per_m2k,
                passive_cooling_w_per_k=passive_cooling_w_per_k,
                ambient_temperature_c=ambient_temperature_c,
                total_surface_area_mm2=float(pose_evaluation.surface_area_mm2),
            )
        return self._solve_multi_node_thermal_network(
            decoded=decoded,
            cells=tuple(pose_evaluation.cells),
            per_cell_heat_w=per_cell_heat_w,
            cooling_coefficient_w_per_m2k=cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=passive_cooling_w_per_k,
            ambient_temperature_c=ambient_temperature_c,
        )

    def thermal_diagnostics(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return optional detailed thermal diagnostics for one candidate."""
        normalized = self._normalize_vector(variables)
        if normalized.shape[0] != self.bounds.lb.shape[0]:
            raise ValueError("Tier-4 thermal diagnostics require the full tier-4 design vector.")
        base_vector = normalized[:-3]
        decoded = super()._decode(base_vector)
        cooling_coefficient, passive_cooling, ambient_temperature = self._thermal_parameters_from_variables(normalized)
        active_count, pose_values = super()._active_count_and_pose_variables(base_vector)
        pose_eval = self._pose_helper_evaluation(active_cell_count=active_count, pose_variables=pose_values)
        thermal_solution = self._solve_thermal_network(
            decoded=decoded,
            pose_evaluation=pose_eval,
            cooling_coefficient_w_per_m2k=cooling_coefficient,
            passive_cooling_w_per_k=passive_cooling,
            ambient_temperature_c=ambient_temperature,
        )
        diagnostics = Tier4ThermalDiagnostics(
            thermal_model=self.thermal_model,
            max_core_temperature_c=thermal_solution.max_core_temperature_c,
            max_surface_temperature_c=thermal_solution.max_surface_temperature_c,
            coolant_temperature_c=thermal_solution.coolant_temperature_c,
            max_core_surface_delta_c=thermal_solution.max_core_surface_delta_c,
        )
        self._latest_thermal_diagnostics = diagnostics
        return {
            "max_core_temperature_c": diagnostics.max_core_temperature_c,
            "max_surface_temperature_c": diagnostics.max_surface_temperature_c,
            "coolant_temperature_c": diagnostics.coolant_temperature_c,
            "max_core_surface_delta_c": diagnostics.max_core_surface_delta_c,
        }

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        normalized = self._normalize_vector(variables)
        if normalized.shape[0] != self.bounds.lb.shape[0]:
            raise ValueError("Tier-4 metric evaluation requires the full tier-4 design vector.")
        base_vector = normalized[:-3]
        base_metrics = super()._metrics_from_variables(base_vector)
        cooling_coefficient, passive_cooling, ambient_temperature = self._thermal_parameters_from_variables(normalized)
        active_count, pose_values = super()._active_count_and_pose_variables(base_vector)
        pose_eval = self._pose_helper_evaluation(active_cell_count=active_count, pose_variables=pose_values)
        decoded = super()._decode(base_vector)
        thermal_solution = self._solve_thermal_network(
            decoded=decoded,
            pose_evaluation=pose_eval,
            cooling_coefficient_w_per_m2k=cooling_coefficient,
            passive_cooling_w_per_k=passive_cooling,
            ambient_temperature_c=ambient_temperature,
        )
        self._latest_thermal_diagnostics = Tier4ThermalDiagnostics(
            thermal_model=self.thermal_model,
            max_core_temperature_c=thermal_solution.max_core_temperature_c,
            max_surface_temperature_c=thermal_solution.max_surface_temperature_c,
            coolant_temperature_c=thermal_solution.coolant_temperature_c,
            max_core_surface_delta_c=thermal_solution.max_core_surface_delta_c,
        )
        return BatteryTierMetrics(
            cell_count=base_metrics.cell_count,
            connection_count=base_metrics.connection_count,
            cost_usd=base_metrics.cost_usd,
            design_volume_mm3=base_metrics.design_volume_mm3,
            max_temperature_c=thermal_solution.max_core_temperature_c,
            voltage_v=base_metrics.voltage_v,
            capacity_ah=base_metrics.capacity_ah,
            current_limit_a=base_metrics.current_limit_a,
            min_clearance_mm=base_metrics.min_clearance_mm,
            is_feasible=True,
            failure_reason=base_metrics.failure_reason,
        )


__all__ = [
    "Battery18650Tier1SeriesParallelOptimizationProblem",
    "Battery18650Tier2LayoutOptimizationProblem",
    "Battery18650Tier3TopologyOptimizationProblem",
    "Battery18650Tier4ThermalOptimizationProblem",
    "Tier2DecodedCandidate",
    "Tier3DecodedCandidate",
    "Tier4DecodedCandidate",
    "Tier4ThermalDiagnostics",
]
