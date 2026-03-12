from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from design_research_problems import MissingOptionalDependencyError
from design_research_problems.problems.grammar._battery_cell_model import (
    BatteryBackendConfig,
    BatteryCellModel,
    BatteryParameterization,
    BatteryThermalPriors,
    battery_backend_config_from_mapping,
)
from design_research_problems.problems.grammar._battery_circuit import (
    BatteryCellInstance,
    BatteryCircuitState,
    BatteryConnection,
    analyze_battery_topology,
    evaluate_battery_circuit,
)
from design_research_problems.problems.grammar._battery_layout import (
    DEFAULT_INTERCONNECT_RESISTANCE_OHM,
    BatteryRequirements,
)


def _static_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
    )


def _relaxed_requirements(
    *,
    target_voltage_v: float,
    minimum_capacity_ah: float,
    minimum_current_a: float,
) -> BatteryRequirements:
    return BatteryRequirements(
        target_voltage_v=target_voltage_v,
        minimum_capacity_ah=minimum_capacity_ah,
        minimum_current_a=minimum_current_a,
        max_width_mm=500.0,
        max_depth_mm=500.0,
        max_height_mm=250.0,
        voltage_tolerance_v=0.1,
    )


def _single_cell_state() -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(
                cell_id=0,
                positive_terminal_id=1,
                negative_terminal_id=0,
                x=0,
                y=0,
                z=0,
            ),
        ),
        connections=(),
        pack_positive_terminal_id=1,
        pack_negative_terminal_id=0,
    )


def _two_cell_series_state() -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(
                cell_id=0,
                positive_terminal_id=1,
                negative_terminal_id=0,
                x=0,
                y=0,
                z=0,
            ),
            BatteryCellInstance(
                cell_id=1,
                positive_terminal_id=3,
                negative_terminal_id=2,
                x=1,
                y=0,
                z=0,
            ),
        ),
        connections=(
            BatteryConnection(
                connection_id=0,
                from_terminal_id=1,
                to_terminal_id=2,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
        ),
        pack_positive_terminal_id=3,
        pack_negative_terminal_id=0,
    )


