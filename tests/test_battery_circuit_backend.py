from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy
import pytest

from design_research_problems import MissingOptionalDependencyError
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    BatteryCellModel,
    BatteryParameterization,
    BatteryThermalPriors,
    battery_backend_config_from_mapping,
    interpolate_cell_model,
)
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCellInstance,
    BatteryCircuitState,
    BatteryConnection,
    analyze_battery_topology,
    evaluate_battery_circuit,
    validate_battery_circuit_state,
)
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
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


def _static_two_rc_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 0.5, 1.0),
        open_circuit_voltage_v=(3.2, 3.7, 4.2),
        series_resistance_ohm=(0.012, 0.011, 0.010),
        transient_resistance_ohm=(0.022, 0.020, 0.018),
        transient_capacitance_f=(120.0, 150.0, 180.0),
        secondary_transient_resistance_ohm=(0.016, 0.014, 0.012),
        secondary_transient_capacitance_f=(900.0, 1000.0, 1100.0),
    )


def _temperature_sensitive_pybamm_module() -> SimpleNamespace:
    defaults = {
        "Cell capacity [A.h]": 100.0,
        "Initial temperature [K]": 298.15,
        "Open-circuit voltage [V]": lambda temperature_k, current_a, soc: 4.2 - (0.05 * (1.0 - soc)),
        "R0 [Ohm]": lambda temperature_k, current_a, soc: 0.015 + (0.001 * (temperature_k - 298.15)),
        "R1 [Ohm]": lambda temperature_k, current_a, soc: 0.015,
        "C1 [F]": lambda temperature_k, current_a, soc: 400.0,
        "Cell-jig heat transfer coefficient [W/K]": 0.2,
        "Jig-air heat transfer coefficient [W/K]": 0.1,
        "Cell thermal mass [J/K]": 2.0,
        "Jig thermal mass [J/K]": 1.0,
    }

    def thevenin_factory(**kwargs: object) -> SimpleNamespace:
        del kwargs
        return SimpleNamespace(default_parameter_values=dict(defaults))

    return SimpleNamespace(
        equivalent_circuit=SimpleNamespace(Thevenin=thevenin_factory),
        ParameterValues=lambda name: dict(defaults),
    )


def _profile_segments(
    battery_circuit_module: SimpleNamespace | object,
    *pairs: tuple[float, float],
) -> tuple[object, ...]:
    return tuple(
        battery_circuit_module._BatteryCurrentProfileSegment(duration_s=duration_s, current_a=current_a)
        for duration_s, current_a in pairs
    )


def _rmse(left: numpy.ndarray, right: numpy.ndarray) -> float:
    return float(numpy.sqrt(numpy.mean((left - right) ** 2)))


def _run_live_pybamm_spm_profile(
    *,
    parameter_set: str,
    initial_soc: float,
    temperature_c: float,
    profile_pairs: tuple[tuple[float, float], ...],
) -> tuple[numpy.ndarray, numpy.ndarray, numpy.ndarray]:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    try:
        pybamm_module = battery_cell_model.import_pybamm()
    except MissingOptionalDependencyError:
        pytest.skip("pybamm is not installed in this environment.")

    steps: list[str] = []
    for duration_s, current_a in profile_pairs:
        duration_label = round(duration_s)
        if abs(current_a) <= 1.0e-12:
            steps.append(f"Rest for {duration_label} seconds")
        else:
            steps.append(f"Discharge at {current_a:.3f} A for {duration_label} seconds")

    parameter_values = pybamm_module.ParameterValues(parameter_set)
    update_method = getattr(parameter_values, "update", None)
    if callable(update_method):
        try:
            update_method(
                {
                    "Initial temperature [K]": 273.15 + temperature_c,
                    "Ambient temperature [K]": 273.15 + temperature_c,
                },
                check_already_exists=False,
            )
        except TypeError:
            update_method(
                {
                    "Initial temperature [K]": 273.15 + temperature_c,
                    "Ambient temperature [K]": 273.15 + temperature_c,
                }
            )
    simulation = pybamm_module.Simulation(
        pybamm_module.lithium_ion.SPM(),
        experiment=pybamm_module.Experiment(steps),
        parameter_values=parameter_values,
    )
    solution = simulation.solve(initial_soc=initial_soc)
    total_duration_s = sum(round(duration_s) for duration_s, _current_a in profile_pairs)
    sample_times = numpy.arange(0.0, float(total_duration_s), 1.0, dtype=float)
    return (
        sample_times,
        numpy.asarray(solution["Current [A]"](sample_times), dtype=float),
        numpy.asarray(solution["Voltage [V]"](sample_times), dtype=float),
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


def test_circuit_validation_reports_each_structural_input_error() -> None:
    requirements = _relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0)
    valid = _single_cell_state()
    cell = valid.cells[0]

    cases = [
        (replace(valid, cells=()), "At least one battery cell"),
        (replace(valid, cells=(cell, replace(cell, x=1))), "Cell identifiers must be unique"),
        (
            replace(valid, cells=(cell, replace(cell, cell_id=1, x=1))),
            "Terminal identifiers must be unique",
        ),
        (replace(valid, cells=(replace(cell, x=999),)), "outside the legal grid envelope"),
        (
            replace(
                valid,
                cells=(cell, replace(cell, cell_id=1, positive_terminal_id=3, negative_terminal_id=2)),
            ),
            "Duplicate physical coordinates",
        ),
        (replace(valid, pack_positive_terminal_id=0), "Pack positive and negative terminals must be distinct"),
        (replace(valid, pack_positive_terminal_id=999), "Pack terminals must reference existing"),
    ]

    base_connection = BatteryConnection(connection_id=0, from_terminal_id=0, to_terminal_id=1)
    two_cell = _two_cell_series_state()
    cases.extend(
        [
            (
                replace(
                    two_cell,
                    connections=(two_cell.connections[0], replace(two_cell.connections[0], ideal=False)),
                ),
                "Connection identifiers must be unique",
            ),
            (replace(valid, connections=(replace(base_connection, to_terminal_id=0),)), "join two distinct terminals"),
            (replace(valid, connections=(replace(base_connection, to_terminal_id=999),)), "reference existing"),
            (replace(valid, connections=(replace(base_connection, resistance_ohm=0),)), "positive resistance"),
            (
                replace(
                    valid,
                    connections=(base_connection, replace(base_connection, connection_id=1, ideal=True)),
                ),
                "Duplicate direct connections",
            ),
            (
                replace(
                    two_cell,
                    connections=(
                        *two_cell.connections,
                        BatteryConnection(connection_id=1, from_terminal_id=2, to_terminal_id=3),
                    ),
                ),
                "cell cannot have its terminals shorted",
            ),
        ]
    )

    for state, expected in cases:
        reason = validate_battery_circuit_state(state, requirements)
        assert reason is not None
        assert expected in reason


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


