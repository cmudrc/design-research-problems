from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy
import pytest

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems import _battery_adapters as battery_adapters
from design_research_problems.problems import _battery_problem_config as battery_problem_config
from design_research_problems.problems import _battery_tier_problems as battery_tier_problems
from design_research_problems.problems._domains.battery_benchmark import BatteryEvaluationMode
from design_research_problems.problems._domains.battery_cell_model import BatteryBackendConfig, BatteryThermalPriors
from design_research_problems.problems._domains.battery_core import (
    BatteryLayoutSummary,
    BatteryMetricSummary,
    compute_analytic_current_limit,
    simulate_series_parallel_pack,
    validate_rectangular_topology,
)
from design_research_problems.problems._domains.battery_layout import BatteryCellPlacement, BatteryRequirements
from design_research_problems.problems._domains.battery_series_parallel import SeriesParallelBatteryState
from design_research_problems.problems._domains.battery_tier_metrics import BatteryTierMetrics
from design_research_problems.problems._metadata import ProblemKind, ProblemMetadata, ProblemTaxonomy
from design_research_problems.problems._optimization import OptimizationResult
from design_research_problems.problems.optimization import _battery_fast_charge as battery_fast_charge
from design_research_problems.problems.optimization import _battery_grid as battery_grid
from design_research_problems.problems.optimization import _battery_open_ended as battery_open_ended
from design_research_problems.problems.optimization import _battery_oriented_layout as battery_oriented_layout


def _metadata(kind: ProblemKind = ProblemKind.OPTIMIZATION) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id="battery_test_problem",
        title="Battery Test Problem",
        summary="Coverage helper metadata.",
        kind=kind,
        taxonomy=ProblemTaxonomy(
            formulation=None,
            convexity=None,
            design_variable_type=None,
            is_dynamic=False,
            orientation=None,
            feasibility_ratio_hint=None,
            objective_mode=None,
            constraint_nature=None,
            bounds_summary=None,
            tags=(),
        ),
        citations=(),
        assets=(),
        capabilities=(),
        study_suitability=(),
        implementation="tests:BatteryTestProblem",
    )


def _manifest(parameters: dict[str, object]) -> ProblemManifest:
    return ProblemManifest(
        metadata=_metadata(),
        resource_dir="tests",
        statement_markdown="# Battery Test",
        parameters=parameters,
    )


def _requirements() -> BatteryRequirements:
    return BatteryRequirements(
        target_voltage_v=7.4,
        minimum_capacity_ah=5.0,
        minimum_current_a=20.0,
        max_width_mm=120.0,
        max_depth_mm=120.0,
        max_height_mm=120.0,
        voltage_tolerance_v=0.2,
    )


def _placements() -> tuple[BatteryCellPlacement, ...]:
    return (
        BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=0, y=0, z=0),
        BatteryCellPlacement(cell_id=1, stage_index=1, branch_index=0, x=0, y=0, z=4),
    )


def _thermal_priors() -> BatteryThermalPriors:
    return BatteryThermalPriors(
        soc_grid=(0.0, 1.0),
        total_resistance_ohm=(0.05, 0.05),
        cell_to_jig_conductance_w_per_k=1.0,
        jig_to_ambient_conductance_w_per_k=0.8,
        cell_thermal_mass_j_per_k=25.0,
        jig_thermal_mass_j_per_k=10.0,
        reference_ambient_temperature_c=25.0,
        source="test_stub",
    )


def _summary(**overrides: object) -> BatteryMetricSummary:
    values: dict[str, object] = {
        "cell_count": 2,
        "num_cells_width": 1,
        "num_cells_depth": 1,
        "num_cells_height": 2,
        "design_width": 18.0,
        "design_depth": 18.0,
        "design_height": 69.0,
        "design_cost": 4.0,
        "surface_area": 1000.0,
        "design_volume": 1200.0,
        "moment_of_inertia_xx": 1.0,
        "moment_of_inertia_yy": 1.0,
        "moment_of_inertia_zz": 1.0,
        "design_voltage": 7.4,
        "design_capacity": 5.0,
        "analytic_current_limit": 20.0,
    }
    values.update(overrides)
    return BatteryMetricSummary(**values)


