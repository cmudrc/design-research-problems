from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from design_research_problems import GrammarProblem, get_problem, list_problems
from design_research_problems.problems._domains import truss_ap as truss_domain
from design_research_problems.problems._domains.truss_ap import (
    TrussAPJoint,
    TrussAPLoad,
    TrussAPMember,
    TrussAPState,
)

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "truss_ap_matlab_parity.json"


def _load_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _state_from_fixture_entry(base_state: TrussAPState, entry: dict[str, Any]) -> TrussAPState:
    state_payload = entry["state"]

    joints = tuple(
        TrussAPJoint(
            joint_id=int(record["joint_id"]),
            x=float(record["x"]),
            y=float(record["y"]),
            is_fixed=bool(record["is_fixed"]),
        )
        for record in state_payload["joints"]
    )
    members = tuple(
        TrussAPMember(
            member_id=int(record["member_id"]),
            start_joint_id=int(record["start_joint_id"]),
            end_joint_id=int(record["end_joint_id"]),
            size_index=int(record["size_index"]),
        )
        for record in state_payload["members"]
    )
    loads = tuple(
        TrussAPLoad(
            joint_id=int(record["joint_id"]),
            direction=str(record["direction"]),
            magnitude_n=float(record["magnitude_n"]),
        )
        for record in state_payload["loads"]
    )
    support_enabled = tuple(bool(value) for value in state_payload["support_enabled"])

    return replace(
        base_state,
        joints=joints,
        members=members,
        loads=loads,
        support_enabled=support_enabled,
    )


def test_registry_exposes_truss_analysis_program_problem() -> None:
    assert "truss_analysis_program_design" in list_problems()
    problem = get_problem("truss_analysis_program_design")
    assert isinstance(problem, GrammarProblem)
    state = problem.initial_state()
    assert isinstance(state, TrussAPState)


def test_truss_analysis_program_evaluator_matches_matlab_fixture() -> None:
    fixture = _load_fixture()
    problem = get_problem("truss_analysis_program_design")
    base_state = problem.initial_state()

    for entry in fixture["entries"]:
        state = _state_from_fixture_entry(base_state, entry)
        evaluation = problem.evaluate(state)
        expected = entry["expected"]

        assert evaluation.mass_kg == pytest.approx(float(expected["mass_kg"]), abs=1e-9)
        expected_min_fos = float(expected["min_fos"])
        if expected_min_fos > 0.0:
            assert evaluation.min_fos > 0.0
        else:
            assert evaluation.min_fos >= 0.0
        assert evaluation.joint_count == int(expected["joint_count"])
        assert evaluation.member_count == int(expected["member_count"])


def test_truss_analysis_program_grammar_rules_reject_invalid_operations() -> None:
    problem = get_problem("truss_analysis_program_design")
    state = problem.initial_state()

    with pytest.raises(ValueError):
        problem.delete_joint(state, joint_id=1)

    state = problem.add_joint(state, x=-3.446939, y=1.847708)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=6, size_index=5)

    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=1, end_joint_id=6, size_index=5)

    with pytest.raises(ValueError):
        problem.set_load(state, joint_id=1, direction="down", magnitude_n=12345.0)


def test_truss_analysis_program_evaluation_is_deterministic() -> None:
    fixture = _load_fixture()
    problem = get_problem("truss_analysis_program_design")
    base_state = problem.initial_state()
    state = _state_from_fixture_entry(base_state, fixture["entries"][-1])

    first = problem.evaluate(state)
    second = problem.evaluate(state)
    assert first == second


def test_truss_analysis_program_evaluator_rejects_malformed_state_fields() -> None:
    problem = get_problem("truss_analysis_program_design")
    state = problem.initial_state()
    state = problem.add_joint(state, x=-3.446939, y=1.847708)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=6, size_index=5)

    invalid_size_state = replace(
        state,
        members=(
            replace(state.members[0], size_index=99),
            *state.members[1:],
        ),
    )
    invalid_size_eval = problem.evaluate(invalid_size_state)
    assert not invalid_size_eval.is_stable
    assert invalid_size_eval.failure_reason == "Member size index is out of bounds."

    invalid_direction_state = replace(
        state,
        loads=(TrussAPLoad(joint_id=1, direction="invalid_direction", magnitude_n=200_000.0),),
    )
    invalid_direction_eval = problem.evaluate(invalid_direction_state)
    assert not invalid_direction_eval.is_stable
    assert invalid_direction_eval.failure_reason == "Load directions must be one of left/down/right/up."