def _two_series_two_parallel_state() -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(cell_id=0, positive_terminal_id=1, negative_terminal_id=0, x=0, y=0, z=0),
            BatteryCellInstance(cell_id=1, positive_terminal_id=3, negative_terminal_id=2, x=1, y=0, z=0),
            BatteryCellInstance(cell_id=2, positive_terminal_id=5, negative_terminal_id=4, x=0, y=1, z=0),
            BatteryCellInstance(cell_id=3, positive_terminal_id=7, negative_terminal_id=6, x=1, y=1, z=0),
        ),
        connections=(
            BatteryConnection(connection_id=0, from_terminal_id=1, to_terminal_id=2, ideal=True),
            BatteryConnection(connection_id=1, from_terminal_id=5, to_terminal_id=6, ideal=True),
            BatteryConnection(connection_id=2, from_terminal_id=0, to_terminal_id=4, ideal=True),
            BatteryConnection(connection_id=3, from_terminal_id=3, to_terminal_id=7, ideal=True),
        ),
        pack_positive_terminal_id=3,
        pack_negative_terminal_id=0,
    )


def _asymmetric_parallel_pack_state(*, link_resistance_ohm: float) -> BatteryCircuitState:
    return BatteryCircuitState(
        cells=(
            BatteryCellInstance(cell_id=0, positive_terminal_id=1, negative_terminal_id=0, x=0, y=0, z=0),
            BatteryCellInstance(cell_id=1, positive_terminal_id=3, negative_terminal_id=2, x=0, y=1, z=0),
        ),
        connections=(
            BatteryConnection(connection_id=0, from_terminal_id=0, to_terminal_id=2, ideal=True),
            BatteryConnection(
                connection_id=1,
                from_terminal_id=1,
                to_terminal_id=3,
                resistance_ohm=link_resistance_ohm,
                ideal=False,
            ),
        ),
        pack_positive_terminal_id=1,
        pack_negative_terminal_id=0,
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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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


def test_battery_backend_config_parses_parameterization_and_thermal_config() -> None:
    config = battery_backend_config_from_mapping(
        {
            "cell_model_mode": "pybamm_ecm",
            "parameterization": {"preset": "fast"},
            "thermal_mode": "isothermal",
            "ambient_temp_c": 22.5,
        }
    )
    assert config.cell_model_mode == "pybamm_ecm"
    assert config.parameterization == BatteryParameterization(preset="fast", parameter_set=None)
    assert config.parameterization.resolved_parameter_set() == "Chen2020"
    assert config.thermal_mode == "isothermal"
    assert config.ambient_temp_c == pytest.approx(22.5)


def test_battery_backend_config_defaults_to_isothermal_with_shared_ambient() -> None:
    config = battery_backend_config_from_mapping({"cell_model_mode": "pybamm_ecm"})
    assert config.thermal_mode == "isothermal"
    assert config.ambient_temp_c == pytest.approx(25.0)


def test_battery_backend_config_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="cell_model_mode"):
        battery_backend_config_from_mapping({"cell_model_mode": "unknown"})


def test_battery_backend_config_rejects_removed_surrogate_mode() -> None:
    with pytest.raises(ValueError, match="cell_model_mode"):
        battery_backend_config_from_mapping({"cell_model_mode": "surrogate_rescaled"})


def test_battery_backend_config_rejects_removed_compatibility_fields() -> None:
    with pytest.raises(ValueError, match="Unsupported battery_backend field"):
        battery_backend_config_from_mapping({"ambient_temp_C": 22.5})

    with pytest.raises(ValueError, match="Unsupported battery_backend field"):
        battery_backend_config_from_mapping({"parasitics": {"R_bus": 0.001}})


