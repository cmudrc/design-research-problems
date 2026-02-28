"""Base class for optimization problems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import numpy
from numpy.typing import NDArray

from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.problems._metadata import ProblemMetadata


@dataclass(frozen=True)
class Bounds:
    """Library-owned variable bounds."""

    lb: NDArray[numpy.float64]
    """Lower bounds for each design variable."""
    ub: NDArray[numpy.float64]
    """Upper bounds for each design variable."""


@dataclass(frozen=True)
class ConstraintDefinition:
    """Minimal solver-independent constraint definition."""

    kind: Literal["eq", "ineq"]
    """Constraint type understood by SciPy-like solvers."""
    evaluate: Callable[[NDArray[numpy.float64]], float]
    """Callable that maps variables to a scalar constraint value."""
    target: float = 0.0
    """Target value for the constraint function."""


def _import_scipy_optimize() -> Any:
    """Import ``scipy.optimize`` lazily for optional solve support.

    Returns:
        Imported SciPy optimize module.

    Raises:
        MissingOptionalDependencyError: If SciPy is not installed.
    """
    try:
        import scipy.optimize as optimize
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "SciPy is required for solve(). Install it with: pip install design-research-problems[opt]"
        ) from exc
    return optimize


class OptimizationProblem(ABC):
    """Abstract base for optimization problems."""

    def __init__(self, metadata: ProblemMetadata, statement_markdown: str = "") -> None:
        """Store shared metadata and initialize empty bounds and constraints.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
        """
        self.metadata = metadata
        self.statement_markdown = statement_markdown
        self.bounds = Bounds(
            lb=numpy.zeros(0, dtype=float),
            ub=numpy.zeros(0, dtype=float),
        )
        self.constraints: list[ConstraintDefinition] = []

    @abstractmethod
    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Generate a deterministic or seeded initial solution.

        Args:
            seed: Optional random seed.

        Returns:
            Initial solution vector.
        """

    @abstractmethod
    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Evaluate the objective function.

        Args:
            variables: Candidate design vector.

        Returns:
            Scalar objective value.
        """

    def generate_data(
        self,
        n: int = 1000,
        seed: int | None = None,
    ) -> tuple[NDArray[numpy.float64], NDArray[numpy.float64]]:
        """Generate uniform samples and their objective values.

        Args:
            n: Number of samples to generate.
            seed: Optional random seed.

        Returns:
            Tuple of sampled variables and objective values.
        """
        rng = numpy.random.default_rng(seed)
        x = rng.random((n, self.bounds.lb.shape[0]))
        scale = self.bounds.ub - self.bounds.lb
        x = x * scale + self.bounds.lb
        y = numpy.empty((n, 1), dtype=float)
        for index, row in enumerate(x):
            y[index, 0] = float(self.objective(row))
        return x, y

    @abstractmethod
    def load_data(self) -> object:
        """Load a curated dataset when available.

        Returns:
            Problem-specific dataset object.
        """

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> object:
        """Solve the optimization problem with SciPy SLSQP.

        Args:
            initial_solution: Optional initial vector. When omitted, one is generated.
            seed: Optional random seed used when generating the initial vector.
            maxiter: Maximum SLSQP iterations.

        Returns:
            SciPy optimization result object.
        """
        optimize = _import_scipy_optimize()
        x0 = self.generate_initial_solution(seed=seed) if initial_solution is None else initial_solution
        scipy_constraints: list[dict[str, object]] = []
        for constraint in self.constraints:
            scipy_constraints.append(
                {
                    "type": constraint.kind,
                    "fun": lambda x, constraint=constraint: constraint.evaluate(x) - constraint.target,
                }
            )
        return optimize.minimize(
            self.objective,
            x0=x0,
            method="SLSQP",
            bounds=optimize.Bounds(self.bounds.lb, self.bounds.ub),
            constraints=scipy_constraints,
            options={"maxiter": maxiter},
        )
