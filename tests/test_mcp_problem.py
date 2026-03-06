from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

pytest.importorskip("mcp.server.fastmcp")
from mcp.server.fastmcp.exceptions import ToolError

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems import MCPProblem, ProblemKind, ProblemMetadata, ProblemTaxonomy

REPO_ROOT = Path(__file__).resolve().parents[1]


def _metadata(problem_id: str) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title="MCP Proxy Test Problem",
        summary="Synthetic MCP-backed problem used for proxy-family tests.",
        kind=ProblemKind.MCP,
        taxonomy=ProblemTaxonomy(
            formulation="mcp_proxy",
            convexity=None,
            design_variable_type=None,
            is_dynamic=False,
            orientation="engineering_practical",
            feasibility_ratio_hint=None,
            objective_mode="qualitative",
            constraint_nature="informal",
            bounds_summary=None,
            tags=("mcp", "agent"),
        ),
        citations=(),
        assets=(),
        capabilities=("statement-markdown",),
        study_suitability=(),
    )


def _write_upstream_server(tmp_path: Path, *, include_final_answer: bool) -> Path:
    lines = [
        "from __future__ import annotations",
        "",
        "from mcp.server.fastmcp import FastMCP",
        "",
        'server = FastMCP("upstream-test-server")',
        'COUNTER = {"value": 0}',
        "",
        '@server.tool(name="echo")',
        "def echo(message: str) -> dict[str, str]:",
        '    return {"message": message}',
        "",
        '@server.tool(name="increment")',
        "def increment(delta: int = 1) -> dict[str, int]:",
        '    COUNTER["value"] += delta',
        '    return {"counter": COUNTER["value"]}',
        "",
        '@server.tool(name="get_counter")',
        "def get_counter() -> dict[str, int]:",
        '    return {"counter": COUNTER["value"]}',
        "",
    ]

    if include_final_answer:
        lines.extend(
            [
                '@server.tool(name="final_answer")',
                "def final_answer(answer: str) -> dict[str, str]:",
                '    return {"source": "upstream", "answer": answer}',
                "",
            ]
        )

    lines.extend(
        [
            'if __name__ == "__main__":',
            '    server.run(transport="stdio")',
            "",
        ]
    )

    script = "\n".join(lines)
    path = tmp_path / "upstream_server.py"
    path.write_text(script, encoding="utf-8")
    return path


def _problem_from_server(script_path: Path, *, problem_id: str) -> MCPProblem:
    return MCPProblem.from_stdio(
        metadata=_metadata(problem_id),
        command=sys.executable,
        args=(str(script_path),),
        env={"PYTHONPATH": str(REPO_ROOT / "src")},
        statement_markdown="# MCP Proxy Test Problem\n\nUse the upstream tools to solve this task.",
    )


def test_mcp_problem_resolves_python_executable_command_marker() -> None:
    problem = MCPProblem.from_stdio(
        metadata=_metadata("mcp_proxy_python_command_marker"),
        command="__python_executable__",
        args=("-c", "print('marker')"),
    )
    assert problem.command == sys.executable


def _tool_names(server: Any) -> list[str]:
    tools = asyncio.run(server.list_tools())
    return [tool.name for tool in tools]


def _resource_uris(server: Any) -> set[str]:
    resources = asyncio.run(server.list_resources())
    return {str(resource.uri) for resource in resources}


def _read_resource_text(server: Any, uri: str) -> str:
    payload = asyncio.run(server.read_resource(uri))
    assert payload
    return payload[0].content


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