def _fake_circuit_evaluation(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "connection_count": 3,
        "pack_nominal_voltage": 7.4,
        "delivered_capacity_ah": 4.5,
        "is_feasible": True,
        "failure_reason": None,
        "cell_model_source": "test_stub",
        "cell_count": 2,
        "surface_area": 1000.0,
        "design_cost": 4.0,
        "design_volume": 1200.0,
        "topology_kind": "series_parallel",
        "max_cell_current_a": 10.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_battery_problem_config_helpers_cover_defaults_and_backend_parsing() -> None:
    manifest = _manifest(
        {
            "target_voltage_v": "14.8",
            "minimum_capacity_ah": 9,
            "minimum_current_a": "55",
            "max_width_mm": "450",
            "max_depth_mm": 425,
            "max_height_mm": "225",
            "voltage_tolerance_v": "0.15",
            "battery_backend": {
                "cell_model_mode": "pybamm_spm",
                "thermal_mode": "isothermal",
                "ambient_temp_c": 30.0,
            },
        }
    )

    assert battery_problem_config._coerce_int(None, 3) == 3
    assert battery_problem_config._coerce_int("4", 0) == 4
    assert battery_problem_config._coerce_float(None, 1.5) == pytest.approx(1.5)
    assert battery_problem_config._coerce_float("2.5", 0.0) == pytest.approx(2.5)

    defaults = battery_problem_config.default_battery_requirements()
    assert defaults.target_voltage_v == pytest.approx(14.8)
    assert battery_problem_config.resolve_battery_requirements(None) == defaults
    custom = _requirements()
    assert battery_problem_config.resolve_battery_requirements(custom) is custom

    parsed = battery_problem_config.parse_battery_requirements(manifest)
    assert parsed.target_voltage_v == pytest.approx(14.8)
    assert parsed.minimum_capacity_ah == pytest.approx(9.0)
    assert parsed.minimum_current_a == pytest.approx(55.0)
    assert parsed.max_width_mm == pytest.approx(450.0)
    assert parsed.max_depth_mm == pytest.approx(425.0)
    assert parsed.max_height_mm == pytest.approx(225.0)
    assert parsed.voltage_tolerance_v == pytest.approx(0.15)

    backend = battery_problem_config.parse_battery_backend_config(manifest)
    assert backend is not None
    assert backend.cell_model_mode == "pybamm_spm"
    assert backend.thermal_mode == "isothermal"
    assert backend.ambient_temp_c == pytest.approx(30.0)
    assert battery_problem_config.parse_battery_backend_config(_manifest({})) is None


def test_battery_core_helpers_cover_validation_and_series_parallel_simulation(monkeypatch: pytest.MonkeyPatch) -> None:
    assert validate_rectangular_topology(SimpleNamespace(series_count=0, parallel_count=1, cells=())) == (
        "Series count must be at least 1."
    )
    assert validate_rectangular_topology(SimpleNamespace(series_count=1, parallel_count=0, cells=())) == (
        "Parallel count must be at least 1."
    )
    assert validate_rectangular_topology(SimpleNamespace(series_count=2, parallel_count=2, cells=_placements())) == (
        "Cell count does not match the required SxP rectangle."
    )
    assert (
        validate_rectangular_topology(
            SimpleNamespace(
                series_count=1,
                parallel_count=2,
                cells=(
                    BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=0, y=0, z=0),
                    BatteryCellPlacement(cell_id=1, stage_index=0, branch_index=0, x=1, y=0, z=0),
                ),
            )
        )
        == "Cells do not fill the complete SxP slot rectangle."
    )

    valid_state = SimpleNamespace(
        series_count=2,
        parallel_count=1,
        cells=(
            BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=0, y=0, z=0),
            BatteryCellPlacement(cell_id=1, stage_index=1, branch_index=0, x=1, y=0, z=0),
        ),
    )
    assert validate_rectangular_topology(valid_state) is None

    empty_layout = BatteryLayoutSummary(
        cell_count=0,
        num_cells_width=0,
        num_cells_depth=0,
        num_cells_height=0,
        design_width=0.0,
        design_depth=0.0,
        design_height=0.0,
        design_cost=0.0,
        surface_area=0.0,
        design_volume=0.0,
        moment_of_inertia_xx=0.0,
        moment_of_inertia_yy=0.0,
        moment_of_inertia_zz=0.0,
    )
    assert compute_analytic_current_limit(empty_layout, parallel_count=1) == pytest.approx(0.0)

    captured: dict[str, Any] = {}
    from design_research_problems.problems._domains import battery_circuit

    def _fake_evaluate_battery_circuit(**kwargs: object) -> SimpleNamespace:
        captured["state"] = kwargs["state"]
        return SimpleNamespace(
            pack_terminal_voltage_end=None,
            delivered_capacity_ah=None,
            is_feasible=False,
        )

    monkeypatch.setattr(battery_circuit, "evaluate_battery_circuit", _fake_evaluate_battery_circuit)
    terminal_v, capacity_ah, feasible = simulate_series_parallel_pack(object(), _requirements(), 2, 2)
    assert terminal_v == pytest.approx(0.0)
    assert capacity_ah == pytest.approx(0.0)
    assert feasible is False
    state = captured["state"]
    assert len(state.cells) == 4
    assert len(state.connections) == 5
    assert state.pack_negative_terminal_id == 0
    assert state.pack_positive_terminal_id == 5