def _two_cell_parallel_state() -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(
                cell_id=0,
                positive_terminal_id=1,
                negative_terminal_id=0,
                x=0,
                y=0,
                z=0,
            ),
            BatteryCellInstance(
                cell_id=1,
                positive_terminal_id=3,
                negative_terminal_id=2,
                x=0,
                y=1,
                z=0,
            ),
        ),
        connections=(
            BatteryConnection(
                connection_id=0,
                from_terminal_id=0,
                to_terminal_id=2,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
            BatteryConnection(
                connection_id=1,
                from_terminal_id=1,
                to_terminal_id=3,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
        ),
        pack_positive_terminal_id=1,
        pack_negative_terminal_id=0,
    )


def _two_cell_parallel_state_with_connection_resistance(resistance_ohm: float) -> BatteryCircuitState:
    baseline = _two_cell_parallel_state()
    return BatteryCircuitState(
        cells=baseline.cells,
        connections=tuple(
            replace(connection, resistance_ohm=resistance_ohm, ideal=False) for connection in baseline.connections
        ),
        pack_positive_terminal_id=baseline.pack_positive_terminal_id,
        pack_negative_terminal_id=baseline.pack_negative_terminal_id,
    )


def _general_cross_link_state() -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(
                cell_id=0,
                positive_terminal_id=1,
                negative_terminal_id=0,
                x=0,
                y=0,
                z=0,
            ),
            BatteryCellInstance(
                cell_id=1,
                positive_terminal_id=3,
                negative_terminal_id=2,
                x=1,
                y=0,
                z=0,
            ),
            BatteryCellInstance(
                cell_id=2,
                positive_terminal_id=5,
                negative_terminal_id=4,
                x=0,
                y=1,
                z=0,
            ),
        ),
        connections=(
            BatteryConnection(
                connection_id=0,
                from_terminal_id=1,
                to_terminal_id=2,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
            BatteryConnection(
                connection_id=1,
                from_terminal_id=0,
                to_terminal_id=4,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
            BatteryConnection(
                connection_id=2,
                from_terminal_id=3,
                to_terminal_id=5,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                ideal=True,
            ),
        ),
        pack_positive_terminal_id=3,
        pack_negative_terminal_id=0,
    )


def _canonical_4s4p_state() -> BatteryCircuitState:
    cells: list[BatteryCellInstance] = []
    connections: list[BatteryConnection] = []
    bus_members: list[list[int]] = [[] for _ in range(5)]
    next_terminal_id = 0
    for stage_index in range(4):
        for branch_index in range(4):
            negative_terminal_id = next_terminal_id
            positive_terminal_id = next_terminal_id + 1
            next_terminal_id += 2
            cells.append(
                BatteryCellInstance(
                    cell_id=len(cells),
                    positive_terminal_id=positive_terminal_id,
                    negative_terminal_id=negative_terminal_id,
                    x=stage_index,
                    y=branch_index,
                    z=0,
                )
            )
            bus_members[stage_index].append(negative_terminal_id)
            bus_members[stage_index + 1].append(positive_terminal_id)

    for members in bus_members:
        anchor = members[0]
        for member in members[1:]:
            connections.append(
                BatteryConnection(
                    connection_id=len(connections),
                    from_terminal_id=anchor,
                    to_terminal_id=member,
                    resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                    ideal=True,
                )
            )

    return BatteryCircuitState(
        cells=tuple(cells),
        connections=tuple(connections),
        pack_positive_terminal_id=bus_members[-1][0],
        pack_negative_terminal_id=bus_members[0][0],
    )


def test_single_cell_backend_evaluates_with_relaxed_requirements() -> None:
    evaluation = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.pybamm_ran is True
    assert evaluation.cell_model_source == "custom"
    assert evaluation.cell_model_warning is None
    assert evaluation.is_feasible is True
    assert evaluation.topology_kind == "series_parallel"
    assert evaluation.pack_nominal_voltage == pytest.approx(3.7)


def test_two_cell_series_backend_reports_doubled_nominal_voltage() -> None:
    state = _two_cell_series_state()
    topology = analyze_battery_topology(state)
    assert topology.topology_kind == "series_parallel"
    assert topology.series_count == 2
    assert topology.parallel_count == 1

    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=_relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.pack_nominal_voltage == pytest.approx(7.4)


def test_two_cell_parallel_backend_preserves_voltage_and_increases_parallel_count() -> None:
    state = _two_cell_parallel_state()
    topology = analyze_battery_topology(state)
    assert topology.topology_kind == "series_parallel"
    assert topology.series_count == 1
    assert topology.parallel_count == 2

    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=2.0, minimum_current_a=2.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.pack_nominal_voltage == pytest.approx(3.7)
    assert evaluation.is_feasible is True


def test_backend_is_sensitive_to_interconnect_resistance() -> None:
    requirements = _relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=5.0)
    low_resistance = evaluate_battery_circuit(
        state=_two_cell_parallel_state_with_connection_resistance(1.0e-4),
        requirements=requirements,
        load_cell_model=_static_cell_model,
    )
    high_resistance = evaluate_battery_circuit(
        state=_two_cell_parallel_state_with_connection_resistance(1.0),
        requirements=requirements,
        load_cell_model=_static_cell_model,
    )

    assert low_resistance.pack_terminal_voltage_end != pytest.approx(high_resistance.pack_terminal_voltage_end)
    assert low_resistance.max_connection_current_a != pytest.approx(high_resistance.max_connection_current_a)
    assert high_resistance.max_cell_current_a is not None
    assert low_resistance.max_cell_current_a is not None
    assert high_resistance.max_cell_current_a > low_resistance.max_cell_current_a

    series_requirements = _relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.0, minimum_current_a=5.0)
    low_series = evaluate_battery_circuit(
        state=BatteryCircuitState(
            cells=_two_cell_series_state().cells,
            connections=(
                replace(
                    _two_cell_series_state().connections[0],
                    resistance_ohm=1.0e-4,
                    ideal=False,
                ),
            ),
            pack_positive_terminal_id=_two_cell_series_state().pack_positive_terminal_id,
            pack_negative_terminal_id=_two_cell_series_state().pack_negative_terminal_id,
        ),
        requirements=series_requirements,
        load_cell_model=_static_cell_model,
    )
    high_series = evaluate_battery_circuit(
        state=BatteryCircuitState(
            cells=_two_cell_series_state().cells,
            connections=(
                replace(
                    _two_cell_series_state().connections[0],
                    resistance_ohm=1.0,
                    ideal=False,
                ),
            ),
            pack_positive_terminal_id=_two_cell_series_state().pack_positive_terminal_id,
            pack_negative_terminal_id=_two_cell_series_state().pack_negative_terminal_id,
        ),
        requirements=series_requirements,
        load_cell_model=_static_cell_model,
    )

    assert low_series.total_connection_loss_w != pytest.approx(high_series.total_connection_loss_w)


