from __future__ import annotations

import numpy
import pytest

from design_research_problems import get_problem
from design_research_problems.problems._optimization import bounded_pattern_search


def test_bounded_pattern_search_improves_within_bounds() -> None:
    result = bounded_pattern_search(
        objective=lambda values: float((values[0] - 0.25) ** 2),
        lower_bounds=numpy.array([0.0]),
        upper_bounds=numpy.array([1.0]),
        initial_solution=numpy.array([0.9]),
        maxiter=8,
    )

    assert result.nit >= 1
    assert result.nfev >= 1
    assert 0.0 <= float(result.x[0]) <= 1.0
    assert result.fun < 0.45


def test_optimization_problem_rejects_invalid_mcp_vectors() -> None:
    problem = get_problem("pill_capsule_min_area")

    with pytest.raises(ValueError, match="one-dimensional numeric vector"):
        problem._coerce_mcp_vector([[1.0, 2.0]])

    with pytest.raises(ValueError, match="Expected a 2-variable design vector"):
        problem._coerce_mcp_vector([1.0])
