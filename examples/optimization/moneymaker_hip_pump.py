"""Inspect the MoneyMaker Hip Pump humanitarian water-lifting benchmark."""

from __future__ import annotations

from design_research_problems import get_problem


def main() -> None:
    """Print the packaged baseline design and the solved SciPy SLSQP design."""
    problem = get_problem("moneymaker_hip_pump_cost_min")
    initial = problem.generate_initial_solution()
    initial_components = problem.objective_components(initial)
    result = problem.solve()
    solved_components = problem.objective_components(result.x)

    print("MoneyMaker Hip Pump humanitarian water-lifting benchmark")
    print(problem.metadata.title)
    print(
        "initial",
        f"flow_lps={initial_components['flow_rate_lps']:.3f}",
        f"tank_m={initial_components['tank_height_m']:.1f}",
        f"cost_usd={initial_components['cost_usd']:.2f}",
    )
    print("solve", result.message)
    print(
        "solved",
        f"flow_lps={solved_components['flow_rate_lps']:.3f}",
        f"tank_m={solved_components['tank_height_m']:.1f}",
        f"cost_usd={solved_components['cost_usd']:.2f}",
    )


if __name__ == "__main__":
    main()