def test_direct_wire_short_is_rejected_before_simulation() -> None:
    state = BatteryCircuitState(
        cells=_single_cell_state().cells,
        connections=(
            BatteryConnection(
                connection_id=0,
                from_terminal_id=0,
                to_terminal_id=1,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
            ),
        ),
        pack_positive_terminal_id=1,
        pack_negative_terminal_id=0,
    )
    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.pybamm_ran is False
    assert evaluation.cell_model_source is None
    assert evaluation.cell_model_warning is None
    assert evaluation.is_feasible is False
    assert evaluation.failure_reason == "Pack terminals cannot be shorted by direct interconnects."


def test_orphan_cell_is_rejected_before_simulation() -> None:
    state = BatteryCircuitState(
        cells=(
            BatteryCellInstance(
                cell_id=0,
                positive_terminal_id=1,
                negative_terminal_id=0,
                x=0,
                y=0,
                z=0,
            ),
            BatteryCellInstance(
                cell_id=1,
                positive_terminal_id=3,
                negative_terminal_id=2,
                x=1,
                y=0,
                z=0,
            ),
        ),
        connections=(),
        pack_positive_terminal_id=1,
        pack_negative_terminal_id=0,
    )
    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.pybamm_ran is False
    assert evaluation.cell_model_source is None
    assert evaluation.cell_model_warning is None
    assert evaluation.is_feasible is False
    assert (
        evaluation.failure_reason == "Every cell must lie on at least one conductive path between the pack terminals."
    )


def test_cross_linked_graph_is_classified_as_general() -> None:
    topology = analyze_battery_topology(_general_cross_link_state())
    assert topology.topology_kind == "general"
    assert topology.series_count is None
    assert topology.parallel_count is None


def test_canonical_4s4p_graph_is_recognized_and_feasible() -> None:
    state = _canonical_4s4p_state()
    topology = analyze_battery_topology(state)
    assert topology.topology_kind == "series_parallel"
    assert topology.series_count == 4
    assert topology.parallel_count == 4

    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=_relaxed_requirements(target_voltage_v=14.8, minimum_capacity_ah=10.0, minimum_current_a=60.0),
        load_cell_model=_static_cell_model,
    )
    assert evaluation.is_feasible is True
    assert evaluation.pack_nominal_voltage == pytest.approx(14.8)
    assert evaluation.delivered_capacity_ah == pytest.approx(10.0)


def test_extended_simulation_can_run_past_required_capacity_and_stay_feasible() -> None:
    state = _two_cell_parallel_state()
    requirements = _relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=10.0)

    baseline = evaluate_battery_circuit(
        state=state,
        requirements=requirements,
        load_cell_model=_static_cell_model,
    )
    extended = evaluate_battery_circuit(
        state=state,
        requirements=requirements,
        load_cell_model=_static_cell_model,
        simulate_to_failure=True,
    )

    assert baseline.is_feasible is True
    assert baseline.delivered_capacity_ah == pytest.approx(1.0)
    assert extended.is_feasible is True
    assert extended.failure_reason is None
    assert extended.delivered_capacity_ah == pytest.approx(5.0)
    assert extended.delivered_capacity_ah > baseline.delivered_capacity_ah


