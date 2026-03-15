from __future__ import annotations

from types import SimpleNamespace

import numpy
import pytest

from design_research_problems import (
    MissingOptionalDependencyError,
    OptimizationEvaluation,
    OptimizationProblem,
    get_problem,
)
from design_research_problems.problems._domains.battery_benchmark import BatteryEvaluationMode
from design_research_problems.problems._domains.battery_cell_model import BatteryCellModel, BatteryThermalPriors
from design_research_problems.problems._domains.battery_geometry import (
    FiniteCylinder,
    min_distance_between_cylinders,
)
from design_research_problems.problems.optimization import (
    Battery18650T1RectangularSurrogateOptimizationProblem,
    Battery18650T2PoseSurrogateOptimizationProblem,
    Battery18650T3ATopologySurrogateOptimizationProblem,
    Battery18650T3BNetlistExplicitOptimizationProblem,
    Battery18650T4ThermalHybridOptimizationProblem,
    BatteryFastChargeDFNAnchorOptimizationProblem,
)
from design_research_problems.problems.optimization._battery_fast_charge import (
    FastChargeMetricSummary,
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
        source="test_stub",
        resolved_mode="pybamm_ecm",
    )


def _patch_battery_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems import _battery_adapters
    from design_research_problems.problems._domains import battery_circuit
    from design_research_problems.problems.optimization import _battery_grid, _battery_open_ended, _battery_tiers

    monkeypatch.setattr(_battery_grid, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_open_ended, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_adapters, "load_18650_cell_model", lambda config=None: _static_cell_model())
    monkeypatch.setattr(_battery_adapters, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
    monkeypatch.setattr(battery_circuit, "load_battery_cell_model", lambda config=None: _static_cell_model())
    monkeypatch.setattr(battery_circuit, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
    monkeypatch.setattr(_battery_tiers, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
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


def _static_fast_charge_metrics(*args: object, **kwargs: object) -> FastChargeMetricSummary:
    del args, kwargs
    return FastChargeMetricSummary(
        charge_time_min=14.5,
        max_plating_mol_m3=0.0,
        max_temperature_c=38.0,
        energy_density_wh_per_l=620.0,
        success=True,
    )


def _directional_fast_charge_metrics(
    design_parameters: dict[str, float],
    **kwargs: object,
) -> FastChargeMetricSummary:
    del kwargs
    negative_thickness = float(design_parameters["Negative electrode thickness [m]"])
    positive_thickness = float(design_parameters["Positive electrode thickness [m]"])
    separator_thickness = float(design_parameters["Separator thickness [m]"])
    negative_porosity = float(design_parameters["Negative electrode porosity"])
    positive_porosity = float(design_parameters["Positive electrode porosity"])
    charge_time = (
        9.0
        + (160_000.0 * (negative_thickness + positive_thickness))
        + (250_000.0 * separator_thickness)
        - (4.0 * (negative_porosity + positive_porosity))
    )
    return FastChargeMetricSummary(
        charge_time_min=float(charge_time),
        max_plating_mol_m3=0.0,
        max_temperature_c=36.0,
        energy_density_wh_per_l=540.0,
        success=True,
    )


def _failed_fast_charge_metrics(*args: object, **kwargs: object) -> FastChargeMetricSummary:
    del args, kwargs
    return FastChargeMetricSummary(
        charge_time_min=999.0,
        max_plating_mol_m3=1.0,
        max_temperature_c=120.0,
        energy_density_wh_per_l=0.0,
        success=False,
        failure_reason="solver failed",
    )


def test_tiered_battery_optimizers_are_registered_and_use_optimization_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    cases = (
        (
            "battery_18650_t1_rectangular_surrogate_opt",
            Battery18650T1RectangularSurrogateOptimizationProblem,
        ),
        ("battery_18650_t2_pose_surrogate_opt", Battery18650T2PoseSurrogateOptimizationProblem),
        (
            "battery_18650_t3a_topology_explicit_2rc_opt",
            Battery18650T3ATopologySurrogateOptimizationProblem,
        ),
        (
            "battery_18650_t3a_topology_surrogate_opt",
            Battery18650T3ATopologySurrogateOptimizationProblem,
        ),
        ("battery_18650_t4_thermal_hybrid_2rc_opt", Battery18650T4ThermalHybridOptimizationProblem),
        ("battery_18650_t4_thermal_hybrid_opt", Battery18650T4ThermalHybridOptimizationProblem),
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


def test_t3b_explicit_battery_optimizer_is_registered_and_uses_shared_metric_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_18650_t3b_netlist_explicit_opt")
    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, Battery18650T3BNetlistExplicitOptimizationProblem)
    initial = problem.generate_initial_solution(seed=7)
    components = problem.objective_components(initial)
    evaluation = problem.evaluate(initial)
    provenance = problem.evaluation_provenance(initial)
    assert set(components) == _COMMON_METRIC_KEYS
    assert isinstance(evaluation, OptimizationEvaluation)
    assert provenance.representation_mode == "explicit_netlist"
    assert provenance.evaluation_mode == "explicit_circuit"
    assert provenance.honored_backend_fields


def test_manifest_backed_2rc_optimizer_variants_report_backend_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    cases = (
        ("battery_18650_t3a_topology_explicit_2rc_opt", "explicit_circuit", None),
        ("battery_18650_t4_thermal_hybrid_2rc_opt", "hybrid_thermal", "test_stub"),
    )
    for problem_id, expected_mode, expected_thermal_source in cases:
        problem = get_problem(problem_id)
        initial = problem.generate_initial_solution(seed=5)
        provenance = problem.evaluation_provenance(initial)
        assert provenance.evaluation_mode == expected_mode
        assert provenance.requested_backend_config == {
            "cell_model_mode": "pybamm_ecm_2rc",
            "parameterization": {"parameter_set": "Marquis2019"},
            "thermal_mode": "isothermal",
            "ambient_temp_c": 25.0,
        }
        assert provenance.resolved_backend_config == provenance.requested_backend_config
        assert provenance.honored_backend_fields == (
            "ambient_temp_c",
            "cell_model_mode",
            "parameterization",
            "thermal_mode",
        )
        assert provenance.cell_model_source == "test_stub"
        assert provenance.thermal_prior_source == expected_thermal_source


def test_t4_problem_loading_is_lazy_about_thermal_priors(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_tiers

    monkeypatch.setattr(
        _battery_tiers,
        "load_18650_thermal_priors",
        lambda: (_ for _ in ()).throw(AssertionError("default thermal priors loaded eagerly")),
    )
    monkeypatch.setattr(
        _battery_tiers,
        "load_battery_thermal_priors",
        lambda config=None: (_ for _ in ()).throw(AssertionError("backend thermal priors loaded eagerly")),
    )

    baseline = get_problem("battery_18650_t4_thermal_hybrid_opt")
    configured = get_problem("battery_18650_t4_thermal_hybrid_2rc_opt")
    assert isinstance(baseline, Battery18650T4ThermalHybridOptimizationProblem)
    assert isinstance(configured, Battery18650T4ThermalHybridOptimizationProblem)
    assert baseline._thermal_priors_cache is None
    assert configured._thermal_priors_cache is None


def test_tiered_battery_dof_progression_is_strictly_increasing(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    t1 = get_problem("battery_18650_t1_rectangular_surrogate_opt")
    t2 = get_problem("battery_18650_t2_pose_surrogate_opt")
    t3 = get_problem("battery_18650_t3a_topology_surrogate_opt")
    t4 = get_problem("battery_18650_t4_thermal_hybrid_opt")
    assert t1.bounds.lb.shape[0] < t2.bounds.lb.shape[0] < t3.bounds.lb.shape[0] < t4.bounds.lb.shape[0]


def test_tiered_battery_seeded_initial_solutions_are_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t1_rectangular_surrogate_opt",
        "battery_18650_t2_pose_surrogate_opt",
        "battery_18650_t3a_topology_explicit_2rc_opt",
        "battery_18650_t3a_topology_surrogate_opt",
        "battery_18650_t3b_netlist_explicit_opt",
        "battery_18650_t4_thermal_hybrid_2rc_opt",
        "battery_18650_t4_thermal_hybrid_opt",
    ):
        problem = get_problem(problem_id)
        x1 = problem.generate_initial_solution(seed=7)
        x2 = problem.generate_initial_solution(seed=7)
        assert numpy.allclose(x1, x2)


def test_tiered_battery_baselines_solve_to_feasible_designs(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t1_rectangular_surrogate_opt",
        "battery_18650_t2_pose_surrogate_opt",
        "battery_18650_t3a_topology_surrogate_opt",
        "battery_18650_t4_thermal_hybrid_opt",
    ):
        problem = get_problem(problem_id)
        result = problem.solve(maxiter=12)
        assert result.x.shape == problem.bounds.lb.shape
        assert problem.max_constraint_violation(result.x) <= 1.0e-9
        assert result.success is True


def test_t2_t3_t4_seeded_runs_show_non_degenerate_variability(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    for problem_id in (
        "battery_18650_t2_pose_surrogate_opt",
        "battery_18650_t3a_topology_surrogate_opt",
        "battery_18650_t4_thermal_hybrid_opt",
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
    baseline = get_problem("battery_18650_t4_thermal_hybrid_opt")
    assert isinstance(baseline, Battery18650T4ThermalHybridOptimizationProblem)
    candidate = baseline.generate_initial_solution(seed=4)

    lumped = type(baseline)(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        resource_bundle=baseline.resource_bundle,
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
        backend_config=baseline.backend_config,
        evaluation_mode=BatteryEvaluationMode.HYBRID_THERMAL.value,
        imbalance_model=baseline.imbalance_model.value,
    )
    multi_node = type(baseline)(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        resource_bundle=baseline.resource_bundle,
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
        backend_config=baseline.backend_config,
        evaluation_mode=BatteryEvaluationMode.HYBRID_THERMAL.value,
        imbalance_model=baseline.imbalance_model.value,
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

    def _missing_thermal_priors(config: object | None = None) -> BatteryThermalPriors:
        del config
        raise MissingOptionalDependencyError("pybamm is required")

    monkeypatch.setattr(_battery_tiers, "load_18650_thermal_priors", _missing_thermal_priors)
    monkeypatch.setattr(_battery_tiers, "load_battery_thermal_priors", _missing_thermal_priors)
    t3 = get_problem("battery_18650_t3a_topology_surrogate_opt")
    assert isinstance(t3, Battery18650T3ATopologySurrogateOptimizationProblem)
    problem = Battery18650T4ThermalHybridOptimizationProblem(
        metadata=t3.metadata,
        requirements=t3.requirements,
    )
    initial = problem.generate_initial_solution(seed=4)
    with pytest.raises(MissingOptionalDependencyError, match="pybamm is required"):
        problem.objective_components(initial)


def test_fast_charge_optimizer_is_registered_and_uses_optimization_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.optimization import _battery_fast_charge

    monkeypatch.setattr(_battery_fast_charge, "evaluate_fast_charge_design", _static_fast_charge_metrics)

    problem = get_problem("battery_fast_charge_dfn_anchor_opt")
    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, BatteryFastChargeDFNAnchorOptimizationProblem)
    initial = problem.generate_initial_solution(seed=7)
    components = problem.objective_components(initial)
    evaluation = problem.evaluate(initial)
    provenance = problem.evaluation_provenance(initial)
    assert set(components) == {
        "charge_time_min",
        "max_plating_mol_m3",
        "max_temperature_c",
        "energy_density_wh_per_l",
        "success",
    }
    assert isinstance(evaluation, OptimizationEvaluation)
    assert evaluation.is_feasible is True
    assert provenance.evaluation_mode == "electrochemical_anchor"
    assert provenance.cell_model_source == "pybamm_dfn"


def test_fast_charge_optimizer_failure_metrics_stay_finite(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_fast_charge

    monkeypatch.setattr(_battery_fast_charge, "evaluate_fast_charge_design", _failed_fast_charge_metrics)

    problem = get_problem("battery_fast_charge_dfn_anchor_opt")
    initial = problem.generate_initial_solution()
    evaluation = problem.evaluate(initial)
    components = problem.objective_components(initial)
    assert components["success"] == pytest.approx(0.0)
    assert numpy.isfinite(evaluation.objective_value)
    assert evaluation.is_feasible is False


def test_fast_charge_optimizer_baseline_search_can_improve_charge_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.optimization import _battery_fast_charge

    monkeypatch.setattr(_battery_fast_charge, "evaluate_fast_charge_design", _directional_fast_charge_metrics)

    problem = get_problem("battery_fast_charge_dfn_anchor_opt")
    initial = problem.generate_initial_solution()
    baseline = problem.objective(initial)
    result = problem.solve(maxiter=1)
    assert result.fun <= baseline
    assert result.x[0] < initial[0]
    assert "baseline/reference search" in result.message


def test_public_battery_optimization_problem_cards_and_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    cases = (
        (
            "battery_18650_t1_rectangular_surrogate_opt",
            "rectangular",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t2_pose_surrogate_opt",
            "pose_layout",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3a_topology_explicit_2rc_opt",
            "topology_allocation",
            "explicit_circuit",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3a_topology_surrogate_opt",
            "topology_allocation",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3b_netlist_explicit_opt",
            "explicit_netlist",
            "explicit_circuit",
            ("explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t4_thermal_hybrid_2rc_opt",
            "thermal_topology",
            "hybrid_thermal",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t4_thermal_hybrid_opt",
            "thermal_topology",
            "hybrid_thermal",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_fast_charge_dfn_anchor_opt",
            "fast_charge_cell",
            "electrochemical_anchor",
            ("electrochemical_anchor",),
        ),
    )
    for problem_id, representation_mode, default_mode, supported_modes in cases:
        problem = get_problem(problem_id)
        card = problem.metadata.benchmark_card
        assert card is not None
        assert card.representation_mode == representation_mode
        assert card.default_evaluation_mode == default_mode
        assert card.supported_evaluation_modes == supported_modes
        assert "## Benchmark Contract" in problem.render_brief(include_citation=False)


def test_t3a_explicit_projection_is_deterministic_and_reports_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    baseline = get_problem("battery_18650_t3a_topology_surrogate_opt")
    assert isinstance(baseline, Battery18650T3ATopologySurrogateOptimizationProblem)
    candidate = baseline.generate_initial_solution(seed=5)
    explicit = type(baseline)(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        resource_bundle=baseline.resource_bundle,
        requirements=baseline.requirements,
        max_cell_count=baseline.max_cell_count,
        minimum_spacing_mm=baseline.minimum_spacing_mm,
        objective_weights=baseline.objective_weights,
        cooling_coefficient_w_per_m2k=baseline.cooling_coefficient_w_per_m2k,
        passive_cooling_w_per_k=baseline.passive_cooling_w_per_k,
        ambient_temperature_c=baseline.ambient_temperature_c,
        maximum_temperature_c=baseline.maximum_temperature_c,
        load_current_a=baseline.load_current_a,
        backend_config=baseline.backend_config,
        evaluation_mode=BatteryEvaluationMode.EXPLICIT_CIRCUIT.value,
        imbalance_model=baseline.imbalance_model.value,
    )
    first = explicit.objective_components(candidate)
    second = explicit.objective_components(candidate)
    provenance = explicit.evaluation_provenance(candidate)
    assert first == pytest.approx(second)
    assert provenance.evaluation_mode == "explicit_circuit"
    assert provenance.electrical_path == "projected"
    assert provenance.thermal_path == "native"
    assert provenance.adaptation_notes
    assert provenance.cell_model_source in {"test_stub", "pybamm_thevenin"}


def test_t3_imbalance_models_are_substitutable_but_not_identical(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    baseline = get_problem("battery_18650_t3a_topology_surrogate_opt")
    assert isinstance(baseline, Battery18650T3ATopologySurrogateOptimizationProblem)
    candidate = baseline.generate_initial_solution(seed=3)
    candidate[0] = 6.0
    candidate[1] = 4.0
    stage_slots = (0.0, 0.0, 0.0, 1.0, 2.0, 3.0)
    for cell_index, stage_slot in enumerate(stage_slots):
        candidate[2 + (7 * cell_index) + 6] = stage_slot
    harmonic = type(baseline)(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        resource_bundle=baseline.resource_bundle,
        requirements=baseline.requirements,
        max_cell_count=baseline.max_cell_count,
        minimum_spacing_mm=baseline.minimum_spacing_mm,
        objective_weights=baseline.objective_weights,
        cooling_coefficient_w_per_m2k=baseline.cooling_coefficient_w_per_m2k,
        passive_cooling_w_per_k=baseline.passive_cooling_w_per_k,
        ambient_temperature_c=baseline.ambient_temperature_c,
        maximum_temperature_c=baseline.maximum_temperature_c,
        load_current_a=baseline.load_current_a,
        backend_config=baseline.backend_config,
        evaluation_mode=baseline.evaluation_mode.value,
        imbalance_model="harmonic_mean_stage",
    )
    min_stage_metrics = baseline._metrics_from_variables(candidate)
    harmonic_metrics = harmonic._metrics_from_variables(candidate)
    assert harmonic_metrics.capacity_ah > min_stage_metrics.capacity_ah
    assert harmonic_metrics.current_limit_a > min_stage_metrics.current_limit_a
    assert baseline.evaluation_provenance(candidate).imbalance_model == "min_stage"
    assert harmonic.evaluation_provenance(candidate).imbalance_model == "harmonic_mean_stage"


def test_t4_public_modes_report_expected_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    baseline = get_problem("battery_18650_t4_thermal_hybrid_opt")
    assert isinstance(baseline, Battery18650T4ThermalHybridOptimizationProblem)
    candidate = baseline.generate_initial_solution(seed=4)

    analytic = type(baseline)(
        metadata=baseline.metadata,
        statement_markdown=baseline.statement_markdown,
        resource_bundle=baseline.resource_bundle,
        requirements=baseline.requirements,
        max_cell_count=baseline.max_cell_count,
        minimum_spacing_mm=baseline.minimum_spacing_mm,
        objective_weights=baseline.objective_weights,
        cooling_coefficient_bounds=baseline.cooling_coefficient_bounds,
        passive_cooling_bounds=baseline.passive_cooling_bounds,
        ambient_temperature_bounds=baseline.ambient_temperature_bounds,
        thermal_model=baseline.thermal_model,
        thermal_neighbor_clearance_mm=baseline.thermal_neighbor_clearance_mm,
        thermal_contact_decay_mm=baseline.thermal_contact_decay_mm,
        thermal_contact_resistance_k_per_w=baseline.thermal_contact_resistance_k_per_w,
        thermal_flow_shadowing_factor=baseline.thermal_flow_shadowing_factor,
        thermal_airflow_axis=baseline.thermal_airflow_axis,
        thermal_reference_soc=baseline.thermal_reference_soc,
        maximum_temperature_c=baseline.maximum_temperature_c,
        load_current_a=baseline.load_current_a,
        backend_config=baseline.backend_config,
        evaluation_mode="analytic_surrogate",
        imbalance_model=baseline.imbalance_model.value,
    )
    explicit = type(analytic)(
        metadata=analytic.metadata,
        statement_markdown=analytic.statement_markdown,
        resource_bundle=analytic.resource_bundle,
        requirements=analytic.requirements,
        max_cell_count=analytic.max_cell_count,
        minimum_spacing_mm=analytic.minimum_spacing_mm,
        objective_weights=analytic.objective_weights,
        cooling_coefficient_bounds=analytic.cooling_coefficient_bounds,
        passive_cooling_bounds=analytic.passive_cooling_bounds,
        ambient_temperature_bounds=analytic.ambient_temperature_bounds,
        thermal_model=analytic.thermal_model,
        thermal_neighbor_clearance_mm=analytic.thermal_neighbor_clearance_mm,
        thermal_contact_decay_mm=analytic.thermal_contact_decay_mm,
        thermal_contact_resistance_k_per_w=analytic.thermal_contact_resistance_k_per_w,
        thermal_flow_shadowing_factor=analytic.thermal_flow_shadowing_factor,
        thermal_airflow_axis=analytic.thermal_airflow_axis,
        thermal_reference_soc=analytic.thermal_reference_soc,
        maximum_temperature_c=analytic.maximum_temperature_c,
        load_current_a=analytic.load_current_a,
        backend_config=analytic.backend_config,
        evaluation_mode="explicit_circuit",
        imbalance_model=analytic.imbalance_model.value,
    )
    assert analytic.evaluation_provenance(candidate).evaluation_mode == "analytic_surrogate"
    explicit_provenance = explicit.evaluation_provenance(candidate)
    hybrid_provenance = baseline.evaluation_provenance(candidate)
    assert explicit_provenance.evaluation_mode == "explicit_circuit"
    assert explicit_provenance.electrical_path == "projected"
    assert explicit_provenance.thermal_path == "native"
    assert hybrid_provenance.evaluation_mode == "hybrid_thermal"
    assert hybrid_provenance.electrical_path == "projected"
    assert hybrid_provenance.thermal_path == "native"
    assert hybrid_provenance.thermal_prior_source == "test_stub"


def test_public_battery_optimizers_reject_unsupported_evaluation_modes() -> None:
    t3b = get_problem("battery_18650_t3b_netlist_explicit_opt")
    with pytest.raises(ValueError, match="Unsupported battery evaluation_mode"):
        type(t3b)(
            metadata=t3b.metadata,
            statement_markdown=t3b.statement_markdown,
            resource_bundle=t3b.resource_bundle,
            requirements=t3b.requirements,
            max_cell_count=t3b.max_cell_count,
            backend_config=t3b.backend_config,
            objective_weights=t3b.objective_weights,
            cooling_coefficient_w_per_m2k=t3b.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=t3b.passive_cooling_w_per_k,
            ambient_temperature_c=t3b.ambient_temperature_c,
            maximum_temperature_c=t3b.maximum_temperature_c,
            load_current_a=t3b.load_current_a,
            thermal_model=t3b.thermal_model,
            thermal_neighbor_clearance_mm=t3b.thermal_neighbor_clearance_mm,
            thermal_contact_decay_mm=t3b.thermal_contact_decay_mm,
            thermal_contact_resistance_k_per_w=t3b.thermal_contact_resistance_k_per_w,
            thermal_flow_shadowing_factor=t3b.thermal_flow_shadowing_factor,
            thermal_airflow_axis=t3b.thermal_airflow_axis,
            thermal_reference_soc=t3b.thermal_reference_soc,
            evaluation_mode="analytic_surrogate",
        )

    fast_charge = get_problem("battery_fast_charge_dfn_anchor_opt")
    with pytest.raises(ValueError, match="Unsupported battery evaluation_mode"):
        type(fast_charge)(
            metadata=fast_charge.metadata,
            statement_markdown=fast_charge.statement_markdown,
            resource_bundle=fast_charge.resource_bundle,
            parameter_set=fast_charge.parameter_set,
            initial_soc_fraction=fast_charge.initial_soc_fraction,
            charge_c_rate=fast_charge.charge_c_rate,
            target_soc_start=fast_charge.target_soc_start,
            target_soc_end=fast_charge.target_soc_end,
            max_voltage_v=fast_charge.max_voltage_v,
            cv_cutoff_denominator=fast_charge.cv_cutoff_denominator,
            maximum_temperature_c=fast_charge.maximum_temperature_c,
            maximum_plating_mol_m3=fast_charge.maximum_plating_mol_m3,
            minimum_energy_density_wh_per_l=fast_charge.minimum_energy_density_wh_per_l,
            ambient_temperature_c=fast_charge.ambient_temperature_c,
            heat_transfer_coefficient_w_per_m2k=fast_charge.heat_transfer_coefficient_w_per_m2k,
            packaging_efficiency=fast_charge.packaging_efficiency,
            rest_before_charge_min=fast_charge.rest_before_charge_min,
            rest_after_charge_min=fast_charge.rest_after_charge_min,
            mesh_points=fast_charge.mesh_points,
            failure_charge_time_min=fast_charge.failure_charge_time_min,
            evaluation_mode="analytic_surrogate",
        )


def test_finite_cylinder_distance_reports_axial_end_gap() -> None:
    first = FiniteCylinder(
        center_mm=(0.0, 0.0, 0.0),
        axis_unit_vector=(0.0, 0.0, 1.0),
        radius_mm=9.0,
        half_length_mm=32.5,
    )
    second = FiniteCylinder(
        center_mm=(0.0, 0.0, 67.0),
        axis_unit_vector=(0.0, 0.0, 1.0),
        radius_mm=9.0,
        half_length_mm=32.5,
    )

    summary = min_distance_between_cylinders(first, second)

    assert summary.classification == "axial"
    assert summary.gap_axial_mm == pytest.approx(2.0)
    assert summary.clearance_true_mm == pytest.approx(2.0)


def test_t4_thermal_contact_model_recognizes_axial_neighbors(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_18650_t4_thermal_hybrid_opt")
    assert isinstance(problem, Battery18650T4ThermalHybridOptimizationProblem)

    cells = (
        SimpleNamespace(x_mm=0.0, y_mm=0.0, z_mm=0.0, angle_x_deg=0.0, angle_y_deg=0.0, angle_z_deg=0.0),
        SimpleNamespace(x_mm=0.0, y_mm=0.0, z_mm=67.0, angle_x_deg=0.0, angle_y_deg=0.0, angle_z_deg=0.0),
    )

    conductances = problem._pairwise_contact_conductances(cells)

    assert (0, 1) in conductances
    assert conductances[(0, 1)] > 0.0


def test_t2_pose_helper_uses_true_axial_clearance(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_18650_t2_pose_surrogate_opt")
    assert isinstance(problem, Battery18650T2PoseSurrogateOptimizationProblem)

    helper = problem._pose_helper
    candidate = numpy.zeros_like(helper.bounds.lb)
    candidate[0] = 2.0
    candidate[1:7] = (50.0, 50.0, 50.0, 0.0, 0.0, 0.0)
    candidate[7:13] = (50.0, 50.0, 117.0, 0.0, 0.0, 0.0)

    evaluation = helper._evaluation_from_variables(candidate)

    assert evaluation.minimum_surface_clearance_mm == pytest.approx(2.0)


def test_t3_metric_payload_marks_empty_stage_topology_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_18650_t3a_topology_surrogate_opt")
    assert isinstance(problem, Battery18650T3ATopologySurrogateOptimizationProblem)

    candidate = problem.generate_initial_solution(seed=3)
    candidate[0] = 3.0
    candidate[1] = 3.0
    for cell_index in range(problem.max_cell_count):
        candidate[2 + (7 * cell_index) + 6] = 0.0

    metrics = problem._metrics_from_variables(candidate)

    assert metrics.failure_reason == "At least one series stage is empty."
    assert metrics.is_feasible is False
