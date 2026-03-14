from __future__ import annotations

import sys
import warnings
from itertools import islice
from types import ModuleType
from typing import cast

import numpy
import pytest
from gmpb import GMPBConfig

from design_research_problems import (
    ComputableProblem,
    DecisionEvaluation,
    DecisionProblem,
    GrammarProblem,
    GrammarTransition,
    MissingOptionalDependencyError,
    OptimizationEvaluation,
    OptimizationProblem,
    Problem,
    ProblemEvaluationError,
    ProblemKind,
    get_problem,
    list_problems,
)
from design_research_problems.problems import DecisionOption
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
from design_research_problems.problems.optimization import (
    BatteryGridSizingProblem,
    GMPBOptimizationProblem,
    PlanarTrussEngineeringOptimizationProblem,
    SpaceTrussEngineeringOptimizationProblem,
)
from design_research_problems.problems.optimization._pill import _pill_area, _pill_volume

MSEVAL_IDS = (
    "decision_mseval_kitchen_utensil_grip_corrosion_resistant",
    "decision_mseval_kitchen_utensil_grip_high_strength",
    "decision_mseval_kitchen_utensil_grip_lightweight",
    "decision_mseval_kitchen_utensil_grip_resistant_to_heat",
    "decision_mseval_safety_helmet_corrosion_resistant",
    "decision_mseval_safety_helmet_high_strength",
    "decision_mseval_safety_helmet_lightweight",
    "decision_mseval_safety_helmet_resistant_to_heat",
    "decision_mseval_spacecraft_component_corrosion_resistant",
    "decision_mseval_spacecraft_component_high_strength",
    "decision_mseval_spacecraft_component_lightweight",
    "decision_mseval_spacecraft_component_resistant_to_heat",
    "decision_mseval_underwater_component_corrosion_resistant",
    "decision_mseval_underwater_component_high_strength",
    "decision_mseval_underwater_component_lightweight",
    "decision_mseval_underwater_component_resistant_to_heat",
)


def test_list_problems_returns_seed_problem_ids() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    assert list_problems() == tuple(entry.problem_id for entry in registry.list())


def test_registry_entries_filter_by_kind() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    decision_kinds = registry.by_kind(ProblemKind.DECISION)
    decision_ids = [entry.problem_id for entry in decision_kinds]
    assert len(decision_ids) == 17
    assert "decision_laptop_design_profit_maximization" in decision_ids
    assert set(MSEVAL_IDS).issubset(decision_ids)
    kinds = registry.by_kind(ProblemKind.TEXT)
    text_ids = [entry.problem_id for entry in kinds]
    assert len(text_ids) == 70
    assert "ideation_accessible_drinking_fountain" in text_ids
    assert "ideation_dark_hour_safety" in text_ids
    assert "ideation_forest_fire_detection" in text_ids
    assert "ideation_public_belongings_security" in text_ids
    assert "ideation_wheelchair_peach_picking" in text_ids
    assert registry.feature_flags("ideation_peanut_shelling_fu_cagan_kotovsky_2010") == (
        "citation-backed",
        "human-subjects-ready",
        "ideation-friendly",
        "prompt-packet",
        "statement-markdown",
    )
    assert registry.capabilities("ideation_peanut_shelling_fu_cagan_kotovsky_2010") == (
        "citation-backed",
        "prompt-packet",
        "statement-markdown",
    )
    assert registry.study_suitability("ideation_peanut_shelling_fu_cagan_kotovsky_2010") == (
        "human-subjects-ready",
        "ideation-friendly",
    )
    optimization_kinds = registry.by_kind(ProblemKind.OPTIMIZATION)
    optimization_ids = [entry.problem_id for entry in optimization_kinds]
    assert len(optimization_ids) == 10
    assert "battery_pack_18650_open_ended_capacity_max" in optimization_ids
    assert "battery_pack_18650_series_parallel_cost_min" in optimization_ids
    assert "gmpb_default_dynamic_min" in optimization_ids
    assert "planar_truss_span_mass_min" in optimization_ids
    assert "planar_truss_span_deflection_min" in optimization_ids
    assert "planar_truss_span_fos_max" in optimization_ids
    assert "space_truss_span_mass_min" in optimization_ids
    assert "planar_truss_span_member_count_min" not in optimization_ids
    assert "planar_truss_span_total_length_min" not in optimization_ids
    mcp_kinds = registry.by_kind(ProblemKind.MCP)
    mcp_ids = [entry.problem_id for entry in mcp_kinds]
    assert mcp_ids == ["mcp_build123d_parametric_mounting_bracket"]


def test_registry_exposes_aggregated_feature_flags_by_kind() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    grouped = registry.kind_feature_flags()
    assert grouped[ProblemKind.DECISION] == (
        "bounded-variables",
        "citation-backed",
        "statement-markdown",
    )
    assert grouped[ProblemKind.TEXT] == (
        "citation-backed",
        "human-subjects-ready",
        "ideation-friendly",
        "intervention-ready",
        "prompt-packet",
        "requirements-study-ready",
        "statement-markdown",
        "variety-study-ready",
    )
    assert grouped[ProblemKind.OPTIMIZATION] == (
        "baseline-solver",
        "bounded-variables",
        "citation-backed",
        "equality-constraint",
        "external-adapter",
        "optional-evaluator",
        "statement-markdown",
    )
    assert grouped[ProblemKind.GRAMMAR] == (
        "discrete-actions",
        "external-adapter",
        "optional-evaluator",
        "serializable-state",
        "statement-markdown",
    )
    assert grouped[ProblemKind.MCP] == (
        "external-adapter",
        "statement-markdown",
    )