def test_battery_adapter_helpers_cover_thermal_and_failure_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    config = battery_adapters.BatteryThermalPromotionConfig(thermal_model=battery_adapters.THERMAL_MODEL_LUMPED)
    payload = config.as_dict()
    assert payload["thermal_model"] == battery_adapters.THERMAL_MODEL_LUMPED
    assert (
        battery_adapters.coerce_battery_thermal_model(" Multi_Node_2Node ") == battery_adapters.THERMAL_MODEL_MULTI_NODE
    )
    assert battery_adapters.coerce_battery_thermal_airflow_axis(" Z ") == "z"
    with pytest.raises(ValueError, match="battery thermal_model"):
        battery_adapters.coerce_battery_thermal_model("bad")
    with pytest.raises(ValueError, match="battery thermal_airflow_axis"):
        battery_adapters.coerce_battery_thermal_airflow_axis("q")

    backend_fields = battery_adapters.resolved_backend_field_names(
        BatteryBackendConfig(cell_model_mode="pybamm_spm", thermal_mode="isothermal", ambient_temp_c=30.0)
    )
    assert backend_fields == ("ambient_temp_c", "cell_model_mode", "thermal_mode")

    promoted = battery_adapters.promoted_hybrid_defaults_payload(config, cell_pose_model="upright")
    assert promoted["cell_pose_model"] == "upright"
    assert (
        battery_adapters.infer_parallel_equivalent_from_cell_current(load_current_a=10.0, max_cell_current_a=None)
        == 1.0
    )
    assert (
        battery_adapters.infer_parallel_equivalent_from_cell_current(load_current_a=10.0, max_cell_current_a=50.0)
        == 1.0
    )
    assert (
        battery_adapters.infer_parallel_equivalent_from_cell_current(load_current_a=10.0, max_cell_current_a=2.0) == 5.0
    )

    poses = battery_adapters.build_upright_thermal_poses_from_grid_cells(_placements())
    assert poses[0].x_mm == pytest.approx(14.0)
    assert battery_adapters.minimum_clearance_mm_from_grid_cells(_placements()) >= 0.0
    assert battery_adapters.minimum_clearance_mm_from_poses((poses[0],)) == pytest.approx(2.0)

    zero_result = battery_adapters.solve_battery_thermal_network(
        (),
        cell_count=0,
        parallel_equivalent=1.0,
        load_current_a=10.0,
        thermal_priors=_thermal_priors(),
        config=config,
        total_surface_area_mm2=0.0,
    )
    assert zero_result.max_core_temperature_c == pytest.approx(config.ambient_temperature_c)

    lumped_result = battery_adapters.solve_battery_thermal_network(
        poses,
        cell_count=2,
        parallel_equivalent=1.0,
        load_current_a=10.0,
        thermal_priors=_thermal_priors(),
        config=config,
        total_surface_area_mm2=1000.0,
    )
    assert lumped_result.max_core_temperature_c > config.ambient_temperature_c

    multi_config = battery_adapters.BatteryThermalPromotionConfig(
        thermal_model=battery_adapters.THERMAL_MODEL_MULTI_NODE,
        thermal_airflow_axis="z",
    )
    multi_result = battery_adapters.solve_battery_thermal_network(
        poses,
        cell_count=2,
        parallel_equivalent=1.0,
        load_current_a=10.0,
        thermal_priors=_thermal_priors(),
        config=multi_config,
        total_surface_area_mm2=1000.0,
    )
    assert multi_result.max_core_temperature_c >= multi_result.max_surface_temperature_c
    assert (
        battery_adapters._airflow_shadow_factors((), thermal_airflow_axis="x", thermal_flow_shadowing_factor=0.5) == []
    )
    assert (
        len(
            battery_adapters._airflow_shadow_factors(
                poses,
                thermal_airflow_axis="z",
                thermal_flow_shadowing_factor=0.5,
            )
        )
        == 2
    )
    adjacent_poses = (
        battery_adapters.BatteryThermalPose(0.0, 0.0, 0.0),
        battery_adapters.BatteryThermalPose(0.0, 0.0, 66.0),
    )
    conductances = battery_adapters._pairwise_contact_conductances(
        adjacent_poses,
        thermal_neighbor_clearance_mm=100.0,
        thermal_contact_decay_mm=2.0,
        thermal_contact_resistance_k_per_w=2.5,
    )
    assert conductances[(0, 1)] > 0.0

    rectangular_cells = (
        BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=0, y=0, z=0),
        BatteryCellPlacement(cell_id=1, stage_index=1, branch_index=0, x=1, y=0, z=0),
    )
    state = SeriesParallelBatteryState(series_count=2, parallel_count=1, cells=rectangular_cells)
    summary = _summary()
    circuit_eval = _fake_circuit_evaluation()
    monkeypatch.setattr(battery_adapters, "compute_metric_summary", lambda *args, **kwargs: summary)
    monkeypatch.setattr(battery_adapters, "evaluate_battery_circuit", lambda **kwargs: circuit_eval)
    monkeypatch.setattr(battery_adapters, "load_battery_thermal_priors", lambda config=None: _thermal_priors())
    monkeypatch.setattr(
        battery_adapters,
        "solve_battery_thermal_network",
        lambda *args, **kwargs: battery_adapters.BatteryThermalNetworkResult(42.0, 39.0, 30.0, 3.0),
    )

    analytic = battery_adapters.evaluate_rectangular_battery_state(
        state,
        requirements=_requirements(),
        backend_config=None,
        evaluation_mode=BatteryEvaluationMode.ANALYTIC_SURROGATE,
        load_current_a=10.0,
        thermal_config=config,
    )
    assert analytic.electrical_path == "native"
    assert analytic.thermal_path == "native"
    assert analytic.metrics.is_feasible is True

    explicit = battery_adapters.evaluate_rectangular_battery_state(
        state,
        requirements=_requirements(),
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm"),
        evaluation_mode=BatteryEvaluationMode.EXPLICIT_CIRCUIT,
        load_current_a=10.0,
        thermal_config=config,
    )
    assert explicit.electrical_path == "promoted"
    assert explicit.thermal_path == "native"
    assert explicit.honored_backend_fields == ("ambient_temp_c", "cell_model_mode", "thermal_mode")

    hybrid = battery_adapters.evaluate_rectangular_battery_state(
        state,
        requirements=_requirements(),
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm"),
        evaluation_mode=BatteryEvaluationMode.HYBRID_THERMAL,
        load_current_a=10.0,
        thermal_config=config,
    )
    assert hybrid.thermal_path == "promoted"
    assert hybrid.assumed_defaults is not None
    assert hybrid.assumed_defaults["cell_pose_model"] == "upright_grid_cylinders"
    assert hybrid.thermal_prior_source == "test_stub"

    netlist_state = SimpleNamespace(cells=_placements())
    with pytest.raises(ValueError, match="analytic_surrogate is intentionally unsupported"):
        battery_adapters.evaluate_explicit_netlist_state(
            netlist_state,
            requirements=_requirements(),
            backend_config=None,
            evaluation_mode=BatteryEvaluationMode.ANALYTIC_SURROGATE,
            load_current_a=10.0,
            thermal_config=config,
        )

    monkeypatch.setattr(
        battery_adapters,
        "evaluate_battery_circuit",
        lambda **kwargs: _fake_circuit_evaluation(topology_kind="mesh", max_cell_current_a=None),
    )
    explicit_netlist = battery_adapters.evaluate_explicit_netlist_state(
        netlist_state,
        requirements=_requirements(),
        backend_config=None,
        evaluation_mode=BatteryEvaluationMode.EXPLICIT_CIRCUIT,
        load_current_a=10.0,
        thermal_config=config,
    )
    assert explicit_netlist.thermal_path == "native"
    assert explicit_netlist.adaptation_notes == ()

    hybrid_netlist = battery_adapters.evaluate_explicit_netlist_state(
        netlist_state,
        requirements=_requirements(),
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm"),
        evaluation_mode=BatteryEvaluationMode.HYBRID_THERMAL,
        load_current_a=10.0,
        thermal_config=config,
    )
    assert len(hybrid_netlist.adaptation_notes) == 2
    assert hybrid_netlist.assumed_defaults is not None

    baseline_summary = _summary()
    valid_rectangular = SeriesParallelBatteryState(series_count=2, parallel_count=1, cells=rectangular_cells)
    assert (
        battery_adapters._analytic_rectangular_failure_reason(valid_rectangular, _requirements(), baseline_summary)
        is None
    )
    assert (
        battery_adapters._analytic_rectangular_failure_reason(
            valid_rectangular,
            _requirements(),
            _summary(analytic_current_limit=1.0),
        )
        == "Analytic current limit is below the required continuous current."
    )
    duplicate_state = SeriesParallelBatteryState(
        series_count=2,
        parallel_count=1,
        cells=(
            BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=0, y=0, z=0),
            BatteryCellPlacement(cell_id=1, stage_index=1, branch_index=0, x=0, y=0, z=0),
        ),
    )
    assert (
        battery_adapters._analytic_rectangular_failure_reason(duplicate_state, _requirements(), baseline_summary)
        == "Duplicate physical coordinates are not allowed."
    )
    negative_state = SeriesParallelBatteryState(
        series_count=2,
        parallel_count=1,
        cells=(
            BatteryCellPlacement(cell_id=0, stage_index=0, branch_index=0, x=-1, y=0, z=0),
            BatteryCellPlacement(cell_id=1, stage_index=1, branch_index=0, x=1, y=0, z=0),
        ),
    )
    assert (
        battery_adapters._analytic_rectangular_failure_reason(negative_state, _requirements(), baseline_summary)
        == "Cell coordinates must be non-negative."
    )
    assert (
        battery_adapters._analytic_rectangular_failure_reason(
            valid_rectangular,
            _requirements(),
            _summary(design_width=999.0),
        )
        == "Pack width exceeds the maximum allowed width."
    )
    assert (
        battery_adapters._analytic_rectangular_failure_reason(
            valid_rectangular,
            _requirements(),
            _summary(design_capacity=1.0),
        )
        == "Pack capacity is below the minimum required capacity."
    )


