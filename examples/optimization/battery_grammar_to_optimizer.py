"""Inspect the packaged rectangular battery optimization benchmark."""

from __future__ import annotations

from design_research_problems import MissingOptionalDependencyError, get_problem


def _format_config(problem: object, variables: object) -> str:
    """Return the rounded ``SxP`` label for one battery design vector.

    Args:
        problem: Optimization problem exposing ``decode_candidate``.
        variables: Candidate design vector to decode.

    Returns:
        Short ``SxP`` battery-pack label.
    """
    state = problem.decode_candidate(variables)
    return f"{state.series_count}S{state.parallel_count}P"


def main() -> None:
    """Print a seeded start and the solved rectangular battery design."""
    problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    initial = problem.generate_initial_solution(seed=1)

    print("Rectangular battery packaged benchmark")
    print(problem.metadata.title)

    try:
        initial_components = problem.objective_components(initial)
        initial_violation = problem.max_constraint_violation(initial)
        result = problem.solve()
        solved_components = problem.objective_components(result.x)
        solved_violation = problem.max_constraint_violation(result.x)
    except MissingOptionalDependencyError as exc:
        print(exc)
        return

    print(
        "initial",
        f"config={_format_config(problem, initial)}",
        f"cost_usd={initial_components['cost_usd']:.2f}",
        f"voltage_v={initial_components['voltage_v']:.2f}",
        f"capacity_ah={initial_components['capacity_ah']:.2f}",
        f"current_limit_a={initial_components['current_limit_a']:.2f}",
        f"violation={initial_violation:.3g}",
    )
    print("solve", result.message)
    print(
        "solved",
        f"config={_format_config(problem, result.x)}",
        f"cost_usd={solved_components['cost_usd']:.2f}",
        f"voltage_v={solved_components['voltage_v']:.2f}",
        f"capacity_ah={solved_components['capacity_ah']:.2f}",
        f"current_limit_a={solved_components['current_limit_a']:.2f}",
        f"violation={solved_violation:.3g}",
    )


if __name__ == "__main__":
    main()