def test_text_problem_renders_statement_and_citation() -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    assert isinstance(problem, Problem)
    packet = problem.render_brief()
    assert packet.count("# Device to shell peanuts") == 1
    assert "Fu, Cagan, and Kotovsky (2010)." in packet
    assert "Must remove the shell with minimal damage to the peanuts." in packet
    assert "## BibTeX" not in packet
    assert problem.metadata.has_feature("human subjects ready") is True
    assert hasattr(problem, "assets") is False


def test_text_problem_can_render_summary_and_raw_citations() -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    packet = problem.render_brief(citation_mode="summary+raw")
    assert "## Sources" in packet
    assert "## BibTeX" in packet
    assert "@article{fu2010design," in packet


def test_new_2025_ideation_problem_renders_statement_and_citation() -> None:
    problem = get_problem("ideation_dark_hour_safety")
    assert isinstance(problem, Problem)
    packet = problem.render_brief()
    assert packet.count("# Dark-Hour Safety") == 1
    assert "Design a way to support safety in the dark morning" in packet
    assert "Wojciechowski, Olagoke, Ng, Wacnik, and Kramer (2025)." in packet


def test_decision_problem_exposes_structured_brief() -> None:
    problem = get_problem("decision_laptop_design_profit_maximization")
    assert isinstance(problem, DecisionProblem)
    assert problem.candidate_kind == "discrete-option"
    assert problem.decision_variables[0] == "LCD size x1 in [10, 17] inches"
    assert (
        problem.objectives[0]
        == "Maximize predicted market share over the explicit conjoint option set as an equal-margin profit proxy."
    )
    assert (
        problem.constraints[0]
        == "Expose the five continuous-design constraints from Equations (8) through (12) as typed formulas."
    )

    brief = problem.render_brief(citation_mode="summary+raw")
    assert "## Context" in brief
    assert "## Decision Variables" in brief
    assert "## Objectives" in brief
    assert "## Constraints" in brief
    assert "## Objective Model" in brief
    assert "## Constraint Equations" in brief
    assert "## Option Space" in brief
    assert "Total discrete options: 3,125" in brief
    assert "## Assumptions" in brief
    assert "## BibTeX" in brief
    assert "Shiau, Tseng, Heutchy, and Michalek (2007)." in brief


def test_mseval_decision_problem_exposes_empirical_choice_benchmarks() -> None:
    problem = get_problem("decision_mseval_kitchen_utensil_grip_lightweight")
    assert isinstance(problem, DecisionProblem)
    assert problem.candidate_kind == "empirical-choice"
    assert tuple(problem.iter_candidates()) == (
        "steel",
        "aluminium",
        "titanium",
        "glass",
        "wood",
        "thermoplastic",
        "elastomer",
        "thermoset",
        "composite",
    )
    assert problem.candidate_count == len(problem.choice_benchmarks)

    steel = problem.evaluate("steel")
    assert isinstance(steel, DecisionEvaluation)
    assert steel.candidate_kind == "empirical-choice"
    assert steel.candidate == "steel"
    assert steel.candidate_label == "Steel"
    assert steel.choice_key == "steel"
    assert steel.choice_label == "Steel"
    assert steel.response_count == 67
    assert steel.objective_metric == "top-choice-share"
    assert steel.top_choice_share == pytest.approx(0.004146, abs=1e-6)
    assert steel.mean_rating == pytest.approx(2.955224, abs=1e-6)
    assert steel.median_rating == pytest.approx(3.0)
    assert steel.std_rating == pytest.approx(2.54316, abs=1e-6)
    assert problem.metadata.citations[0].raw_text.startswith("@misc{jain2024msevaldatasetmaterialselection,")

    assert problem.evaluate("Steel") == steel
    assert problem.best_evaluation().choice_key == "composite"
    assert problem.best_evaluation(metric="mean-rating").choice_key == "composite"
    assert problem.rank_evaluations(metric="median-rating")[0].objective_metric == "median-rating"

    brief = problem.render_brief()
    assert "## Choices" in brief
    assert "## Empirical Benchmark" in brief

    with pytest.raises(ValueError):
        problem.evaluate("ceramic")

    with pytest.raises(TypeError):
        problem.evaluate(DecisionOption(values={"z1": 10.4}))