def test_battery_backend_config_rejects_unknown_thermal_mode() -> None:
    with pytest.raises(ValueError, match="thermal_mode"):
        battery_backend_config_from_mapping({"thermal_mode": "multi_node"})


def test_load_battery_cell_model_auto_mode_requires_pybamm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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


def test_isothermal_backend_propagates_ambient_temperature_to_cell_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
    monkeypatch.setattr(battery_cell_model, "import_pybamm", _temperature_sensitive_pybamm_module)

    requirements = _relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=0.5, minimum_current_a=5.0)
    cool = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=requirements,
        load_cell_model=lambda: (_ for _ in ()).throw(AssertionError("backend-config path expected")),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=15.0,
        ),
    )
    warm = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=requirements,
        load_cell_model=lambda: (_ for _ in ()).throw(AssertionError("backend-config path expected")),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=35.0,
        ),
    )

    assert cool.thermal_mode == "isothermal"
    assert warm.thermal_mode == "isothermal"
    assert cool.end_cell_temperature_c == pytest.approx(15.0)
    assert warm.end_cell_temperature_c == pytest.approx(35.0)
    assert cool.max_cell_temperature_c == pytest.approx(15.0)
    assert warm.max_cell_temperature_c == pytest.approx(35.0)
    assert cool.pack_terminal_voltage_end != pytest.approx(warm.pack_terminal_voltage_end)

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()


def test_lumped_backend_produces_distinct_temperature_and_voltage_trajectory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
    monkeypatch.setattr(battery_cell_model, "import_pybamm", _temperature_sensitive_pybamm_module)

    requirements = _relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=0.5, minimum_current_a=10.0)
    isothermal = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=requirements,
        load_cell_model=lambda: (_ for _ in ()).throw(AssertionError("backend-config path expected")),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    lumped = evaluate_battery_circuit(
        state=_single_cell_state(),
        requirements=requirements,
        load_cell_model=lambda: (_ for _ in ()).throw(AssertionError("backend-config path expected")),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="lumped",
            ambient_temp_c=25.0,
        ),
    )

    assert isothermal.thermal_mode == "isothermal"
    assert lumped.thermal_mode == "lumped"
    assert isothermal.end_cell_temperature_c == pytest.approx(25.0)
    assert lumped.end_cell_temperature_c is not None
    assert lumped.max_cell_temperature_c is not None
    assert lumped.end_cell_temperature_c > 25.0
    assert lumped.max_cell_temperature_c >= lumped.end_cell_temperature_c
    assert lumped.pack_terminal_voltage_end is not None
    assert isothermal.pack_terminal_voltage_end is not None
    assert lumped.pack_terminal_voltage_end < isothermal.pack_terminal_voltage_end

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()


def test_load_18650_cell_model_requires_supported_thevenin_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_cell_model.cache_clear()
    fake_module = SimpleNamespace(equivalent_circuit=SimpleNamespace(Thevenin=None))
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match=r"equivalent_circuit\.Thevenin"):
        battery_cell_model.load_18650_cell_model()

    battery_cell_model.load_18650_cell_model.cache_clear()


def test_load_18650_cell_model_raises_when_pybamm_extraction_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

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
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
    fake_module = SimpleNamespace(equivalent_circuit=SimpleNamespace(Thevenin=None))
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_module)

    with pytest.raises(MissingOptionalDependencyError, match=r"equivalent_circuit\.Thevenin"):
        battery_cell_model.load_18650_thermal_priors()

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()


