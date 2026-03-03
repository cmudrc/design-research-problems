from __future__ import annotations

import sys
from itertools import islice
from types import ModuleType

import numpy
import pytest

from design_research_problems import MissingOptionalDependencyError, ProblemKind, get_problem, list_problems
from design_research_problems.problems.grammar import (
    AddCell,
    AddConnection,
    AddJointPair,
    AddMember,
    AddParallelBranch,
    AddSeriesStage,
    MoveCell,
    RemoveCell,
    RemoveConnection,
    RemoveMember,
    RemoveParallelBranch,
    RemoveSeriesStage,
)
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
from design_research_problems import (
    DecisionProblem,
    MissingOptionalDependencyError,
    ProblemEvaluationError,
    ProblemKind,
    get_problem,
    list_problems,
)
from design_research_problems.problems.grammar import AddMember, RemoveMember
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
    assert list_problems() == (
        "battery_pack_18650_open_ended",
        "battery_pack_18650_series_parallel",
        "ideation_accessible_drinking_fountain",
        "ideation_accessible_drinking_fountain_derivative",
        "ideation_car_mounted_bicycle_rack",
        "ideation_chocolate_packaging",
        "ideation_disposable_spill_proof_coffee_cup",
        "ideation_home_energy_conservation",
        "ideation_human_motion_energy_harvesting",
        "ideation_human_motion_energy_harvesting_rural_communities",
        "ideation_injured_athlete_campus_mobility",
        "ideation_joint_immobilization_device",
        "ideation_joint_immobilization_mountain_trek",
        "ideation_measure_passage_of_time",
        "ideation_measure_passage_of_time_room_clock",
        "ideation_measuring_cup_for_blind_users",
        "ideation_measuring_cup_for_blind_users_jansson_smith_1991",
        "ideation_milk_frothing_product",
        "ideation_milk_frothing_product_toh_miller_2014",
        "ideation_one_handed_lidded_container_opening",
        "ideation_one_handed_lidded_container_opening_framework",
        "ideation_out_of_reach_book_retrieval",
        "ideation_out_of_reach_book_retrieval_cardoso_badke_schaub_2011",
        "ideation_peanut_shelling",
        "ideation_peanut_shelling_fu_cagan_kotovsky_2010",
        "ideation_peanut_shelling_linsey_green_murphy_wood_markman_2005",
        "ideation_powdered_surface_coating",
        "ideation_powdered_surface_coating_domain_specific",
        "ideation_powdered_surface_coating_general",
        "ideation_public_belongings_security",
        "ideation_public_place_belongings_securer",
        "ideation_remote_village_rainwater_access",
        "ideation_remote_village_rainwater_access_framework",
        "ideation_small_towel_folding",
        "ideation_small_towel_folding_linsey_wood_markman_2008",
        "ideation_snow_transport_for_novices",
        "ideation_snow_transport_for_novices_framework",
        "ideation_travel_exercise_device",
        "ideation_travel_exercise_device_linsey_viswanathan_2014",
        "ideation_walking_texting_accident_reduction",
        "ideation_walking_texting_accident_reduction_miller_bailey_kirlik_2014",
        "ideation_wheelchair_peach_picking",
        "pill_capsule_min_area",
        "planar_roof_truss_seven_point_asymmetric",
        "planar_roof_truss_seven_point_symmetric",
        "planar_roof_truss_three_point_symmetric",
        "planar_roof_truss_three_point_symmetric_depth_eighth",
        "planar_roof_truss_three_point_symmetric_depth_sixth",
        "planar_roof_truss_three_point_symmetric_depth_sixth_discrete_sizing",
        "planar_truss_span",
    )


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
    assert len(text_ids) == 40
    assert "ideation_accessible_drinking_fountain" in text_ids
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
        "bounded-variables",
        "equality-constraint",
        "optional-solver",
        "seeded-data-generation",
        "statement-markdown",
    )
    assert grouped[ProblemKind.GRAMMAR] == (
        "discrete-actions",
        "external-adapter",
        "optional-evaluator",
        "serializable-state",
        "statement-markdown",
    )