def test_battery_grid_helpers_cover_manifest_caching_and_search_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        battery_grid.BatteryGridSizingProblem,
        "resource_bundle_from_manifest",
        classmethod(lambda cls, manifest: None),
    )
    manifest = _manifest(
        {
            "target_voltage_v": 7.4,
            "minimum_capacity_ah": 5.0,
            "minimum_current_a": 20.0,
            "max_width_mm": 120.0,
            "max_depth_mm": 120.0,
            "max_height_mm": 120.0,
            "voltage_tolerance_v": 0.2,
            "battery_backend": {"cell_model_mode": "pybamm_spm"},
        }
    )
    from_manifest = battery_grid.BatteryGridSizingProblem.from_manifest(manifest)
    assert from_manifest.requirements.target_voltage_v == pytest.approx(7.4)
    assert from_manifest.backend_config is not None
    assert from_manifest.backend_config.cell_model_mode == "pybamm_spm"

    problem = battery_grid.BatteryGridSizingProblem(metadata=_metadata(), requirements=_requirements())
    monkeypatch.setattr(problem, "_baseline_initial_solution", lambda: numpy.array([2.0, 2.0], dtype=float))
    monkeypatch.setattr(problem, "_max_parallel_count", lambda: 4)
    assert numpy.array_equal(problem.generate_initial_solution(seed=None), numpy.array([2.0, 2.0], dtype=float))
    assert problem.generate_initial_solution(seed=1)[0] == pytest.approx(2.0)

    monkeypatch.setattr(problem, "_max_parallel_count", lambda: 1)
    monkeypatch.setattr(problem, "_max_series_count", lambda: 5)
    series_seeded = problem.generate_initial_solution(seed=2)
    assert series_seeded[1] == pytest.approx(1.0)

    monkeypatch.setattr(problem, "_max_series_count", lambda: 1)
    assert numpy.array_equal(problem.generate_initial_solution(seed=3), numpy.array([2.0, 2.0], dtype=float))

    with pytest.raises(ValueError, match="Expected a 2-variable design vector"):
        problem._normalize_vector(numpy.zeros(3, dtype=float))
    assert tuple(problem._normalize_vector(numpy.array([999.0, -1.0], dtype=float))) == (
        problem.bounds.ub[0],
        problem.bounds.lb[1],
    )

    evaluation = SimpleNamespace(
        design_cost=12.5,
        design_voltage=7.4,
        design_capacity=5.0,
        analytic_current_limit=20.0,
        cell_count=2,
        design_width=18.0,
        design_depth=18.0,
        design_height=69.0,
        is_feasible=True,
    )
    monkeypatch.setattr(problem, "_evaluation_from_variables", lambda variables: evaluation)
    assert problem.objective_components(numpy.array([2.0, 2.0], dtype=float))["cost_usd"] == pytest.approx(12.5)
    assert problem._width_margin(numpy.array([2.0, 2.0], dtype=float)) == pytest.approx(
        problem.requirements.max_width_mm - 18.0
    )
    assert problem._backend_feasibility_margin(numpy.array([2.0, 2.0], dtype=float)) == pytest.approx(1.0)

    calls: list[tuple[int, int]] = []

    def _fake_evaluate_series_parallel_state(state: object, requirements: object, evaluator: object) -> SimpleNamespace:
        del requirements, evaluator
        calls.append((state.series_count, state.parallel_count))
        return evaluation

    monkeypatch.setattr(
        battery_grid,
        "build_canonical_series_parallel_state",
        lambda series_count, parallel_count: SimpleNamespace(series_count=series_count, parallel_count=parallel_count),
    )
    monkeypatch.setattr(battery_grid, "evaluate_series_parallel_state", _fake_evaluate_series_parallel_state)
    first = problem._evaluation_for_counts(2, 3)
    second = problem._evaluation_for_counts(2, 3)
    assert first is second
    assert calls == [(2, 3)]

    scores = {
        (1, 1): 10.0,
        (1, 2): 8.0,
        (2, 1): 6.0,
        (2, 2): 4.0,
    }
    monkeypatch.setattr(problem, "_max_series_count", lambda: 2)
    monkeypatch.setattr(problem, "_max_parallel_count", lambda: 2)
    monkeypatch.setattr(problem, "generate_initial_solution", lambda seed=None: numpy.array([2.0, 2.0], dtype=float))
    monkeypatch.setattr(problem, "objective", lambda candidate: scores[tuple(int(value) for value in candidate)])
    monkeypatch.setattr(
        problem,
        "max_constraint_violation",
        lambda candidate: 0.0 if tuple(int(value) for value in candidate) == (2, 2) else 1.0,
    )
    result = problem.solve(maxiter=4)
    assert result.success is True
    assert "feasible baseline" in result.message

    monkeypatch.setattr(problem, "max_constraint_violation", lambda candidate: 1.5)
    result = problem.solve(initial_solution=numpy.array([2.0, 2.0], dtype=float), maxiter=2)
    assert result.success is False
    assert "best-effort design" in result.message
    with pytest.raises(ValueError, match="Expected a 2-variable design vector"):
        problem.solve(initial_solution=numpy.zeros(3, dtype=float))