def test_truss_analysis_program_top_node_fan_with_bottom_chain_is_stable() -> None:
    problem = get_problem("truss_analysis_program_design")
    state = problem.initial_state()

    state = problem.add_joint(state, x=-0.111, y=2.569)
    top_joint_id = max(joint.joint_id for joint in state.joints)

    for base_joint_id in (1, 2, 3, 4, 5):
        state = problem.add_member(
            state,
            start_joint_id=base_joint_id,
            end_joint_id=top_joint_id,
            size_index=5,
        )

    for start_joint_id, end_joint_id in ((1, 4), (4, 2), (2, 5), (5, 3)):
        state = problem.add_member(
            state,
            start_joint_id=start_joint_id,
            end_joint_id=end_joint_id,
            size_index=5,
        )

    evaluation = problem.evaluate(state)
    assert evaluation.is_stable
    assert evaluation.failure_reason is None
    assert len(evaluation.fos_by_member) == len(state.members)


def test_truss_geometry_helpers_cover_boundary_intersection_cases() -> None:
    square = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
    assert truss_domain._point_in_polygon(1.0, 1.0, square)
    assert truss_domain._point_in_polygon(0.0, 1.0, square)
    assert not truss_domain._point_in_polygon(3.0, 1.0, square)

    assert truss_domain._segments_intersect(0, 0, 2, 2, 0, 2, 2, 0)
    assert truss_domain._segments_intersect(0, 0, 2, 0, 1, 0, 3, 0)
    assert truss_domain._segments_intersect(0, 0, 2, 0, 2, 0, 3, 1)
    assert truss_domain._segments_intersect(1, 0, 3, 0, 0, 0, 2, 0)
    assert truss_domain._segments_intersect(0, 0, 2, 0, 3, 0, 2, 0)
    assert not truss_domain._segments_intersect(0, 0, 1, 0, 0, 1, 1, 1)

    assert truss_domain._segment_intersects_polygon((1, 1), (3, 3), square)
    assert truss_domain._segment_intersects_polygon((-1, 1), (3, 1), square)
    assert not truss_domain._segment_intersects_polygon((-2, -2), (-1, -1), square)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda state: replace(state, required_support_joint_ids=(1, 2)), "Exactly three"),
        (lambda state: replace(state, support_enabled=(True,)), "support_enabled length"),
        (
            lambda state: replace(state, loads=(TrussAPLoad(joint_id=999, direction="down", magnitude_n=1),)),
            "Loads must reference",
        ),
        (
            lambda state: replace(state, loads=(TrussAPLoad(joint_id=1, direction="down", magnitude_n=float("inf")),)),
            "magnitudes must be finite",
        ),
        (
            lambda state: replace(
                state,
                members=(TrussAPMember(member_id=1, start_joint_id=1, end_joint_id=1, size_index=1),),
            ),
            "cannot connect a joint to itself",
        ),
        (
            lambda state: replace(
                state,
                members=(TrussAPMember(member_id=1, start_joint_id=1, end_joint_id=999, size_index=1),),
            ),
            "reference existing joints",
        ),
        (
            lambda state: replace(
                state,
                members=(TrussAPMember(member_id=1, start_joint_id=1, end_joint_id=2, size_index=0),),
            ),
            "size index is out of bounds",
        ),
        (
            lambda state: replace(
                state,
                size_index_max=99,
                members=(TrussAPMember(member_id=1, start_joint_id=1, end_joint_id=2, size_index=11),),
            ),
            "exceeds the available section table",
        ),
        (
            lambda state: replace(
                state,
                members=(
                    TrussAPMember(member_id=1, start_joint_id=1, end_joint_id=2, size_index=1),
                    TrussAPMember(member_id=2, start_joint_id=2, end_joint_id=1, size_index=1),
                ),
            ),
            "Duplicate members",
        ),
    ],
)
def test_truss_state_validation_reports_malformed_fields(
    mutator: Callable[[TrussAPState], TrussAPState],
    message: str,
) -> None:
    state = mutator(truss_domain.build_default_truss_ap_state())
    evaluation = truss_domain.evaluate_truss_ap_state(state)
    assert evaluation.failure_reason is not None
    assert message in evaluation.failure_reason