def test_text_problem_renders_statement_and_citation() -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    packet = problem.render_packet()
    assert packet.count("# Design Problem - Device to shell peanuts") == 1
    assert "Fu, Cagan, and Kotovsky (2010)." in packet
    assert "Must remove the shell with minimal damage to the peanuts." in packet
    assert "## BibTeX" not in packet
    assert problem.metadata.has_feature("human subjects ready") is True


def test_text_problem_can_render_summary_and_raw_citations() -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    packet = problem.render_packet(citation_mode="summary+raw")
    assert "## Sources" in packet
    assert "## BibTeX" in packet
    assert "@article{fu2010design," in packet


def test_decision_problem_exposes_structured_brief() -> None:
    problem = get_problem("decision_laptop_design_profit_maximization")
    assert isinstance(problem, DecisionProblem)
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
    assert problem.choice_options == (
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

    steel = problem.evaluate_choice("steel")
    assert steel.choice_key == "steel"
    assert steel.choice_label == "Steel"
    assert steel.response_count == 67
    assert steel.objective_metric == "top-choice-share"
    assert steel.top_choice_share == pytest.approx(0.004146, abs=1e-6)
    assert steel.mean_rating == pytest.approx(2.955224, abs=1e-6)
    assert steel.median_rating == pytest.approx(3.0)
    assert steel.std_rating == pytest.approx(2.54316, abs=1e-6)
    assert problem.metadata.citations[0].raw_text.startswith("@misc{jain2024msevaldatasetmaterialselection,")

    assert problem.evaluate_choice("Steel") == steel
    assert problem.best_choice().choice_key == "composite"
    assert problem.best_choice(metric="mean-rating").choice_key == "composite"

    brief = problem.render_brief()
    assert "## Choices" in brief
    assert "## Empirical Benchmark" in brief

    with pytest.raises(ValueError):
        problem.evaluate_choice("ceramic")
    with pytest.raises(ProblemEvaluationError, match="use evaluate_choice"):
        problem.evaluate_option({})


def test_decision_problem_exposes_typed_option_space_and_evaluator() -> None:
    problem = get_problem("decision_laptop_design_profit_maximization")
    assert isinstance(problem, DecisionProblem)

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

    options_iter = problem.iter_options()
    first_option = next(options_iter)
    last_option = None
    for option in problem.iter_options():
        last_option = option
    assert last_option is not None
    assert first_option.values == {"z1": 10.4, "z2": 0.75, "z3": 1.0, "z4": 2.5, "z5": 7.5}
    assert last_option.values == {"z1": 17.0, "z2": 1.75, "z3": 8.0, "z4": 10.0, "z5": 20.0}

    sample_options = list(islice(problem.iter_options(), 3))
    assert all(tuple(option.values) == ("z1", "z2", "z3", "z4", "z5") for option in sample_options)

    evaluation = problem.evaluate_option(first_option)
    assert numpy.isfinite(evaluation.utility)
    assert 0.0 < evaluation.predicted_share < 1.0
    assert evaluation.expected_demand_units == pytest.approx(1_600_000 * evaluation.predicted_share)
    assert evaluation.objective_value == evaluation.predicted_share

    best = problem.best_option()
    assert best == max(problem.iter_option_evaluations(), key=lambda item: item.objective_value)


def test_registry_search_filters_by_feature_flags() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    matches = registry.search(feature_flags=("seeded data generation",))
    assert [entry.problem_id for entry in matches] == ["pill_capsule_min_area"]
    decision_matches = registry.search(kind=ProblemKind.DECISION, text="laptop")
    assert [entry.problem_id for entry in decision_matches] == ["decision_laptop_design_profit_maximization"]
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
    state = problem.apply_action(state, AddSeriesStage(placements=((1, 0, 0),)))
    state = problem.apply_action(state, AddSeriesStage(placements=((2, 0, 0),)))
    state = problem.apply_action(state, AddSeriesStage(placements=((3, 0, 0),)))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0))))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 2, 0), (1, 2, 0), (2, 2, 0), (3, 2, 0))))
    state = problem.apply_action(state, AddParallelBranch(placements=((0, 3, 0), (1, 3, 0), (2, 3, 0), (3, 3, 0))))
    return state


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
        state = problem.apply_action(
            state,
            AddCell(
                x=0,
                y=branch_index,
                z=0,
                connect_negative_to_terminal_id=stage_input_terminal_id,
                connect_positive_to_terminal_id=stage_output_terminal_id,
            ),
        )

    for stage_index in range(1, 4):
        previous_stage_output_terminal_id = stage_output_terminal_id
        state = problem.apply_action(
            state,
            AddCell(
                x=stage_index,
                y=0,
                z=0,
                connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                use_positive_as_pack_terminal=True,
            ),
        )
        stage_output_terminal_id = state.pack_positive_terminal_id
        for branch_index in range(1, 4):
            state = problem.apply_action(
                state,
                AddCell(
                    x=stage_index,
                    y=branch_index,
                    z=0,
                    connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                    connect_positive_to_terminal_id=stage_output_terminal_id,
                ),
            )
    return state