def test_fast_charge_helper_functions_and_mocked_simulation_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = object()
    monkeypatch.setattr(battery_fast_charge, "import_optional_module", lambda *args, **kwargs: sentinel)
    assert battery_fast_charge.import_pybamm_fast_charge() is sentinel

    failure = battery_fast_charge._failure_metrics(
        failure_reason="bad",
        failure_charge_time_min=99.0,
        maximum_temperature_c=40.0,
        maximum_plating_mol_m3=0.01,
    )
    assert failure.success is False
    assert failure.max_temperature_c == pytest.approx(100.0)

    solution = {
        "present": SimpleNamespace(entries=numpy.array([1.0, 3.0], dtype=float)),
        "also_present": SimpleNamespace(entries=numpy.array([2.0, 4.0], dtype=float)),
    }
    assert battery_fast_charge._safe_solution_max(solution, ("missing", "present"), default=0.0) == pytest.approx(3.0)
    assert battery_fast_charge._safe_solution_min(solution, ("missing", "also_present"), default=0.0) == pytest.approx(
        2.0
    )
    assert battery_fast_charge._safe_solution_max(solution, ("missing",), default=7.0) == pytest.approx(7.0)
    assert battery_fast_charge._safe_parameter_value(
        {"Cell volume [m3]": 2.0e-5}, "Cell volume [m3]", 0.0
    ) == pytest.approx(2.0e-5)

    class _ExplodingParameters(dict):
        def __getitem__(self, key: str) -> float:
            raise RuntimeError("missing")

    assert battery_fast_charge._safe_parameter_value(_ExplodingParameters(), "Cell volume [m3]", 1.0) == pytest.approx(
        1.0
    )

    class FakeParameters(dict[str, float]):
        def __init__(self, parameter_set: str) -> None:
            super().__init__()
            self["parameter_set"] = parameter_set

        def update(self, values: dict[str, float], check_already_exists: bool = False) -> None:
            del check_already_exists
            super().update(values)

        def set_initial_stoichiometries(self, value: float) -> None:
            self["initial_soc"] = value

    class FakeSimulation:
        def __init__(
            self, model: object, parameter_values: object, experiment: object, var_pts: dict[str, int]
        ) -> None:
            self.model = model
            self.parameter_values = parameter_values
            self.experiment = experiment
            self.var_pts = var_pts

        def solve(self, solver: object) -> dict[str, SimpleNamespace]:
            del solver
            return {
                "Current [A]": SimpleNamespace(entries=numpy.array([-1.0, -1.0, -1.0], dtype=float)),
                "Time [s]": SimpleNamespace(entries=numpy.array([0.0, 1800.0, 3600.0], dtype=float)),
                "Terminal voltage [V]": SimpleNamespace(entries=numpy.array([3.0, 3.6, 4.2], dtype=float)),
                "Negative lithium plating concentration [mol.m-3]": SimpleNamespace(
                    entries=numpy.array([0.0, 0.2, 0.3], dtype=float)
                ),
                "X-averaged cell temperature [K]": SimpleNamespace(
                    entries=numpy.array([298.15, 301.15, 305.15], dtype=float)
                ),
            }

    class FakePybamm:
        class lithium_ion:
            @staticmethod
            def DFN(options: dict[str, str]) -> dict[str, str]:
                return options

        ParameterValues = FakeParameters

        @staticmethod
        def Experiment(steps: list[str]) -> list[str]:
            return steps

        Simulation = FakeSimulation

        @staticmethod
        def IDAKLUSolver() -> object:
            raise RuntimeError("idaklu unavailable")

        @staticmethod
        def CasadiSolver(**kwargs: object) -> dict[str, object]:
            return dict(kwargs)

    monkeypatch.setattr(battery_fast_charge, "import_pybamm_fast_charge", lambda: FakePybamm())
    metrics = battery_fast_charge.evaluate_fast_charge_design(
        {"Negative electrode thickness [m]": 1.0e-4},
        target_soc_start=0.1,
        target_soc_end=0.8,
    )
    assert metrics.success is True
    assert metrics.charge_time_min == pytest.approx(30.0)
    assert metrics.max_plating_mol_m3 == pytest.approx(0.3)
    assert metrics.max_temperature_c == pytest.approx(32.0)
    assert metrics.energy_density_wh_per_l > 0.0

    class FailingSimulation(FakeSimulation):
        def solve(self, solver: object) -> dict[str, SimpleNamespace]:
            del solver
            raise RuntimeError("solver exploded")

    class FailingPybamm(FakePybamm):
        Simulation = FailingSimulation

    monkeypatch.setattr(battery_fast_charge, "import_pybamm_fast_charge", lambda: FailingPybamm())
    failed = battery_fast_charge.evaluate_fast_charge_design({"Negative electrode thickness [m]": 1.0e-4})
    assert failed.success is False
    assert failed.failure_reason == "solver exploded"