def test_truss_grammar_enumerates_and_applies_the_full_editing_workflow() -> None:
    problem = get_problem("truss_analysis_program_design")
    state = problem.initial_state()
    assert {transition.rule_name for transition in problem.enumerate_transitions(state)} >= {
        "add_joint",
        "add_member",
        "set_support_enabled",
        "set_load",
        "clear_load",
    }

    state = problem.add_joint(state, x=-3.446939, y=1.847708)
    editable_id = max(joint.joint_id for joint in state.joints)
    moved = problem.move_joint(state, joint_id=editable_id, x=-2.0, y=2.0)
    with pytest.raises(ValueError, match="Unknown joint"):
        problem.move_joint(state, joint_id=999, x=0, y=0)
    with pytest.raises(ValueError, match="Fixed joints"):
        problem.move_joint(state, joint_id=1, x=0, y=0)
    with pytest.raises(ValueError, match="design bounds"):
        problem.move_joint(state, joint_id=editable_id, x=999, y=999)
    with pytest.raises(ValueError, match="already exists"):
        problem.move_joint(state, joint_id=editable_id, x=-5.0, y=0.0)

    state = problem.add_member(moved, start_joint_id=1, end_joint_id=editable_id, size_index=5)
    member_id = state.members[-1].member_id
    assert {transition.rule_name for transition in problem.enumerate_transitions(state)} >= {
        "move_joint",
        "delete_joint",
        "delete_member",
        "set_member_size",
    }
    with pytest.raises(ValueError, match="itself"):
        problem.add_member(state, start_joint_id=1, end_joint_id=1, size_index=5)
    with pytest.raises(ValueError, match="existing joints"):
        problem.add_member(state, start_joint_id=1, end_joint_id=999, size_index=5)
    with pytest.raises(ValueError, match="already exists"):
        problem.add_member(state, start_joint_id=editable_id, end_joint_id=1, size_index=5)
    with pytest.raises(ValueError, match="out of bounds"):
        problem.add_member(state, start_joint_id=2, end_joint_id=editable_id, size_index=99)
    with pytest.raises(ValueError, match="Unknown member"):
        problem.delete_member(state, member_id=999)
    with pytest.raises(ValueError, match="out of bounds"):
        problem.set_member_size(state, member_id=member_id, size_index=99)
    with pytest.raises(ValueError, match="Unknown member"):
        problem.set_member_size(state, member_id=999, size_index=5)
    resized = problem.set_member_size(state, member_id=member_id, size_index=6)
    assert resized.members[-1].size_index == 6

    with pytest.raises(ValueError, match="support_id"):
        problem.set_support_enabled(state, support_id=0, enabled=False)
    assert problem.set_support_enabled(state, support_id=1, enabled=False).support_enabled[0] is False
    with pytest.raises(ValueError, match="Unknown joint"):
        problem.set_load(state, joint_id=999, direction="down", magnitude_n=50_000)
    with pytest.raises(ValueError, match="direction"):
        problem.set_load(state, joint_id=1, direction="bad", magnitude_n=50_000)
    with pytest.raises(ValueError, match="Unsupported load"):
        problem.set_load(state, joint_id=1, direction="down", magnitude_n=1)
    loaded = problem.set_load(state, joint_id=1, direction="left", magnitude_n=50_000)
    with pytest.raises(ValueError, match="Unknown joint"):
        problem.clear_load(loaded, joint_id=999, direction="left")
    with pytest.raises(ValueError, match="direction"):
        problem.clear_load(loaded, joint_id=1, direction="bad")
    assert len(problem.clear_load(loaded, joint_id=1, direction="left").loads) < len(loaded.loads)

    deleted = problem.delete_member(state, member_id=member_id)
    assert len(deleted.members) == len(state.members) - 1
    without_joint = problem.delete_joint(state, joint_id=editable_id)
    assert all(joint.joint_id != editable_id for joint in without_joint.joints)
