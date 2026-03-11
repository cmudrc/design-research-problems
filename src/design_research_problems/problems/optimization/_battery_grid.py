"""Rectangular 18650 battery-grid sizing optimization problem."""

from __future__ import annotations

import math

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.battery_cell_model import BatteryBackendConfig, load_18650_cell_model
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    evaluate_battery_circuit,
)
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    BatteryRequirements,
    grid_index_limits,
)
from design_research_problems.problems._domains.battery_series_parallel import (
    SeriesParallelBatteryEvaluation,
    SeriesParallelBatteryState,
    build_canonical_series_parallel_state,
    evaluate_series_parallel_state,
    series_parallel_requirement_violation,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)
from design_research_problems.problems.grammar._battery_problem_base import (
    parse_battery_backend_config,
    parse_battery_requirements,
)

_INFEASIBILITY_PENALTY_SCALE = 1_000.0


class BatteryGridSizingProblem(OptimizationProblem):
    """Cost minimization over canonical rectangular ``S x P`` battery packs."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        backend_config: BatteryBackendConfig | None = None,
    ) -> None:
        """Initialize the packaged battery-grid sizing instance.

        Args:
            metadata: Value for ``metadata``.
            statement_markdown: Value for ``statement_markdown``.
            resource_bundle: Value for ``resource_bundle``.
            requirements: Value for ``requirements``.
            backend_config: Value for ``backend_config``.
        """
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
        max_x, max_y, _ = grid_index_limits(self.requirements)
        self.bounds = Bounds(
            lb=numpy.array([1.0, 1.0], dtype=float),
            ub=numpy.array([float(max_x + 1), float(max_y + 1)], dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._width_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._depth_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._height_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._current_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._backend_feasibility_margin),
        ]
        self._evaluation_cache: dict[tuple[int, int], SeriesParallelBatteryEvaluation] = {}
        self.backend_config = backend_config

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryGridSizingProblem:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Value for ``manifest``.

        Returns:
            Computed result for this callable.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            backend_config=parse_battery_backend_config(manifest),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return a deterministic near-feasible starting point.

        Args:
            seed: Value for ``seed``.

        Returns:
            Computed result for this callable.
        """
        baseline = self._baseline_initial_solution()
        if seed is None:
            return baseline

        baseline_series, baseline_parallel = self._normalized_counts(baseline)
        max_parallel = self._max_parallel_count()
        if max_parallel > 1:
            parallel_count = 1 + ((abs(seed) + baseline_parallel - 1) % max_parallel)
            if parallel_count == baseline_parallel:
                parallel_count = 1 + (parallel_count % max_parallel)
            return numpy.array([float(baseline_series), float(parallel_count)], dtype=float)

        max_series = self._max_series_count()
        if max_series > 1:
            series_count = 1 + ((abs(seed) + baseline_series - 1) % max_series)
            if series_count == baseline_series:
                series_count = 1 + (series_count % max_series)
            return numpy.array([float(series_count), float(baseline_parallel)], dtype=float)

        return baseline

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return deterministic pack cost with a fixed infeasibility penalty.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        evaluation = self._evaluation_from_variables(variables)
        total_violation, _ = series_parallel_requirement_violation(evaluation, self.requirements)
        return evaluation.design_cost + (_INFEASIBILITY_PENALTY_SCALE * total_violation)

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the main reported pack metrics for one design vector.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        evaluation = self._evaluation_from_variables(variables)
        return {
            "cost_usd": evaluation.design_cost,
            "voltage_v": evaluation.design_voltage,
            "capacity_ah": evaluation.design_capacity,
            "current_limit_a": evaluation.analytic_current_limit,
            "cell_count": float(evaluation.cell_count),
        }

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Search the discrete ``S x P`` grid in deterministic nearest-first order.

        Args:
            initial_solution: Value for ``initial_solution``.
            seed: Value for ``seed``.
            maxiter: Value for ``maxiter``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        if initial_solution is None:
            anchor = self.generate_initial_solution(seed=seed)
        else:
            anchor = self._normalize_vector(initial_solution)
        if anchor.shape != (2,):
            raise ValueError(f"Expected a 2-variable design vector, received shape {anchor.shape!r}.")

        anchor_series, anchor_parallel = self._normalized_counts(anchor)
        candidates = [
            numpy.array([float(series_count), float(parallel_count)], dtype=float)
            for series_count in range(1, self._max_series_count() + 1)
            for parallel_count in range(1, self._max_parallel_count() + 1)
        ]
        candidates.sort(
            key=lambda candidate: (
                abs(int(candidate[0]) - anchor_series) + abs(int(candidate[1]) - anchor_parallel),
                abs(int(candidate[0]) - self._default_series_count()),
                int(candidate[0]),
                int(candidate[1]),
            )
        )
        budget = max(1, min(maxiter, len(candidates)))

        best_vector = candidates[0]
        best_score = math.inf
        evaluations = 0
        for candidate in candidates[:budget]:
            score = self.objective(candidate)
            evaluations += 1
            if score < best_score:
                best_score = score
                best_vector = candidate

        max_violation = self.max_constraint_violation(best_vector)
        best_evaluation = self._evaluation_from_variables(best_vector)
        if max_violation <= 1e-9:
            message = (
                "Evaluated the nearest rectangular battery grids and found a feasible baseline "
                f"(cost ${best_evaluation.design_cost:.2f})."
            )
        else:
            message = (
                "Evaluated the nearest rectangular battery grids and returned a best-effort design "
                f"(cost ${best_evaluation.design_cost:.2f}, max violation {max_violation:.3g})."
            )
        return OptimizationResult(
            x=best_vector.copy(),
            fun=self.objective(best_vector),
            success=max_violation <= 1e-9,
            message=message,
            nit=budget,
            nfev=evaluations,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return a clipped two-variable vector.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != (2,):
            raise ValueError(f"Expected a 2-variable design vector, received shape {normalized.shape!r}.")
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _normalized_counts(self, variables: NDArray[numpy.float64]) -> tuple[int, int]:
        """Return the rounded, clipped integer counts represented by ``variables``.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        normalized = self._normalize_vector(variables)
        series_count = round(float(normalized[0]))
        parallel_count = round(float(normalized[1]))
        series_count = max(1, min(series_count, self._max_series_count()))
        parallel_count = max(1, min(parallel_count, self._max_parallel_count()))
        return (series_count, parallel_count)

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> SeriesParallelBatteryState:
        """Translate one optimization vector into the canonical rectangular battery state.

        Args:
            variables: Two-variable ``(series_count, parallel_count)`` candidate vector.

        Returns:
            Canonical shared series-parallel battery state for the rounded design.
        """
        series_count, parallel_count = self._normalized_counts(variables)
        return build_canonical_series_parallel_state(series_count, parallel_count)

    def _state_from_variables(self, variables: NDArray[numpy.float64]) -> SeriesParallelBatteryState:
        """Translate the optimization vector into the canonical rectangular battery state.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self.decode_candidate(variables)

    def _evaluate_circuit_state(self, state: BatteryCircuitState) -> BatteryCircuitEvaluation:
        """Evaluate one explicit battery circuit using the shared backend.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        return evaluate_battery_circuit(
            state=state,
            requirements=self.requirements,
            load_cell_model=load_18650_cell_model,
            backend_config=self.backend_config,
        )

    def _evaluation_for_counts(self, series_count: int, parallel_count: int) -> SeriesParallelBatteryEvaluation:
        """Return the cached series-parallel evaluation for one integer ``S x P`` design.

        Args:
            series_count: Value for ``series_count``.
            parallel_count: Value for ``parallel_count``.

        Returns:
            Computed result for this callable.
        """
        key = (series_count, parallel_count)
        cached = self._evaluation_cache.get(key)
        if cached is not None:
            return cached

        state = build_canonical_series_parallel_state(series_count, parallel_count)
        evaluation = evaluate_series_parallel_state(
            state,
            self.requirements,
            self._evaluate_circuit_state,
        )
        self._evaluation_cache[key] = evaluation
        return evaluation

    def _evaluation_from_variables(self, variables: NDArray[numpy.float64]) -> SeriesParallelBatteryEvaluation:
        """Return the shared series-parallel evaluation for the rounded design vector.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        series_count, parallel_count = self._normalized_counts(variables)
        return self._evaluation_for_counts(series_count, parallel_count)

    def _default_series_count(self) -> int:
        """Return the nominal series count nearest the target pack voltage.

        Returns:
            Computed result for this callable.
        """
        target = self.requirements.target_voltage_v / CELL_SPEC_18650.nominal_voltage_v
        rounded = round(target)
        return max(1, min(rounded, self._max_series_count()))

    def _baseline_initial_solution(self) -> NDArray[numpy.float64]:
        """Return the deterministic smallest feasible rectangular baseline.

        Returns:
            Computed result for this callable.
        """
        target_series = self._default_series_count()
        max_parallel = self._max_parallel_count()
        for parallel_count in range(1, max_parallel + 1):
            vector = numpy.array([float(target_series), float(parallel_count)], dtype=float)
            if self.max_constraint_violation(vector) <= 1e-9:
                return vector
        return numpy.array([float(target_series), 1.0], dtype=float)

    def _max_series_count(self) -> int:
        """Return the largest legal series count under the configured bounds.

        Returns:
            Computed result for this callable.
        """
        return round(float(self.bounds.ub[0]))

    def _max_parallel_count(self) -> int:
        """Return the largest legal parallel count under the configured bounds.

        Returns:
            Computed result for this callable.
        """
        return round(float(self.bounds.ub[1]))

    def _width_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining width margin in millimeters.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self.requirements.max_width_mm - self._evaluation_from_variables(variables).design_width

    def _depth_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining depth margin in millimeters.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self.requirements.max_depth_mm - self._evaluation_from_variables(variables).design_depth

    def _height_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining height margin in millimeters.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self.requirements.max_height_mm - self._evaluation_from_variables(variables).design_height

    def _voltage_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the allowed remaining voltage error margin in volts.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        evaluation = self._evaluation_from_variables(variables)
        voltage_error = abs(evaluation.design_voltage - self.requirements.target_voltage_v)
        return self.requirements.voltage_tolerance_v - voltage_error

    def _capacity_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining capacity margin in amp-hours.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self._evaluation_from_variables(variables).design_capacity - self.requirements.minimum_capacity_ah

    def _current_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining analytic current margin in amps.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return self._evaluation_from_variables(variables).analytic_current_limit - self.requirements.minimum_current_a

    def _backend_feasibility_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return a binary margin indicating whether the shared backend accepted the design.

        Args:
            variables: Value for ``variables``.

        Returns:
            Computed result for this callable.
        """
        return 1.0 if self._evaluation_from_variables(variables).is_feasible else -1.0


__all__ = ["BatteryGridSizingProblem"]