def test_decision_problem_exposes_typed_option_space_and_evaluator() -> None:
    problem = get_problem("decision_laptop_design_profit_maximization")
    assert isinstance(problem, DecisionProblem)
    assert problem.candidate_kind == "discrete-option"

    assert len(problem.decision_variable_specs) == 6
    assert problem.decision_variable_specs[0].symbol == "x1"
    assert problem.decision_variable_specs[0].unit == "inch"
    assert problem.decision_variable_specs[0].lower_bound == 10.0
    assert problem.decision_variable_specs[0].upper_bound == 17.0
    assert problem.decision_variable_specs[4].symbol == "x5"
    assert problem.decision_variable_specs[4].unit is None
    assert problem.decision_variable_specs[-1].symbol == "p"
    assert problem.decision_variable_specs[-1].unit == "$100"

    assert len(problem.option_factors) == 5
    assert problem.option_factors[0].key == "z1"
    assert problem.option_factors[0].levels == (10.4, 12.1, 14.1, 15.4, 17.0)
    assert problem.option_factors[0].part_worths == (-1.076, -0.509, 0.231, 0.583, 0.381)
    assert problem.option_factors[-1].key == "z5"
    assert problem.option_factors[-1].levels == (7.5, 10.0, 12.5, 15.0, 20.0)
    assert problem.option_factors[-1].part_worths == (0.659, 0.314, 0.279, -0.018, -1.624)

    assert len(problem.competitor_profiles) == 10
    assert problem.competitor_profiles[0].name == "U2"
    assert tuple(problem.competitor_profiles[0].values) == ("z1", "z2", "z3", "z4", "z5")

    assert len(problem.objective_specs) == 1
    assert problem.objective_specs[0].sense == "maximize"
    assert problem.objective_specs[0].domain == "discrete-option"
    assert problem.objective_specs[0].executable is True

    assert len(problem.constraint_specs) == 5
    assert problem.constraint_specs[0].key == "g1"
    assert problem.constraint_specs[0].domain == "continuous-design"
    assert problem.constraint_specs[0].executable is False

    assert problem.option_count == 3125
    assert problem.candidate_count == 3125

    candidates_iter = problem.iter_candidates()
    first_option = next(candidates_iter)
    assert isinstance(first_option, DecisionOption)
    last_option: DecisionOption | None = None
    for option in problem.iter_candidates():
        assert isinstance(option, DecisionOption)
        last_option = option
    assert last_option is not None
    assert first_option.values == {"z1": 10.4, "z2": 0.75, "z3": 1.0, "z4": 2.5, "z5": 7.5}
    assert last_option.values == {"z1": 17.0, "z2": 1.75, "z3": 8.0, "z4": 10.0, "z5": 20.0}

    sample_options = [cast(DecisionOption, option) for option in islice(problem.iter_candidates(), 3)]
    assert all(tuple(option.values) == ("z1", "z2", "z3", "z4", "z5") for option in sample_options)

    evaluation = problem.evaluate(first_option)
    assert isinstance(evaluation, DecisionEvaluation)
    assert evaluation.candidate_kind == "discrete-option"
    assert evaluation.candidate == first_option
    assert evaluation.candidate_label == "z1=10.4, z2=0.75, z3=1, z4=2.5, z5=7.5"
    assert evaluation.objective_metric == "market_share_proxy"
    assert evaluation.option == first_option
    assert evaluation.choice_key is None
    assert evaluation.choice_label is None
    assert numpy.isfinite(evaluation.utility)
    assert 0.0 < evaluation.predicted_share < 1.0
    assert evaluation.expected_demand_units == pytest.approx(1_600_000 * evaluation.predicted_share)
    assert evaluation.objective_value == evaluation.predicted_share

    best = problem.best_evaluation()
    assert best == problem.rank_evaluations()[0]

    with pytest.raises(ProblemEvaluationError):
        problem.best_evaluation(metric="mean-rating")

    with pytest.raises(TypeError):
        problem.evaluate("steel")


def test_non_text_problems_are_computable() -> None:
    problem_ids = (
        "decision_laptop_design_profit_maximization",
        "decision_mseval_kitchen_utensil_grip_lightweight",
        "battery_pack_18650_open_ended_capacity_max",
        "battery_pack_18650_series_parallel_cost_min",
        "iot_home_cooling_system_design",
        "pill_capsule_min_area",
        "planar_truss_span",
        "truss_analysis_program_design",
    )
    for problem_id in problem_ids:
        assert isinstance(get_problem(problem_id), ComputableProblem)


def test_registry_search_filters_by_feature_flags() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    matches = registry.search(feature_flags=("baseline solver",))
    assert [entry.problem_id for entry in matches] == [
        "battery_pack_18650_open_ended_capacity_max",
        "battery_pack_18650_series_parallel_cost_min",
        "gmpb_default_dynamic_min",
        "moneymaker_hip_pump_cost_min",
        "pill_capsule_min_area",
        "planar_truss_span_deflection_min",
        "planar_truss_span_fos_max",
        "planar_truss_span_mass_min",
        "space_truss_span_mass_min",
        "treadle_pump_ide_material_min",
    ]
    text_matches = registry.search(
        kind=ProblemKind.TEXT,
        capabilities=("citation-backed",),
        study_suitability=("intervention-ready",),
    )
    assert [entry.problem_id for entry in text_matches] == [
        "ideation_injured_athlete_campus_mobility",
        "ideation_one_handed_lidded_container_opening",
        "ideation_public_belongings_security",
        "ideation_remote_village_rainwater_access",
        "ideation_snow_transport_for_novices",
    ]


def test_pill_helpers_return_expected_positive_values() -> None:
    assert _pill_volume(0.1, 0.2) > 0.0
    assert _pill_area(0.1, 0.2) > 0.0


def _build_feasible_battery_state() -> object:
    problem = get_problem("battery_pack_18650_series_parallel")
    state = problem.initial_state()
    state = problem.add_series_stage(state, placements=((1, 0, 0),))
    state = problem.add_series_stage(state, placements=((2, 0, 0),))
    state = problem.add_series_stage(state, placements=((3, 0, 0),))
    state = problem.add_parallel_branch(state, placements=((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0)))
    state = problem.add_parallel_branch(state, placements=((0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0)))
    return state


