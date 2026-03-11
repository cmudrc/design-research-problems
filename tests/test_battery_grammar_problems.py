from __future__ import annotations

from dataclasses import fields

from design_research_problems import GrammarProblem, get_problem
from design_research_problems.problems._domains.battery_tier_metrics import BatteryTierMetrics
from design_research_problems.problems.grammar import (
    Battery18650Tier1SeriesParallelGrammarProblem,
    Battery18650Tier2LayoutGrammarProblem,
    Battery18650Tier3TopologyGrammarProblem,
    Battery18650Tier4ThermalGrammarProblem,
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


def test_tiered_battery_grammars_are_registered_and_share_metric_contract() -> None:
    cases = (
        ("battery_18650_t1_series_parallel_grammar", Battery18650Tier1SeriesParallelGrammarProblem),
        ("battery_18650_t2_layout_grammar", Battery18650Tier2LayoutGrammarProblem),
        ("battery_18650_t3_topology_grammar", Battery18650Tier3TopologyGrammarProblem),
        ("battery_18650_t4_thermal_grammar", Battery18650Tier4ThermalGrammarProblem),
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
    t2 = get_problem("battery_18650_t2_layout_grammar")
    t4 = get_problem("battery_18650_t4_thermal_grammar")
    t2_state = t2.initial_state()
    t4_state = t4.initial_state()
    assert isinstance(t2_state, tuple)
    assert isinstance(t4_state, tuple)
    assert len(t2_state) < len(t4_state)


def test_tiered_battery_grammar_evaluation_is_deterministic_for_initial_state() -> None:
    for problem_id in (
        "battery_18650_t1_series_parallel_grammar",
        "battery_18650_t2_layout_grammar",
        "battery_18650_t3_topology_grammar",
        "battery_18650_t4_thermal_grammar",
    ):
        problem = get_problem(problem_id)
        state = problem.initial_state()
        first = problem.evaluate(state)
        second = problem.evaluate(state)
        assert first == second
