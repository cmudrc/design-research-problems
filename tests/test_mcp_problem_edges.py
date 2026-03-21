from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from typing import Any, cast

import pytest

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems import ProblemKind, ProblemMetadata, ProblemTaxonomy
from design_research_problems.problems import _mcp_problem as mcp_problem_module
from design_research_problems.problems._mcp_problem import (
    MCPProblem,
    _annotation_from_schema,
    _proxy_signature,
    _safe_identifier,
    _serialize_content_block,
    _upstream_error_message,
    parse_mcp_stdio_parameters,
)


def _metadata(problem_id: str) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title="MCP Edge Problem",
        summary="Synthetic MCP-backed problem for edge-path coverage.",
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
            tags=("mcp", "proxy"),
        ),
        citations=(),
        assets=(),
        capabilities=("statement-markdown",),
        study_suitability=(),
    )


class _FakeServer:
    def __init__(self) -> None:
        self.tools: list[dict[str, object]] = []

    def add_tool(self, func: object, *, name: str, title: str | None = None, description: str | None = None) -> None:
        self.tools.append(
            {
                "func": func,
                "name": name,
                "title": title,
                "description": description,
            }
        )


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({}, "transport='stdio'"),
        ({"transport": "stdio", "command": ""}, "non-empty string command"),
        ({"transport": "stdio", "command": "python", "args": "not-a-sequence"}, "args as a sequence"),
        ({"transport": "stdio", "command": "python", "args": [1]}, "args entries must be strings"),
        ({"transport": "stdio", "command": "python", "cwd": ""}, "cwd must be a non-empty string"),
        ({"transport": "stdio", "command": "python", "env": []}, "env must be a mapping"),
        (
            {"transport": "stdio", "command": "python", "env": {"OK": 1}},
            "env entries must use string keys and string values",
        ),
    ],
)
def test_parse_mcp_stdio_parameters_rejects_invalid_payloads(parameters: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_mcp_stdio_parameters(parameters)


def test_from_manifest_wraps_stdio_validation_errors() -> None:
    manifest = SimpleNamespace(
        metadata=_metadata("bad_manifest"),
        parameters={"transport": "stdio"},
        statement_markdown="# Bad manifest",
    )

    with pytest.raises(ProblemEvaluationError, match="Invalid MCP stdio parameters"):
        MCPProblem.from_manifest(manifest)


def test_to_mcp_server_handles_duplicate_names_and_fallback_submit_final(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_problem_module, "create_fastmcp_server", lambda *args, **kwargs: _FakeServer())
    monkeypatch.setattr(mcp_problem_module, "register_design_brief_resource", lambda *args, **kwargs: None)

    problem = MCPProblem.from_stdio(metadata=_metadata("proxy"), command="python")

    duplicate_upstream = (
        SimpleNamespace(
            name="echo",
            title="Echo",
            description=None,
            inputSchema={"type": "object", "properties": {}},
        ),
        SimpleNamespace(
            name="echo",
            title="Echo Again",
            description=None,
            inputSchema={"type": "object", "properties": {}},
        ),
    )
    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: duplicate_upstream)
    with pytest.raises(ProblemEvaluationError, match="must be unique"):
        problem.to_mcp_server()

    monkeypatch.setattr(problem, "_discover_upstream_tools", lambda: ())
    server = problem.to_mcp_server()
    submit_tool = next(entry["func"] for entry in server.tools if entry["name"] == "submit_final")
    assert callable(submit_tool)

    payload = submit_tool(answer="  final answer  ", justification="  rationale  ")
    assert payload["answer"] == "final answer"
    assert payload["justification"] == "rationale"

    with pytest.raises(ValueError, match="non-empty string"):
        submit_tool(answer="   ")

    server.close_upstream_session()

    async def close_inside_loop() -> None:
        with pytest.raises(RuntimeError, match="active event loop"):
            server.close_upstream_session()

    asyncio.run(close_inside_loop())


def test_discover_upstream_tools_refuses_active_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSession:
        async def __aenter__(self) -> FakeSession:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

        async def initialize(self) -> None:
            return None

        async def list_tools(self) -> SimpleNamespace:
            return SimpleNamespace(tools=())

    class FakeStdioContext:
        async def __aenter__(self) -> tuple[object, object]:
            return (object(), object())

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

    fake_stdio = SimpleNamespace(
        stdio_client=lambda params: FakeStdioContext(),
        StdioServerParameters=lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        mcp_problem_module,
        "_import_mcp_client_modules",
        lambda: (SimpleNamespace(run=lambda coro: ()), FakeSession, fake_stdio),
    )

    problem = MCPProblem.from_stdio(metadata=_metadata("loop_bound"), command="python")

    async def invoke() -> None:
        with pytest.raises(RuntimeError, match="outside an active event loop"):
            problem._discover_upstream_tools()

    asyncio.run(invoke())


