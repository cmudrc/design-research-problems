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
        "peanut_sheller_fu2010",
        "pill_capsule_min_area",
        "planar_truss_span",
    )


def test_registry_entries_filter_by_kind() -> None:
    from design_research_problems import ProblemRegistry

    registry = ProblemRegistry()
    kinds = registry.by_kind(ProblemKind.TEXT)
    assert [entry.problem_id for entry in kinds] == ["peanut_sheller_fu2010"]


def test_text_problem_renders_statement_and_citation() -> None:
    problem = get_problem("peanut_sheller_fu2010")
    packet = problem.render_packet()
    assert "Design Problem - Device to shell peanuts" in packet
    assert "fu2010design" in packet
    assert "Must remove the shell with minimal damage to the peanuts." in packet


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


def test_planar_truss_reports_missing_dependency() -> None:
    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.apply_action(state, AddMember(start_joint_id=0, end_joint_id=2))
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
