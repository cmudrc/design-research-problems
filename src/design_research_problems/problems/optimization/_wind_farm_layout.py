"""Compact grid-based wind-farm layout optimization benchmark."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.wind_farm import (
    WindFarmLayoutState,
    count_spacing_violations,
    create_wind_farm_layout_backend,
    evaluate_layout_selection,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)

_INFEASIBILITY_PENALTY = 10_000.0


class WindFarmLayoutOptimizationProblem(OptimizationProblem):
    """Binary layout optimizer derived from Quan and Kim's grid QKP."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        grid_rows: int = 4,
        grid_cols: int = 4,
        edge_length_m: float = 960.0,
        turbine_count: int = 4,
        base_power_mw: float = 1.5,
        minimum_spacing_m: float = 450.0,
        rotor_diameter_m: float = 80.0,
        wake_expansion_coefficient: float = 0.075,
        pairwise_loss_scale_mw: float = 0.42,
        direction_profile_name: str = "east_skewed_seed",
    ) -> None:
        """Initialize the packaged compact wind-farm benchmark.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            grid_rows: Number of grid rows.
            grid_cols: Number of grid columns.
            edge_length_m: Side length of the square farm boundary in meters.
            turbine_count: Fixed number of turbines to place.
            base_power_mw: Stand-alone power estimate per turbine.
            minimum_spacing_m: Hard inter-turbine spacing threshold.
            rotor_diameter_m: Rotor diameter used by the wake proxy.
            wake_expansion_coefficient: Linear wake-cone expansion rate.
            pairwise_loss_scale_mw: Peak pairwise wake-loss scale.
            direction_profile_name: Named in-package directional profile.

        Raises:
            ValueError: If any geometric parameter is invalid.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        if grid_rows <= 0 or grid_cols <= 0:
            raise ValueError("grid_rows and grid_cols must be positive.")
        if edge_length_m <= 0.0:
            raise ValueError("edge_length_m must be positive.")
        if turbine_count <= 0:
            raise ValueError("turbine_count must be positive.")
        if base_power_mw <= 0.0:
            raise ValueError("base_power_mw must be positive.")
        if minimum_spacing_m <= 0.0:
            raise ValueError("minimum_spacing_m must be positive.")
        if rotor_diameter_m <= 0.0:
            raise ValueError("rotor_diameter_m must be positive.")
        if wake_expansion_coefficient < 0.0:
            raise ValueError("wake_expansion_coefficient must be nonnegative.")
        if pairwise_loss_scale_mw <= 0.0:
            raise ValueError("pairwise_loss_scale_mw must be positive.")

        self.grid_rows = grid_rows
        self.grid_cols = grid_cols
        self.edge_length_m = edge_length_m
        self.turbine_count = turbine_count
        self.base_power_mw = base_power_mw
        self.minimum_spacing_m = minimum_spacing_m
        self.rotor_diameter_m = rotor_diameter_m
        self.wake_expansion_coefficient = wake_expansion_coefficient
        self.pairwise_loss_scale_mw = pairwise_loss_scale_mw
        self.backend = create_wind_farm_layout_backend(
            grid_rows=grid_rows,
            grid_cols=grid_cols,
            edge_length_m=edge_length_m,
            minimum_spacing_m=minimum_spacing_m,
            rotor_diameter_m=rotor_diameter_m,
            wake_expansion_coefficient=wake_expansion_coefficient,
            pairwise_loss_scale_mw=pairwise_loss_scale_mw,
            direction_profile_name=direction_profile_name,
        )
        self.direction_profile_name = self.backend.direction_profile_name
        self.direction_profile = self.backend.direction_profile
        self.coordinates_m = self.backend.coordinates_m
        self.variable_count = len(self.coordinates_m)
        if self.turbine_count > self.variable_count:
            raise ValueError("turbine_count cannot exceed the number of grid nodes.")
        self._conflicting_pairs = self.backend.conflicting_pairs
        self._pairwise_loss_matrix_mw = self.backend.pairwise_loss_matrix_mw

        self.bounds = Bounds(
            lb=numpy.zeros(self.variable_count, dtype=float),
            ub=numpy.ones(self.variable_count, dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(
                kind="eq",
                evaluate=lambda variables: float(len(self._selected_indices(variables))),
                target=float(self.turbine_count),
            ),
            *[
                ConstraintDefinition(
                    kind="ineq",
                    evaluate=self._pair_margin_factory(index_i, index_j),
                )
                for index_i, index_j in self._conflicting_pairs
            ],
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> WindFarmLayoutOptimizationProblem:
        """Construct the compact benchmark from packaged manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            grid_rows=int(cast(int, parameters.get("grid_rows", 4))),
            grid_cols=int(cast(int, parameters.get("grid_cols", 4))),
            edge_length_m=float(cast(float, parameters.get("edge_length_m", 960.0))),
            turbine_count=int(cast(int, parameters.get("turbine_count", 4))),
            base_power_mw=float(cast(float, parameters.get("base_power_mw", 1.5))),
            minimum_spacing_m=float(cast(float, parameters.get("minimum_spacing_m", 450.0))),
            rotor_diameter_m=float(cast(float, parameters.get("rotor_diameter_m", 80.0))),
            wake_expansion_coefficient=float(cast(float, parameters.get("wake_expansion_coefficient", 0.075))),
            pairwise_loss_scale_mw=float(cast(float, parameters.get("pairwise_loss_scale_mw", 0.42))),
            direction_profile_name=str(cast(str, parameters.get("direction_profile_name", "east_skewed_seed"))),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return one deterministic or seeded greedy feasible layout."""
        start_order = list(range(self.variable_count))
        if seed is not None:
            random.Random(seed).shuffle(start_order)
        return self._greedy_layout(start_order=start_order, start_index=start_order[0])

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the negative expected power with a hard infeasibility penalty."""
        components = self.objective_components(variables)
        penalty = _INFEASIBILITY_PENALTY * components["violation_count"]
        return float(-components["expected_power_mw"] + penalty)

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return a compact objective breakdown for one candidate."""
        selected = self._selected_indices(variables)
        layout = evaluate_layout_selection(
            selected,
            coordinates_m=self.coordinates_m,
            pairwise_loss_matrix_mw=self._pairwise_loss_matrix_mw,
            base_power_mw=self.base_power_mw,
        )
        return {
            "selected_count": float(len(selected)),
            "expected_power_mw": float(layout.expected_power_mw),
            "total_wake_loss_mw": float(layout.total_wake_loss_mw),
            "violation_count": float(self._violation_count(variables)),
        }

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Run the paper-inspired multi-start greedy baseline."""
        del maxiter
        start_order = list(range(self.variable_count))
        if seed is not None:
            random.Random(seed).shuffle(start_order)

        candidates: list[NDArray[numpy.float64]] = []
        if initial_solution is not None:
            candidates.append(self._normalize_vector(initial_solution))
        for start_index in start_order:
            candidates.append(self._greedy_layout(start_order=start_order, start_index=start_index))

        best = min(
            candidates,
            key=lambda candidate: (
                not self.evaluate(candidate).is_feasible,
                abs(len(self._selected_indices(candidate)) - self.turbine_count),
                self.objective(candidate),
            ),
        )
        evaluation = self.evaluate(best)
        message = (
            "Ran the compact wind-farm greedy baseline and found a feasible fixed-count layout."
            if evaluation.is_feasible
            else "Ran the compact wind-farm greedy baseline and returned the best-effort layout."
        )
        return OptimizationResult(
            x=best,
            fun=float(evaluation.objective_value),
            success=evaluation.is_feasible,
            message=message,
            nit=len(candidates),
            nfev=len(candidates),
        )

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> WindFarmLayoutState:
        """Decode one candidate vector into a compact wind-farm state."""
        return evaluate_layout_selection(
            self._selected_indices(variables),
            coordinates_m=self.coordinates_m,
            pairwise_loss_matrix_mw=self._pairwise_loss_matrix_mw,
            base_power_mw=self.base_power_mw,
        )

    def _pair_margin_factory(self, index_i: int, index_j: int) -> Callable[[NDArray[numpy.float64]], float]:
        return lambda variables: float(1 - self._bit_tuple(variables)[index_i] - self._bit_tuple(variables)[index_j])

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != (self.variable_count,):
            raise ValueError(f"variables must match the compact wind-farm grid shape ({self.variable_count},).")
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _bit_tuple(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        normalized = self._normalize_vector(variables)
        return tuple(1 if float(value) >= 0.5 else 0 for value in normalized)

    def _selected_indices(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        return tuple(index for index, bit in enumerate(self._bit_tuple(variables)) if bit == 1)

    def _violation_count(self, variables: NDArray[numpy.float64]) -> int:
        selected = self._selected_indices(variables)
        count_violation = int(len(selected) != self.turbine_count)
        return count_violation + count_spacing_violations(selected, self._conflicting_pairs)

    def _is_partial_layout_valid(self, variables: NDArray[numpy.float64]) -> bool:
        selected = self._selected_indices(variables)
        if len(selected) > self.turbine_count:
            return False
        return count_spacing_violations(selected, self._conflicting_pairs) == 0

    def _greedy_layout(self, *, start_order: list[int], start_index: int) -> NDArray[numpy.float64]:
        current = numpy.zeros(self.variable_count, dtype=float)
        current[start_index] = 1.0
        if not self._is_partial_layout_valid(current):
            return numpy.zeros(self.variable_count, dtype=float)

        while len(self._selected_indices(current)) < self.turbine_count:
            best_candidate: NDArray[numpy.float64] | None = None
            best_value: float | None = None
            for index in start_order:
                if current[index] >= 0.5:
                    continue
                candidate = numpy.array(current, copy=True)
                candidate[index] = 1.0
                if not self._is_partial_layout_valid(candidate):
                    continue
                value = self.objective(candidate)
                if best_candidate is None or value < cast(float, best_value):
                    best_candidate = candidate
                    best_value = value
            if best_candidate is None:
                break
            current = best_candidate
        return current