def test_extended_simulation_still_fails_when_required_capacity_is_not_met() -> None:
    evaluation = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=3.0, minimum_current_a=10.0),
        load_cell_model=_static_cell_model,
        simulate_to_failure=True,
    )

    assert evaluation.is_feasible is False
    assert evaluation.delivered_capacity_ah == pytest.approx(2.5)
    assert evaluation.failure_reason == "A cell depleted before the required discharge duration completed."


def test_evaluation_records_cell_model_mode_and_parameter_set_metadata() -> None:
    configured_model = BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
        source="custom",
        warning_message=None,
        resolved_mode="pybamm_ecm",
        resolved_parameter_set="Chen2020",
    )
    evaluation = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=lambda: configured_model,
    )
    assert evaluation.cell_model_mode == "pybamm_ecm"
    assert evaluation.cell_model_parameter_set == "Chen2020"


def test_evaluate_battery_circuit_uses_backend_config_loader_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    def _unexpected_load() -> BatteryCellModel:
        raise AssertionError("load_cell_model should not be used when backend_config is provided.")

    monkeypatch.setattr(
        battery_cell_model,
        "import_pybamm",
        lambda: (_ for _ in ()).throw(MissingOptionalDependencyError("backend-config loader invoked")),
    )
    with pytest.raises(MissingOptionalDependencyError, match="backend-config loader invoked"):
        evaluate_battery_circuit(
            state=_single_cell_state(),
            requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
            load_cell_model=_unexpected_load,
            backend_config=BatteryBackendConfig(cell_model_mode="pybamm_spm"),
        )


def test_battery_backend_config_parses_parameterization_and_options() -> None:
    config = battery_backend_config_from_mapping(
        {
            "cell_model_mode": "pybamm_ecm",
            "parameterization": {"preset": "fast"},
            "thermal_mode": "isothermal",
            "ambient_temp_C": 22.5,
            "parasitics": {"R_bus": 0.001, "R_contact": 0.002},
            "solver_policy": {"dt_s": 1.0, "rel_tol": 1e-6},
        }
    )
    assert config.cell_model_mode == "pybamm_ecm"
    assert config.parameterization == BatteryParameterization(preset="fast", parameter_set=None)
    assert config.parameterization.resolved_parameter_set() == "Chen2020"
    assert config.thermal_mode == "isothermal"
    assert config.ambient_temp_c == pytest.approx(22.5)
    assert dict(config.parasitics) == {"R_bus": 0.001, "R_contact": 0.002}
    assert dict(config.solver_policy) == {"dt_s": 1.0, "rel_tol": 1e-6}


def test_battery_backend_config_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="cell_model_mode"):
        battery_backend_config_from_mapping({"cell_model_mode": "unknown"})


def test_battery_backend_config_rejects_removed_surrogate_mode() -> None:
    with pytest.raises(ValueError, match="cell_model_mode"):
        battery_backend_config_from_mapping({"cell_model_mode": "surrogate_rescaled"})


