from __future__ import annotations

import numpy
import pytest

from design_research_problems import OptimizationEvaluation, OptimizationProblem, get_problem
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
from design_research_problems.problems.optimization import (
    Battery18650Tier1SeriesParallelOptimizationProblem,
    Battery18650Tier2LayoutOptimizationProblem,
    Battery18650Tier3TopologyOptimizationProblem,
    Battery18650Tier4ThermalOptimizationProblem,
)

_COMMON_METRIC_KEYS = {
    "cell_count",
    "connection_count",
    "cost_usd",
    "design_volume_mm3",
    "max_temperature_c",
    "voltage_v",
    "capacity_ah",
    "current_limit_a",
    "min_clearance_mm",
}


def _static_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
    )


def _patch_battery_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_grid

    monkeypatch.setattr(_battery_grid, "load_18650_cell_model", _static_cell_model)


def test_tiered_battery_optimizers_are_registered_and_use_optimization_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    cases = (
        ("battery_18650_t1_series_parallel_opt", Battery18650Tier1SeriesParallelOptimizationProblem),
        ("battery_18650_t2_layout_opt", Battery18650Tier2LayoutOptimizationProblem),
        ("battery_18650_t3_topology_opt", Battery18650Tier3TopologyOptimizationProblem),
        ("battery_18650_t4_thermal_opt", Battery18650Tier4ThermalOptimizationProblem),
    )
    for problem_id, expected_type in cases:
        problem = get_problem(problem_id)
        assert isinstance(problem, OptimizationProblem)
        assert isinstance(problem, expected_type)
        initial = problem.generate_initial_solution()
        components = problem.objective_components(initial)
        evaluation = problem.evaluate(initial)
        assert set(components) == _COMMON_METRIC_KEYS
        assert isinstance(evaluation, OptimizationEvaluation)
        assert evaluation.x.shape == initial.shape


def test_tiered_battery_dof_progression_is_strictly_increasing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    t1 = get_problem("battery_18650_t1_series_parallel_opt")
    t2 = get_problem("battery_18650_t2_layout_opt")
    t3 = get_problem("battery_18650_t3_topology_opt")
    t4 = get_problem("battery_18650_t4_thermal_opt")
    assert t1.bounds.lb.shape[0] < t2.bounds.lb.shape[0] < t3.bounds.lb.shape[0] < t4.bounds.lb.shape[0]


def test_tiered_battery_seeded_initial_solutions_are_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t1_series_parallel_opt",
        "battery_18650_t2_layout_opt",
        "battery_18650_t3_topology_opt",
        "battery_18650_t4_thermal_opt",
    ):
        problem = get_problem(problem_id)
        x1 = problem.generate_initial_solution(seed=7)
        x2 = problem.generate_initial_solution(seed=7)
        assert numpy.allclose(x1, x2)


def test_tiered_battery_baselines_solve_to_feasible_designs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t1_series_parallel_opt",
        "battery_18650_t2_layout_opt",
        "battery_18650_t3_topology_opt",
        "battery_18650_t4_thermal_opt",
    ):
        problem = get_problem(problem_id)
        result = problem.solve(maxiter=12)
        assert result.x.shape == problem.bounds.lb.shape
        assert problem.max_constraint_violation(result.x) <= 1.0e-9
        assert result.success is True


def test_t2_t3_t4_seeded_runs_show_non_degenerate_variability(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t2_layout_opt",
        "battery_18650_t3_topology_opt",
        "battery_18650_t4_thermal_opt",
    ):
        problem = get_problem(problem_id)
        outcomes: set[tuple[float, ...]] = set()
        for seed in range(5):
            result = problem.solve(seed=seed, maxiter=4)
            components = problem.objective_components(result.x)
            outcomes.add(
                (
                    round(result.fun, 5),
                    round(components["cell_count"], 2),
                    round(components["design_volume_mm3"], 1),
                    round(components["max_temperature_c"], 2),
                )
            )
        assert len(outcomes) >= 2
