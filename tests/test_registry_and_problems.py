from __future__ import annotations

import sys
from types import ModuleType

import numpy
import pytest

from design_research_problems import MissingOptionalDependencyError, ProblemKind, get_problem, list_problems
from design_research_problems.problems.grammar import AddMember, RemoveMember
from design_research_problems.problems.optimization._pill import _pill_area, _pill_volume


def test_list_problems_returns_seed_problem_ids() -> None:
    assert list_problems() == (
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
        "moneymaker_hip_pump_cost_min",
        "pill_capsule_min_area",
        "planar_truss_span",
    )


def test_registry_entries_filter_by_kind() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    kinds = registry.by_kind(ProblemKind.TEXT)
    assert [entry.problem_id for entry in kinds] == [
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
    ]
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
        "citation-backed",
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


def test_registry_search_filters_by_feature_flags() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    matches = registry.search(feature_flags=("seeded data generation",))
    assert [entry.problem_id for entry in matches] == [
        "moneymaker_hip_pump_cost_min",
        "pill_capsule_min_area",
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
