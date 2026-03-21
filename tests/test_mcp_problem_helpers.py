from __future__ import annotations

import asyncio
import inspect
import sys
from types import SimpleNamespace
from typing import Any, cast

import pytest

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems import MCPProblem, ProblemKind, ProblemMetadata, ProblemTaxonomy
from design_research_problems.problems import _mcp_problem as mcp_problem_module
from design_research_problems.problems._mcp_problem import (
    _annotation_from_schema,
    _proxy_signature,
    _safe_identifier,
    _upstream_error_message,
    parse_mcp_stdio_parameters,
)


def _metadata(problem_id: str) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title="MCP Helper Test Problem",
        summary="Synthetic MCP-backed problem used for helper coverage.",
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
            tags=("mcp", "helper"),
        ),
        citations=(),
        assets=(),
        capabilities=("statement-markdown",),
        study_suitability=(),
    )


def _problem(problem_id: str = "mcp_helper") -> MCPProblem:
    return MCPProblem.from_stdio(
        metadata=_metadata(problem_id),
        command=sys.executable,
        args=("-c", "print('unused')"),
    )


class _FakeServer:
    def __init__(self) -> None:
        self.tools: list[tuple[Any, dict[str, object]]] = []

    def add_tool(self, func: Any, **kwargs: object) -> None:
        self.tools.append((func, dict(kwargs)))


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({}, "transport='stdio'"),
        ({"transport": "stdio"}, "non-empty string command"),
        ({"transport": "stdio", "command": "python", "args": "bad"}, "args as a sequence"),
        (
            {"transport": "stdio", "command": "python", "args": ["ok", 1]},
            "args entries must be strings",
        ),
        (
            {"transport": "stdio", "command": "python", "args": [], "cwd": ""},
            "cwd must be a non-empty string",
        ),
        (
            {"transport": "stdio", "command": "python", "args": [], "env": []},
            "env must be a mapping",
        ),
        (
            {"transport": "stdio", "command": "python", "args": [], "env": {"A": 1}},
            "env entries must use string keys and string values",
        ),
    ],
)
def test_parse_mcp_stdio_parameters_validates_bad_inputs(
    parameters: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        parse_mcp_stdio_parameters(parameters)


def test_proxy_signature_and_annotation_helpers_cover_schema_edges() -> None:
    signature = _proxy_signature(
        tool_name="echo",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "count": {"type": "integer"},
                "options": {"type": ["null", "array"]},
            },
            "required": ["message"],
        },
    )

    assert list(signature.parameters) == ["message", "count", "options"]
    assert signature.parameters["message"].default is inspect._empty
    assert signature.parameters["count"].default is None
    assert signature.parameters["message"].annotation is str
    assert _annotation_from_schema({"type": "number"}) is float
    assert _annotation_from_schema({"type": "boolean"}) is bool
    assert _annotation_from_schema({"type": "array"}) == list[object]
    assert _annotation_from_schema({"type": "object"}) == dict[str, object]
    assert _annotation_from_schema({"type": ["null", "integer"]}) is int
    assert _annotation_from_schema("not a schema") is object

    with pytest.raises(ProblemEvaluationError, match="expected an object schema"):
        _proxy_signature(tool_name="bad", input_schema={"type": "array"})

    with pytest.raises(ProblemEvaluationError, match="required must be a sequence"):
        _proxy_signature(tool_name="bad", input_schema={"properties": {}, "required": 1})

    with pytest.raises(ProblemEvaluationError, match="required entries must be strings"):
        _proxy_signature(tool_name="bad", input_schema={"properties": {"x": {}}, "required": [1]})

    with pytest.raises(ProblemEvaluationError, match="required contains unknown properties"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"properties": {"x": {}}, "required": ["missing"]},
        )

    with pytest.raises(ProblemEvaluationError, match="property names must be strings"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"properties": {1: {"type": "string"}}},
        )

    with pytest.raises(ProblemEvaluationError, match="not a valid Python identifier"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"properties": {"not-valid-name": {"type": "string"}}},
        )


def test_mcp_helper_functions_cover_error_message_and_identifier_logic() -> None:
    structured_message = _upstream_error_message(
        cast(
            Any,
            SimpleNamespace(
                structuredContent={"detail": "upstream detail"},
                content=[],
            ),
        )
    )
    text_message = _upstream_error_message(
        cast(
            Any,
            SimpleNamespace(
                structuredContent=None,
                content=[SimpleNamespace(text="tool text detail")],
            ),
        )
    )
    empty_message = _upstream_error_message(
        cast(
            Any,
            SimpleNamespace(
                structuredContent={},
                content=[],
            ),
        )
    )

    assert structured_message == "upstream detail"
    assert text_message == "tool text detail"
    assert empty_message == "upstream tool returned an error result without details."
    assert _safe_identifier("tool-name/with spaces") == "tool_name_with_spaces"


