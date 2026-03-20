from __future__ import annotations

import numpy
import pytest
from numpy.typing import NDArray

from design_research_problems.problems import ProblemKind, ProblemMetadata, ProblemTaxonomy
from design_research_problems.problems._optimization import (
    Bounds,
    LocalSearchResult,
    OptimizationProblem,
    OptimizationResult,
    bounded_pattern_search,
)


def _metadata() -> ProblemMetadata:
    return ProblemMetadata(
        problem_id="dummy_optimization",
        title="Dummy Optimization",
        summary="Minimal optimization problem for helper coverage.",
        kind=ProblemKind.OPTIMIZATION,
        taxonomy=ProblemTaxonomy(
            formulation="continuous",
            convexity="convex",
            design_variable_type="continuous",
            is_dynamic=False,
            orientation="engineering_practical",
            feasibility_ratio_hint=1.0,
            objective_mode="single",
            constraint_nature="hard",
            bounds_summary="two variables",
            tags=("dummy", "optimization"),
        ),
        citations=(),
        assets=(),
        capabilities=("bounded-variables", "statement-markdown"),
        study_suitability=(),
    )


class _DummyOptimizationProblem(OptimizationProblem):
    def __init__(self) -> None:
        super().__init__(metadata=_metadata(), statement_markdown="# Dummy Optimization")
        self.bounds = Bounds(
            lb=numpy.array([0.0, 0.0], dtype=float),
            ub=numpy.array([2.0, 2.0], dtype=float),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        del seed
        return numpy.array([1.5, 0.5], dtype=float)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        return float(numpy.sum((variables - 1.0) ** 2))

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        del initial_solution, seed, maxiter
        raise NotImplementedError

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        return {"sum": float(numpy.sum(variables))}

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> dict[str, object]:
        return {"rounded": [int(round(float(value))) for value in variables]}


def test_bounded_pattern_search_covers_improvement_and_no_improvement_paths() -> None:
    improving = bounded_pattern_search(
        objective=lambda x: float((x[0] - 1.0) ** 2),
        lower_bounds=numpy.array([0.0], dtype=float),
        upper_bounds=numpy.array([2.0], dtype=float),
        initial_solution=numpy.array([0.0], dtype=float),
        maxiter=20,
    )
    assert isinstance(improving, LocalSearchResult)
    assert improving.fun <= 0.05
    assert improving.nit >= 1
    assert improving.nfev >= 2

    stationary = bounded_pattern_search(
        objective=lambda x: 1.0,
        lower_bounds=numpy.array([0.0], dtype=float),
        upper_bounds=numpy.array([0.0], dtype=float),
        initial_solution=numpy.array([0.0], dtype=float),
        maxiter=10,
        minimum_step_fraction=0.5,
    )
    assert stationary.fun == pytest.approx(1.0)
    assert stationary.nit >= 1


def test_optimization_problem_reports_and_vector_validation_cover_edge_cases() -> None:
    problem = _DummyOptimizationProblem()

    report = problem._mcp_evaluation_report([1.25, 0.75])
    assert report["problem_id"] == "dummy_optimization"
    assert report["objective_components"] == {"sum": 2.0}
    assert report["decoded_candidate"] == {"rounded": [1, 1]}

    with pytest.raises(ValueError, match="one-dimensional numeric vector"):
        problem._coerce_mcp_vector([[1.0, 2.0]])  # type: ignore[list-item]

    with pytest.raises(ValueError, match="Expected a 2-variable design vector"):
        problem._coerce_mcp_vector([1.0])
