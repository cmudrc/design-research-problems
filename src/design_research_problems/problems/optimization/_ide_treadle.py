"""Reduced IDE-style treadle pump material-minimization problem."""

from __future__ import annotations

import math
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    LocalSearchResult,
    OptimizationProblem,
    OptimizationResult,
    bounded_pattern_search,
)

_CYLINDER_RADIUS_LB = 0.018
_CYLINDER_RADIUS_UB = 0.035
_HOSE_RADIUS_LB = 0.010
_HOSE_RADIUS_UB = 0.028
_TREADLE_LENGTH_LB = 1.2
_TREADLE_LENGTH_UB = 2.2
_STEP_RATE_LB = 0.6
_STEP_RATE_UB = 2.0

_MIN_STROKE = 0.12
_MAX_STROKE = 0.30
_FLOW_FACTOR = 3.0
_SUCTION_HEAD_MAX = 10.0
_HOSE_LOSS_COEFFICIENT = 3.0
_REFERENCE_HOSE_RADIUS = 0.014
_STROKE_LOSS_COEFFICIENT = 0.8
_REFERENCE_STROKE = 0.2

_TREADLE_WIDTH = 0.04
_TREADLE_THICKNESS = 0.015
_CYLINDER_WALL_THICKNESS = 0.003
_HOSE_WALL_THICKNESS = 0.0015
_PISTON_THICKNESS = 0.008
_MANIFOLD_VOLUME = 0.00145
_HOSE_LENGTH_OFFSET = 2.0

_ZONE_I_BASELINE_VECTOR = numpy.array([0.03382759, 0.01388933, 1.2, 1.9317264], dtype=float)
_REDUCED_SOLVER_INDICES = (0, 2)


