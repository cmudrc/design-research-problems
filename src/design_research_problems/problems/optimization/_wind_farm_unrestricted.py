"""Compact unrestricted wind-farm layout optimization benchmark."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.wind_farm import (
    UnrestrictedWindFarmLayoutState,
    count_l1_spacing_violations,
    decode_coordinate_vector,
    evaluate_unrestricted_layout,
    flatten_coordinates,
    get_continuous_wind_profile,
    l1_distance,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
    bounded_pattern_search,
)

_INFEASIBILITY_PENALTY = 1_000.0
_CURATED_ZERO_OVERLAP_LAYOUT_M = (
    (43.72020044238818, 429.52248857886207),
    (111.59766943249089, 82.1459871105066),
    (221.66540225338184, 639.9506879833697),
    (308.17161590785463, 299.0038449775436),
    (443.18279529537006, 1.7620158094729277),
    (620.0350859625122, 176.3059566304521),
    (628.0066860474154, 546.3217673710446),
)
_CURATED_ZERO_OVERLAP_VECTOR = flatten_coordinates(_CURATED_ZERO_OVERLAP_LAYOUT_M)


class UnrestrictedWindFarmLayoutOptimizationProblem(OptimizationProblem):
    """Continuous wind-farm layout benchmark derived from Quan and Kim's MILP."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        turbine_count: int = 7,
        edge_length_m: float = 650.0,
        minimum_l1_spacing_m: float = 350.0,
        rotor_diameter_m: float = 77.0,
        thrust_coefficient: float = 0.8,
        wake_expansion_coefficient: float = 0.075,
        wake_membership_alpha: float = 1.0,
        direction_profile_name: str = "quan_kim_2015_reduced",
    ) -> None:
        """Initialize the packaged unrestricted wind-farm seed instance."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        if turbine_count <= 0:
            raise ValueError("turbine_count must be positive.")
        if edge_length_m <= 0.0:
            raise ValueError("edge_length_m must be positive.")
        if minimum_l1_spacing_m <= 0.0:
            raise ValueError("minimum_l1_spacing_m must be positive.")
        if rotor_diameter_m <= 0.0:
            raise ValueError("rotor_diameter_m must be positive.")
        if not 0.0 <= thrust_coefficient <= 1.0:
            raise ValueError("thrust_coefficient must lie in [0, 1].")
        if wake_expansion_coefficient < 0.0:
            raise ValueError("wake_expansion_coefficient must be nonnegative.")
        if not 0.0 <= wake_membership_alpha <= 1.0:
            raise ValueError("wake_membership_alpha must lie in [0, 1].")

        self.turbine_count = turbine_count
        self.edge_length_m = edge_length_m
        self.minimum_l1_spacing_m = minimum_l1_spacing_m
        self.rotor_diameter_m = rotor_diameter_m
        self.thrust_coefficient = thrust_coefficient
        self.wake_expansion_coefficient = wake_expansion_coefficient
        self.wake_membership_alpha = wake_membership_alpha
        self.direction_profile_name = direction_profile_name
        self.direction_profile = get_continuous_wind_profile(direction_profile_name)
        self.variable_count = 2 * turbine_count
        self.bounds = Bounds(
            lb=numpy.zeros(self.variable_count, dtype=float),
            ub=numpy.full(self.variable_count, edge_length_m, dtype=float),
        )
        self._pair_indices = tuple(
            (index_i, index_j)
            for index_i in range(self.turbine_count - 1)
            for index_j in range(index_i + 1, self.turbine_count)
        )
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._pair_margin_factory(index_i, index_j))
            for index_i, index_j in self._pair_indices
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> UnrestrictedWindFarmLayoutOptimizationProblem:
        """Construct the compact benchmark from packaged manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            turbine_count=int(cast(int, parameters.get("turbine_count", 7))),
            edge_length_m=float(cast(float, parameters.get("edge_length_m", 650.0))),
            minimum_l1_spacing_m=float(cast(float, parameters.get("minimum_l1_spacing_m", 350.0))),
            rotor_diameter_m=float(cast(float, parameters.get("rotor_diameter_m", 77.0))),
            thrust_coefficient=float(cast(float, parameters.get("thrust_coefficient", 0.8))),
            wake_expansion_coefficient=float(cast(float, parameters.get("wake_expansion_coefficient", 0.075))),
            wake_membership_alpha=float(cast(float, parameters.get("wake_membership_alpha", 1.0))),
            direction_profile_name=str(cast(str, parameters.get("direction_profile_name", "quan_kim_2015_reduced"))),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the deterministic zero-overlap seed discovered for the packaged case."""
        del seed
        if self.turbine_count != len(_CURATED_ZERO_OVERLAP_LAYOUT_M) or not numpy.all(
            self.bounds.ub == self.edge_length_m
        ):
            # Fall back to a boundary-clipped copy if the packaged defaults are altered.
            return self._normalize_vector(_CURATED_ZERO_OVERLAP_VECTOR[: self.variable_count])
        return numpy.array(_CURATED_ZERO_OVERLAP_VECTOR, dtype=float, copy=True)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the weighted worst-case wake deficit plus an infeasibility penalty."""
        normalized = self._normalize_vector(variables)
        state = self.decode_candidate(normalized)
        return float(state.weighted_wake_deficit_mps + (_INFEASIBILITY_PENALTY * self.constraint_violation(normalized)))

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return a compact objective breakdown for one candidate layout."""
        normalized = self._normalize_vector(variables)
        state = self.decode_candidate(normalized)
        overlap_count = float(sum(state.directional_overlap_counts))
        return {
            "weighted_wake_deficit_mps": float(state.weighted_wake_deficit_mps),
            "max_directional_wake_deficit_mps": float(max(state.directional_wake_deficits_mps, default=0.0)),
            "overlap_count": overlap_count,
            "minimum_l1_spacing_m": float(state.minimum_l1_spacing_m),
            "spacing_violation_count": float(self._spacing_violation_count(normalized)),
            "constraint_violation": float(self.constraint_violation(normalized)),
        }

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Run a compact multi-start bounded pattern search baseline."""
        del seed
        starts = [self.generate_initial_solution()]
        if initial_solution is not None:
            starts.insert(0, self._normalize_vector(initial_solution))

        search_results = [
            bounded_pattern_search(
                self.objective,
                self.bounds.lb,
                self.bounds.ub,
                start,
                maxiter=max(1, min(maxiter, 60)),
                initial_step_fraction=0.08,
                minimum_step_fraction=1e-3,
            )
            for start in starts
        ]

        best = min(
            search_results,
            key=lambda result: (
                not self.evaluate(result.x).is_feasible,
                self.objective(result.x),
            ),
        )
        evaluation = self.evaluate(best.x)
        decoded = self.decode_candidate(best.x)
        zero_overlap = sum(decoded.directional_overlap_counts) == 0
        message = (
            "Ran the compact unrestricted wind-farm baseline and recovered a feasible zero-overlap layout."
            if evaluation.is_feasible and zero_overlap
            else "Ran the compact unrestricted wind-farm baseline and returned the best feasible layout found."
            if evaluation.is_feasible
            else "Ran the compact unrestricted wind-farm baseline and returned the least-infeasible layout found."
        )
        return OptimizationResult(
            x=best.x,
            fun=float(evaluation.objective_value),
            success=evaluation.is_feasible,
            message=message,
            nit=sum(result.nit for result in search_results),
            nfev=sum(result.nfev for result in search_results),
        )

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> UnrestrictedWindFarmLayoutState:
        """Decode one candidate vector into a compact unrestricted-layout state."""
        coordinates = decode_coordinate_vector(self._normalize_vector(variables), turbine_count=self.turbine_count)
        return evaluate_unrestricted_layout(
            coordinates,
            direction_profile=self.direction_profile,
            rotor_diameter_m=self.rotor_diameter_m,
            thrust_coefficient=self.thrust_coefficient,
            wake_expansion_coefficient=self.wake_expansion_coefficient,
            wake_membership_alpha=self.wake_membership_alpha,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != (self.variable_count,):
            raise ValueError(
                f"variables must match the compact unrestricted wind layout shape ({self.variable_count},)."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _pair_margin_factory(self, index_i: int, index_j: int) -> Callable[[NDArray[numpy.float64]], float]:
        return lambda variables: float(
            l1_distance(
                self._coordinates(variables)[index_i],
                self._coordinates(variables)[index_j],
            )
            - self.minimum_l1_spacing_m
        )

    def _coordinates(self, variables: NDArray[numpy.float64]) -> tuple[tuple[float, float], ...]:
        return decode_coordinate_vector(self._normalize_vector(variables), turbine_count=self.turbine_count)

    def _spacing_violation_count(self, variables: NDArray[numpy.float64]) -> int:
        return count_l1_spacing_violations(
            self._coordinates(variables),
            minimum_spacing_m=self.minimum_l1_spacing_m,
        )