def test_oriented_layout_helpers_cover_manifest_objective_and_solve_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        battery_oriented_layout.BatteryOrientedLayoutProblem,
        "resource_bundle_from_manifest",
        classmethod(lambda cls, manifest: None),
    )
    manifest = _manifest(
        {
            "target_voltage_v": 7.4,
            "minimum_capacity_ah": 5.0,
            "minimum_current_a": 20.0,
            "max_width_mm": 120.0,
            "max_depth_mm": 120.0,
            "max_height_mm": 120.0,
            "voltage_tolerance_v": 0.2,
            "max_cell_count": 3,
            "minimum_spacing_mm": 2.5,
        }
    )
    problem = battery_oriented_layout.BatteryOrientedLayoutProblem.from_manifest(manifest)
    candidate = problem.generate_initial_solution(seed=3)
    evaluation = battery_oriented_layout.OrientedBatteryEvaluation(
        cell_count=2,
        series_count=2,
        parallel_equivalent=1.0,
        design_width_mm=18.0,
        design_depth_mm=20.0,
        design_height_mm=70.0,
        surface_area_mm2=1000.0,
        design_volume_mm3=1500.0,
        design_cost_usd=4.0,
        minimum_surface_clearance_mm=3.5,
        design_voltage_v=7.4,
        design_capacity_ah=5.0,
        current_limit_a=20.0,
        max_temperature_c=36.0,
        cells=(
            battery_oriented_layout.OrientedBatteryCellPlacement(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
            battery_oriented_layout.OrientedBatteryCellPlacement(1, 18.0, 0.0, 0.0, 0.0, 0.0, 0.0),
        ),
    )
    monkeypatch.setattr(problem, "_evaluation_from_variables", lambda variables: evaluation)
    monkeypatch.setattr(problem, "constraint_violation", lambda variables: 0.0)
    monkeypatch.setattr(problem, "max_constraint_violation", lambda variables: 0.0)

    decoded = problem.decode_candidate(candidate)
    assert decoded.cell_count == 2
    assert decoded.series_count == 2
    assert decoded.parallel_equivalent == pytest.approx(1.0)
    assert problem.objective_components(candidate)["cost_usd"] == pytest.approx(4.0)
    assert problem.objective(candidate) > 0.0
    assert problem._width_margin(candidate) == pytest.approx(problem.requirements.max_width_mm - 18.0)
    assert problem._depth_margin(candidate) == pytest.approx(problem.requirements.max_depth_mm - 20.0)
    assert problem._height_margin(candidate) == pytest.approx(problem.requirements.max_height_mm - 70.0)
    assert problem._voltage_margin(candidate) == pytest.approx(problem.requirements.voltage_tolerance_v)
    assert problem._capacity_margin(candidate) == pytest.approx(0.0)
    assert problem._current_margin(candidate) == pytest.approx(0.0)
    assert problem._clearance_margin(candidate) == pytest.approx(3.5)
    assert problem._minimum_spacing_margin(candidate) == pytest.approx(1.0)
    assert problem._temperature_margin(candidate) == pytest.approx(problem.maximum_temperature_c - 36.0)

    single_eval_result = problem.solve(initial_solution=candidate, maxiter=0)
    assert single_eval_result.success is True
    assert "one oriented battery layout candidate" in single_eval_result.message
    with pytest.raises(ValueError, match="Expected a 19-variable design vector"):
        problem._normalize_vector(numpy.zeros(2, dtype=float))

    search = SimpleNamespace(x=candidate.copy(), nit=2, nfev=3)
    search.x[0] = 2.0
    monkeypatch.setattr(battery_oriented_layout, "bounded_pattern_search", lambda **kwargs: search)
    monkeypatch.setattr(problem, "objective", lambda variables: float(numpy.asarray(variables, dtype=float)[0]))
    monkeypatch.setattr(problem, "max_constraint_violation", lambda variables: 0.0)
    feasible_result = problem.solve(initial_solution=candidate, maxiter=1)
    assert feasible_result.success is True
    assert "found a feasible design" in feasible_result.message
    monkeypatch.setattr(problem, "max_constraint_violation", lambda variables: 2.0)
    best_effort_result = problem.solve(initial_solution=candidate, maxiter=1)
    assert best_effort_result.success is False
    assert "best-effort design" in best_effort_result.message


def test_open_ended_solver_helpers_cover_successful_dispatch_and_public_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        battery_open_ended.BatteryOpenEndedCapacityMaxProblem,
        "_build_canonical_seed_program",
        lambda self: tuple([0] * 32),
    )
    monkeypatch.setattr(
        battery_open_ended.BatteryOpenEndedCapacityMaxProblem,
        "resource_bundle_from_manifest",
        classmethod(lambda cls, manifest: None),
    )
    manifest = _manifest(
        {
            "target_voltage_v": 7.4,
            "minimum_capacity_ah": 5.0,
            "minimum_current_a": 20.0,
            "max_width_mm": 120.0,
            "max_depth_mm": 120.0,
            "max_height_mm": 120.0,
            "voltage_tolerance_v": 0.2,
            "max_cell_count": 24,
            "battery_backend": {"cell_model_mode": "pybamm_spm"},
        }
    )
    from_manifest = battery_open_ended.BatteryOpenEndedCapacityMaxProblem.from_manifest(manifest)
    assert from_manifest.max_cell_count == 24
    assert from_manifest.backend_config is not None
    assert from_manifest.backend_config.cell_model_mode == "pybamm_spm"

    problem = battery_open_ended.BatteryOpenEndedCapacityMaxProblem(metadata=_metadata(), requirements=_requirements())
    candidate = problem.generate_initial_solution()
    evaluation = SimpleNamespace(
        delivered_capacity_ah=6.0,
        pack_terminal_voltage_end=7.35,
        pack_nominal_voltage=7.4,
        cell_count=5,
        connection_count=6,
        design_volume=2500.0,
        is_feasible=True,
    )
    monkeypatch.setattr(problem, "_evaluation_from_variables", lambda variables: evaluation)
    monkeypatch.setattr(problem, "constraint_violation", lambda variables: 0.0)
    monkeypatch.setattr(problem, "max_constraint_violation", lambda variables: 0.0)

    decoded = problem.decode_candidate(candidate)
    assert len(decoded.cells) >= 1
    assert problem.objective_components(candidate)["end_voltage_v"] == pytest.approx(7.35)
    assert problem.objective(candidate) < 0.0

    local_result = problem.solve(initial_solution=candidate, maxiter=0, solver_backend="local")
    assert local_result.success is True
    assert "delivered capacity" in local_result.message

    monkeypatch.setattr(problem, "objective", lambda variables: float(numpy.sum(variables)))
    baseline = candidate.copy()
    baseline[0] += 1.0
    monkeypatch.setattr(problem, "generate_initial_solution", lambda seed=None: baseline.copy())
    incumbent_x, incumbent_fun, incumbent_nfev = problem._solver_incumbent(
        initial_solution=candidate,
        initial_solution_supplied=False,
    )
    assert numpy.array_equal(incumbent_x, candidate)
    assert incumbent_fun == pytest.approx(float(numpy.sum(candidate)))
    assert incumbent_nfev == 2

    monkeypatch.setattr(problem, "_solve_with_pymoo", lambda **kwargs: "pymoo")
    monkeypatch.setattr(problem, "_solve_with_nevergrad", lambda **kwargs: "nevergrad")
    monkeypatch.setattr(problem, "_solve_with_local_search", lambda **kwargs: "local")
    assert (
        problem._solve_with_backend(
            solver_backend="pymoo",
            initial_solution=candidate,
            initial_solution_supplied=True,
            seed=1,
            maxiter=2,
        )
        == "pymoo"
    )
    assert (
        problem._solve_with_backend(
            solver_backend="nevergrad",
            initial_solution=candidate,
            initial_solution_supplied=False,
            seed=2,
            maxiter=3,
        )
        == "nevergrad"
    )
    assert (
        problem._solve_with_backend(
            solver_backend="local",
            initial_solution=candidate,
            initial_solution_supplied=False,
            seed=None,
            maxiter=4,
        )
        == "local"
    )

    module_map = {
        "pymoo.core.problem": SimpleNamespace(ElementwiseProblem=object),
        "pymoo.algorithms.soo.nonconvex.ga": SimpleNamespace(GA=object),
        "pymoo.operators.repair.rounding": SimpleNamespace(RoundingRepair=object),
        "pymoo.optimize": SimpleNamespace(minimize=lambda *args, **kwargs: None),
    }
    monkeypatch.setattr(battery_open_ended, "import_optional_module", lambda name, **kwargs: module_map[name])
    elementwise_problem, ga, rounding_repair, minimize = problem._import_pymoo_namespace()
    assert elementwise_problem is object
    assert ga is object
    assert rounding_repair is object
    assert callable(minimize)

    t3b = battery_open_ended.Battery18650T3BNetlistExplicitOptimizationProblem(
        metadata=_metadata(),
        requirements=_requirements(),
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm"),
    )
    monkeypatch.setattr(
        battery_open_ended.BatteryOpenEndedCapacityMaxProblem,
        "solve",
        lambda self, **kwargs: OptimizationResult(
            x=candidate,
            fun=1.0,
            success=False,
            message="base result",
            nit=2,
            nfev=3,
        ),
    )
    wrapped = t3b.solve(maxiter=1)
    assert wrapped.success is False
    assert "explicit-netlist battery benchmark" in wrapped.message