def test_load_battery_cell_model_auto_mode_requires_pybamm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    monkeypatch.setattr(
        battery_cell_model,
        "import_pybamm",
        lambda: (_ for _ in ()).throw(MissingOptionalDependencyError("pybamm is required")),
    )
    with pytest.raises(MissingOptionalDependencyError, match="pybamm is required"):
        battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="auto"))
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_load_battery_cell_model_spm_mode_uses_lithium_ion_spm_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    fake_defaults = {
        "Nominal cell capacity [A.h]": 100.0,
        "Initial temperature [K]": 298.15,
        "Open-circuit voltage [V]": lambda soc: 3.0 + (1.2 * soc),
        "R0 [Ohm]": lambda temperature_k, current_a, soc: 0.08 + (0.01 * soc),
        "R1 [Ohm]": lambda temperature_k, current_a, soc: 0.02,
        "C1 [F]": lambda temperature_k, current_a, soc: 600.0,
    }
    fake_module = SimpleNamespace(
        lithium_ion=SimpleNamespace(
            SPM=lambda: SimpleNamespace(default_parameter_values=dict(fake_defaults)),
            DFN=lambda: SimpleNamespace(default_parameter_values=dict(fake_defaults)),
        ),
        ParameterValues=lambda name: dict(fake_defaults),
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    model = battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_spm"))
    assert model.source == "pybamm_spm"
    assert model.resolved_mode == "pybamm_spm"
    assert model.warning_message is None
    assert len(model.soc_grid) == 11
    assert model.open_circuit_voltage_v[0] < model.open_circuit_voltage_v[-1]
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_load_battery_cell_model_spm_mode_fails_fast_without_required_ecm_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    fake_defaults = {
        "Nominal cell capacity [A.h]": 100.0,
        "Initial temperature [K]": 298.15,
        "Open-circuit voltage [V]": lambda soc: 3.0 + soc,
        "R1 [Ohm]": lambda temperature_k, current_a, soc: 0.02,
        "C1 [F]": lambda temperature_k, current_a, soc: 600.0,
    }
    fake_module = SimpleNamespace(
        lithium_ion=SimpleNamespace(
            SPM=lambda: SimpleNamespace(default_parameter_values=dict(fake_defaults)),
            DFN=lambda: SimpleNamespace(default_parameter_values=dict(fake_defaults)),
        ),
        ParameterValues=lambda name: dict(fake_defaults),
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match=r"R0 \[Ohm\]"):
        battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_spm"))
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_load_battery_cell_model_dfn_mode_respects_parameter_set_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    parameter_set_calls: list[str] = []
    fake_defaults = {
        "Cell capacity [A.h]": 100.0,
        "Initial temperature [K]": 298.15,
        "Open-circuit voltage [V]": lambda soc: 3.2 + soc,
        "R0 [Ohm]": lambda temperature_k, current_a, soc: 0.07,
        "R1 [Ohm]": lambda temperature_k, current_a, soc: 0.02,
        "C1 [F]": lambda temperature_k, current_a, soc: 800.0,
    }

    def _parameter_values(name: str) -> dict[str, object]:
        parameter_set_calls.append(name)
        return dict(fake_defaults)

    fake_module = SimpleNamespace(
        lithium_ion=SimpleNamespace(
            SPM=lambda: SimpleNamespace(default_parameter_values=dict(fake_defaults)),
            DFN=lambda: SimpleNamespace(default_parameter_values={"unused": 1.0}),
        ),
        ParameterValues=_parameter_values,
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    model = battery_cell_model.load_battery_cell_model(
        BatteryBackendConfig(
            cell_model_mode="pybamm_dfn",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        )
    )
    assert parameter_set_calls == ["Marquis2019"]
    assert model.source == "pybamm_dfn"
    assert model.resolved_mode == "pybamm_dfn"
    assert model.resolved_parameter_set == "Marquis2019"
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_load_18650_cell_model_requires_supported_thevenin_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_cell_model.cache_clear()
    fake_module = SimpleNamespace(equivalent_circuit=SimpleNamespace(Thevenin=None))
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match=r"equivalent_circuit\.Thevenin"):
        battery_cell_model.load_18650_cell_model()

    battery_cell_model.load_18650_cell_model.cache_clear()


def test_load_18650_cell_model_raises_when_pybamm_extraction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_cell_model.cache_clear()
    fake_module = SimpleNamespace(
        equivalent_circuit=SimpleNamespace(Thevenin=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match="parameter extraction failed"):
        battery_cell_model.load_18650_cell_model()

    battery_cell_model.load_18650_cell_model.cache_clear()


@pytest.mark.pybamm_real
def test_load_18650_cell_model_uses_expected_pybamm_thevenin_contract() -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    try:
        pybamm_module = battery_cell_model.import_pybamm()
    except MissingOptionalDependencyError:
        pytest.skip("pybamm is not installed in this environment.")

    equivalent_circuit = getattr(pybamm_module, "equivalent_circuit", None)
    thevenin_factory = getattr(equivalent_circuit, "Thevenin", None)
    assert callable(thevenin_factory)

    model = thevenin_factory(options={"number of rc elements": 1})
    parameter_values = battery_cell_model._copy_parameter_values(model.default_parameter_values)
    assert "Open-circuit voltage [V]" in parameter_values
    assert "R0 [Ohm]" in parameter_values
    assert "R1 [Ohm]" in parameter_values
    assert "C1 [F]" in parameter_values

    battery_cell_model.load_18650_cell_model.cache_clear()
    extracted = battery_cell_model.load_18650_cell_model()
    assert extracted.source == "pybamm_thevenin"
    assert extracted.warning_message is None
    battery_cell_model.load_18650_cell_model.cache_clear()


def test_load_18650_thermal_priors_requires_supported_thevenin_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    fake_module = SimpleNamespace(equivalent_circuit=SimpleNamespace(Thevenin=None))
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match=r"equivalent_circuit\.Thevenin"):
        battery_cell_model.load_18650_thermal_priors()

    battery_cell_model.load_18650_thermal_priors.cache_clear()


def test_load_18650_thermal_priors_extracts_and_normalizes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model.load_18650_cell_model.cache_clear()

    fake_module = SimpleNamespace(
        equivalent_circuit=SimpleNamespace(
            Thevenin=lambda **kwargs: SimpleNamespace(
                default_parameter_values={
                    "Cell capacity [A.h]": 100.0,
                    "Initial temperature [K]": 298.15,
                    "Cell-jig heat transfer coefficient [W/K]": 10.0,
                    "Jig-air heat transfer coefficient [W/K]": 8.0,
                    "Cell thermal mass [J/K]": 1000.0,
                    "Jig thermal mass [J/K]": 500.0,
                }
            )
        )
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)
    monkeypatch.setattr(battery_cell_model, "load_18650_cell_model", lambda: _static_cell_model())

    priors = battery_cell_model.load_18650_thermal_priors()
    assert isinstance(priors, BatteryThermalPriors)
    assert priors.soc_grid == (0.0, 1.0)
    assert priors.total_resistance_ohm == pytest.approx((0.01, 0.01))
    assert priors.reference_ambient_temperature_c == pytest.approx(25.0, abs=1.0e-6)
    assert priors.cell_to_jig_conductance_w_per_k == pytest.approx(0.85498797, rel=1.0e-5)
    assert priors.jig_to_ambient_conductance_w_per_k == pytest.approx(0.68399038, rel=1.0e-5)
    assert priors.cell_thermal_mass_j_per_k == pytest.approx(25.0, abs=1.0e-6)
    assert priors.jig_thermal_mass_j_per_k == pytest.approx(12.5, abs=1.0e-6)

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    cache_clear = getattr(battery_cell_model.load_18650_cell_model, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def test_load_18650_thermal_priors_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model.load_18650_cell_model.cache_clear()
    calls = {"count": 0}

    def _thevenin(**kwargs: object) -> SimpleNamespace:
        del kwargs
        calls["count"] += 1
        return SimpleNamespace(
            default_parameter_values={
                "Cell capacity [A.h]": 100.0,
                "Initial temperature [K]": 298.15,
                "Cell-jig heat transfer coefficient [W/K]": 10.0,
                "Jig-air heat transfer coefficient [W/K]": 10.0,
                "Cell thermal mass [J/K]": 1000.0,
                "Jig thermal mass [J/K]": 500.0,
            }
        )

    fake_module = SimpleNamespace(equivalent_circuit=SimpleNamespace(Thevenin=_thevenin))
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)
    monkeypatch.setattr(battery_cell_model, "load_18650_cell_model", lambda: _static_cell_model())

    first = battery_cell_model.load_18650_thermal_priors()
    second = battery_cell_model.load_18650_thermal_priors()
    assert first is second
    assert calls["count"] == 1

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    cache_clear = getattr(battery_cell_model.load_18650_cell_model, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()
