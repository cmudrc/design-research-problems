"""Seed constrained optimization problem: minimum-area pill capsule."""

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
    OptimizationProblem,
    OptimizationResult,
)


def _pill_volume(radius: float, length: float) -> float:
    """Calculate the capsule volume.

    Args:
        radius: Capsule end-cap radius.
        length: Cylindrical section length.

    Returns:
        Capsule volume.
    """
    return 4.0 / 3.0 * math.pi * radius**3 + length * math.pi * radius**2


def _pill_area(radius: float, length: float) -> float:
    """Calculate the capsule surface area.

    Args:
        radius: Capsule end-cap radius.
        length: Cylindrical section length.

    Returns:
        Capsule surface area.
    """
    return 2.0 * math.pi * radius * length + 4.0 * math.pi * radius**2


class PillCapsuleMinArea(OptimizationProblem):
    """Two-variable constrained optimization problem."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        required_volume: float = 1e-6,
    ) -> None:
        """Initialize the seed pill optimization problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            required_volume: Fixed target volume.
        """
        super().__init__(metadata=metadata, statement_markdown=statement_markdown)
        self.required_volume = required_volume
        self.bounds = Bounds(
            lb=numpy.array([0.0, 0.0], dtype=float),
            ub=numpy.array([1.0, 1.0], dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(
                kind="eq",
                evaluate=lambda values: _pill_volume(float(values[0]), float(values[1])),
                target=self.required_volume,
            )
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest, statement_markdown: str) -> PillCapsuleMinArea:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.
            statement_markdown: Human-readable problem statement.

        Returns:
            Initialized problem instance.
        """
        required_volume = float(cast(float, manifest.parameters.get("required_volume", 1e-6)))
        return cls(metadata=manifest.metadata, statement_markdown=statement_markdown, required_volume=required_volume)

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return a feasible deterministic or seeded starting point.

        Args:
            seed: Optional random seed.

        Returns:
            Two-variable initial solution vector.
        """
        radius_upper = min(float(self.bounds.ub[0]), (3.0 * self.required_volume / (4.0 * math.pi)) ** (1.0 / 3.0))
        radius_lower = max(float(self.bounds.lb[0]), 1e-9)
        if seed is None:
            radius = 0.5 * (radius_lower + radius_upper)
        else:
            rng = numpy.random.default_rng(seed)
            radius = float(rng.uniform(radius_lower, radius_upper))
        length = (self.required_volume - 4.0 / 3.0 * math.pi * radius**3) / (math.pi * radius**2)
        return numpy.array([radius, max(length, 0.0)], dtype=float)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the pill area.

        Args:
            variables: Two-element vector of ``radius`` and ``length``.

        Returns:
            Surface area objective value.
        """
        return _pill_area(float(variables[0]), float(variables[1]))

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Solve the fixed-volume capsule problem by searching along the feasible manifold.

        The equality constraint permits a one-dimensional parameterization:
        once the capsule radius is chosen, the cylindrical length is fully
        determined. This solver uses a deterministic golden-section search over
        the feasible radius interval and reconstructs the matching length.

        Args:
            initial_solution: Optional caller-supplied starting point. The
                radius component is used to seed the search bracket.
            seed: Optional random seed used when a starting point is generated.
            maxiter: Maximum golden-section iterations.

        Returns:
            Numerically optimized capsule design.

        Raises:
            ValueError: If ``initial_solution`` is provided with the wrong
                shape.
        """
        radius_upper = (3.0 * self.required_volume / (4.0 * math.pi)) ** (1.0 / 3.0)
        radius_lower = max(float(self.bounds.lb[0]), 1e-9)

        if initial_solution is None:
            x0 = self.generate_initial_solution(seed=seed)
        else:
            x0 = numpy.array(initial_solution, dtype=float, copy=True)
            if x0.shape != (2,):
                raise ValueError(f"Expected a 2-variable design vector, received shape {x0.shape!r}.")
        seed_radius = float(numpy.clip(x0[0], radius_lower, min(radius_upper, float(self.bounds.ub[0]))))
        if seed_radius >= radius_upper:
            seed_radius = 0.5 * (radius_lower + radius_upper)

        phi = (math.sqrt(5.0) - 1.0) / 2.0
        left = radius_lower
        right = radius_upper
        left_probe = max(left, min(right, seed_radius))
        right_probe = left + phi * (right - left)
        if abs(right_probe - left_probe) <= 1e-12:
            left_probe = left + (1.0 - phi) * (right - left)
            right_probe = left + phi * (right - left)

        def candidate(radius: float) -> NDArray[numpy.float64]:
            length = (self.required_volume - 4.0 / 3.0 * math.pi * radius**3) / (math.pi * radius**2)
            return numpy.array([radius, max(length, 0.0)], dtype=float)

        left_vector = candidate(left_probe)
        right_vector = candidate(right_probe)
        left_value = self.objective(left_vector)
        right_value = self.objective(right_vector)
        nfev = 2
        nit = 0

        for _ in range(maxiter):
            nit += 1
            if right - left <= 1e-12:
                break
            if left_value <= right_value:
                right = right_probe
                right_probe = left_probe
                right_value = left_value
                left_probe = left + (1.0 - phi) * (right - left)
                left_vector = candidate(left_probe)
                left_value = self.objective(left_vector)
            else:
                left = left_probe
                left_probe = right_probe
                left_value = right_value
                right_probe = left + phi * (right - left)
                right_vector = candidate(right_probe)
                right_value = self.objective(right_vector)
            nfev += 1

        solution = left_vector if left_value <= right_value else right_vector
        success = self.max_constraint_violation(solution) <= 1e-9
        if success:
            message = "Converged golden-section search on the feasible capsule manifold."
        else:
            message = "Golden-section search ended with residual constraint error."
        return OptimizationResult(
            x=solution,
            fun=self.objective(solution),
            success=success,
            message=message,
            nit=nit,
            nfev=nfev,
        )
