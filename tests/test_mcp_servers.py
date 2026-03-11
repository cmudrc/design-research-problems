from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from typing import Any, cast

import pytest

pytest.importorskip("mcp.server.fastmcp")
from mcp.server.fastmcp.exceptions import ToolError

from design_research_problems import get_problem
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.problems import _mcp as mcp_helpers


def _tool_names(server: Any) -> set[str]:
    tools = asyncio.run(server.list_tools())
    return {tool.name for tool in tools}


def _resource_uris(server: Any) -> set[str]:
    resources = asyncio.run(server.list_resources())
    return {str(resource.uri) for resource in resources}


def _read_resource_text(server: Any, uri: str) -> str:
    payload = asyncio.run(server.read_resource(uri))
    assert payload
    return payload[0].content


def _read_resource_json(server: Any, uri: str) -> dict[str, Any]:
    text = _read_resource_text(server, uri)
    return cast(dict[str, Any], json.loads(text))


def _call_tool_json(server: Any, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    payload = asyncio.run(server.call_tool(name, arguments))
    if isinstance(payload, tuple):
        _, structured = payload
        return cast(dict[str, Any], structured)

    content = cast(Sequence[Any], payload)
    assert content
    text = getattr(content[0], "text", None)
    assert isinstance(text, str)
    return cast(dict[str, Any], json.loads(text))


def test_text_problem_to_mcp_server_exposes_brief_and_submit_final() -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    server = problem.to_mcp_server()

    assert "problem://design-brief" in _resource_uris(server)
    assert "submit_final" in _tool_names(server)

    brief = _read_resource_text(server, "problem://design-brief")
    assert "Device to shell peanuts" in brief

    payload = _call_tool_json(server, "submit_final", {"answer": "Use a hand-crank shelling mechanism."})
    assert payload["problem_id"] == problem.metadata.problem_id
    assert payload["answer"] == "Use a hand-crank shelling mechanism."


def test_decision_problem_to_mcp_server_exposes_indexed_candidates() -> None:
    problem = get_problem("decision_mseval_kitchen_utensil_grip_lightweight")
    server = problem.to_mcp_server()

    assert "problem://design-brief" in _resource_uris(server)
    assert "problem://decision-candidates" in _resource_uris(server)
    assert {"list_candidates", "evaluate", "submit_final"}.issubset(_tool_names(server))

    candidates = _read_resource_json(server, "problem://decision-candidates")
    assert candidates["candidate_count"] == problem.candidate_count
    assert candidates["candidates"][0]["choice_index"] == 0
    assert candidates["candidates"][0]["candidate"] == "steel"

    listed = _call_tool_json(server, "list_candidates", {})
    assert listed["candidate_count"] == problem.candidate_count

    evaluation = _call_tool_json(server, "evaluate", {"choice_index": 0})
    assert evaluation["choice_index"] == 0
    assert evaluation["evaluation"]["candidate_kind"] == "empirical-choice"
    assert evaluation["higher_is_better"] is True
    assert evaluation["is_feasible"] is True

    payload = _call_tool_json(server, "submit_final", {"choice_index": 0, "justification": "Good baseline choice."})
    assert payload["choice_index"] == 0
    assert payload["justification"] == "Good baseline choice."
    assert payload["evaluation"]["candidate_kind"] == "empirical-choice"
    assert payload["higher_is_better"] is True
    assert payload["is_feasible"] is True

    with pytest.raises(ToolError):
        asyncio.run(server.call_tool("submit_final", {"choice_index": 999}))


def test_optimization_problem_to_mcp_server_exposes_evaluate_and_submit_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("pill_capsule_min_area")

    monkeypatch.setattr(
        problem,
        "objective_components",
        lambda variables: {"sum": float(variables.sum())},
        raising=False,
    )
    monkeypatch.setattr(
        problem,
        "decode_candidate",
        lambda variables: {"radius": float(variables[0]), "length": float(variables[1])},
        raising=False,
    )

    server = problem.to_mcp_server()
    assert "problem://design-brief" in _resource_uris(server)
    assert {"evaluate", "submit_final"}.issubset(_tool_names(server))

    candidate = problem.generate_initial_solution(seed=3).tolist()
    report = _call_tool_json(server, "evaluate", {"x": candidate})
    assert report["evaluation"]["is_feasible"] is True
    assert report["objective_components"]["sum"] == pytest.approx(sum(candidate))
    assert report["decoded_candidate"]["radius"] == pytest.approx(candidate[0])
    assert report["higher_is_better"] is False
    assert report["objective_value"] == pytest.approx(report["evaluation"]["objective_value"])

    submission = _call_tool_json(
        server,
        "submit_final",
        {"final_x": candidate, "justification": "Compact and feasible solution."},
    )
    assert submission["justification"] == "Compact and feasible solution."
    assert submission["report"]["evaluation"]["is_feasible"] is True


def test_grammar_problem_to_mcp_server_is_stateful_and_toggleable() -> None:
    problem = get_problem("planar_truss_span")
    server = problem.to_mcp_server()

    tool_names = _tool_names(server)
    assert {"get_design", "reset_design", "list_transitions", "evaluate", "submit_final"}.issubset(tool_names)
    assert {"add_member", "add_joint", "remove_member"}.issubset(tool_names)

    before = _call_tool_json(server, "get_design", {})
    assert before["design"]["members"] == []

    after = _call_tool_json(server, "add_member", {"start_joint_id": 0, "end_joint_id": 2})
    assert len(after["design"]["members"]) == 1

    transitions = _call_tool_json(server, "list_transitions", {})
    assert transitions["transition_count"] > 0

    try:
        final_payload = _call_tool_json(server, "submit_final", {})
    except ToolError as exc:
        assert "trussme is required for truss evaluation" in str(exc)
    else:
        assert final_payload["design"] == after["design"]

    no_helpers_server = problem.to_mcp_server(include_grammar_helpers=False)
    no_helper_tool_names = _tool_names(no_helpers_server)
    assert "submit_final" in no_helper_tool_names
    assert {"add_member", "add_joint", "remove_member"}.issubset(no_helper_tool_names)
    assert "get_design" not in no_helper_tool_names
    assert "reset_design" not in no_helper_tool_names
    assert "list_transitions" not in no_helper_tool_names
    assert "evaluate" not in no_helper_tool_names


def test_grammar_evaluate_helper_returns_current_state_report() -> None:
    problem = get_problem("battery_18650_t1_series_parallel_grammar")
    server = problem.to_mcp_server()

    payload = _call_tool_json(server, "evaluate", {})
    assert payload["evaluation"]["is_feasible"] is False
    assert "failure_reason" in payload["evaluation"]


def test_to_mcp_server_raises_missing_optional_dependency_when_mcp_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")

    def _missing_import(
        module_name: str,
        *,
        required_for: str,
        extras: tuple[str, ...],
        dependency_label: str | None = None,
        make_target: str | None = None,
    ) -> object:
        raise MissingOptionalDependencyError(
            f"{dependency_label or module_name} is required for {required_for}. extras={extras!r}"
        )

    monkeypatch.setattr(mcp_helpers, "import_optional_module", _missing_import)
    with pytest.raises(MissingOptionalDependencyError):
        problem.to_mcp_server()