def test_generic_grammar_family_api_supports_multiple_problems(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_structural_fake_truss(monkeypatch)
    for problem_id in (
        "battery_pack_18650_series_parallel",
        "iot_home_cooling_system_design",
        "planar_truss_span",
        "space_truss_span",
        "truss_analysis_program_design",
    ):
        problem = get_problem(problem_id)
        assert isinstance(problem, GrammarProblem)
        state = problem.initial_state()
        transitions = problem.enumerate_transitions(state)
        next_states = problem.enumerate_next_states(state)
        assert next_states == tuple(transition.next_state for transition in transitions)
        evaluation = problem.evaluate(state)
        assert hasattr(evaluation, "is_feasible")


def test_battery_grid_sizing_problem_uses_optimization_family_api(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_grid as battery_grid

    monkeypatch.setattr(battery_grid, "load_18650_cell_model", _fake_cell_model)

    problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, BatteryGridSizingProblem)
    assert hasattr(problem, "initial_state") is False
    assert hasattr(problem, "add_series_stage") is False

    initial = problem.generate_initial_solution()
    assert initial.shape == (2,)
    evaluation = problem.evaluate(initial)
    assert isinstance(evaluation, OptimizationEvaluation)

    result = problem.solve(maxiter=25)
    assert result.x.shape == (2,)
    assert isinstance(result.fun, float)


def test_gmpb_problem_uses_optimization_family_api() -> None:
    problem = get_problem("gmpb_default_dynamic_min")
    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, GMPBOptimizationProblem)

    initial = problem.generate_initial_solution(seed=7)
    assert initial.shape == (5,)
    assert numpy.all(initial >= problem.bounds.lb)
    assert numpy.all(initial <= problem.bounds.ub)

    starting_environment = problem.current_environment_index()
    starting_evaluations = problem.evaluations_in_environment()
    evaluation = problem.evaluate(initial)
    assert isinstance(evaluation, OptimizationEvaluation)
    assert evaluation.is_feasible is True
    assert evaluation.total_constraint_violation == 0.0
    assert evaluation.max_constraint_violation == 0.0
    assert problem.current_environment_index() == starting_environment
    assert problem.evaluations_in_environment() == starting_evaluations + 1

    state = problem.current_state()
    assert state.t == problem.current_environment_index()
    assert len(state.components) == problem.config.m

    problem.reset(seed=7)
    assert problem.current_environment_index() == 0
    assert problem.evaluations_in_environment() == 0

    result = problem.solve(seed=3, maxiter=6)
    assert result.x.shape == (5,)
    assert numpy.isfinite(result.fun)
    assert result.nfev == 6
    assert "dynamic random-search baseline" in result.message


def test_gmpb_problem_auto_steps_after_change_frequency() -> None:
    metadata = get_problem("gmpb_default_dynamic_min").metadata
    problem = GMPBOptimizationProblem(
        metadata=metadata,
        config=GMPBConfig(d=2, m=3, change_frequency=2, auto_step=True),
        seed=11,
    )

    candidate = numpy.zeros(2, dtype=float)
    assert problem.current_environment_index() == 0
    problem.evaluate(candidate)
    assert problem.current_environment_index() == 0
    problem.evaluate(candidate)
    assert problem.current_environment_index() == 1
    assert problem.evaluations_in_environment() == 0

    problem.reset(seed=11)
    assert problem.current_environment_index() == 0
    assert problem.evaluations_in_environment() == 0


def test_battery_grid_and_grammar_share_series_parallel_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_problem_base as battery_problem_base
    from design_research_problems.problems.optimization import _battery_grid as battery_grid

    monkeypatch.setattr(battery_problem_base, "load_18650_cell_model", _fake_cell_model)
    monkeypatch.setattr(battery_grid, "load_18650_cell_model", _fake_cell_model)

    optimization_problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    grammar_problem = get_problem("battery_pack_18650_series_parallel")
    assert isinstance(optimization_problem, BatteryGridSizingProblem)
    assert isinstance(grammar_problem, GrammarProblem)

    candidate = numpy.array([4.0, 4.0], dtype=float)
    state = optimization_problem.decode_candidate(candidate)
    assert state == _build_feasible_battery_state()
    assert grammar_problem.evaluate(state) == optimization_problem._evaluation_from_variables(candidate)


def test_truss_engineering_optimizers_use_optimization_family_api(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_structural_fake_truss(monkeypatch)

    for problem_id, expected_type in (
        ("planar_truss_span_mass_min", PlanarTrussEngineeringOptimizationProblem),
        ("planar_truss_span_deflection_min", PlanarTrussEngineeringOptimizationProblem),
        ("planar_truss_span_fos_max", PlanarTrussEngineeringOptimizationProblem),
        ("space_truss_span_mass_min", SpaceTrussEngineeringOptimizationProblem),
    ):
        problem = get_problem(problem_id)
        assert isinstance(problem, OptimizationProblem)
        assert isinstance(problem, expected_type)
        assert hasattr(problem, "enumerate_transitions") is False

        initial = problem.generate_initial_solution()
        assert initial.ndim == 1
        assert initial.shape[0] > 0

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            evaluation = problem.evaluate(initial)
            result = problem.solve(maxiter=64)
        assert isinstance(evaluation, OptimizationEvaluation)
        runtime_warnings = [item for item in caught if issubclass(item.category, RuntimeWarning)]
        assert runtime_warnings == []

        assert result.x.shape == initial.shape
        assert isinstance(result.fun, float)
        assert result.success is (problem.max_constraint_violation(result.x) <= 1e-9)

        state = problem.decode_candidate(result.x)
        assert len(state.members) >= 0


def test_domain_backends_remain_importable_from_legacy_and_new_paths() -> None:
    from design_research_problems.problems._domains.battery_circuit import (
        BatteryCircuitState as DomainBatteryCircuitState,
    )
    from design_research_problems.problems._domains.planar_truss import PlanarTrussState as DomainPlanarTrussState
    from design_research_problems.problems._domains.space_truss import SpaceTrussState as DomainSpaceTrussState
    from design_research_problems.problems.grammar._battery_circuit import (
        BatteryCircuitState as LegacyBatteryCircuitState,
    )
    from design_research_problems.problems.grammar._planar_truss import PlanarTrussState as LegacyPlanarTrussState
    from design_research_problems.problems.grammar._space_truss import SpaceTrussState as LegacySpaceTrussState

    assert DomainBatteryCircuitState is LegacyBatteryCircuitState
    assert DomainPlanarTrussState is LegacyPlanarTrussState
    assert DomainSpaceTrussState is LegacySpaceTrussState


def _fake_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
    )


