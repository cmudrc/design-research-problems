"""Oriented 18650 battery-pack layout optimization problem."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    MIN_SPACING_MM,
    BatteryRequirements,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
    bounded_pattern_search,
)
from design_research_problems.problems.grammar._battery_problem_base import parse_battery_requirements

_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_CACHE_DECIMALS = 5
_MAX_ABS_ANGLE_DEG = 180.0
_VOLUME_WEIGHT = 0.45
_CELL_COUNT_WEIGHT = 0.35
_TEMPERATURE_WEIGHT = 0.20


@dataclass(frozen=True)
class OrientedBatteryCellPlacement:
    """Continuous-position and orientation description for one cylindrical cell."""

    cell_id: int
    """Stable cell identifier in one decoded candidate."""
    x_mm: float
    """Cell-center x location in millimeters."""
    y_mm: float
    """Cell-center y location in millimeters."""
    z_mm: float
    """Cell-center z location in millimeters."""
    angle_x_deg: float
    """Rotation about the x-axis in degrees."""
    angle_y_deg: float
    """Rotation about the y-axis in degrees."""
    angle_z_deg: float
    """Rotation about the z-axis in degrees."""


@dataclass(frozen=True)
class OrientedBatteryDecodedCandidate:
    """Decoded oriented-cell candidate summary."""

    cell_count: int
    """Active physical cell count."""
    series_count: int
    """Integer series count used by the electrical approximation."""
    parallel_equivalent: float
    """Equivalent parallel count ``cell_count / series_count``."""
    cells: tuple[OrientedBatteryCellPlacement, ...]
    """Active oriented-cell placement records."""


@dataclass(frozen=True)
class OrientedBatteryEvaluation:
    """Computed geometric, electrical, and thermal summary for one candidate."""

    cell_count: int
    """Active physical cell count."""
    series_count: int
    """Integer series count used by the electrical approximation."""
    parallel_equivalent: float
    """Equivalent parallel count ``cell_count / series_count``."""
    design_width_mm: float
    """Bounding-box width in millimeters."""
    design_depth_mm: float
    """Bounding-box depth in millimeters."""
    design_height_mm: float
    """Bounding-box height in millimeters."""
    surface_area_mm2: float
    """Bounding-box surface area in square millimeters."""
    design_volume_mm3: float
    """Bounding-box volume in cubic millimeters."""
    design_cost_usd: float
    """Pack cost proxy based on active cell count."""
    minimum_surface_clearance_mm: float
    """Smallest pairwise cell-to-cell surface clearance."""
    design_voltage_v: float
    """Approximated pack voltage in volts."""
    design_capacity_ah: float
    """Approximated pack capacity in amp-hours."""
    current_limit_a: float
    """Approximated continuous current limit in amps."""
    max_temperature_c: float
    """Steady-state maximum pack temperature under the fixed load."""
    cells: tuple[OrientedBatteryCellPlacement, ...]
    """Active oriented-cell placements."""


class BatteryOrientedLayoutProblem(OptimizationProblem):
    """Oriented 18650 cell-layout optimization with continuous geometry variables."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        minimum_spacing_mm: float = MIN_SPACING_MM,
        cooling_coefficient_w_per_m2k: float = 18.0,
        passive_cooling_w_per_k: float = 1.0,
        ambient_temperature_c: float = 25.0,
        maximum_temperature_c: float = 60.0,
        load_current_a: float | None = None,
    ) -> None:
        """Initialize one packaged oriented battery-layout optimization problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            requirements: Optional battery requirements override.
            max_cell_count: Maximum active cell count represented by the vector.
            minimum_spacing_mm: Minimum required cell-to-cell surface clearance.
            cooling_coefficient_w_per_m2k: Convective cooling coefficient.
            passive_cooling_w_per_k: Constant baseline cooling conductance.
            ambient_temperature_c: Ambient temperature for the thermal proxy.
            maximum_temperature_c: Maximum allowable peak temperature.
            load_current_a: Fixed discharge current used for thermal and current checks.
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
        self.max_cell_count = max(1, int(max_cell_count))
        self.minimum_spacing_mm = max(0.0, float(minimum_spacing_mm))
        self.cooling_coefficient_w_per_m2k = max(0.0, float(cooling_coefficient_w_per_m2k))
        self.passive_cooling_w_per_k = max(1.0e-6, float(passive_cooling_w_per_k))
        self.ambient_temperature_c = float(ambient_temperature_c)
        self.maximum_temperature_c = max(self.ambient_temperature_c + 1.0, float(maximum_temperature_c))
        self.load_current_a = (
            float(load_current_a) if load_current_a is not None else float(self.requirements.minimum_current_a)
        )
        self._cell_radius_mm = CELL_SPEC_18650.diameter_mm / 2.0
        self._cell_half_length_mm = CELL_SPEC_18650.length_mm / 2.0

        dimension = 1 + (6 * self.max_cell_count)
        lower_bounds = numpy.zeros(dimension, dtype=float)
        upper_bounds = numpy.zeros(dimension, dtype=float)
        lower_bounds[0] = 1.0
        upper_bounds[0] = float(self.max_cell_count)
        for cell_index in range(self.max_cell_count):
            offset = 1 + (6 * cell_index)
            lower_bounds[offset : offset + 6] = (
                0.0,
                0.0,
                0.0,
                -_MAX_ABS_ANGLE_DEG,
                -_MAX_ABS_ANGLE_DEG,
                -_MAX_ABS_ANGLE_DEG,
            )
            upper_bounds[offset : offset + 6] = (
                self.requirements.max_width_mm,
                self.requirements.max_depth_mm,
                self.requirements.max_height_mm,
                _MAX_ABS_ANGLE_DEG,
                _MAX_ABS_ANGLE_DEG,
                _MAX_ABS_ANGLE_DEG,
            )
        self.bounds = Bounds(lb=lower_bounds, ub=upper_bounds)
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._width_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._depth_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._height_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._current_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._clearance_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._minimum_spacing_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._temperature_margin),
        ]
        self._evaluation_cache: dict[tuple[float, ...], OrientedBatteryEvaluation] = {}

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryOrientedLayoutProblem:
        """Construct one instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized oriented battery-layout optimization problem.
        """
        requirements = parse_battery_requirements(manifest)
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=requirements,
            max_cell_count=int(cast(int, manifest.parameters.get("max_cell_count", 24))),
            minimum_spacing_mm=float(cast(float, manifest.parameters.get("minimum_spacing_mm", MIN_SPACING_MM))),
            cooling_coefficient_w_per_m2k=float(
                cast(float, manifest.parameters.get("cooling_coefficient_w_per_m2k", 18.0))
            ),
            passive_cooling_w_per_k=float(cast(float, manifest.parameters.get("passive_cooling_w_per_k", 1.0))),
            ambient_temperature_c=float(cast(float, manifest.parameters.get("ambient_temperature_c", 25.0))),
            maximum_temperature_c=float(cast(float, manifest.parameters.get("maximum_temperature_c", 60.0))),
            load_current_a=cast(float | None, manifest.parameters.get("load_current_a")),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return a deterministic baseline or seeded oriented-cell candidate.

        Args:
            seed: Optional seed used to jitter the baseline.

        Returns:
            One bounded design vector.
        """
        vector = numpy.zeros_like(self.bounds.lb, dtype=float)
        baseline_cell_count = self._baseline_cell_count()
        vector[0] = float(baseline_cell_count)

        x_step = CELL_SPEC_18650.diameter_mm + self.minimum_spacing_mm
        y_step = x_step
        z_step = CELL_SPEC_18650.length_mm + self.minimum_spacing_mm
        safe_x_min = self._cell_radius_mm + (self.minimum_spacing_mm / 2.0)
        safe_y_min = self._cell_radius_mm + (self.minimum_spacing_mm / 2.0)
        safe_z_min = self._cell_half_length_mm + (self.minimum_spacing_mm / 2.0)
        max_columns = max(
            1,
            math.floor(
                (self.requirements.max_width_mm - (2.0 * safe_x_min))
                / max(CELL_SPEC_18650.diameter_mm + self.minimum_spacing_mm, 1.0e-6)
            )
            + 1,
        )
        max_rows = max(
            1,
            math.floor(
                (self.requirements.max_depth_mm - (2.0 * safe_y_min))
                / max(CELL_SPEC_18650.diameter_mm + self.minimum_spacing_mm, 1.0e-6)
            )
            + 1,
        )
        cells_per_layer = max_columns * max_rows
        for cell_index in range(self.max_cell_count):
            layer_index = cell_index // cells_per_layer
            in_layer_index = cell_index % cells_per_layer
            row_index = in_layer_index // max_columns
            column_index = in_layer_index % max_columns
            x_mm = safe_x_min + (column_index * x_step)
            y_mm = safe_y_min + (row_index * y_step)
            z_mm = safe_z_min + (layer_index * z_step)
            offset = 1 + (6 * cell_index)
            vector[offset + 0] = float(numpy.clip(x_mm, self.bounds.lb[offset + 0], self.bounds.ub[offset + 0]))
            vector[offset + 1] = float(numpy.clip(y_mm, self.bounds.lb[offset + 1], self.bounds.ub[offset + 1]))
            vector[offset + 2] = float(numpy.clip(z_mm, self.bounds.lb[offset + 2], self.bounds.ub[offset + 2]))
            vector[offset + 3] = 0.0
            vector[offset + 4] = 0.0
            vector[offset + 5] = 0.0

        if seed is None:
            return vector

        rng = numpy.random.default_rng(seed)
        seeded = vector.copy()
        cell_count_shift = int(rng.integers(-2, 3))
        seeded[0] = float(
            numpy.clip(
                float(baseline_cell_count + cell_count_shift),
                self.bounds.lb[0],
                self.bounds.ub[0],
            )
        )
        active_count = round(seeded[0])
        for cell_index in range(self.max_cell_count):
            offset = 1 + (6 * cell_index)
            if cell_index < active_count:
                seeded[offset + 3 : offset + 6] = rng.uniform(-10.0, 10.0, size=3)
            else:
                seeded[offset + 0] = rng.uniform(self.bounds.lb[offset + 0], self.bounds.ub[offset + 0])
                seeded[offset + 1] = rng.uniform(self.bounds.lb[offset + 1], self.bounds.ub[offset + 1])
                seeded[offset + 2] = rng.uniform(self.bounds.lb[offset + 2], self.bounds.ub[offset + 2])
                seeded[offset + 3] = rng.uniform(-_MAX_ABS_ANGLE_DEG, _MAX_ABS_ANGLE_DEG)
                seeded[offset + 4] = rng.uniform(-_MAX_ABS_ANGLE_DEG, _MAX_ABS_ANGLE_DEG)
                seeded[offset + 5] = rng.uniform(-_MAX_ABS_ANGLE_DEG, _MAX_ABS_ANGLE_DEG)
        return seeded

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> OrientedBatteryDecodedCandidate:
        """Decode one candidate vector into active oriented cell placements.

        Args:
            variables: Candidate design vector.

        Returns:
            Decoded oriented candidate.
        """
        evaluation = self._evaluation_from_variables(variables)
        return OrientedBatteryDecodedCandidate(
            cell_count=evaluation.cell_count,
            series_count=evaluation.series_count,
            parallel_equivalent=evaluation.parallel_equivalent,
            cells=evaluation.cells,
        )

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return primary metrics for one oriented battery candidate.

        Args:
            variables: Candidate design vector.

        Returns:
            Reported scalar metrics.
        """
        evaluation = self._evaluation_from_variables(variables)
        return {
            "design_volume_mm3": evaluation.design_volume_mm3,
            "cell_count": float(evaluation.cell_count),
            "cost_usd": evaluation.design_cost_usd,
            "max_temperature_c": evaluation.max_temperature_c,
            "voltage_v": evaluation.design_voltage_v,
            "capacity_ah": evaluation.design_capacity_ah,
            "current_limit_a": evaluation.current_limit_a,
            "minimum_surface_clearance_mm": evaluation.minimum_surface_clearance_mm,
        }

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return a scalarized volume/cell-count/temperature objective.

        Args:
            variables: Candidate design vector.

        Returns:
            Scalar minimization objective.
        """
        normalized = self._normalize_vector(variables)
        evaluation = self._evaluation_from_variables(normalized)
        max_pack_volume = max(
            self.requirements.max_width_mm * self.requirements.max_depth_mm * self.requirements.max_height_mm,
            1.0,
        )
        volume_term = evaluation.design_volume_mm3 / max_pack_volume
        cell_count_term = float(evaluation.cell_count) / float(self.max_cell_count)
        thermal_span = max(self.maximum_temperature_c - self.ambient_temperature_c, 1.0)
        temperature_term = (evaluation.max_temperature_c - self.ambient_temperature_c) / thermal_span
        penalty = _INFEASIBILITY_PENALTY_SCALE * self.constraint_violation(normalized)
        return (
            (_VOLUME_WEIGHT * volume_term)
            + (_CELL_COUNT_WEIGHT * cell_count_term)
            + (_TEMPERATURE_WEIGHT * temperature_term)
            + penalty
        )

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 80,
    ) -> OptimizationResult:
        """Run the deterministic bounded local-search baseline.

        Args:
            initial_solution: Optional starting vector.
            seed: Optional random seed for generating the start vector.
            maxiter: Maximum local-search iterations.

        Returns:
            Baseline optimization result.
        """
        start = (
            self.generate_initial_solution(seed=seed)
            if initial_solution is None
            else self._normalize_vector(initial_solution)
        )
        if maxiter <= 0:
            best = self._normalize_vector(start)
            max_violation = self.max_constraint_violation(best)
            evaluation = self._evaluation_from_variables(best)
            return OptimizationResult(
                x=best,
                fun=self.objective(best),
                success=max_violation <= 1.0e-9,
                message=(
                    "Evaluated one oriented battery layout candidate "
                    f"(cells={evaluation.cell_count}, volume={evaluation.design_volume_mm3:.1f} mm^3)."
                ),
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
        best_score = self.objective(best)
        evaluations = search.nfev + 1
        for cell_count in range(1, self.max_cell_count + 1):
            candidate = best.copy()
            candidate[0] = float(cell_count)
            candidate_score = self.objective(candidate)
            evaluations += 1
            if candidate_score < best_score:
                best = self._normalize_vector(candidate)
                best_score = candidate_score

        max_violation = self.max_constraint_violation(best)
        evaluation = self._evaluation_from_variables(best)
        if max_violation <= 1.0e-9:
            message = (
                "Evaluated oriented battery layouts and found a feasible design "
                f"(cells={evaluation.cell_count}, volume={evaluation.design_volume_mm3:.1f} mm^3)."
            )
        else:
            message = (
                "Evaluated oriented battery layouts and returned a best-effort design "
                f"(cells={evaluation.cell_count}, max violation {max_violation:.3g})."
            )
        return OptimizationResult(
            x=best,
            fun=best_score,
            success=max_violation <= 1.0e-9,
            message=message,
            nit=search.nit,
            nfev=evaluations,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return a clipped vector with the expected oriented-layout dimension.

        Args:
            variables: Candidate design vector.

        Returns:
            Clipped candidate vector.

        Raises:
            ValueError: If ``variables`` has an invalid shape.
        """
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != self.bounds.lb.shape:
            raise ValueError(
                f"Expected a {self.bounds.lb.shape[0]}-variable design vector, received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _cache_key(self, variables: NDArray[numpy.float64]) -> tuple[float, ...]:
        """Return the rounded cache key for one normalized candidate vector.

        Args:
            variables: Candidate vector.

        Returns:
            Hashable rounded key for cached evaluation summaries.
        """
        normalized = self._normalize_vector(variables)
        return tuple(float(round(value, _CACHE_DECIMALS)) for value in normalized)

    def _evaluation_from_variables(self, variables: NDArray[numpy.float64]) -> OrientedBatteryEvaluation:
        """Return computed geometry/electrical/thermal summary for one candidate.

        Args:
            variables: Candidate design vector.

        Returns:
            Cached oriented battery evaluation summary.
        """
        key = self._cache_key(variables)
        cached = self._evaluation_cache.get(key)
        if cached is not None:
            return cached

        normalized = numpy.array(key, dtype=float)
        cell_count = int(numpy.clip(round(float(normalized[0])), 1, self.max_cell_count))
        cells: list[OrientedBatteryCellPlacement] = []
        for cell_index in range(cell_count):
            offset = 1 + (6 * cell_index)
            cells.append(
                OrientedBatteryCellPlacement(
                    cell_id=cell_index,
                    x_mm=float(normalized[offset + 0]),
                    y_mm=float(normalized[offset + 1]),
                    z_mm=float(normalized[offset + 2]),
                    angle_x_deg=float(normalized[offset + 3]),
                    angle_y_deg=float(normalized[offset + 4]),
                    angle_z_deg=float(normalized[offset + 5]),
                )
            )
        cells_tuple = tuple(cells)

        if not cells_tuple:
            width_mm = 0.0
            depth_mm = 0.0
            height_mm = 0.0
            min_surface_clearance_mm = self.minimum_spacing_mm
            surface_area_mm2 = 0.0
            design_volume_mm3 = 0.0
        else:
            min_x = math.inf
            min_y = math.inf
            min_z = math.inf
            max_x = -math.inf
            max_y = -math.inf
            max_z = -math.inf
            segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
            for cell in cells_tuple:
                axis_x, axis_y, axis_z = self._axis_unit_vector(cell)
                extent_x = (abs(axis_x) * self._cell_half_length_mm) + (
                    self._cell_radius_mm * math.sqrt(max(0.0, 1.0 - (axis_x * axis_x)))
                )
                extent_y = (abs(axis_y) * self._cell_half_length_mm) + (
                    self._cell_radius_mm * math.sqrt(max(0.0, 1.0 - (axis_y * axis_y)))
                )
                extent_z = (abs(axis_z) * self._cell_half_length_mm) + (
                    self._cell_radius_mm * math.sqrt(max(0.0, 1.0 - (axis_z * axis_z)))
                )
                min_x = min(min_x, cell.x_mm - extent_x)
                min_y = min(min_y, cell.y_mm - extent_y)
                min_z = min(min_z, cell.z_mm - extent_z)
                max_x = max(max_x, cell.x_mm + extent_x)
                max_y = max(max_y, cell.y_mm + extent_y)
                max_z = max(max_z, cell.z_mm + extent_z)
                segment_start = (
                    cell.x_mm - (axis_x * self._cell_half_length_mm),
                    cell.y_mm - (axis_y * self._cell_half_length_mm),
                    cell.z_mm - (axis_z * self._cell_half_length_mm),
                )
                segment_end = (
                    cell.x_mm + (axis_x * self._cell_half_length_mm),
                    cell.y_mm + (axis_y * self._cell_half_length_mm),
                    cell.z_mm + (axis_z * self._cell_half_length_mm),
                )
                segments.append((segment_start, segment_end))

            width_mm = max(0.0, max_x - min_x)
            depth_mm = max(0.0, max_y - min_y)
            height_mm = max(0.0, max_z - min_z)
            surface_area_mm2 = 2.0 * ((width_mm * depth_mm) + (width_mm * height_mm) + (depth_mm * height_mm))
            design_volume_mm3 = width_mm * depth_mm * height_mm

            if len(segments) < 2:
                min_surface_clearance_mm = self.minimum_spacing_mm
            else:
                min_surface_clearance_mm = math.inf
                for first_index in range(len(segments)):
                    for second_index in range(first_index + 1, len(segments)):
                        distance = self._segment_distance(
                            segments[first_index][0],
                            segments[first_index][1],
                            segments[second_index][0],
                            segments[second_index][1],
                        )
                        clearance = distance - CELL_SPEC_18650.diameter_mm
                        min_surface_clearance_mm = min(min_surface_clearance_mm, clearance)
                if not math.isfinite(min_surface_clearance_mm):
                    min_surface_clearance_mm = self.minimum_spacing_mm

        series_count, parallel_equivalent, design_voltage_v, design_capacity_ah, current_limit_a = (
            self._electrical_summary(cell_count)
        )
        per_cell_current = self.load_current_a / max(parallel_equivalent, 1.0e-9)
        total_heat_w = float(cell_count) * (per_cell_current**2) * CELL_SPEC_18650.internal_resistance_ohm
        cooling_area_m2 = surface_area_mm2 * 1.0e-6
        cooling_conductance = self.passive_cooling_w_per_k + (self.cooling_coefficient_w_per_m2k * cooling_area_m2)
        max_temperature_c = self.ambient_temperature_c + (total_heat_w / max(cooling_conductance, 1.0e-9))

        evaluation = OrientedBatteryEvaluation(
            cell_count=cell_count,
            series_count=series_count,
            parallel_equivalent=parallel_equivalent,
            design_width_mm=width_mm,
            design_depth_mm=depth_mm,
            design_height_mm=height_mm,
            surface_area_mm2=surface_area_mm2,
            design_volume_mm3=design_volume_mm3,
            design_cost_usd=float(cell_count) * CELL_SPEC_18650.unit_cost_usd,
            minimum_surface_clearance_mm=min_surface_clearance_mm,
            design_voltage_v=design_voltage_v,
            design_capacity_ah=design_capacity_ah,
            current_limit_a=current_limit_a,
            max_temperature_c=max_temperature_c,
            cells=cells_tuple,
        )
        self._evaluation_cache[key] = evaluation
        return evaluation

    def _electrical_summary(self, cell_count: int) -> tuple[int, float, float, float, float]:
        """Return the approximated electrical summary for one active cell count.

        Args:
            cell_count: Active cell count.

        Returns:
            Series count, equivalent parallel count, voltage, capacity, and current limit.
        """
        best_series = 1
        best_error = math.inf
        best_parallel = 1.0
        for series_count in range(1, max(2, cell_count + 1)):
            voltage = float(series_count) * CELL_SPEC_18650.nominal_voltage_v
            error = abs(voltage - self.requirements.target_voltage_v)
            parallel_equivalent = float(cell_count) / float(series_count)
            if (error + 1.0e-12) < best_error:
                best_series = series_count
                best_error = error
                best_parallel = parallel_equivalent
                continue
            if abs(error - best_error) <= 1.0e-12 and parallel_equivalent > best_parallel:
                best_series = series_count
                best_parallel = parallel_equivalent

        design_voltage = float(best_series) * CELL_SPEC_18650.nominal_voltage_v
        design_capacity = best_parallel * CELL_SPEC_18650.nominal_capacity_ah
        current_limit = best_parallel * CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
        return (best_series, best_parallel, design_voltage, design_capacity, current_limit)

    def _baseline_cell_count(self) -> int:
        """Return a deterministic initial cell-count guess from packaged requirements.

        Returns:
            Initial active cell count.
        """
        series_count = max(1, round(self.requirements.target_voltage_v / CELL_SPEC_18650.nominal_voltage_v))
        parallel_for_capacity = max(
            1,
            math.ceil(self.requirements.minimum_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah),
        )
        per_cell_current_limit = CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
        parallel_for_current = max(1, math.ceil(self.requirements.minimum_current_a / per_cell_current_limit))
        baseline = series_count * max(parallel_for_capacity, parallel_for_current)
        return int(numpy.clip(float(baseline), 1.0, float(self.max_cell_count)))

    def _axis_unit_vector(self, cell: OrientedBatteryCellPlacement) -> tuple[float, float, float]:
        """Return one normalized cell-axis direction from XYZ Euler angles.

        Args:
            cell: Oriented cell placement.

        Returns:
            Unit axis vector for the rotated cell centerline.
        """
        angle_x = math.radians(cell.angle_x_deg)
        angle_y = math.radians(cell.angle_y_deg)
        angle_z = math.radians(cell.angle_z_deg)

        x_value = 0.0
        y_value = 0.0
        z_value = 1.0

        cos_x = math.cos(angle_x)
        sin_x = math.sin(angle_x)
        y_rot = (y_value * cos_x) - (z_value * sin_x)
        z_rot = (y_value * sin_x) + (z_value * cos_x)
        x_rot = x_value

        cos_y = math.cos(angle_y)
        sin_y = math.sin(angle_y)
        x_rot2 = (x_rot * cos_y) + (z_rot * sin_y)
        z_rot2 = (-x_rot * sin_y) + (z_rot * cos_y)
        y_rot2 = y_rot

        cos_z = math.cos(angle_z)
        sin_z = math.sin(angle_z)
        x_rot3 = (x_rot2 * cos_z) - (y_rot2 * sin_z)
        y_rot3 = (x_rot2 * sin_z) + (y_rot2 * cos_z)
        z_rot3 = z_rot2

        norm = math.sqrt((x_rot3 * x_rot3) + (y_rot3 * y_rot3) + (z_rot3 * z_rot3))
        if norm <= 1.0e-12:
            return (0.0, 0.0, 1.0)
        return (x_rot3 / norm, y_rot3 / norm, z_rot3 / norm)

    def _segment_distance(
        self,
        point_a0: tuple[float, float, float],
        point_a1: tuple[float, float, float],
        point_b0: tuple[float, float, float],
        point_b1: tuple[float, float, float],
    ) -> float:
        """Return the shortest distance between two finite 3D line segments.

        Args:
            point_a0: First segment start.
            point_a1: First segment end.
            point_b0: Second segment start.
            point_b1: Second segment end.

        Returns:
            Shortest point-to-point segment distance.
        """
        u = numpy.array(point_a1, dtype=float) - numpy.array(point_a0, dtype=float)
        v = numpy.array(point_b1, dtype=float) - numpy.array(point_b0, dtype=float)
        w = numpy.array(point_a0, dtype=float) - numpy.array(point_b0, dtype=float)
        a_value = float(numpy.dot(u, u))
        b_value = float(numpy.dot(u, v))
        c_value = float(numpy.dot(v, v))
        d_value = float(numpy.dot(u, w))
        e_value = float(numpy.dot(v, w))
        denominator = (a_value * c_value) - (b_value * b_value)
        epsilon = 1.0e-12

        s_numerator = denominator
        s_denominator = denominator
        t_numerator = denominator
        t_denominator = denominator

        if denominator <= epsilon:
            s_numerator = 0.0
            s_denominator = 1.0
            t_numerator = e_value
            t_denominator = c_value
        else:
            s_numerator = (b_value * e_value) - (c_value * d_value)
            t_numerator = (a_value * e_value) - (b_value * d_value)
            if s_numerator < 0.0:
                s_numerator = 0.0
                t_numerator = e_value
                t_denominator = c_value
            elif s_numerator > s_denominator:
                s_numerator = s_denominator
                t_numerator = e_value + b_value
                t_denominator = c_value

        if t_numerator < 0.0:
            t_numerator = 0.0
            if (-d_value) < 0.0:
                s_numerator = 0.0
            elif (-d_value) > a_value:
                s_numerator = s_denominator
            else:
                s_numerator = -d_value
                s_denominator = a_value
        elif t_numerator > t_denominator:
            t_numerator = t_denominator
            if (-d_value + b_value) < 0.0:
                s_numerator = 0.0
            elif (-d_value + b_value) > a_value:
                s_numerator = s_denominator
            else:
                s_numerator = -d_value + b_value
                s_denominator = a_value

        sc = 0.0 if abs(s_numerator) <= epsilon else s_numerator / s_denominator
        tc = 0.0 if abs(t_numerator) <= epsilon else t_numerator / t_denominator
        delta = w + (sc * u) - (tc * v)
        return float(math.sqrt(float(numpy.dot(delta, delta))))

    def _width_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the maximum-width constraint margin."""
        return self.requirements.max_width_mm - self._evaluation_from_variables(variables).design_width_mm

    def _depth_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the maximum-depth constraint margin."""
        return self.requirements.max_depth_mm - self._evaluation_from_variables(variables).design_depth_mm

    def _height_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the maximum-height constraint margin."""
        return self.requirements.max_height_mm - self._evaluation_from_variables(variables).design_height_mm

    def _voltage_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the target-voltage tolerance margin."""
        evaluation = self._evaluation_from_variables(variables)
        voltage_error = abs(evaluation.design_voltage_v - self.requirements.target_voltage_v)
        return self.requirements.voltage_tolerance_v - voltage_error

    def _capacity_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimum-capacity constraint margin."""
        return self._evaluation_from_variables(variables).design_capacity_ah - self.requirements.minimum_capacity_ah

    def _current_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimum-current constraint margin."""
        return self._evaluation_from_variables(variables).current_limit_a - self.requirements.minimum_current_a

    def _clearance_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the non-overlap clearance margin."""
        return self._evaluation_from_variables(variables).minimum_surface_clearance_mm

    def _minimum_spacing_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimum-spacing clearance margin."""
        return self._evaluation_from_variables(variables).minimum_surface_clearance_mm - self.minimum_spacing_mm

    def _temperature_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the maximum-temperature margin."""
        return self.maximum_temperature_c - self._evaluation_from_variables(variables).max_temperature_c


__all__ = [
    "BatteryOrientedLayoutProblem",
    "OrientedBatteryCellPlacement",
    "OrientedBatteryDecodedCandidate",
    "OrientedBatteryEvaluation",
]
