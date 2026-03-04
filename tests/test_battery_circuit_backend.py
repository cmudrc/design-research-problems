from __future__ import annotations

from types import SimpleNamespace

import pytest

from design_research_problems import MissingOptionalDependencyError
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
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
            ),
            BatteryConnection(
                connection_id=1,
                from_terminal_id=1,
                to_terminal_id=3,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
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
            ),
            BatteryConnection(
                connection_id=1,
                from_terminal_id=0,
                to_terminal_id=4,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
            ),
            BatteryConnection(
                connection_id=2,
                from_terminal_id=3,
                to_terminal_id=5,
                resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
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