def test_open_ended_local_search_and_cache_paths_cover_remaining_branches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        battery_open_ended.BatteryOpenEndedCapacityMaxProblem,
        "_build_canonical_seed_program",
        lambda self: tuple([0] * 32),
    )
    problem = battery_open_ended.BatteryOpenEndedCapacityMaxProblem(
        metadata=_metadata(),
        requirements=_requirements(),
    )
    initial = numpy.full(32, 5.0, dtype=float)

    monkeypatch.setattr(problem, "objective", lambda variables: float(numpy.sum(variables)))
    monkeypatch.setattr(problem, "_build_result", lambda **kwargs: kwargs)
    local_search = problem._solve_with_local_search(initial_solution=initial, maxiter=1)
    assert local_search["nit"] == 1
    assert local_search["nfev"] > 1
    assert numpy.sum(local_search["x"]) < numpy.sum(initial)

    evaluation = SimpleNamespace(
        delivered_capacity_ah=6.0,
        pack_terminal_voltage_end=7.3,
        pack_nominal_voltage=7.4,
        cell_count=5,
        connection_count=6,
        design_volume=1800.0,
        is_feasible=True,
    )
    calls: list[object] = []
    monkeypatch.setattr(problem, "_state_from_genes", lambda genes: "decoded-state")
    monkeypatch.setattr(problem, "_evaluate_state", lambda state: calls.append(state) or evaluation)
    first = problem._evaluation_from_variables(initial)
    second = problem._evaluation_from_variables(initial)
    assert first is second
    assert calls == ["decoded-state"]

    monkeypatch.setattr(problem, "_evaluation_from_variables", lambda variables: evaluation)
    assert problem._voltage_margin(initial) == pytest.approx(problem.requirements.voltage_tolerance_v)
    assert problem._capacity_margin(initial) == pytest.approx(1.0)
    assert problem._backend_feasibility_margin(initial) == pytest.approx(1.0)

    direct_problem = battery_open_ended.BatteryOpenEndedCapacityMaxProblem(
        metadata=_metadata(),
        requirements=_requirements(),
    )
    sentinel = object()
    monkeypatch.setattr(battery_open_ended, "evaluate_battery_circuit", lambda **kwargs: sentinel)
    assert direct_problem._evaluate_state(SimpleNamespace()) is sentinel