def _build_feasible_open_battery_state() -> object:
    problem = get_problem("battery_pack_18650_open_ended")
    state = problem.initial_state()
    stage_input_terminal_id = state.pack_negative_terminal_id
    stage_output_terminal_id = state.pack_positive_terminal_id
    for branch_index in range(1, 4):
        state = problem.add_cell(
            state,
            x=0,
            y=branch_index,
            z=0,
            connect_negative_to_terminal_id=stage_input_terminal_id,
            connect_positive_to_terminal_id=stage_output_terminal_id,
        )

    for stage_index in range(1, 4):
        previous_stage_output_terminal_id = stage_output_terminal_id
        state = problem.add_cell(
            state,
            x=stage_index,
            y=0,
            z=0,
            connect_negative_to_terminal_id=previous_stage_output_terminal_id,
            use_positive_as_pack_terminal=True,
        )
        stage_output_terminal_id = state.pack_positive_terminal_id
        for branch_index in range(1, 4):
            state = problem.add_cell(
                state,
                x=stage_index,
                y=branch_index,
                z=0,
                connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                connect_positive_to_terminal_id=stage_output_terminal_id,
            )
    return state


def test_battery_problem_state_and_rule_methods_are_validated() -> None:
    problem = get_problem("battery_pack_18650_series_parallel")
    assert isinstance(problem, GrammarProblem)
    assert hasattr(problem, "apply_action") is False
    assert hasattr(problem, "enumerate_actions") is False
    state = problem.initial_state()
    assert state.series_count == 1
    assert state.parallel_count == 1
    assert len(state.cells) == 1

    transitions = problem.enumerate_transitions(state)
    assert all(isinstance(transition, GrammarTransition) for transition in transitions)
    assert any(transition.rule_name == "move_cell" for transition in transitions)

    state = problem.move_cell(state, cell_id=0, x=1, y=0, z=0)
    assert state.cells[0].x == 1

    state = problem.add_series_stage(state, placements=((0, 0, 0),))
    assert state.series_count == 2
    assert len(state.cells) == 2

    with pytest.raises(ValueError):
        problem.move_cell(state, cell_id=0, x=0, y=0, z=0)

    state = problem.add_parallel_branch(state, placements=((0, 1, 0), (1, 1, 0)))
    assert state.parallel_count == 2
    assert len(state.cells) == 4

    with pytest.raises(ValueError):
        problem.add_series_stage(state, placements=((2, 0, 0),))

    state = problem.remove_parallel_branch(state)
    assert state.parallel_count == 1
    assert len(state.cells) == 2

    state = problem.remove_series_stage(state)
    assert state.series_count == 1
    assert len(state.cells) == 1

    with pytest.raises(ValueError):
        problem.remove_series_stage(problem.initial_state())


