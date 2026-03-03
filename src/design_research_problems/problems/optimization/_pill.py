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


def _pill_length_for_volume(required_volume: float, radius: float) -> float:
    """Return the cylindrical length needed to meet the target volume.

    Args:
        required_volume: Fixed target capsule volume.
        radius: Capsule end-cap radius.

    Returns:
        Cylindrical section length.
    """
    return (required_volume - 4.0 / 3.0 * math.pi * radius**3) / (math.pi * radius**2)


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
        length_upper = float(self.bounds.ub[1])
        if _pill_length_for_volume(self.required_volume, radius_lower) > length_upper:
            lo = radius_lower
            hi = radius_upper
            for _ in range(64):
                midpoint = 0.5 * (lo + hi)
                if _pill_length_for_volume(self.required_volume, midpoint) > length_upper:
                    lo = midpoint
                else:
                    hi = midpoint
            radius_lower = hi
        if seed is None:
            radius = 0.5 * (radius_lower + radius_upper)
        else:
            rng = numpy.random.default_rng(seed)
            radius = float(rng.uniform(radius_lower, radius_upper))
        length = _pill_length_for_volume(self.required_volume, radius)
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
        """Solve the fixed-volume capsule problem with SciPy's SLSQP baseline.

        Args:
            initial_solution: Optional caller-supplied starting point.
            seed: Optional random seed used when a starting point is generated.
            maxiter: Maximum SLSQP iterations.

        Returns:
            Numerically optimized capsule design.

        Raises:
            ValueError: If ``initial_solution`` is provided with the wrong
                shape.
        """
        from scipy.optimize import minimize

        if initial_solution is None:
            x0 = self.generate_initial_solution(seed=seed)
        else:
            x0 = numpy.array(initial_solution, dtype=float, copy=True)
            if x0.shape != (2,):
                raise ValueError(f"Expected a 2-variable design vector, received shape {x0.shape!r}.")
        x0 = numpy.clip(x0, self.bounds.lb, self.bounds.ub)
        slsqp_bounds = list(zip(self.bounds.lb.tolist(), self.bounds.ub.tolist(), strict=True))
        raw_result = minimize(
            self.objective,
            x0=x0,
            method="SLSQP",
            bounds=slsqp_bounds,
            constraints=(
                {
                    "type": "eq",
                    "fun": lambda values: _pill_volume(float(values[0]), float(values[1])) - self.required_volume,
                },
            ),
            options={"maxiter": maxiter, "ftol": 1e-12, "disp": False},
        )

        solution = numpy.clip(numpy.array(raw_result.x, dtype=float, copy=True), self.bounds.lb, self.bounds.ub)
        max_violation = self.max_constraint_violation(solution)
        success = max_violation <= 1e-9
        if success:
            message = f"Converged SciPy SLSQP baseline (max violation {max_violation:.3g})."
        else:
            message = f"SciPy SLSQP returned a best-effort pill design (max violation {max_violation:.3g})."
        return OptimizationResult(
            x=solution,
            fun=self.objective(solution),
            success=success,
            message=message,
            nit=int(getattr(raw_result, "nit", 0) or 0),
            nfev=int(getattr(raw_result, "nfev", 0) or 0),
        )
