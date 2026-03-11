from __future__ import annotations

import numpy
import pytest

from design_research_problems import (
    MissingOptionalDependencyError,
    OptimizationEvaluation,
    OptimizationProblem,
    get_problem,
)
from design_research_problems.problems.grammar._battery_cell_model import (
    BatteryCellModel,
    BatteryThermalPriors,
)
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
    from design_research_problems.problems.optimization import _battery_grid, _battery_tiers

    monkeypatch.setattr(_battery_grid, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_tiers, "load_18650_thermal_priors", _static_thermal_priors)


def _static_thermal_priors() -> BatteryThermalPriors:
    return BatteryThermalPriors(
        soc_grid=(0.0, 1.0),
        total_resistance_ohm=(0.05, 0.05),
        cell_to_jig_conductance_w_per_k=1.0,
        jig_to_ambient_conductance_w_per_k=0.8,
        cell_thermal_mass_j_per_k=25.0,
        jig_thermal_mass_j_per_k=12.5,
        reference_ambient_temperature_c=25.0,
        source="test_stub",
    )


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


def test_t4_lumped_and_multi_node_modes_share_contract_and_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    baseline = get_problem("battery_18650_t4_thermal_opt")
    assert isinstance(baseline, Battery18650Tier4ThermalOptimizationProblem)
    candidate = baseline.generate_initial_solution(seed=4)

    lumped = Battery18650Tier4ThermalOptimizationProblem(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        requirements=baseline.requirements,
        max_cell_count=baseline.max_cell_count,
        minimum_spacing_mm=baseline.minimum_spacing_mm,
        objective_weights=baseline.objective_weights,
        cooling_coefficient_bounds=baseline.cooling_coefficient_bounds,
        passive_cooling_bounds=baseline.passive_cooling_bounds,
        ambient_temperature_bounds=baseline.ambient_temperature_bounds,
        thermal_model="lumped",
        thermal_neighbor_clearance_mm=baseline.thermal_neighbor_clearance_mm,
        thermal_contact_decay_mm=baseline.thermal_contact_decay_mm,
        thermal_contact_resistance_k_per_w=baseline.thermal_contact_resistance_k_per_w,
        thermal_flow_shadowing_factor=baseline.thermal_flow_shadowing_factor,
        thermal_airflow_axis=baseline.thermal_airflow_axis,
        thermal_reference_soc=baseline.thermal_reference_soc,
        maximum_temperature_c=baseline.maximum_temperature_c,
        load_current_a=baseline.load_current_a,
    )
    multi_node = Battery18650Tier4ThermalOptimizationProblem(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        requirements=baseline.requirements,
        max_cell_count=baseline.max_cell_count,
        minimum_spacing_mm=baseline.minimum_spacing_mm,
        objective_weights=baseline.objective_weights,
        cooling_coefficient_bounds=baseline.cooling_coefficient_bounds,
        passive_cooling_bounds=baseline.passive_cooling_bounds,
        ambient_temperature_bounds=baseline.ambient_temperature_bounds,
        thermal_model="multi_node_2node",
        thermal_neighbor_clearance_mm=baseline.thermal_neighbor_clearance_mm,
        thermal_contact_decay_mm=baseline.thermal_contact_decay_mm,
        thermal_contact_resistance_k_per_w=baseline.thermal_contact_resistance_k_per_w,
        thermal_flow_shadowing_factor=baseline.thermal_flow_shadowing_factor,
        thermal_airflow_axis=baseline.thermal_airflow_axis,
        thermal_reference_soc=baseline.thermal_reference_soc,
        maximum_temperature_c=baseline.maximum_temperature_c,
        load_current_a=baseline.load_current_a,
    )

    lumped_components_first = lumped.objective_components(candidate)
    lumped_components_second = lumped.objective_components(candidate)
    multi_components_first = multi_node.objective_components(candidate)
    multi_components_second = multi_node.objective_components(candidate)
    assert set(lumped_components_first) == _COMMON_METRIC_KEYS
    assert set(multi_components_first) == _COMMON_METRIC_KEYS
    assert lumped_components_first == pytest.approx(lumped_components_second)
    assert multi_components_first == pytest.approx(multi_components_second)
    assert lumped_components_first["max_temperature_c"] >= candidate[-1]
    assert multi_components_first["max_temperature_c"] >= candidate[-1]
    diagnostics = multi_node.thermal_diagnostics(candidate)
    assert set(diagnostics) == {
        "max_core_temperature_c",
        "max_surface_temperature_c",
        "coolant_temperature_c",
        "max_core_surface_delta_c",
    }
    assert diagnostics["max_core_temperature_c"] >= diagnostics["max_surface_temperature_c"]


def test_t4_requires_pybamm_for_thermal_priors(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_tiers

    def _missing_thermal_priors() -> BatteryThermalPriors:
        raise MissingOptionalDependencyError("pybamm is required")

    monkeypatch.setattr(_battery_tiers, "load_18650_thermal_priors", _missing_thermal_priors)
    t3 = get_problem("battery_18650_t3_topology_opt")
    assert isinstance(t3, Battery18650Tier3TopologyOptimizationProblem)
    with pytest.raises(MissingOptionalDependencyError, match="pybamm is required"):
        Battery18650Tier4ThermalOptimizationProblem(
            metadata=t3.metadata,
            requirements=t3.requirements,
        )