def test_battery_problem_precheck_skips_pybamm(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_problem_base as battery_problem_base

    def _unexpected_load() -> BatteryCellModel:
        raise AssertionError("The effective cell model should not load when deterministic prechecks fail.")

    monkeypatch.setattr(battery_problem_base, "load_18650_cell_model", _unexpected_load)

    problem = get_problem("battery_pack_18650_series_parallel")
    evaluation = problem.evaluate(problem.initial_state())
    assert evaluation.is_feasible is False
    assert evaluation.pybamm_ran is False
    assert evaluation.cell_model_source is None
    assert evaluation.cell_model_warning is None
    assert evaluation.failure_reason == "Pack voltage does not match the required target voltage."


def test_battery_problem_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_problem_base as battery_problem_base

    def _missing_cell_model() -> BatteryCellModel:
        raise MissingOptionalDependencyError("pybamm is required")

    problem = get_problem("battery_pack_18650_series_parallel")
    state = _build_feasible_battery_state()
    monkeypatch.setattr(battery_problem_base, "load_18650_cell_model", _missing_cell_model)
    with pytest.raises(MissingOptionalDependencyError):
        problem.evaluate(state)


def test_battery_problem_evaluate_uses_fake_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_problem_base as battery_problem_base

    monkeypatch.setattr(battery_problem_base, "load_18650_cell_model", _fake_cell_model)

    problem = get_problem("battery_pack_18650_series_parallel")
    evaluation = problem.evaluate(_build_feasible_battery_state())
    assert evaluation.pybamm_ran is True
    assert evaluation.cell_model_source == "custom"
    assert evaluation.cell_model_warning is None
    assert evaluation.pybamm_feasible is True
    assert evaluation.is_feasible is True
    assert evaluation.cell_count == 16


def test_open_ended_battery_problem_state_and_rule_methods_are_validated() -> None:
    problem = get_problem("battery_pack_18650_open_ended")
    assert isinstance(problem, GrammarProblem)
    assert hasattr(problem, "apply_action") is False
    assert hasattr(problem, "enumerate_actions") is False
    state = problem.initial_state()
    assert len(state.cells) == 1
    assert len(state.connections) == 0

    transitions = problem.enumerate_transitions(state)
    assert all(isinstance(transition, GrammarTransition) for transition in transitions)
    assert any(transition.rule_name == "add_cell" for transition in transitions)

    initial_negative_terminal_id = state.pack_negative_terminal_id
    initial_positive_terminal_id = state.pack_positive_terminal_id
    state = problem.add_cell(
        state,
        x=1,
        y=0,
        z=0,
        connect_negative_to_terminal_id=initial_positive_terminal_id,
        use_positive_as_pack_terminal=True,
    )
    assert len(state.cells) == 2
    assert len(state.connections) == 1
    assert state.pack_positive_terminal_id != initial_positive_terminal_id

    with pytest.raises(ValueError):
        problem.add_cell(
            state,
            x=2,
            y=0,
            z=0,
            connect_negative_to_terminal_id=initial_positive_terminal_id,
            connect_positive_to_terminal_id=initial_positive_terminal_id,
        )

    series_cell = next(cell for cell in state.cells if cell.cell_id != 0)
    state = problem.add_cell(
        state,
        x=1,
        y=1,
        z=0,
        connect_negative_to_terminal_id=initial_positive_terminal_id,
        connect_positive_to_terminal_id=state.pack_positive_terminal_id,
    )
    assert len(state.cells) == 3
    assert len(state.connections) == 3
    parallel_cell = max(state.cells, key=lambda cell: cell.cell_id)

    state = problem.add_connection(
        state,
        from_terminal_id=initial_negative_terminal_id,
        to_terminal_id=parallel_cell.negative_terminal_id,
    )
    assert len(state.connections) == 4

    state = problem.move_cell(state, cell_id=parallel_cell.cell_id, x=1, y=2, z=0)
    moved_parallel_cell = next(cell for cell in state.cells if cell.cell_id == parallel_cell.cell_id)
    assert moved_parallel_cell.y == 2

    extra_connection_id = max(connection.connection_id for connection in state.connections)
    state = problem.remove_connection(state, connection_id=extra_connection_id)
    assert len(state.connections) == 3

    state = problem.remove_cell(state, cell_id=parallel_cell.cell_id)
    assert len(state.cells) == 2
    assert all(
        connection.from_terminal_id not in {parallel_cell.negative_terminal_id, parallel_cell.positive_terminal_id}
        and connection.to_terminal_id not in {parallel_cell.negative_terminal_id, parallel_cell.positive_terminal_id}
        for connection in state.connections
    )

    state = problem.remove_cell(state, cell_id=series_cell.cell_id)
    assert len(state.cells) == 1
    assert len(state.connections) == 0
    assert state.pack_positive_terminal_id == state.cells[0].positive_terminal_id
    assert state.pack_negative_terminal_id == state.cells[0].negative_terminal_id

    with pytest.raises(ValueError):
        problem.remove_cell(state, cell_id=state.cells[0].cell_id)


def test_open_ended_battery_problem_evaluate_uses_fake_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.grammar import _battery_problem_base as battery_problem_base

    monkeypatch.setattr(battery_problem_base, "load_18650_cell_model", _fake_cell_model)

    problem = get_problem("battery_pack_18650_open_ended")
    evaluation = problem.evaluate(_build_feasible_open_battery_state())
    assert evaluation.pybamm_ran is True
    assert evaluation.cell_model_source == "custom"
    assert evaluation.cell_model_warning is None
    assert evaluation.is_feasible is True
    assert evaluation.cell_count == 16
    assert evaluation.connection_count == 27
    assert evaluation.topology_kind == "series_parallel"


@pytest.mark.pybamm_real
def test_battery_problem_evaluates_when_pybamm_is_installed() -> None:
    problem = get_problem("battery_pack_18650_series_parallel")
    try:
        evaluation = problem.evaluate(_build_feasible_battery_state())
    except MissingOptionalDependencyError:
        pytest.skip("pybamm is not installed in this environment.")
    assert evaluation.pybamm_ran is True
    assert evaluation.cell_model_source == "pybamm_thevenin"
    assert evaluation.pybamm_pack_end_voltage is not None


def test_pill_problem_is_deterministic() -> None:
    problem = get_problem("pill_capsule_min_area")
    x1 = problem.generate_initial_solution(seed=7)
    x2 = problem.generate_initial_solution(seed=7)
    assert x1.shape == (2,)
    assert numpy.allclose(x1, x2)


def test_pill_problem_evaluate_returns_standardized_optimization_evaluation() -> None:
    problem = get_problem("pill_capsule_min_area")
    candidate = problem.generate_initial_solution(seed=5)
    evaluation = problem.evaluate(candidate)
    assert isinstance(evaluation, OptimizationEvaluation)
    assert evaluation.x.shape == (2,)
    assert evaluation.objective_value == pytest.approx(problem.objective(candidate))
    assert evaluation.total_constraint_violation == pytest.approx(problem.constraint_violation(candidate))
    assert evaluation.max_constraint_violation == pytest.approx(problem.max_constraint_violation(candidate))
    assert evaluation.is_feasible is True


def test_pill_problem_seeded_initial_solution_stays_within_bounds() -> None:
    problem = get_problem("pill_capsule_min_area")
    initial = problem.generate_initial_solution(seed=3)

    assert numpy.all(initial >= problem.bounds.lb)
    assert numpy.all(initial <= problem.bounds.ub)
    assert _pill_volume(float(initial[0]), float(initial[1])) == pytest.approx(problem.required_volume)


def test_pill_problem_clamps_infeasible_seeded_initial_solution_to_bounds() -> None:
    baseline_problem = get_problem("pill_capsule_min_area")
    problem = type(baseline_problem)(
        metadata=baseline_problem.metadata,
        statement_markdown="",
        required_volume=_pill_volume(1.0, 1.0) + 1.0,
    )
    initial = problem.generate_initial_solution(seed=3)

    assert numpy.all(initial >= problem.bounds.lb)
    assert numpy.all(initial <= problem.bounds.ub)
    assert float(initial[0]) == pytest.approx(float(problem.bounds.ub[0]))
    assert float(initial[1]) == pytest.approx(float(problem.bounds.ub[1]))


def test_pill_problem_solve_returns_feasible_manifold_solution() -> None:
    problem = get_problem("pill_capsule_min_area")
    initial = problem.generate_initial_solution(seed=1)
    result = problem.solve(initial_solution=initial)
    assert result.success is True
    assert "Converged SciPy SLSQP baseline" in result.message
    assert result.x.shape == (2,)
    assert _pill_volume(float(result.x[0]), float(result.x[1])) == pytest.approx(problem.required_volume)
    assert result.fun == pytest.approx(_pill_area(float(result.x[0]), float(result.x[1])))
    assert result.fun < problem.objective(initial)


def test_planar_truss_state_and_rule_methods_are_validated() -> None:
    problem = get_problem("planar_truss_span")
    assert isinstance(problem, GrammarProblem)
    assert hasattr(problem, "apply_action") is False
    assert hasattr(problem, "enumerate_actions") is False
    state = problem.initial_state()

    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=0, end_joint_id=0)

    transitions = problem.enumerate_transitions(state)
    assert all(isinstance(transition, GrammarTransition) for transition in transitions)
    assert any(transition.rule_name == "add_member" for transition in transitions)

    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=1)
    assert len(state.members) == 3

    state = problem.remove_member(state, member_id=1)
    assert len(state.members) == 2