def test_proxy_helpers_cover_error_conversion_and_schema_edges() -> None:
    problem = MCPProblem.from_stdio(metadata=_metadata("proxy_helpers"), command="python")

    class FakeSession:
        def __init__(self, result: object) -> None:
            self.result = result
            self.seen_arguments: dict[str, object] | None = None

        async def call_tool(self, name: str, arguments: dict[str, object]) -> object:
            del name
            self.seen_arguments = dict(arguments)
            return self.result

    error_session = FakeSession(
        SimpleNamespace(
            isError=True,
            structuredContent={"message": "bad input"},
            content=[],
        )
    )
    proxy = problem._build_proxy_tool(
        tool_name="tool-name",
        input_schema={
            "type": "object",
            "properties": {
                "required_text": {"type": "string"},
                "optional_flag": {"type": "boolean"},
            },
            "required": ["required_text"],
        },
        session=error_session,
    )

    with pytest.raises(ValueError, match="bad input"):
        asyncio.run(proxy(required_text="hello", optional_flag=None))
    assert error_session.seen_arguments == {"required_text": "hello"}
    assert cast(Any, proxy).__name__ == "proxy_tool_name"

    class DumpableBlock:
        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"kind": "dumped"}

    success_session = FakeSession(
        SimpleNamespace(
            isError=False,
            structuredContent=["not", "a", "mapping"],
            content=[DumpableBlock(), SimpleNamespace(text="fallback")],
        )
    )
    proxy = problem._build_proxy_tool(
        tool_name="mixed content",
        input_schema={"type": "object", "properties": {"item_count": {"type": "integer"}}},
        session=success_session,
    )
    payload = asyncio.run(proxy(item_count=2))
    assert payload["tool_name"] == "mixed content"
    assert payload["structured_content"] == ["not", "a", "mapping"]
    assert payload["content"][0] == {"kind": "dumped"}

    with pytest.raises(ProblemEvaluationError, match="expected an object schema"):
        _proxy_signature(tool_name="bad", input_schema={"type": "array"})
    with pytest.raises(ProblemEvaluationError, match="required must be a sequence"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"type": "object", "properties": {}, "required": "name"},
        )
    with pytest.raises(ProblemEvaluationError, match="required entries must be strings"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"type": "object", "properties": {"name": {}}, "required": [1]},
        )
    with pytest.raises(ProblemEvaluationError, match="unknown properties"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"type": "object", "properties": {"name": {}}, "required": ["missing"]},
        )
    with pytest.raises(ProblemEvaluationError, match="property names must be strings"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"type": "object", "properties": {1: {}}, "required": []},
        )
    with pytest.raises(ProblemEvaluationError, match="not a valid Python identifier"):
        _proxy_signature(
            tool_name="bad",
            input_schema={"type": "object", "properties": {"not-valid": {}}, "required": []},
        )

    signature = _proxy_signature(
        tool_name="typed",
        input_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name"],
        },
    )
    assert isinstance(signature, inspect.Signature)
    assert signature.parameters["name"].default is inspect._empty
    assert signature.parameters["count"].default is None

    assert _annotation_from_schema({"type": "string"}) is str
    assert _annotation_from_schema({"type": "number"}) is float
    assert _annotation_from_schema({"type": "integer"}) is int
    assert _annotation_from_schema({"type": "boolean"}) is bool
    assert _annotation_from_schema({"type": "array"}) == list[object]
    assert _annotation_from_schema({"type": "object"}) == dict[str, object]
    assert _annotation_from_schema({"type": ["null", "string"]}) is str
    assert _annotation_from_schema("not-a-mapping") is object

    assert _serialize_content_block(SimpleNamespace(model_dump=lambda mode: {"mode": mode})) == {"mode": "json"}
    assert _serialize_content_block({"raw": True}) == {"raw": True}

    assert (
        _upstream_error_message(
            SimpleNamespace(structuredContent={"detail": "boom"}, content=[]),
        )
        == "boom"
    )
    assert (
        _upstream_error_message(
            SimpleNamespace(
                structuredContent=None,
                content=[SimpleNamespace(text="fallback")],
            ),
        )
        == "fallback"
    )
    assert (
        _upstream_error_message(SimpleNamespace(structuredContent=None, content=[SimpleNamespace(text="  ")]))
        == "upstream tool returned an error result without details."
    )

    assert _safe_identifier("tool-name/with spaces") == "tool_name_with_spaces"