class IDETreadlePumpMaterialMin(OptimizationProblem):
    """Reduced scalarized IDE-style treadle pump benchmark."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        target_flow_rate_lps: float = 2.5,
        target_lift_height_m: float = 1.9,
    ) -> None:
        """Initialize the packaged low-flow Zone I treadle-pump instance.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            target_flow_rate_lps: Fixed design flow rate in liters per second.
            target_lift_height_m: Fixed suction lift in meters.
        """
        super().__init__(metadata=metadata, statement_markdown=statement_markdown)
        self.target_flow_rate_lps = target_flow_rate_lps
        self.target_flow_rate_m3_per_s = target_flow_rate_lps / 1000.0
        self.target_lift_height_m = target_lift_height_m
        self.bounds = Bounds(
            lb=numpy.array(
                [_CYLINDER_RADIUS_LB, _HOSE_RADIUS_LB, _TREADLE_LENGTH_LB, _STEP_RATE_LB],
                dtype=float,
            ),
            ub=numpy.array(
                [_CYLINDER_RADIUS_UB, _HOSE_RADIUS_UB, _TREADLE_LENGTH_UB, _STEP_RATE_UB],
                dtype=float,
            ),
        )
        self.constraints = [
            ConstraintDefinition(kind="eq", evaluate=self.flow_rate_lps, target=self.target_flow_rate_lps),
            ConstraintDefinition(kind="eq", evaluate=self.lift_height_m, target=self.target_lift_height_m),
            ConstraintDefinition(kind="ineq", evaluate=self._step_rate_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._hose_within_cylinder_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._stroke_margin),
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest, statement_markdown: str) -> IDETreadlePumpMaterialMin:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.
            statement_markdown: Human-readable problem statement.

        Returns:
            Initialized problem instance.
        """
        target_flow_rate_lps = float(cast(float, manifest.parameters.get("target_flow_rate_lps", 2.5)))
        target_lift_height_m = float(cast(float, manifest.parameters.get("target_lift_height_m", 1.9)))
        return cls(
            metadata=manifest.metadata,
            statement_markdown=statement_markdown,
            target_flow_rate_lps=target_flow_rate_lps,
            target_lift_height_m=target_lift_height_m,
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the packaged Zone I baseline, or a seeded perturbation.

        Args:
            seed: Optional random seed for the perturbation.

        Returns:
            Four-variable initial solution vector.
        """
        if seed is None:
            return _ZONE_I_BASELINE_VECTOR.copy()

        rng = numpy.random.default_rng(seed)
        span = self.bounds.ub - self.bounds.lb
        perturbation = rng.normal(loc=0.0, scale=0.04, size=4) * span
        guess = _ZONE_I_BASELINE_VECTOR + perturbation
        return numpy.clip(guess, self.bounds.lb, self.bounds.ub)

    def stroke_length_m(self, variables: NDArray[numpy.float64]) -> float:
        """Return the effective piston stroke implied by treadle length.

        Args:
            variables: Four-variable design vector.

        Returns:
            Effective stroke length in meters.
        """
        treadle_length = float(variables[2])
        fraction = (treadle_length - _TREADLE_LENGTH_LB) / (_TREADLE_LENGTH_UB - _TREADLE_LENGTH_LB)
        clamped_fraction = min(max(fraction, 0.0), 1.0)
        return _MIN_STROKE + (_MAX_STROKE - _MIN_STROKE) * clamped_fraction

    def flow_rate_lps(self, variables: NDArray[numpy.float64]) -> float:
        """Return the predicted steady-state flow rate.

        Args:
            variables: Four-variable design vector.

        Returns:
            Flow rate in liters per second.
        """
        cylinder_radius = float(variables[0])
        step_rate = float(variables[3])
        stroke_length = self.stroke_length_m(variables)
        return 1000.0 * _FLOW_FACTOR * math.pi * cylinder_radius**2 * stroke_length * step_rate

    def lift_height_m(self, variables: NDArray[numpy.float64]) -> float:
        """Return the predicted maximum suction lift height.

        Args:
            variables: Four-variable design vector.

        Returns:
            Lift height in meters.
        """
        hose_radius = float(variables[1])
        stroke_length = self.stroke_length_m(variables)
        hose_term = _HOSE_LOSS_COEFFICIENT * self.target_flow_rate_lps * (_REFERENCE_HOSE_RADIUS / hose_radius) ** 2
        stroke_term = _STROKE_LOSS_COEFFICIENT * (stroke_length / _REFERENCE_STROKE)
        return _SUCTION_HEAD_MAX - hose_term - stroke_term

    def material_volume_m3(self, variables: NDArray[numpy.float64]) -> float:
        """Return the reduced material-volume proxy for the treadle pump.

        Args:
            variables: Four-variable design vector.

        Returns:
            Estimated material volume in cubic meters.
        """
        cylinder_radius = float(variables[0])
        hose_radius = float(variables[1])
        treadle_length = float(variables[2])
        stroke_length = self.stroke_length_m(variables)
        cylinder_length = stroke_length + 0.08
        hose_length = self.target_lift_height_m + _HOSE_LENGTH_OFFSET
        treadles = 2.0 * _TREADLE_WIDTH * _TREADLE_THICKNESS * treadle_length
        cylinder = math.pi * ((cylinder_radius + _CYLINDER_WALL_THICKNESS) ** 2 - cylinder_radius**2) * cylinder_length
        hose = math.pi * ((hose_radius + _HOSE_WALL_THICKNESS) ** 2 - hose_radius**2) * hose_length
        piston = 2.0 * math.pi * cylinder_radius**2 * _PISTON_THICKNESS
        return treadles + cylinder + hose + piston + _MANIFOLD_VOLUME

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the main reported objective values for one design vector.

        Args:
            variables: Four-variable design vector.

        Returns:
            Mapping of material, flow, and lift values.
        """
        return {
            "flow_rate_lps": self.flow_rate_lps(variables),
            "lift_height_m": self.lift_height_m(variables),
            "material_volume_m3": self.material_volume_m3(variables),
        }

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the scalar material-volume objective.

        Args:
            variables: Four-variable design vector.

        Returns:
            Material-volume proxy.
        """
        return self.material_volume_m3(variables)

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Solve the reduced treadle-pump subproblem with local search.

        Args:
            initial_solution: Optional full four-variable starting point.
            seed: Optional random seed used to generate deterministic restart
                candidates.
            maxiter: Maximum local-search sweeps per restart.

        Returns:
            Locally optimized feasible treadle-pump design.

        Raises:
            ValueError: If ``initial_solution`` is provided with the wrong
                shape.
        """
        restarts = self._solver_start_points(initial_solution=initial_solution, seed=seed)
        reduced_lb = self.bounds.lb[list(_REDUCED_SOLVER_INDICES)]
        reduced_ub = self.bounds.ub[list(_REDUCED_SOLVER_INDICES)]
        best_search: LocalSearchResult | None = None
        best_vector: NDArray[numpy.float64] | None = None
        total_nit = 0
        total_nfev = 0

        for start in restarts:
            search = bounded_pattern_search(
                objective=self._solver_merit,
                lower_bounds=reduced_lb,
                upper_bounds=reduced_ub,
                initial_solution=start,
                maxiter=maxiter,
            )
            total_nit += search.nit
            total_nfev += search.nfev
            candidate = self._reconstruct_solution(search.x)
            if candidate is None:
                continue
            if best_search is None or search.fun < best_search.fun:
                best_search = search
                best_vector = candidate

        if best_search is None or best_vector is None:
            fallback = self.generate_initial_solution(seed=seed)
            reduced_fallback = fallback[list(_REDUCED_SOLVER_INDICES)]
            best_vector = fallback
            best_search = LocalSearchResult(
                x=reduced_fallback,
                fun=self._solver_merit(reduced_fallback),
                nit=0,
                nfev=1,
            )
            total_nfev += 1

        max_violation = self.max_constraint_violation(best_vector)
        material = self.objective(best_vector)
        if max_violation <= 1e-6:
            message = (
                "Converged reduced-coordinate pattern search "
                f"(material {material:.4f} m^3, max violation {max_violation:.3g})."
            )
        else:
            message = (
                "Reduced-coordinate pattern search returned a best-effort design "
                f"(material {material:.4f} m^3, max violation {max_violation:.3g})."
            )
        return OptimizationResult(
            x=numpy.array(best_vector, dtype=float, copy=True),
            fun=material,
            success=max_violation <= 1e-6,
            message=message,
            nit=total_nit,
            nfev=total_nfev,
        )

    def _solver_start_points(
        self,
        initial_solution: NDArray[numpy.float64] | None,
        seed: int | None,
    ) -> tuple[NDArray[numpy.float64], ...]:
        """Return deterministic reduced-coordinate restart points.

        Args:
            initial_solution: Optional full four-variable starting point.
            seed: Optional random seed for deterministic jittered restarts.

        Returns:
            Reduced-coordinate restart points.

        Raises:
            ValueError: If ``initial_solution`` has the wrong shape.
        """
        starts: list[NDArray[numpy.float64]] = []
        if initial_solution is not None:
            candidate = numpy.array(initial_solution, dtype=float, copy=True)
            if candidate.shape != (4,):
                raise ValueError(f"Expected a 4-variable design vector, received shape {candidate.shape!r}.")
            starts.append(candidate[list(_REDUCED_SOLVER_INDICES)])
        else:
            starts.append(self.generate_initial_solution(seed=seed)[list(_REDUCED_SOLVER_INDICES)])

        reduced_lb = self.bounds.lb[list(_REDUCED_SOLVER_INDICES)]
        reduced_ub = self.bounds.ub[list(_REDUCED_SOLVER_INDICES)]
        starts.append(0.5 * (reduced_lb + reduced_ub))

        rng = numpy.random.default_rng(0 if seed is None else seed)
        span = reduced_ub - reduced_lb
        for _ in range(4):
            starts.append(reduced_lb + rng.random(reduced_lb.shape) * span)
        return tuple(starts)

    def _reconstruct_solution(self, reduced_variables: NDArray[numpy.float64]) -> NDArray[numpy.float64] | None:
        """Rebuild a full four-variable vector while satisfying both equalities.

        Args:
            reduced_variables: Reduced two-variable design vector.

        Returns:
            Full four-variable design vector, or ``None`` when reconstruction is
            not physically valid.
        """
        cylinder_radius, treadle_length = (float(value) for value in reduced_variables)
        probe = numpy.array([cylinder_radius, _REFERENCE_HOSE_RADIUS, treadle_length, 1.0], dtype=float)
        stroke_length = self.stroke_length_m(probe)
        denominator = _FLOW_FACTOR * math.pi * cylinder_radius**2 * stroke_length
        if denominator <= 0.0:
            return None

        step_rate = self.target_flow_rate_m3_per_s / denominator
        lift_reserve = (
            _SUCTION_HEAD_MAX
            - self.target_lift_height_m
            - _STROKE_LOSS_COEFFICIENT * (stroke_length / _REFERENCE_STROKE)
        )
        if lift_reserve <= 0.0:
            return None

        hose_radius = _REFERENCE_HOSE_RADIUS * math.sqrt(
            _HOSE_LOSS_COEFFICIENT * self.target_flow_rate_lps / lift_reserve
        )
        return numpy.array([cylinder_radius, hose_radius, treadle_length, step_rate], dtype=float)

    def _solver_merit(self, reduced_variables: NDArray[numpy.float64]) -> float:
        """Return a penalized merit value for reduced-coordinate search.

        Args:
            reduced_variables: Reduced two-variable design vector.

        Returns:
            Penalized scalar merit.
        """
        candidate = self._reconstruct_solution(reduced_variables)
        if candidate is None:
            return 1e12
        violation = self.constraint_violation(candidate)
        return float(self.objective(candidate) + 1e5 * violation**2 + 1e2 * violation)

    def _step_rate_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining cadence margin before exceeding the operator limit.

        Args:
            variables: Four-variable design vector.

        Returns:
            Positive slack before exceeding the step-rate bound.
        """
        return _STEP_RATE_UB - float(variables[3])

    def _hose_within_cylinder_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the radial clearance between the cylinder and hose radii.

        Args:
            variables: Four-variable design vector.

        Returns:
            Positive slack when the hose radius does not exceed the cylinder radius.
        """
        return float(variables[0]) - float(variables[1])

    def _stroke_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining ergonomic stroke margin.

        Args:
            variables: Four-variable design vector.

        Returns:
            Positive slack before exceeding the maximum stroke.
        """
        return _MAX_STROKE - self.stroke_length_m(variables)