def test_load_18650_thermal_priors_extracts_and_normalizes_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
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
    monkeypatch.setattr(battery_cell_model, "load_battery_cell_model", lambda config=None: _static_cell_model())

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
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
    cache_clear = getattr(battery_cell_model.load_battery_cell_model, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def test_load_18650_thermal_priors_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
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
    monkeypatch.setattr(battery_cell_model, "load_battery_cell_model", lambda config=None: _static_cell_model())

    first = battery_cell_model.load_18650_thermal_priors()
    second = battery_cell_model.load_18650_thermal_priors()
    assert first is second
    assert calls["count"] == 1

    battery_cell_model.load_18650_thermal_priors.cache_clear()
    battery_cell_model._load_battery_thermal_priors_cached.cache_clear()
    cache_clear = getattr(battery_cell_model.load_battery_cell_model, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def test_battery_backend_config_accepts_two_rc_mode() -> None:
    config = battery_backend_config_from_mapping({"cell_model_mode": "pybamm_ecm_2rc"})
    assert config.cell_model_mode == "pybamm_ecm_2rc"
    assert config.thermal_mode == "isothermal"


def test_battery_backend_config_accepts_direct_mode() -> None:
    config = battery_backend_config_from_mapping({"cell_model_mode": "pybamm_direct"})
    assert config.cell_model_mode == "pybamm_direct"
    assert config.thermal_mode == "isothermal"


def test_load_battery_cell_model_direct_mode_reports_evaluator_only_usage() -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    with pytest.raises(ValueError, match="evaluator mode"):
        battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_direct"))
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_load_battery_cell_model_two_rc_mode_uses_fitted_trace_bundle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    fake_parameter_values = {
        "Nominal cell capacity [A.h]": 2.5,
        "Initial temperature [K]": 298.15,
        "Open-circuit voltage [V]": lambda temperature_k, current_a, soc: 3.0 + (1.1 * soc),
    }
    traces = tuple(
        battery_cell_model._BatteryCurrentTrace(
            initial_soc=soc,
            temperature_c=temperature_c,
            time_s=(0.0, 1.0),
            current_a=(0.0, 0.0),
            voltage_v=(4.0, 4.0),
        )
        for temperature_c in battery_cell_model._TWO_RC_IDENTIFICATION_TEMPERATURES_C
        for soc in battery_cell_model._TWO_RC_IDENTIFICATION_SOC_GRID
    )

    monkeypatch.setattr(
        battery_cell_model,
        "_load_lithium_ion_parameter_values",
        lambda **kwargs: (dict(fake_parameter_values), 1.0, 298.15),
    )
    monkeypatch.setattr(
        battery_cell_model,
        "_generate_pybamm_two_rc_identification_traces",
        lambda **kwargs: traces,
    )
    monkeypatch.setattr(
        battery_cell_model,
        "_fit_two_rc_trace",
        lambda trace, **kwargs: battery_cell_model._TwoRcFitResult(
            initial_soc=trace.initial_soc,
            temperature_c=trace.temperature_c,
            series_resistance_ohm=0.010 + (0.002 * (1.0 - trace.initial_soc)),
            transient_resistance_ohm=0.020 + (0.001 * trace.temperature_c / 25.0),
            transient_capacitance_f=150.0 + (20.0 * trace.initial_soc),
            secondary_transient_resistance_ohm=0.012 + (0.001 * (35.0 - trace.temperature_c) / 20.0),
            secondary_transient_capacitance_f=900.0 + (50.0 * trace.initial_soc),
        ),
    )

    model = battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_ecm_2rc"))
    assert model.resolved_mode == "pybamm_ecm_2rc"
    assert model.source == "pybamm_spm_fit_2rc"
    assert model.secondary_transient_resistance_ohm
    assert model.secondary_transient_capacitance_f
    assert model.dynamic_parameters is not None
    assert model.dynamic_parameters.temperature_grid_c == pytest.approx((15.0, 25.0, 35.0))

    battery_cell_model._load_battery_cell_model_cached.cache_clear()


def test_two_rc_trace_residuals_accept_tuple_voltage_trace() -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    trace = battery_cell_model._BatteryCurrentTrace(
        initial_soc=0.5,
        temperature_c=25.0,
        time_s=(0.0, 1.0, 2.0),
        current_a=(0.0, 0.0, 0.0),
        voltage_v=(4.0, 4.0, 4.0),
    )
    residuals = battery_cell_model._two_rc_trace_residuals(
        numpy.array([0.01, 0.02, 8.0, 0.01, 100.0], dtype=float),
        trace,
        capacity_ah=2.5,
        open_circuit_voltage_v=tuple(4.0 for _ in battery_cell_model._TWO_RC_REFERENCE_SOC_GRID),
    )

    assert residuals.dtype == numpy.float64
    assert residuals.shape == (3,)
    assert numpy.allclose(residuals, 0.0)


def test_two_rc_identification_adapter_builds_and_fits_traces(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    class _Solution:
        t = numpy.array([0.0, 2.0])

        def __getitem__(self, name: str) -> object:
            value = 1.5 if name == "Current [A]" else 3.8
            return lambda times: numpy.full(numpy.asarray(times).shape, value)

    class _Simulation:
        def __init__(self, model: object, **kwargs: object) -> None:
            del model, kwargs

        def solve(self, *, initial_soc: float) -> _Solution:
            assert initial_soc in battery_cell_model._TWO_RC_IDENTIFICATION_SOC_GRID
            return _Solution()

    defaults = {
        "Nominal cell capacity [A.h]": 2.5,
        "Initial temperature [K]": 298.15,
    }
    fake_pybamm = SimpleNamespace(
        lithium_ion=SimpleNamespace(SPM=lambda: SimpleNamespace(default_parameter_values=dict(defaults))),
        Experiment=lambda steps: tuple(steps),
        Simulation=_Simulation,
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_pybamm)

    short_steps = battery_cell_model._build_two_rc_identification_experiment_steps(include_long_rest=False)
    long_steps = battery_cell_model._build_two_rc_identification_experiment_steps(include_long_rest=True)
    assert len(short_steps) == 8
    assert long_steps[-1] == "Rest for 300 seconds"

    traces = battery_cell_model._generate_pybamm_two_rc_identification_traces(resolved_parameter_set=None)
    assert len(traces) == 15
    assert traces[0].time_s == (0.0, 1.0, 2.0)
    assert traces[0].current_a == (1.5, 1.5, 1.5)

    monkeypatch.setattr(
        battery_cell_model,
        "_load_named_parameter_values",
        lambda **kwargs: dict(defaults),
    )
    named_traces = battery_cell_model._generate_pybamm_two_rc_identification_traces(resolved_parameter_set="test-set")
    assert len(named_traces) == len(traces)

    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: SimpleNamespace())
    with pytest.raises(MissingOptionalDependencyError, match=r"lithium_ion\.SPM"):
        battery_cell_model._generate_pybamm_two_rc_identification_traces(resolved_parameter_set=None)
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_pybamm)

    fitted = SimpleNamespace(success=True, x=numpy.array([0.01, 0.02, 8.0, 0.03, 120.0]))
    monkeypatch.setattr("scipy.optimize.least_squares", lambda *args, **kwargs: fitted)
    result = battery_cell_model._fit_two_rc_trace(
        traces[0],
        parameter_values=defaults,
        resistance_scale=2.0,
        open_circuit_voltage_v=tuple(4.0 for _ in battery_cell_model._TWO_RC_REFERENCE_SOC_GRID),
    )
    assert result.series_resistance_ohm == pytest.approx(0.02)
    assert result.transient_capacitance_f == pytest.approx(200.0)
    assert result.secondary_transient_capacitance_f == pytest.approx(2000.0)

    monkeypatch.setattr(
        "scipy.optimize.least_squares",
        lambda *args, **kwargs: SimpleNamespace(success=False, x=fitted.x),
    )
    with pytest.raises(MissingOptionalDependencyError, match="did not converge"):
        battery_cell_model._fit_two_rc_trace(
            traces[0],
            parameter_values=defaults,
            resistance_scale=1.0,
            open_circuit_voltage_v=tuple(4.0 for _ in battery_cell_model._TWO_RC_REFERENCE_SOC_GRID),
        )


def test_two_rc_ocv_and_dynamic_interpolation_adapters(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    direct = battery_cell_model._build_reference_ocv_lookup(
        parameter_values={"Open-circuit voltage [V]": lambda temperature_k, current_a, soc: 3.0 + soc},
        resolved_parameter_set=None,
    )
    assert direct[0] == pytest.approx(3.0)
    assert direct[-1] == pytest.approx(4.0)

    class _Solution:
        def __getitem__(self, name: str) -> object:
            assert name == "Voltage [V]"
            return lambda _time: 3.75

    fake_pybamm = SimpleNamespace(
        lithium_ion=SimpleNamespace(
            SPM=lambda: SimpleNamespace(default_parameter_values={"Initial temperature [K]": 298.15})
        ),
        Experiment=lambda steps: tuple(steps),
        Simulation=lambda *args, **kwargs: SimpleNamespace(solve=lambda **solve_kwargs: _Solution()),
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_pybamm)
    fallback = battery_cell_model._build_reference_ocv_lookup(parameter_values={}, resolved_parameter_set=None)
    assert fallback == pytest.approx((3.75,) * 11)

    model = replace(
        _static_two_rc_cell_model(),
        dynamic_parameters=battery_cell_model._BatteryCellDynamicParameters(
            parameter_values={},
            open_circuit_voltage_fn=lambda temperature_k, current_a, soc: 3.0 + soc,
            resistance_scale=2.0,
            resistance_normalization=0.5,
            capacitance_normalization=2.0,
            secondary_capacitance_normalization=2.0,
            temperature_grid_c=(15.0, 35.0),
            series_resistance_by_temperature_ohm=((0.02,) * 11, (0.04,) * 11),
            transient_resistance_by_temperature_ohm=((0.03,) * 11, (0.05,) * 11),
            transient_capacitance_by_temperature_f=((100.0,) * 11, (200.0,) * 11),
            secondary_transient_resistance_by_temperature_ohm=((0.01,) * 11, (0.03,) * 11),
            secondary_transient_capacitance_by_temperature_f=((800.0,) * 11, (1200.0,) * 11),
        ),
    )
    interpolated = battery_cell_model.interpolate_cell_model(model, 0.5, temperature_c=25.0)
    assert interpolated == pytest.approx((3.5, 0.03, 0.04, 37.5, 0.02, 250.0))


def test_evaluate_battery_circuit_uses_pybamm_direct_path(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    calls: list[tuple[int, int]] = []

    def _fake_direct(
        state: BatteryCircuitState,
        requirements: BatteryRequirements,
        analysis: object,
        *,
        simulate_to_failure: bool,
        backend_config: BatteryBackendConfig,
    ) -> tuple[object, str, str | None]:
        del requirements, simulate_to_failure
        calls.append((analysis.series_count, analysis.parallel_count))
        return (
            battery_circuit.BatteryCircuitSimulationResult(
                pack_terminal_voltage_end=7.8,
                required_pack_terminal_voltage_end=7.8,
                delivered_capacity_ah=1.2,
                max_cell_current_a=0.6,
                min_cell_voltage_v=3.9,
                total_connection_loss_w=0.0,
                max_connection_current_a=0.0,
                solver_steps=60,
                is_feasible=True,
                failure_reason=None,
                end_cell_temperature_c=25.0,
                max_cell_temperature_c=25.0,
            ),
            "pybamm_spm_direct",
            backend_config.parameterization.resolved_parameter_set(),
        )

    monkeypatch.setattr(battery_circuit, "_simulate_battery_circuit_pybamm_direct", _fake_direct)

    evaluation = evaluate_battery_circuit(
        state=_two_cell_series_state(),
        requirements=_relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=lambda: (_ for _ in ()).throw(AssertionError("direct path should bypass surrogate loading")),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_direct",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        ),
    )

    assert calls == [(2, 1)]
    assert evaluation.is_feasible is True
    assert evaluation.cell_model_mode == "pybamm_direct"
    assert evaluation.cell_model_source == "pybamm_spm_direct"
    assert evaluation.cell_model_parameter_set == "Marquis2019"
    assert evaluation.pack_terminal_voltage_end == pytest.approx(7.8)


def test_pybamm_direct_adapter_runs_without_the_optional_solver(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    class _Solution:
        t = numpy.array([0.0, 1.0])
        termination = "final time"

        def __getitem__(self, name: str) -> object:
            if name == "Voltage [V]":
                return lambda times: numpy.full(numpy.asarray(times).shape, 3.9)
            if name == "Volume-averaged cell temperature [K]":
                return lambda times: numpy.full((len(numpy.asarray(times)), 2), 300.15)
            if name == "Irreversible electrochemical heating [W]":
                return lambda times: numpy.full(numpy.asarray(times).shape, 0.2)
            raise KeyError(name)

    model_options: list[object] = []

    def _spm(*, options: object = None) -> object:
        model_options.append(options)
        return object()

    fake_pybamm = SimpleNamespace(
        lithium_ion=SimpleNamespace(SPM=_spm),
        Experiment=lambda steps: tuple(steps),
        Simulation=lambda *args, **kwargs: SimpleNamespace(solve=lambda **solve_kwargs: _Solution()),
    )
    monkeypatch.setattr(battery_circuit, "import_pybamm", lambda: fake_pybamm)
    monkeypatch.setattr(
        battery_circuit,
        "_load_lithium_ion_parameter_values",
        lambda **kwargs: ({}, 1.0, 298.15),
    )

    state = _single_cell_state()
    requirements = _relaxed_requirements(
        target_voltage_v=3.7,
        minimum_capacity_ah=1.0 / 3600.0,
        minimum_current_a=1.0,
    )
    result, source, parameter_set = battery_circuit._simulate_battery_circuit_pybamm_direct(
        state,
        requirements,
        analyze_battery_topology(state),
        simulate_to_failure=False,
        backend_config=BatteryBackendConfig(
            parameterization=BatteryParameterization(parameter_set="test-set"),
            thermal_mode="lumped",
        ),
    )
    assert source == "pybamm_spm_direct"
    assert parameter_set == "test-set"
    assert result.is_feasible is True
    assert result.pack_terminal_voltage_end == pytest.approx(3.9)
    assert result.end_cell_temperature_c == pytest.approx(27.0)
    assert result.cumulative_cell_heat_j == pytest.approx(0.2)
    assert model_options == [{"thermal": "lumped"}]

    with pytest.raises(ValueError, match="does not support thermal_mode"):
        battery_circuit._simulate_battery_circuit_pybamm_direct(
            state,
            requirements,
            analyze_battery_topology(state),
            simulate_to_failure=False,
            backend_config=BatteryBackendConfig(thermal_mode="x-full"),
        )


def test_pybamm_direct_helpers_report_unsupported_states_and_missing_traces() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    state = _single_cell_state()
    analysis = analyze_battery_topology(state)
    unsupported = SimpleNamespace(topology_kind="custom", series_count=None, parallel_count=None)
    assert "series-parallel" in battery_circuit._validate_pybamm_direct_state(state, unsupported)
    assert "at least one active cell" in battery_circuit._validate_pybamm_direct_state(
        replace(state, cells=()), analysis
    )

    sample_times = numpy.array([0.0, 1.0])
    with pytest.raises(KeyError, match="temperature variable"):
        battery_circuit._load_pybamm_direct_temperature_trace_c({}, sample_times)
    assert numpy.array_equal(
        battery_circuit._load_pybamm_direct_heat_trace_w({}, sample_times),
        numpy.zeros(2),
    )


def test_pybamm_direct_rejects_nonideal_interconnect_topologies() -> None:
    with pytest.raises(ValueError, match="ideal interconnects"):
        evaluate_battery_circuit(
            state=_two_cell_parallel_state_with_connection_resistance(0.01),
            requirements=_relaxed_requirements(target_voltage_v=3.7, minimum_capacity_ah=1.0, minimum_current_a=1.0),
            load_cell_model=_static_cell_model,
            backend_config=BatteryBackendConfig(cell_model_mode="pybamm_direct"),
        )


def test_two_rc_profile_runner_exposes_fast_invariants() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    model = _static_two_rc_cell_model()
    result = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        model,
        profile_segments=_profile_segments(
            battery_circuit,
            (45.0, 2.5),
            (180.0, 0.0),
        ),
        required_step_index=225,
        backend_config=BatteryBackendConfig(thermal_mode="isothermal"),
    )

    assert result.is_feasible is True
    assert result.max_kcl_residual_a < 1.0e-9
    assert result.max_kvl_residual_v < 1.0e-9
    assert result.delivered_capacity_ah > 0.0
    assert result.cumulative_delivered_energy_j > 0.0
    assert result.cumulative_cell_heat_j >= 0.0
    assert result.cumulative_connection_loss_j >= 0.0
    assert result.trace
    assert all(0.0 <= soc <= 1.0 for _cell_id, soc in result.end_soc_by_cell_id)
    assert all(soc < 1.0 for _cell_id, soc in result.end_soc_by_cell_id)
    assert all(numpy.isfinite(value) for _cell_id, value in result.end_primary_rc_voltage_by_cell_id)
    assert all(numpy.isfinite(value) for _cell_id, value in result.end_secondary_rc_voltage_by_cell_id)
    available_energy_upper_bound_j = (
        len(_single_cell_state().cells)
        * CELL_SPEC_18650.nominal_capacity_ah
        * 3600.0
        * max(model.open_circuit_voltage_v)
    )
    assert (
        result.cumulative_delivered_energy_j + result.cumulative_cell_heat_j + result.cumulative_connection_loss_j
        <= available_energy_upper_bound_j
    )


def test_two_rc_long_rest_converges_toward_ocv() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    model = _static_two_rc_cell_model()
    result = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        model,
        profile_segments=_profile_segments(
            battery_circuit,
            (30.0, 5.0),
            (300.0, 0.0),
        ),
        required_step_index=330,
        backend_config=BatteryBackendConfig(thermal_mode="isothermal"),
    )
    rest_points = [point for point in result.trace if abs(point.pack_current_a) <= 1.0e-12]
    assert rest_points
    end_soc = result.end_soc_by_cell_id[0][1]
    end_ocv_v, *_rest = interpolate_cell_model(model, end_soc)
    assert abs(rest_points[-1].pack_terminal_voltage_v - end_ocv_v) < abs(
        rest_points[0].pack_terminal_voltage_v - end_ocv_v
    )
    assert abs(rest_points[-1].pack_terminal_voltage_v - end_ocv_v) < 0.03


def test_profile_runner_pack_sentinels_capture_symmetric_and_asymmetric_branch_split() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    model = _static_two_rc_cell_model()
    symmetric = battery_circuit._simulate_battery_circuit_current_profile(
        _two_series_two_parallel_state(),
        model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(thermal_mode="isothermal"),
    )
    symmetric_currents = dict(symmetric.end_cell_current_by_cell_id)
    assert symmetric_currents[0] == pytest.approx(symmetric_currents[2], rel=1.0e-6, abs=1.0e-6)
    assert symmetric_currents[1] == pytest.approx(symmetric_currents[3], rel=1.0e-6, abs=1.0e-6)

    asymmetric = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.02),
        model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(thermal_mode="isothermal"),
    )
    asymmetric_currents = dict(asymmetric.end_cell_current_by_cell_id)
    assert asymmetric_currents[0] > asymmetric_currents[1]


