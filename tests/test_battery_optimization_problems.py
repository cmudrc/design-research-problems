from __future__ import annotations

import numpy
import pytest

from design_research_problems import OptimizationEvaluation, OptimizationProblem, get_problem
from design_research_problems.problems._domains.battery_layout import BatteryRequirements
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
from design_research_problems.problems.grammar._battery_circuit import BatteryCircuitState
from design_research_problems.problems.optimization import (
    BatteryGridSizingProblem,
    BatteryOpenEndedCapacityMaxProblem,
)


def _static_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
    )


def _patch_battery_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_grid, _battery_open_ended

    monkeypatch.setattr(_battery_grid, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_open_ended, "load_18650_cell_model", _static_cell_model)


def test_battery_grid_seeded_initial_solution_is_deterministic_and_nonbaseline() -> None:
    problem = get_problem("battery_pack_18650_series_parallel_cost_min")

    baseline = problem.generate_initial_solution()
    x1 = problem.generate_initial_solution(seed=7)
    x2 = problem.generate_initial_solution(seed=7)

    assert x1.shape == (2,)
    assert numpy.allclose(x1, x2)
    assert numpy.all(x1 >= problem.bounds.lb)
    assert numpy.all(x1 <= problem.bounds.ub)
    assert not numpy.allclose(x1, baseline)


def test_battery_grid_objective_components_and_solve_stay_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    assert isinstance(problem, BatteryGridSizingProblem)

    baseline = problem.generate_initial_solution()
    components = problem.objective_components(baseline)
    evaluation = problem.evaluate(baseline)
    result = problem.solve(maxiter=25)
    state = problem.decode_candidate(result.x)

    assert set(components) == {"capacity_ah", "cell_count", "cost_usd", "current_limit_a", "voltage_v"}
    assert components["cost_usd"] == pytest.approx(evaluation.objective_value)
    assert components["cell_count"] == pytest.approx(16.0)
    assert result.success is True
    assert (state.series_count, state.parallel_count) == (4, 4)


def test_open_ended_battery_optimizer_is_registered_and_decodes_seed_state() -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")

    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)

    initial = problem.generate_initial_solution()
    state = problem.decode_candidate(initial)

    assert initial.shape == (32,)
    assert isinstance(state, BatteryCircuitState)
    assert len(state.cells) == 24
    assert len(state.connections) == 43


def test_open_ended_battery_optimizer_evaluate_and_solve_use_optimization_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    packaged_problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(packaged_problem, BatteryOpenEndedCapacityMaxProblem)

    requirements = BatteryRequirements(
        target_voltage_v=14.8,
        minimum_capacity_ah=10.0,
        minimum_current_a=240.0,
        max_width_mm=500.0,
        max_depth_mm=500.0,
        max_height_mm=250.0,
        voltage_tolerance_v=0.1,
    )
    problem = type(packaged_problem)(
        metadata=packaged_problem.metadata,
        requirements=requirements,
        max_cell_count=packaged_problem.max_cell_count,
    )

    initial = problem.generate_initial_solution()
    components = problem.objective_components(initial)
    evaluation = problem.evaluate(initial)
    result = problem.solve(maxiter=0)

    assert set(components) == {
        "cell_count",
        "connection_count",
        "delivered_capacity_ah",
        "design_volume_mm3",
        "end_voltage_v",
    }
    assert components["cell_count"] == pytest.approx(24.0)
    assert components["connection_count"] == pytest.approx(43.0)
    assert components["delivered_capacity_ah"] >= problem.requirements.minimum_capacity_ah
    assert isinstance(evaluation, OptimizationEvaluation)
    assert evaluation.x.shape == (32,)
    assert evaluation.is_feasible is True
    assert result.x.shape == (32,)
    assert result.success is (problem.max_constraint_violation(result.x) <= 1.0e-9)
    assert result.message.startswith("Evaluated the explicit battery transition program")
