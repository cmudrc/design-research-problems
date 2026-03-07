"""Inspect the packaged dynamic GMPB optimization wrapper."""

from __future__ import annotations

import numpy

import design_research_problems as derp


def main() -> None:
    """Print stateful GMPB evaluation and solve details."""
    problem = derp.get_problem("gmpb_default_dynamic_min")
    print(problem.metadata.problem_id)
    print(f"dimension {problem.bounds.lb.shape[0]}")
    print(f"before env={problem.current_environment_index()} evals={problem.evaluations_in_environment()}")
    candidate = numpy.zeros(problem.bounds.lb.shape, dtype=float)
    evaluation = problem.evaluate(candidate)
    print(f"evaluate objective={evaluation.objective_value:.6f}")
    print(f"after env={problem.current_environment_index()} evals={problem.evaluations_in_environment()}")
    result = problem.solve(seed=3, maxiter=16)
    print(f"solve best={result.fun:.6f} nfev={result.nfev}")
    print(f"final env={problem.current_environment_index()} evals={problem.evaluations_in_environment()}")


if __name__ == "__main__":
    main()