def test_t2_pose_surrogate_promoted_paths_cover_explicit_and_hybrid_modes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    helper = SimpleNamespace(
        surface_area_mm2=1400.0,
        design_volume_mm3=2600.0,
        minimum_surface_clearance_mm=4.0,
        cells=(battery_adapters.BatteryThermalPose(0.0, 0.0, 0.0),),
    )
    circuit_outcome = battery_adapters.BatteryEvaluationAdapterOutcome(
        metrics=BatteryTierMetrics(
            cell_count=4.0,
            connection_count=5.0,
            cost_usd=8.0,
            design_volume_mm3=1200.0,
            max_temperature_c=33.0,
            voltage_v=7.4,
            capacity_ah=5.0,
            current_limit_a=20.0,
            min_clearance_mm=2.0,
            is_feasible=True,
            failure_reason=None,
        ),
        electrical_path="promoted",
        thermal_path="native",
        honored_backend_fields=("ambient_temp_c", "cell_model_mode"),
        cell_model_source="test_stub",
    )
    monkeypatch.setattr(
        battery_tier_problems, "evaluate_rectangular_battery_state", lambda *args, **kwargs: circuit_outcome
    )
    monkeypatch.setattr(
        battery_tier_problems,
        "load_battery_thermal_priors",
        lambda config=None: _thermal_priors(),
    )
    monkeypatch.setattr(
        battery_tier_problems,
        "solve_battery_thermal_network",
        lambda *args, **kwargs: battery_adapters.BatteryThermalNetworkResult(42.0, 39.0, 31.0, 3.0),
    )

    explicit_problem = battery_tier_problems.Battery18650T2PoseSurrogateOptimizationProblem(
        metadata=_metadata(),
        requirements=_requirements(),
        max_cell_count=4,
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm", ambient_temp_c=30.0),
        evaluation_mode=BatteryEvaluationMode.EXPLICIT_CIRCUIT.value,
    )
    monkeypatch.setattr(explicit_problem, "_pose_helper_evaluation", lambda **kwargs: helper)
    candidate = explicit_problem.generate_initial_solution(seed=4)
    explicit_outcome = explicit_problem._outcome_from_variables(candidate)
    assert explicit_problem._thermal_config().ambient_temperature_c == pytest.approx(
        explicit_problem.ambient_temperature_c
    )
    assert explicit_outcome.electrical_path == "promoted"
    assert explicit_outcome.thermal_path == "native"
    assert explicit_outcome.metrics.connection_count == pytest.approx(5.0)
    assert explicit_problem.evaluation_provenance(candidate).cell_model_source == "test_stub"

    hybrid_problem = battery_tier_problems.Battery18650T2PoseSurrogateOptimizationProblem(
        metadata=_metadata(),
        requirements=_requirements(),
        max_cell_count=4,
        backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm", ambient_temp_c=30.0),
        evaluation_mode=BatteryEvaluationMode.HYBRID_THERMAL.value,
    )
    monkeypatch.setattr(hybrid_problem, "_pose_helper_evaluation", lambda **kwargs: helper)
    hybrid_outcome = hybrid_problem._outcome_from_variables(candidate)
    assert hybrid_outcome.thermal_path == "promoted"
    assert hybrid_outcome.thermal_prior_source == "test_stub"
    assert hybrid_outcome.assumed_defaults is not None
    assert len(hybrid_outcome.adaptation_notes) == 2
    assert hybrid_problem._outcome_from_variables(candidate) is hybrid_outcome
