from __future__ import annotations

import importlib.util

import pytest

from design_research_problems import get_problem


@pytest.mark.trussme_real
def test_real_trussme_integration_if_available() -> None:
    if importlib.util.find_spec("trussme") is None:
        pytest.skip("trussme is not installed in this environment.")

    problem = get_problem("planar_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=1)
    evaluation = problem.evaluate(state)
    assert evaluation.number_of_members == 3
    assert evaluation.failure_reason is None


@pytest.mark.trussme_real
def test_real_space_truss_integration_if_available() -> None:
    if importlib.util.find_spec("trussme") is None:
        pytest.skip("trussme is not installed in this environment.")

    problem = get_problem("space_truss_span")
    state = problem.initial_state()
    state = problem.add_member(state, start_joint_id=0, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=2, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=3, end_joint_id=4)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=1)
    state = problem.add_member(state, start_joint_id=2, end_joint_id=3)
    state = problem.add_member(state, start_joint_id=0, end_joint_id=2)
    state = problem.add_member(state, start_joint_id=1, end_joint_id=3)
    evaluation = problem.evaluate(state)
    assert evaluation.number_of_members == 8
    assert evaluation.failure_reason is None