def test_planar_roof_variant_initial_state_tracks_multiple_loads() -> None:
    problem = get_problem("planar_roof_truss_seven_point_asymmetric")
    state = problem.initial_state()

    assert len(state.joints) == 9
    assert len(state.additional_loads) == 6
    assert state.symmetry_axis_x is None


def test_planar_roof_symmetric_variant_enforces_mirrored_actions() -> None:
    problem = get_problem("planar_roof_truss_three_point_symmetric")
    state = problem.initial_state()
    transitions = problem.enumerate_transitions(state)

    assert any(transition.rule_name == "add_joint_pair" for transition in transitions)

    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    assert len(state.members) == 2
    edges = {tuple(sorted((member.start_joint_id, member.end_joint_id))) for member in state.members}
    assert edges == {(0, 2), (1, 4)}

    state = problem.remove_member(state, member_id=0)
    assert state.members == ()


def test_planar_truss_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    monkeypatch.setitem(sys.modules, "trussme", None)
    with pytest.raises(MissingOptionalDependencyError):
        problem.evaluate(state)


def test_planar_truss_evaluate_uses_fake_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTruss:
        def __init__(self) -> None:
            self._members = 0
            self._joints = 0
            self.mass = 12.5
            self.fos = 1.2
            self.fos_buckling = 1.4
            self.fos_yielding = 1.2
            self.deflection = 0.01

        def add_pinned_joint(self, coordinates: list[float]) -> int:
            del coordinates
            index = self._joints
            self._joints += 1
            return index

        def add_roller_joint(self, coordinates: list[float], constrained_axis: str = "y") -> int:
            del constrained_axis
            return self.add_pinned_joint(coordinates)

        def add_free_joint(self, coordinates: list[float]) -> int:
            return self.add_pinned_joint(coordinates)

        def add_out_of_plane_support(self, constrained_axis: str = "z") -> None:
            del constrained_axis

        def add_member(self, start_joint_index: int, end_joint_index: int) -> int:
            del start_joint_index, end_joint_index
            index = self._members
            self._members += 1
            return index

        def set_load(self, joint_index: int, load: list[float]) -> None:
            del joint_index, load

        def analyze(self) -> None:
            return None

    fake_module = ModuleType("trussme")
    fake_module.Truss = FakeTruss
    monkeypatch.setitem(sys.modules, "trussme", fake_module)

    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=2)
    evaluation = problem.evaluate(state)
    assert evaluation.is_feasible is True
    assert evaluation.number_of_members == 2


