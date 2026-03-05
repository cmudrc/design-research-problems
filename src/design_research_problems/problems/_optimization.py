"""Base class for optimization problems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import numpy
from numpy.typing import NDArray

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._computable import ComputableProblem
from design_research_problems.problems._mcp import (
    create_fastmcp_server,
    normalized_optional_text,
    register_design_brief_resource,
    to_json_value,
)
from design_research_problems.problems._metadata import ProblemMetadata

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


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
    """Constraint type understood by baseline optimization routines."""
    evaluate: Callable[[NDArray[numpy.float64]], float]
    """Callable that maps variables to a scalar constraint value."""
    target: float = 0.0
    """Target value for the constraint function."""


@dataclass(frozen=True)
class OptimizationResult:
    """Minimal SciPy-like result object returned by built-in baseline solvers."""

    x: NDArray[numpy.float64]
    """Best candidate vector returned by the baseline routine."""
    fun: float
    """Objective value evaluated at ``x``."""
    success: bool
    """Whether the baseline routine reached a representative valid answer."""
    message: str
    """Short human-readable status summary."""
    nit: int = 1
    """Number of baseline iterations or candidates considered."""
    nfev: int = 0
    """Number of objective evaluations used by the solver."""


@dataclass(frozen=True)
class OptimizationEvaluation:
    """Standardized evaluation result for one optimization candidate."""

    x: NDArray[numpy.float64]
    """Evaluated candidate vector."""
    objective_value: float
    """Objective value at ``x``."""
    total_constraint_violation: float
    """Sum of all bound and constraint violations."""
    max_constraint_violation: float
    """Largest single bound or constraint violation."""
    is_feasible: bool
    """Whether ``x`` is feasible under the default tolerance."""


@dataclass(frozen=True)
class LocalSearchResult:
    """Internal result object for bounded pattern search."""

    x: NDArray[numpy.float64]
    """Best point found by the local search."""
    fun: float
    """Objective value at ``x``."""
    nit: int
    """Number of search sweeps performed."""
    nfev: int
    """Number of objective evaluations performed."""


def bounded_pattern_search(
    objective: Callable[[NDArray[numpy.float64]], float],
    lower_bounds: NDArray[numpy.float64],
    upper_bounds: NDArray[numpy.float64],
    initial_solution: NDArray[numpy.float64],
    maxiter: int = 200,
    initial_step_fraction: float = 0.15,
    minimum_step_fraction: float = 1e-4,
) -> LocalSearchResult:
    """Run a deterministic bounded coordinate-pattern local search.

    Args:
        objective: Scalar objective to minimize.
        lower_bounds: Inclusive lower bounds.
        upper_bounds: Inclusive upper bounds.
        initial_solution: Starting point for the search.
        maxiter: Maximum number of coordinate-sweep iterations.
        initial_step_fraction: Initial step size as a fraction of the bound span.
        minimum_step_fraction: Search stops when all steps fall below this
            fraction of the span.

    Returns:
        Local search result with the best point found.
    """
    span = upper_bounds - lower_bounds
    safe_span = numpy.where(span > 0.0, span, 1.0)
    current = numpy.clip(numpy.array(initial_solution, dtype=float, copy=True), lower_bounds, upper_bounds)
    step = numpy.maximum(initial_step_fraction * safe_span, minimum_step_fraction * safe_span)
    value = float(objective(current))
    nfev = 1
    nit = 0
    tolerance = 1e-12

    for _ in range(maxiter):
        nit += 1
        improved = False
        for index in range(current.shape[0]):
            for direction in (-1.0, 1.0):
                candidate = current.copy()
                candidate[index] = float(
                    numpy.clip(candidate[index] + direction * step[index], lower_bounds[index], upper_bounds[index])
                )
                candidate_value = float(objective(candidate))
                nfev += 1
                if candidate_value + tolerance < value:
                    current = candidate
                    value = candidate_value
                    improved = True
        if improved:
            step = numpy.minimum(step * 1.1, 0.3 * safe_span)
            continue
        step *= 0.5
        if bool(numpy.all(step <= minimum_step_fraction * safe_span)):
            break

    return LocalSearchResult(x=current, fun=value, nit=nit, nfev=nfev)


class OptimizationProblem(ComputableProblem[NDArray[numpy.float64], OptimizationEvaluation], ABC):
    """Abstract base for optimization problems."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Store shared metadata and initialize empty bounds and constraints.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.bounds = Bounds(
            lb=numpy.zeros(0, dtype=float),
            ub=numpy.zeros(0, dtype=float),
        )
        self.constraints: list[ConstraintDefinition] = []

    def evaluate(self, variables: NDArray[numpy.float64]) -> OptimizationEvaluation:
        """Evaluate one candidate vector without invoking the solver.

        Args:
            variables: Candidate design vector to score.

        Returns:
            Standardized optimization evaluation for ``variables``.
        """
        candidate = numpy.array(variables, dtype=float, copy=True)
        total_violation = self.constraint_violation(candidate)
        max_violation = self.max_constraint_violation(candidate)
        return OptimizationEvaluation(
            x=candidate,
            objective_value=self.objective(candidate),
            total_constraint_violation=total_violation,
            max_constraint_violation=max_violation,
            is_feasible=max_violation <= 1e-9,
        )

    def to_mcp_server(
        self,
        *,
        server_name: str | None = None,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> FastMCP:
        """Expose this optimization problem through FastMCP.

        The exported server exposes:
        - ``problem://design-brief`` resource
        - ``evaluate(x)`` tool for stateless candidate scoring
        - ``final_answer(final_x, justification?)`` tool

        Args:
            server_name: Optional explicit server name.
            include_citation: Whether the design brief includes citations.
            citation_mode: Citation rendering mode for the design brief.

        Returns:
            Configured FastMCP server.
        """
        server = create_fastmcp_server(self, server_name=server_name)
        register_design_brief_resource(
            server,
            brief_text=self.render_packet(include_citation=include_citation, citation_mode=citation_mode),
        )

        def evaluate_tool(x: list[float]) -> dict[str, object]:
            """Evaluate one candidate vector and return a complete report."""
            return self._mcp_evaluation_report(x)

        def final_answer(final_x: list[float], justification: str | None = None) -> dict[str, object]:
            """Submit one final optimization vector with an optional justification."""
            report = self._mcp_evaluation_report(final_x)
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "final_x": report["candidate_x"],
                "justification": normalized_optional_text(justification),
                "report": report,
            }

        server.add_tool(
            evaluate_tool,
            name="evaluate",
            title="Evaluate Design",
            description="Evaluate a candidate vector and return feasibility/objective metrics.",
        )
        server.add_tool(
            final_answer,
            name="final_answer",
            title="Submit Final Answer",
            description="Submit the final candidate vector with optional justification.",
        )
        return server

    def _mcp_evaluation_report(self, x: list[float]) -> dict[str, object]:
        """Return one MCP-facing optimization report.

        Args:
            x: Candidate design vector.

        Returns:
            JSON-safe report containing standardized evaluation fields and
            available problem-specific extras.
        """
        vector = self._coerce_mcp_vector(x)
        evaluation = self.evaluate(vector)
        report: dict[str, object] = {
            "problem_id": self.metadata.problem_id,
            "candidate_x": to_json_value(vector),
            "evaluation": to_json_value(evaluation),
        }

        objective_components = getattr(self, "objective_components", None)
        if callable(objective_components):
            report["objective_components"] = to_json_value(objective_components(vector))

        decode_candidate = getattr(self, "decode_candidate", None)
        if callable(decode_candidate):
            report["decoded_candidate"] = to_json_value(decode_candidate(vector))

        return report

    def _coerce_mcp_vector(self, x: list[float]) -> NDArray[numpy.float64]:
        """Validate and normalize one MCP-provided vector.

        Args:
            x: Candidate vector from the MCP tool input.

        Returns:
            Float numpy vector with the expected shape.

        Raises:
            ValueError: If ``x`` is not a one-dimensional vector matching the
                problem dimensionality.
        """
        candidate = numpy.array(x, dtype=float, copy=True)
        if candidate.ndim != 1:
            raise ValueError("x must be a one-dimensional numeric vector.")
        expected_shape = self.bounds.lb.shape
        if candidate.shape != expected_shape:
            raise ValueError(
                f"Expected a {expected_shape[0]}-variable design vector, received shape {candidate.shape!r}."
            )
        return candidate

    def bound_violation(self, variables: NDArray[numpy.float64]) -> float:
        """Return the total amount by which bounds are violated.

        Args:
            variables: Candidate design vector.

        Returns:
            Sum of lower- and upper-bound violations.
        """
        lower = numpy.maximum(self.bounds.lb - variables, 0.0)
        upper = numpy.maximum(variables - self.bounds.ub, 0.0)
        return float(lower.sum() + upper.sum())

    def constraint_violation(self, variables: NDArray[numpy.float64]) -> float:
        """Return the total equality, inequality, and bound violation.

        Args:
            variables: Candidate design vector.

        Returns:
            Total scalar violation measure.
        """
        violation = self.bound_violation(variables)
        for constraint in self.constraints:
            value = constraint.evaluate(variables)
            if constraint.kind == "eq":
                violation += abs(value - constraint.target)
            else:
                violation += max(constraint.target - value, 0.0)
        return float(violation)

    def max_constraint_violation(self, variables: NDArray[numpy.float64]) -> float:
        """Return the largest single equality, inequality, or bound violation.

        Args:
            variables: Candidate design vector.

        Returns:
            Maximum scalar violation.
        """
        values: list[float] = [self.bound_violation(variables)]
        for constraint in self.constraints:
            value = constraint.evaluate(variables)
            if constraint.kind == "eq":
                values.append(abs(value - constraint.target))
            else:
                values.append(max(constraint.target - value, 0.0))
        return float(max(values, default=0.0))

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

    @abstractmethod
    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Run the problem's representative baseline optimization routine.

        Args:
            initial_solution: Optional candidate vector supplied by the caller.
            seed: Optional random seed for any stochastic baseline logic.
            maxiter: Problem-specific iteration or candidate budget.

        Returns:
            Baseline optimization result.
        """
