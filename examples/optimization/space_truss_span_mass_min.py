"""Solve the packaged 3D space-truss mass-minimization benchmark."""

from __future__ import annotations

import warnings

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems._domains.space_truss import evaluate_space_truss_state


def main() -> None:
    """Run the built-in structural baseline for the 3D space-truss optimizer."""
    problem = get_problem("space_truss_span_mass_min")
    initial = problem.generate_initial_solution()
    print(problem.metadata.problem_id)
    print("variables", initial.shape[0])
    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"trussme\\.components")
            initial_evaluation = problem.evaluate(initial)
            result = problem.solve(maxiter=64)
            final_state = problem.decode_candidate(result.x)
            structural = evaluate_space_truss_state(final_state)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return
    print("initial", round(initial_evaluation.objective_value, 3), initial_evaluation.is_feasible)
    print("members", len(final_state.members))
    print("mass", round(structural.mass, 3))
    print("fos", round(structural.fos, 3))
    print("deflection", round(structural.deflection, 3))
    print("solve", bool(result.success))


if __name__ == "__main__":
    main()