def test_mcp_problem_proxies_upstream_tools_and_exposes_design_brief(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_tools_and_brief")
    server = problem.to_mcp_server()

    assert "problem://design-brief" in _resource_uris(server)
    brief = _read_resource_text(server, "problem://design-brief")
    assert "MCP Proxy Test Problem" in brief

    tool_names = _tool_names(server)
    assert "echo" in tool_names
    assert "increment" in tool_names
    assert "get_counter" in tool_names

    echo_payload = _call_tool_json(server, "echo", {"message": "hello"})
    assert echo_payload["message"] == "hello"


def test_mcp_problem_injects_fallback_final_answer_when_upstream_missing(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_fallback_final_answer")
    server = problem.to_mcp_server()

    tool_names = _tool_names(server)
    assert "final_answer" in tool_names
    assert tool_names.count("final_answer") == 1

    payload = _call_tool_json(server, "final_answer", {"answer": "Proxy result summary."})
    assert payload["problem_id"] == problem.metadata.problem_id
    assert payload["problem_kind"] == "mcp"
    assert payload["answer"] == "Proxy result summary."


def test_mcp_problem_uses_upstream_final_answer_when_present(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=True)
    problem = _problem_from_server(script, problem_id="mcp_proxy_upstream_final_answer")
    server = problem.to_mcp_server()

    tool_names = _tool_names(server)
    assert tool_names.count("final_answer") == 1

    payload = _call_tool_json(server, "final_answer", {"answer": "Upstream answer"})
    assert payload["source"] == "upstream"
    assert payload["answer"] == "Upstream answer"
    assert "problem_id" not in payload


def test_mcp_problem_preserves_upstream_state_within_one_event_loop(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_stateful")
    server = problem.to_mcp_server()

    async def run_sequence() -> dict[str, Any]:
        await server.call_tool("increment", {"delta": 2})
        await server.call_tool("increment", {})
        payload = await server.call_tool("get_counter", {})
        if isinstance(payload, tuple):
            _, structured = payload
            return cast(dict[str, Any], structured)
        raise AssertionError("Expected structured call_tool tuple payload.")

    result = asyncio.run(run_sequence())
    assert result["counter"] == 3


def test_mcp_problem_session_is_loop_bound_across_asyncio_run_calls(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_loop_bound")
    server = problem.to_mcp_server()

    asyncio.run(server.call_tool("get_counter", {}))
    with pytest.raises(ToolError, match="different event loop"):
        asyncio.run(server.call_tool("get_counter", {}))


def test_mcp_problem_rejects_unsupported_tool_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = MCPProblem.from_stdio(
        metadata=_metadata("mcp_proxy_bad_schema"),
        command=sys.executable,
        args=("-c", "print('unused')"),
    )

    fake_tool = SimpleNamespace(
        name="bad_tool",
        title="Bad Tool",
        description="Malformed schema tool",
        inputSchema={"type": "object"},
    )
    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: (fake_tool,))

    with pytest.raises(ProblemEvaluationError, match="missing object-style named properties"):
        problem.to_mcp_server()


def test_mcp_problem_exposes_close_hooks_and_sync_close_noops_before_use(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_close_hooks")
    server = problem.to_mcp_server()

    server_any = cast(Any, server)
    assert hasattr(server_any, "aclose_upstream_session")
    assert hasattr(server_any, "close_upstream_session")
    server_any.close_upstream_session()


def test_mcp_problem_sync_close_requires_async_when_session_is_active(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_sync_close_active")
    server = problem.to_mcp_server()

    asyncio.run(server.call_tool("get_counter", {}))
    with pytest.raises(RuntimeError, match=r"Use await server\.aclose_upstream_session\(\)"):
        cast(Any, server).close_upstream_session()


def test_mcp_problem_async_close_marks_session_closed(tmp_path: Path) -> None:
    script = _write_upstream_server(tmp_path, include_final_answer=False)
    problem = _problem_from_server(script, problem_id="mcp_proxy_async_close")
    server = problem.to_mcp_server()

    async def use_and_close() -> None:
        await server.call_tool("get_counter", {})
        await cast(Any, server).aclose_upstream_session()

    asyncio.run(use_and_close())
    with pytest.raises(ToolError, match="session has been closed"):
        asyncio.run(server.call_tool("get_counter", {}))