def test_battery_problem_state_and_actions_are_validated() -> None:
    problem = get_problem("battery_pack_18650_series_parallel")
    state = problem.initial_state()
    assert state.series_count == 1
    assert state.parallel_count == 1
    assert len(state.cells) == 1

    state = problem.apply_action(state, MoveCell(cell_id=0, x=1, y=0, z=0))
    assert state.cells[0].x == 1

    state = problem.apply_action(state, AddSeriesStage(placements=((0, 0, 0),)))
    assert state.series_count == 2
    assert len(state.cells) == 2

    with pytest.raises(ValueError):
        problem.apply_action(state, MoveCell(cell_id=0, x=0, y=0, z=0))

    state = problem.apply_action(state, AddParallelBranch(placements=((0, 1, 0), (1, 1, 0))))
    assert state.parallel_count == 2
    assert len(state.cells) == 4

    with pytest.raises(ValueError):
        problem.apply_action(state, AddSeriesStage(placements=((2, 0, 0),)))

    state = problem.apply_action(state, RemoveParallelBranch())
    assert state.parallel_count == 1
    assert len(state.cells) == 2

    state = problem.apply_action(state, RemoveSeriesStage())
    assert state.series_count == 1
    assert len(state.cells) == 1

    with pytest.raises(ValueError):
        problem.apply_action(problem.initial_state(), RemoveSeriesStage())


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