@pytest.mark.pybamm_real
def test_load_battery_cell_model_two_rc_mode_fits_live_pybamm_traces() -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    battery_cell_model._load_battery_cell_model_cached.cache_clear()
    model = battery_cell_model.load_battery_cell_model(
        BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        )
    )
    assert model.resolved_mode == "pybamm_ecm_2rc"
    assert model.secondary_transient_resistance_ohm
    assert model.secondary_transient_capacitance_f
    battery_cell_model._load_battery_cell_model_cached.cache_clear()


@pytest.mark.pybamm_real
def test_two_rc_mode_beats_one_rc_on_live_pybamm_pulse_rest_trace() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    profile_pairs = (
        (60.0, CELL_SPEC_18650.nominal_capacity_ah),
        (300.0, 0.0),
    )
    _times_s, _currents_a, oracle_voltage_v = _run_live_pybamm_spm_profile(
        parameter_set="Marquis2019",
        initial_soc=0.7,
        temperature_c=25.0,
        profile_pairs=profile_pairs,
    )

    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    one_rc_model = battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_ecm"))
    two_rc_model = battery_cell_model.load_battery_cell_model(
        BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        )
    )
    one_rc = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        one_rc_model,
        profile_segments=_profile_segments(battery_circuit, *profile_pairs),
        required_step_index=sum(int(duration_s) for duration_s, _current_a in profile_pairs),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    two_rc = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, *profile_pairs),
        required_step_index=sum(int(duration_s) for duration_s, _current_a in profile_pairs),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )

    one_rc_voltage_v = numpy.asarray([point.pack_terminal_voltage_v for point in one_rc.trace], dtype=float)
    two_rc_voltage_v = numpy.asarray([point.pack_terminal_voltage_v for point in two_rc.trace], dtype=float)
    one_rc_rmse_v = _rmse(one_rc_voltage_v, oracle_voltage_v)
    two_rc_rmse_v = _rmse(two_rc_voltage_v, oracle_voltage_v)
    one_rc_end_rest_error_v = abs(one_rc_voltage_v[-1] - oracle_voltage_v[-1])
    two_rc_end_rest_error_v = abs(two_rc_voltage_v[-1] - oracle_voltage_v[-1])

    assert two_rc_rmse_v <= 0.8 * one_rc_rmse_v
    assert two_rc_end_rest_error_v <= 0.8 * one_rc_end_rest_error_v