def test_planar_truss_unstable_state_is_infeasible(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTruss:
        def __init__(self) -> None:
            self.mass = 0.0
            self.fos = 0.0
            self.fos_buckling = 0.0
            self.fos_yielding = 0.0
            self.deflection = 0.0
            self._joints = 0

        def add_pinned_joint(self, coordinates: list[float]) -> int:
            del coordinates
            index = self._joints
            self._joints += 1
            return index

        def add_roller_joint(self, coordinates: list[float], constrained_axis: str = "y") -> int:
            del constrained_axis
            return self.add_pinned_joint(coordinates)

        def add_free_joint(self, coordinates: list[float]) -> int:
            return self.add_pinned_joint(coordinates)

        def add_out_of_plane_support(self, constrained_axis: str = "z") -> None:
            del constrained_axis

        def add_member(self, start_joint_index: int, end_joint_index: int) -> int:
            del start_joint_index, end_joint_index
            return 0

        def set_load(self, joint_index: int, load: list[float]) -> None:
            del joint_index, load

        def analyze(self) -> None:
            raise numpy.linalg.LinAlgError("singular")

    fake_module = ModuleType("trussme")
    fake_module.Truss = FakeTruss
    monkeypatch.setitem(sys.modules, "trussme", fake_module)

    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    evaluation = problem.evaluate(state)
    assert evaluation.is_feasible is False
    assert evaluation.failure_reason is not None


def test_planar_roof_truss_evaluate_applies_all_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeTruss:
        def __init__(self) -> None:
            self.mass = 10.0
            self.fos = 1.1
            self.fos_buckling = 1.1
            self.fos_yielding = 1.1
            self.deflection = 0.01
            self._joints = 0
            self.load_calls = 0

        def add_pinned_joint(self, coordinates: list[float]) -> int:
            del coordinates
            index = self._joints
            self._joints += 1
            return index

        def add_roller_joint(self, coordinates: list[float], constrained_axis: str = "y") -> int:
            del constrained_axis
            return self.add_pinned_joint(coordinates)

        def add_free_joint(self, coordinates: list[float]) -> int:
            return self.add_pinned_joint(coordinates)

        def add_out_of_plane_support(self, constrained_axis: str = "z") -> None:
            del constrained_axis

        def add_member(self, start_joint_index: int, end_joint_index: int) -> int:
            del start_joint_index, end_joint_index
            return 0

        def set_load(self, joint_index: int, load: list[float]) -> None:
            del joint_index, load
            self.load_calls += 1

        def analyze(self) -> None:
            return None

    fake_module = ModuleType("trussme")
    fake_truss = FakeTruss()
    fake_module.Truss = lambda: fake_truss
    monkeypatch.setitem(sys.modules, "trussme", fake_module)

    problem = get_problem("planar_roof_truss_seven_point_asymmetric")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    evaluation = problem.evaluate(state)

    assert evaluation.is_feasible is True
    assert fake_truss.load_calls == 7


class _StructuralFakeTruss:
    def __init__(self) -> None:
        self._joints = 0
        self._members = 0
        self.mass = 0.0
        self.fos = 0.0
        self.fos_buckling = 0.0
        self.fos_yielding = 0.0
        self.deflection = 1.0
        self.coordinates: list[tuple[float, float, float]] = []

    def add_pinned_joint(self, coordinates: list[float]) -> int:
        self.coordinates.append(tuple(float(value) for value in coordinates))
        index = self._joints
        self._joints += 1
        return index

    def add_roller_joint(self, coordinates: list[float], constrained_axis: str = "y") -> int:
        del constrained_axis
        return self.add_pinned_joint(coordinates)

    def add_free_joint(self, coordinates: list[float]) -> int:
        return self.add_pinned_joint(coordinates)

    def add_out_of_plane_support(self, constrained_axis: str = "z") -> None:
        del constrained_axis

    def add_member(self, start_joint_index: int, end_joint_index: int) -> int:
        del start_joint_index, end_joint_index
        index = self._members
        self._members += 1
        return index

    def set_load(self, joint_index: int, load: list[float]) -> None:
        del joint_index, load

    def analyze(self) -> None:
        self.mass = float(self._members)
        self.fos = 1.0 + (0.5 * self._members)
        self.fos_buckling = self.fos
        self.fos_yielding = self.fos
        self.deflection = 1.0 if self._members == 0 else 0.1


def _install_structural_fake_truss(monkeypatch: pytest.MonkeyPatch) -> _StructuralFakeTruss:
    fake_module = ModuleType("trussme")
    fake_truss = _StructuralFakeTruss()
    fake_module.Truss = lambda: fake_truss
    monkeypatch.setitem(sys.modules, "trussme", fake_module)
    return fake_truss


def test_planar_truss_engineering_optimizers_report_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    for problem_id in ("planar_truss_span_mass_min", "planar_truss_span_deflection_min", "planar_truss_span_fos_max"):
        problem = get_problem(problem_id)
        monkeypatch.setitem(sys.modules, "trussme", None)
        with pytest.raises(MissingOptionalDependencyError):
            problem.evaluate(problem.generate_initial_solution())
        monkeypatch.delitem(sys.modules, "trussme", raising=False)


def test_planar_truss_engineering_objectives_use_structural_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    for problem_id, expected_objective in (
        ("planar_truss_span_mass_min", 3.0),
        ("planar_truss_span_deflection_min", 0.1),
        ("planar_truss_span_fos_max", -2.5),
    ):
        _install_structural_fake_truss(monkeypatch)
        problem = get_problem(problem_id)
        assert isinstance(problem, PlanarTrussEngineeringOptimizationProblem)
        vector = numpy.zeros_like(problem.generate_initial_solution())
        for index, edge in enumerate(problem._candidate_edges):
            if edge in {(0, 1), (0, 2), (1, 2)}:
                vector[index] = 1.0
        evaluation = problem.evaluate(vector)
        assert evaluation.objective_value == pytest.approx(expected_objective)
        assert evaluation.is_feasible is True
        result = problem.solve(maxiter=32)
        assert result.success is (problem.max_constraint_violation(result.x) <= 1e-9)


def test_space_truss_grammar_seed_and_rules() -> None:
    problem = get_problem("space_truss_span")
    state = problem.initial_state()

    assert len(state.joints) == 5
    assert state.joints[0].z == 0.0
    assert state.joints[-1].z == state.max_height

    state = problem.add_joint(state, x=2.5, y=0.0, z=2.0)
    assert len(state.joints) == 6
    with pytest.raises(ValueError):
        problem.add_joint(state, x=2.5, y=0.0, z=2.0)
    with pytest.raises(ValueError):
        problem.add_joint(state, x=-1.0, y=0.0, z=2.0)

    state = problem.add_member(state, start_joint_id=0, end_joint_id=4)
    assert len(state.members) == 1
    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=0, end_joint_id=4)
    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=0, end_joint_id=0)
    state = problem.remove_member(state, member_id=0)
    assert state.members == ()


def test_space_truss_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("space_truss_span")
    monkeypatch.setitem(sys.modules, "trussme", None)
    with pytest.raises(MissingOptionalDependencyError):
        problem.evaluate(problem.initial_state())


def test_space_truss_evaluate_uses_fake_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_truss = _install_structural_fake_truss(monkeypatch)
    problem = get_problem("space_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=2, end_joint_id=4)
    evaluation = problem.evaluate(state)
    assert evaluation.mass == pytest.approx(3.0)
    assert evaluation.fos == pytest.approx(2.5)
    assert evaluation.deflection == pytest.approx(0.1)
    assert any(coordinate[2] > 0.0 for coordinate in fake_truss.coordinates)


def test_space_truss_optimization_uses_structural_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_structural_fake_truss(monkeypatch)
    problem = get_problem("space_truss_span_mass_min")
    assert isinstance(problem, SpaceTrussEngineeringOptimizationProblem)
    vector = numpy.zeros_like(problem.generate_initial_solution())
    vector[:4] = 1.0
    evaluation = problem.evaluate(vector)
    assert evaluation.objective_value == pytest.approx(4.0)
    assert evaluation.is_feasible is True


def test_space_truss_optimization_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("space_truss_span_mass_min")
    monkeypatch.setitem(sys.modules, "trussme", None)
    with pytest.raises(MissingOptionalDependencyError):
        problem.evaluate(problem.generate_initial_solution())