def test_open_ended_battery_problem_state_and_actions_are_validated() -> None:
    problem = get_problem("battery_pack_18650_open_ended")
    state = problem.initial_state()
    assert len(state.cells) == 1
    assert len(state.connections) == 0

    initial_negative_terminal_id = state.pack_negative_terminal_id
    initial_positive_terminal_id = state.pack_positive_terminal_id
    state = problem.apply_action(
        state,
        AddCell(
            x=1,
            y=0,
            z=0,
            connect_negative_to_terminal_id=initial_positive_terminal_id,
            use_positive_as_pack_terminal=True,
        ),
    )
    assert len(state.cells) == 2
    assert len(state.connections) == 1
    assert state.pack_positive_terminal_id != initial_positive_terminal_id

    with pytest.raises(ValueError):
        problem.apply_action(
            state,
            AddCell(
                x=2,
                y=0,
                z=0,
                connect_negative_to_terminal_id=initial_positive_terminal_id,
                connect_positive_to_terminal_id=initial_positive_terminal_id,
            ),
        )

    series_cell = next(cell for cell in state.cells if cell.cell_id != 0)
    state = problem.apply_action(
        state,
        AddCell(
            x=1,
            y=1,
            z=0,
            connect_negative_to_terminal_id=initial_positive_terminal_id,
            connect_positive_to_terminal_id=state.pack_positive_terminal_id,
        ),
    )
    assert len(state.cells) == 3
    assert len(state.connections) == 3
    parallel_cell = max(state.cells, key=lambda cell: cell.cell_id)

    state = problem.apply_action(
        state,
        AddConnection(
            from_terminal_id=initial_negative_terminal_id,
            to_terminal_id=parallel_cell.negative_terminal_id,
        ),
    )
    assert len(state.connections) == 4

    state = problem.apply_action(state, MoveCell(cell_id=parallel_cell.cell_id, x=1, y=2, z=0))
    moved_parallel_cell = next(cell for cell in state.cells if cell.cell_id == parallel_cell.cell_id)
    assert moved_parallel_cell.y == 2

    extra_connection_id = max(connection.connection_id for connection in state.connections)
    state = problem.apply_action(state, RemoveConnection(connection_id=extra_connection_id))
    assert len(state.connections) == 3

    state = problem.apply_action(state, RemoveCell(cell_id=parallel_cell.cell_id))
    assert len(state.cells) == 2
    assert all(
        connection.from_terminal_id not in {parallel_cell.negative_terminal_id, parallel_cell.positive_terminal_id}
        and connection.to_terminal_id not in {parallel_cell.negative_terminal_id, parallel_cell.positive_terminal_id}
        for connection in state.connections
    )

    state = problem.apply_action(state, RemoveCell(cell_id=series_cell.cell_id))
    assert len(state.cells) == 1
    assert len(state.connections) == 0
    assert state.pack_positive_terminal_id == state.cells[0].positive_terminal_id
    assert state.pack_negative_terminal_id == state.cells[0].negative_terminal_id

    with pytest.raises(ValueError):
        problem.apply_action(state, RemoveCell(cell_id=state.cells[0].cell_id))


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
    x1, y1 = problem.generate_data(n=4, seed=7)
    x2, y2 = problem.generate_data(n=4, seed=7)
    assert x1.shape == (4, 2)
    assert y1.shape == (4, 1)
    assert numpy.allclose(x1, x2)
    assert numpy.allclose(y1, y2)


def test_pill_problem_load_data_is_not_available() -> None:
    problem = get_problem("pill_capsule_min_area")
    with pytest.raises(NotImplementedError):
        problem.load_data()


def test_pill_problem_reports_missing_scipy(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("pill_capsule_min_area")
    monkeypatch.setitem(sys.modules, "scipy", None)
    monkeypatch.setitem(sys.modules, "scipy.optimize", None)
    with pytest.raises(MissingOptionalDependencyError):
        problem.solve(seed=1)


def test_planar_truss_state_and_actions_are_validated() -> None:
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()

    with pytest.raises(ValueError):
        problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=0))

    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=1, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=1))
    assert len(state.members) == 3

    state = problem.apply_action(state, RemoveMember(member_id=1))
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
    actions = problem.enumerate_actions(state)

    assert any(isinstance(action, AddJointPair) for action in actions)

    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    assert len(state.members) == 2
    edges = {tuple(sorted((member.start_joint_id, member.end_joint_id))) for member in state.members}
    assert edges == {(0, 2), (1, 4)}

    state = problem.apply_action(state, RemoveMember(member_id=0))
    assert state.members == ()


def test_planar_truss_reports_missing_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
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

        def add_roller_joint(self, coordinates: list[float]) -> int:
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
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    state = problem.apply_action(state, AddMember(start_joint_id=1, end_joint_id=2))
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

        def add_roller_joint(self, coordinates: list[float]) -> int:
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
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
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

        def add_roller_joint(self, coordinates: list[float]) -> int:
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
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
    evaluation = problem.evaluate(state)

    assert evaluation.is_feasible is True
    assert fake_truss.load_calls == 7