@pytest.mark.pybamm_real
def test_two_rc_mode_tracks_short_live_pybamm_dynamic_profile() -> None:
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    profile_pairs = (
        (45.0, 1.25),
        (30.0, 0.0),
        (60.0, 2.50),
        (30.0, 0.75),
        (45.0, 5.00),
        (30.0, 0.0),
        (60.0, 1.50),
    )
    _times_s, _currents_a, oracle_voltage_v = _run_live_pybamm_spm_profile(
        parameter_set="Marquis2019",
        initial_soc=0.7,
        temperature_c=25.0,
        profile_pairs=profile_pairs,
    )
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model

    one_rc_model = battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_ecm"))
    two_rc_model = battery_cell_model.load_battery_cell_model(
        BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        )
    )
    one_rc = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        one_rc_model,
        profile_segments=_profile_segments(battery_circuit, *profile_pairs),
        required_step_index=sum(int(duration_s) for duration_s, _current_a in profile_pairs),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    two_rc = battery_circuit._simulate_battery_circuit_current_profile(
        _single_cell_state(),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, *profile_pairs),
        required_step_index=sum(int(duration_s) for duration_s, _current_a in profile_pairs),
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )

    one_rc_rmse_v = _rmse(
        numpy.asarray([point.pack_terminal_voltage_v for point in one_rc.trace], dtype=float),
        oracle_voltage_v,
    )
    two_rc_rmse_v = _rmse(
        numpy.asarray([point.pack_terminal_voltage_v for point in two_rc.trace], dtype=float),
        oracle_voltage_v,
    )
    assert two_rc_rmse_v <= (0.75 * one_rc_rmse_v)
    assert two_rc_rmse_v < 0.30