def test_mcp_problem_rejects_duplicate_upstream_and_exposed_tool_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mcp_problem_module,
        "create_fastmcp_server",
        lambda *args, **kwargs: _FakeServer(),
    )
    monkeypatch.setattr(
        mcp_problem_module,
        "register_design_brief_resource",
        lambda *args, **kwargs: None,
    )

    problem = _problem("mcp_duplicate_tools")

    duplicate_tool = SimpleNamespace(
        name="echo",
        title="Echo",
        description="Echo tool",
        inputSchema={"type": "object", "properties": {}},
    )
    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: (duplicate_tool, duplicate_tool))
    with pytest.raises(ProblemEvaluationError, match="must be unique"):
        problem.to_mcp_server()

    problem = _problem("mcp_duplicate_exposed_tools")
    submit_tool = SimpleNamespace(
        name="submit_final",
        title="Submit",
        description="Submit tool",
        inputSchema={"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]},
    )
    final_answer_tool = SimpleNamespace(
        name="final_answer",
        title="Final",
        description="Final answer tool",
        inputSchema={"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]},
    )
    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: (submit_tool, final_answer_tool))
    server = problem.to_mcp_server()
    assert server is not None


def test_mcp_problem_close_helpers_and_discovery_guard_cover_event_loop_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mcp_problem_module,
        "create_fastmcp_server",
        lambda *args, **kwargs: _FakeServer(),
    )
    monkeypatch.setattr(
        mcp_problem_module,
        "register_design_brief_resource",
        lambda *args, **kwargs: None,
    )

    problem = _problem("mcp_close_helpers")
    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: ())
    server = problem.to_mcp_server()

    async def _call_close_inside_loop() -> None:
        with pytest.raises(RuntimeError, match="cannot be called from an active event loop"):
            cast(Any, server).close_upstream_session()

    asyncio.run(_call_close_inside_loop())

    problem = _problem("mcp_discovery_guard")

    class FakeStdioModule:
        stdio_client = None

        class StdioServerParameters:
            def __init__(self, **kwargs: object) -> None:
                self.kwargs = kwargs

    monkeypatch.setattr(
        mcp_problem_module,
        "_import_mcp_client_modules",
        lambda: (SimpleNamespace(run=lambda func: func()), object(), FakeStdioModule),
    )

    async def _discover_inside_loop() -> None:
        with pytest.raises(RuntimeError, match="outside an active event loop"):
            problem._discover_upstream_tools()

    asyncio.run(_discover_inside_loop())


def test_mcp_problem_build_proxy_tool_covers_error_and_fallback_payloads() -> None:
    problem = _problem("mcp_proxy_helper")

    class FakeSession:
        async def call_tool(self, name: str, arguments: dict[str, object]) -> SimpleNamespace:
            if name == "error_tool":
                return SimpleNamespace(
                    isError=True,
                    structuredContent={"message": "bad tool call"},
                    content=[],
                )
            return SimpleNamespace(
                isError=False,
                structuredContent=None,
                content=[SimpleNamespace(text="payload")],
            )

    fallback_tool = problem._build_proxy_tool(
        tool_name="fallback_tool",
        input_schema={
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "optional": {"type": "string"},
            },
            "required": ["message"],
        },
        session=cast(Any, FakeSession()),
    )
    payload = asyncio.run(fallback_tool(message="hello", optional=None))
    assert payload["tool_name"] == "fallback_tool"
    assert payload["is_error"] is False
    assert payload["structured_content"] is None

    error_tool = problem._build_proxy_tool(
        tool_name="error_tool",
        input_schema={"type": "object", "properties": {}},
        session=cast(Any, FakeSession()),
    )
    with pytest.raises(ValueError, match="bad tool call"):
        asyncio.run(error_tool())


def test_mcp_problem_from_manifest_wraps_parse_errors() -> None:
    manifest = SimpleNamespace(
        metadata=_metadata("mcp_bad_manifest"),
        parameters={"transport": "http"},
        statement_markdown="# bad manifest",
    )

    with pytest.raises(ProblemEvaluationError, match="Invalid MCP stdio parameters"):
        MCPProblem.from_manifest(manifest)
