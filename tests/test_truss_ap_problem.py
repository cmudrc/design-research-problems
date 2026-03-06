from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from design_research_problems import GrammarProblem, get_problem, list_problems
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