@pytest.mark.pybamm_real
def test_live_fitted_two_rc_model_preserves_pack_sentinels() -> None:
    from design_research_problems.problems._domains import battery_cell_model as battery_cell_model
    from design_research_problems.problems._domains import battery_circuit as battery_circuit

    one_rc_model = battery_cell_model.load_battery_cell_model(BatteryBackendConfig(cell_model_mode="pybamm_ecm"))
    two_rc_model = battery_cell_model.load_battery_cell_model(
        BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
        )
    )
    symmetric = battery_circuit._simulate_battery_circuit_current_profile(
        _two_series_two_parallel_state(),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    asymmetric = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.02),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )

    symmetric_currents = dict(symmetric.end_cell_current_by_cell_id)
    asymmetric_currents = dict(asymmetric.end_cell_current_by_cell_id)
    one_rc_low_res = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.005),
        one_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    one_rc_high_res = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.02),
        one_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm",
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    two_rc_low_res = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.005),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    two_rc_high_res = battery_circuit._simulate_battery_circuit_current_profile(
        _asymmetric_parallel_pack_state(link_resistance_ohm=0.02),
        two_rc_model,
        profile_segments=_profile_segments(battery_circuit, (60.0, 5.0)),
        required_step_index=60,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_ecm_2rc",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )

    assert symmetric.is_feasible is True
    assert symmetric_currents[0] == pytest.approx(symmetric_currents[2], rel=1.0e-5, abs=1.0e-5)
    assert asymmetric_currents[0] > asymmetric_currents[1]
    assert one_rc_low_res.pack_terminal_voltage_end > one_rc_high_res.pack_terminal_voltage_end
    assert two_rc_low_res.pack_terminal_voltage_end > two_rc_high_res.pack_terminal_voltage_end


@pytest.mark.pybamm_real
def test_pybamm_direct_mode_runs_for_ideal_series_parallel_pack() -> None:
    evaluation = evaluate_battery_circuit(
        state=_two_cell_series_state(),
        requirements=_relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.0, minimum_current_a=1.0),
        load_cell_model=_static_cell_model,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_direct",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )

    assert evaluation.is_feasible is True
    assert evaluation.cell_model_mode == "pybamm_direct"
    assert evaluation.cell_model_source == "pybamm_spm_direct"
    assert evaluation.pack_terminal_voltage_end is not None
    assert evaluation.delivered_capacity_ah is not None


@pytest.mark.pybamm_real
def test_pybamm_direct_mode_supports_lumped_thermal_feedback() -> None:
    baseline = evaluate_battery_circuit(
        state=_two_cell_series_state(),
        requirements=_relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.5, minimum_current_a=5.0),
        load_cell_model=_static_cell_model,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_direct",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="isothermal",
            ambient_temp_c=25.0,
        ),
    )
    lumped = evaluate_battery_circuit(
        state=_two_cell_series_state(),
        requirements=_relaxed_requirements(target_voltage_v=7.4, minimum_capacity_ah=1.5, minimum_current_a=5.0),
        load_cell_model=_static_cell_model,
        backend_config=BatteryBackendConfig(
            cell_model_mode="pybamm_direct",
            parameterization=BatteryParameterization(parameter_set="Marquis2019"),
            thermal_mode="lumped",
            ambient_temp_c=25.0,
        ),
    )

    assert baseline.is_feasible is True
    assert lumped.is_feasible is True
    assert lumped.end_cell_temperature_c is not None
    assert lumped.max_cell_temperature_c is not None
    assert lumped.end_cell_temperature_c > baseline.end_cell_temperature_c
    assert lumped.max_cell_temperature_c >= lumped.end_cell_temperature_c
