from __future__ import annotations

from dataclasses import fields

import pytest

from design_research_problems import GrammarProblem, get_problem
from design_research_problems.problems._domains.battery_benchmark import BatteryEvaluationMode
from design_research_problems.problems._domains.battery_cell_model import BatteryCellModel, BatteryThermalPriors
from design_research_problems.problems._domains.battery_tier_metrics import BatteryTierMetrics
from design_research_problems.problems.grammar import (
    Battery18650T1RectangularSurrogateGrammarProblem,
    Battery18650T2PoseSurrogateGrammarProblem,
    Battery18650T3ATopologySurrogateGrammarProblem,
    Battery18650T3BNetlistExplicitGrammarProblem,
    Battery18650T4ThermalHybridGrammarProblem,
)
from design_research_problems.problems.optimization import (
    Battery18650T3ATopologySurrogateOptimizationProblem,
)

_CORE_METRIC_KEYS = {
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

_FULL_METRIC_KEYS = {field.name for field in fields(BatteryTierMetrics)}


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


@pytest.fixture(autouse=True)
def _patch_battery_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems import _battery_adapters
    from design_research_problems.problems._domains import battery_circuit
    from design_research_problems.problems.grammar import _battery_problem_base
    from design_research_problems.problems.optimization import _battery_tiers

    monkeypatch.setattr(_battery_problem_base, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_tiers, "load_18650_cell_model", lambda *args, **kwargs: _static_cell_model())
    monkeypatch.setattr(_battery_adapters, "load_18650_cell_model", lambda config=None: _static_cell_model())
    monkeypatch.setattr(_battery_adapters, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
    monkeypatch.setattr(battery_circuit, "load_battery_cell_model", lambda config=None: _static_cell_model())
    monkeypatch.setattr(battery_circuit, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
    monkeypatch.setattr(_battery_tiers, "load_battery_thermal_priors", lambda config=None: _static_thermal_priors())
    monkeypatch.setattr(_battery_tiers, "load_18650_thermal_priors", _static_thermal_priors)


def test_tiered_battery_grammars_are_registered_and_share_metric_contract() -> None:
    cases = (
        ("battery_18650_t1_rectangular_surrogate_grammar", Battery18650T1RectangularSurrogateGrammarProblem),
        ("battery_18650_t2_pose_surrogate_grammar", Battery18650T2PoseSurrogateGrammarProblem),
        ("battery_18650_t3a_topology_surrogate_grammar", Battery18650T3ATopologySurrogateGrammarProblem),
        ("battery_18650_t3b_netlist_explicit_2rc_grammar", Battery18650T3BNetlistExplicitGrammarProblem),
        ("battery_18650_t3b_netlist_explicit_grammar", Battery18650T3BNetlistExplicitGrammarProblem),
        ("battery_18650_t4_thermal_hybrid_grammar", Battery18650T4ThermalHybridGrammarProblem),
    )
    for problem_id, expected_type in cases:
        problem = get_problem(problem_id)
        assert isinstance(problem, GrammarProblem)
        assert isinstance(problem, expected_type)

        state = problem.initial_state()
        transitions = problem.enumerate_transitions(state)
        evaluation = problem.evaluate(state)

        assert isinstance(evaluation, BatteryTierMetrics)
        assert set(evaluation.as_dict()) == _CORE_METRIC_KEYS
        assert set(evaluation.__dict__) == _FULL_METRIC_KEYS
        assert isinstance(transitions, tuple)


def test_tiered_battery_grammar_vector_state_dimensions_increase() -> None:
    t2 = get_problem("battery_18650_t2_pose_surrogate_grammar")
    t4 = get_problem("battery_18650_t4_thermal_hybrid_grammar")
    t2_state = t2.initial_state()
    t4_state = t4.initial_state()
    assert isinstance(t2_state, tuple)
    assert isinstance(t4_state, tuple)
    assert len(t2_state) < len(t4_state)


def test_tiered_battery_grammar_evaluation_is_deterministic_for_initial_state() -> None:
    for problem_id in (
        "battery_18650_t1_rectangular_surrogate_grammar",
        "battery_18650_t2_pose_surrogate_grammar",
        "battery_18650_t3a_topology_surrogate_grammar",
        "battery_18650_t3b_netlist_explicit_2rc_grammar",
        "battery_18650_t3b_netlist_explicit_grammar",
        "battery_18650_t4_thermal_hybrid_grammar",
    ):
        problem = get_problem(problem_id)
        state = problem.initial_state()
        first = problem.evaluate(state)
        second = problem.evaluate(state)
        assert first == second


def test_public_battery_grammar_problem_cards_and_modes() -> None:
    cases = (
        (
            "battery_18650_t1_rectangular_surrogate_grammar",
            "rectangular",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t2_pose_surrogate_grammar",
            "pose_layout",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3a_topology_surrogate_grammar",
            "topology_allocation",
            "analytic_surrogate",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3b_netlist_explicit_2rc_grammar",
            "explicit_netlist",
            "explicit_circuit",
            ("explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t3b_netlist_explicit_grammar",
            "explicit_netlist",
            "explicit_circuit",
            ("explicit_circuit", "hybrid_thermal"),
        ),
        (
            "battery_18650_t4_thermal_hybrid_grammar",
            "thermal_topology",
            "hybrid_thermal",
            ("analytic_surrogate", "explicit_circuit", "hybrid_thermal"),
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


def test_t3a_surrogate_grammar_and_optimizer_share_metrics() -> None:
    grammar_problem = get_problem("battery_18650_t3a_topology_surrogate_grammar")
    optimization_problem = get_problem("battery_18650_t3a_topology_surrogate_opt")
    assert isinstance(grammar_problem, Battery18650T3ATopologySurrogateGrammarProblem)
    assert isinstance(optimization_problem, Battery18650T3ATopologySurrogateOptimizationProblem)

    state = grammar_problem.initial_state()
    vector = optimization_problem.generate_initial_solution()
    assert state == tuple(float(value) for value in vector)

    grammar_metrics = grammar_problem.evaluate(state)
    optimization_metrics = optimization_problem._metrics_from_variables(vector)
    assert grammar_metrics.as_dict() == pytest.approx(optimization_metrics.as_dict())

    grammar_provenance = grammar_problem.evaluation_provenance(state)
    assert grammar_provenance.representation_mode == "topology_allocation"
    assert grammar_provenance.evaluation_mode == "analytic_surrogate"


def test_public_battery_grammars_reject_unsupported_evaluation_modes() -> None:
    t3b = get_problem("battery_18650_t3b_netlist_explicit_grammar")
    with pytest.raises(ValueError, match="Unsupported battery evaluation_mode"):
        type(t3b)(
            metadata=t3b.metadata,
            statement_markdown=t3b.statement_markdown,
            resource_bundle=t3b.resource_bundle,
            requirements=t3b.requirements,
            max_cell_count=t3b.max_cell_count,
            backend_config=t3b.backend_config,
            cooling_coefficient_w_per_m2k=t3b.cooling_coefficient_w_per_m2k,
            passive_cooling_w_per_k=t3b.passive_cooling_w_per_k,
            ambient_temperature_c=t3b.ambient_temperature_c,
            load_current_a=t3b.load_current_a,
            thermal_model=t3b.thermal_model,
            thermal_neighbor_clearance_mm=t3b.thermal_neighbor_clearance_mm,
            thermal_contact_decay_mm=t3b.thermal_contact_decay_mm,
            thermal_contact_resistance_k_per_w=t3b.thermal_contact_resistance_k_per_w,
            thermal_flow_shadowing_factor=t3b.thermal_flow_shadowing_factor,
            thermal_airflow_axis=t3b.thermal_airflow_axis,
            thermal_reference_soc=t3b.thermal_reference_soc,
            evaluation_mode=BatteryEvaluationMode.ANALYTIC_SURROGATE.value,
        )


def test_manifest_backed_2rc_grammar_variant_reports_backend_provenance() -> None:
    problem = get_problem("battery_18650_t3b_netlist_explicit_2rc_grammar")
    state = problem.initial_state()
    provenance = problem.evaluation_provenance(state)
    assert provenance.representation_mode == "explicit_netlist"
    assert provenance.evaluation_mode == "explicit_circuit"
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
