"""MCP-backed problem family that proxies upstream MCP tools."""

from __future__ import annotations

import asyncio
import inspect
import sys
from collections.abc import Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, cast

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._mcp import (
    create_fastmcp_server,
    register_design_brief_resource,
    to_json_value,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._problem import Problem

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult
    from mcp.types import Tool as MCPTool

    from design_research_problems._catalog._manifest import ProblemManifest


@dataclass(frozen=True)
class MCPStdioConfig:
    """Parsed stdio transport parameters for one MCP-backed problem."""

    command: str
    args: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str]


def _resolve_stdio_command(command: str) -> str:
    """Resolve special stdio command markers to executable paths.

    Args:
        command: Raw command value from constructor or manifest parameters.

    Returns:
        Resolved executable command string.
    """
    if command == "__python_executable__":
        return sys.executable
    return command


def parse_mcp_stdio_parameters(parameters: Mapping[str, object]) -> MCPStdioConfig:
    """Parse MCP stdio configuration from manifest parameters.

    Args:
        parameters: Manifest ``[parameters]`` payload.

    Returns:
        Parsed stdio configuration.

    Raises:
        ValueError: If the payload does not match the expected schema.
    """
    transport_raw = parameters.get("transport")
    if not isinstance(transport_raw, str) or transport_raw.strip().lower() != "stdio":
        raise ValueError("mcp parameters must declare transport='stdio'.")

    command_raw = parameters.get("command")
    if not isinstance(command_raw, str) or not command_raw.strip():
        raise ValueError("mcp stdio parameters require a non-empty string command.")
    command = command_raw.strip()

    args_raw = parameters.get("args", ())
    if isinstance(args_raw, str | bytes) or not isinstance(args_raw, Sequence):
        raise ValueError("mcp stdio parameters require args as a sequence of strings.")
    parsed_args: list[str] = []
    for arg in args_raw:
        if not isinstance(arg, str):
            raise ValueError("mcp stdio args entries must be strings.")
        parsed_args.append(arg)

    cwd_raw = parameters.get("cwd")
    cwd: str | None = None
    if cwd_raw is not None:
        if not isinstance(cwd_raw, str) or not cwd_raw.strip():
            raise ValueError("mcp stdio cwd must be a non-empty string when provided.")
        cwd = cwd_raw.strip()

    env_raw = parameters.get("env", {})
    if env_raw is None:
        env_raw = {}
    if not isinstance(env_raw, Mapping):
        raise ValueError("mcp stdio env must be a mapping of string keys and values.")
    env: dict[str, str] = {}
    for key, value in env_raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("mcp stdio env entries must use string keys and string values.")
        env[key] = value

    return MCPStdioConfig(
        command=command,
        args=tuple(parsed_args),
        cwd=cwd,
        env=MappingProxyType(env),
    )


class _LoopBoundUpstreamSession:
    """Lazy persistent upstream session bound to one running event loop."""

    def __init__(self, stdio_config: MCPStdioConfig) -> None:
        self._stdio_config = stdio_config
        self._bound_loop: asyncio.AbstractEventLoop | None = None
        self._loop_lock: asyncio.Lock | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._session: object | None = None
        self._closed = False

    @property
    def has_active_session(self) -> bool:
        """Return whether an upstream session has been initialized."""
        return self._session is not None

    async def call_tool(self, name: str, arguments: Mapping[str, object]) -> CallToolResult:
        """Call one upstream tool through the persistent session.

        Args:
            name: Upstream MCP tool name.
            arguments: Tool arguments.

        Returns:
            Upstream call result object.
        """
        session = await self._ensure_session()
        session_obj = cast(Any, session)
        return cast("CallToolResult", await session_obj.call_tool(name, dict(arguments)))

    async def aclose(self) -> None:
        """Close the persistent upstream session on its bound event loop.

        Raises:
            RuntimeError: If called from a different event loop than the session
                that initialized the upstream client.
        """
        current_loop = asyncio.get_running_loop()
        if self._bound_loop is not None and self._bound_loop is not current_loop:
            raise RuntimeError(
                "This wrapped MCP server is bound to a different event loop. "
                "Call await server.aclose_upstream_session() from the same event loop used for tool calls."
            )
        if self._loop_lock is None:
            self._loop_lock = asyncio.Lock()

        async with self._loop_lock:
            exit_stack = self._exit_stack
            self._session = None
            self._exit_stack = None
            self._closed = True

        if exit_stack is not None:
            await exit_stack.aclose()

    async def _ensure_session(self) -> object:
        """Create or return the loop-bound upstream session.

        Returns:
            Initialized ``ClientSession`` object.

        Raises:
            RuntimeError: If reused across different event loops.
        """
        if self._closed:
            raise RuntimeError(
                "The upstream MCP session has been closed. "
                "Create a new wrapped server by calling to_mcp_server() again."
            )
        current_loop = asyncio.get_running_loop()
        if self._bound_loop is None:
            self._bound_loop = current_loop
        elif self._bound_loop is not current_loop:
            raise RuntimeError(
                "This wrapped MCP server is bound to a different event loop. "
                "Create a new server by calling to_mcp_server() again."
            )

        if self._loop_lock is None:
            self._loop_lock = asyncio.Lock()

        async with self._loop_lock:
            if self._session is not None:
                return self._session

            _anyio_module, client_session_cls, stdio_module = _import_mcp_client_modules()
            stdio_module_any = cast(Any, stdio_module)
            client_session_cls_any = cast(Any, client_session_cls)
            stdio_client = stdio_module_any.stdio_client
            params = stdio_module_any.StdioServerParameters(
                command=self._stdio_config.command,
                args=list(self._stdio_config.args),
                cwd=self._stdio_config.cwd,
                env=dict(self._stdio_config.env) if self._stdio_config.env else None,
            )

            exit_stack = AsyncExitStack()
            read_stream, write_stream = await exit_stack.enter_async_context(stdio_client(params))
            session = await exit_stack.enter_async_context(client_session_cls_any(read_stream, write_stream))
            await cast(Any, session).initialize()
            self._session = session
            self._exit_stack = exit_stack
            return session


class MCPProblem(Problem):
    """Problem wrapper that ingests one external MCP server over stdio."""

    def __init__(
        self,
        *,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        command: str,
        args: tuple[str, ...] = (),
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Store metadata and upstream stdio server launch configuration.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Canonical Markdown statement.
            command: Executable command used to start the upstream MCP server.
            args: Command-line arguments passed to the upstream server.
            cwd: Optional working directory for the subprocess.
            env: Optional environment variables merged over inherited defaults.
            resource_bundle: Optional package-resource loader for problem assets.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.transport: Literal["stdio"] = "stdio"
        self.command = _resolve_stdio_command(command)
        self.args = tuple(args)
        self.cwd = cwd
        self.env = MappingProxyType(dict(env or {}))
        self._stdio_config = MCPStdioConfig(
            command=self.command,
            args=self.args,
            cwd=self.cwd,
            env=self.env,
        )

    @classmethod
    def from_stdio(
        cls,
        *,
        metadata: ProblemMetadata,
        command: str,
        args: Sequence[str] = (),
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
    ) -> MCPProblem:
        """Construct one MCP-backed problem directly from stdio launch parameters.

        Args:
            metadata: Shared packaged metadata.
            command: Executable command used to start the upstream MCP server.
            args: Command-line arguments passed to the upstream server.
            cwd: Optional working directory for the subprocess.
            env: Optional environment variables merged over inherited defaults.
            statement_markdown: Canonical Markdown statement.
            resource_bundle: Optional package-resource loader for problem assets.

        Returns:
            MCP problem instance with validated stdio configuration.
        """
        parsed = parse_mcp_stdio_parameters(
            {
                "transport": "stdio",
                "command": command,
                "args": list(args),
                "cwd": cwd,
                "env": dict(env or {}),
            }
        )
        return cls(
            metadata=metadata,
            statement_markdown=statement_markdown,
            command=parsed.command,
            args=parsed.args,
            cwd=parsed.cwd,
            env=parsed.env,
            resource_bundle=resource_bundle,
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> MCPProblem:
        """Construct one MCP-backed problem directly from a packaged manifest.

        Args:
            manifest: Parsed manifest used to initialize the problem instance.

        Returns:
            Problem instance populated from the manifest data.

        Raises:
            ProblemEvaluationError: If the manifest parameters are invalid.
        """
        try:
            config = parse_mcp_stdio_parameters(manifest.parameters)
        except ValueError as exc:
            raise ProblemEvaluationError(
                f"Invalid MCP stdio parameters for {manifest.metadata.problem_id!r}: {exc}"
            ) from exc
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            command=config.command,
            args=config.args,
            cwd=config.cwd,
            env=config.env,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    def to_mcp_server(
        self,
        *,
        server_name: str | None = None,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> FastMCP:
        """Expose this MCP-backed problem through a local FastMCP proxy server.

        The exported server exposes the standard ``problem://design-brief``
        resource and proxies upstream MCP tools one-for-one.

        Args:
            server_name: Optional explicit server name.
            include_citation: Whether the design brief includes citations.
            citation_mode: Citation rendering mode for the design brief.

        Returns:
            Configured FastMCP server.

        Raises:
            ProblemEvaluationError: If discovered upstream tool schemas are not
                compatible with keyword-argument proxy wrapping.
        """
        server = create_fastmcp_server(self, server_name=server_name)
        register_design_brief_resource(
            server,
            brief_text=self.render_brief(include_citation=include_citation, citation_mode=citation_mode),
        )

        upstream_tools = self._discover_upstream_tools()
        if len({tool.name for tool in upstream_tools}) != len(upstream_tools):
            raise ProblemEvaluationError("Upstream MCP tool names must be unique.")

        persistent_session = _LoopBoundUpstreamSession(self._stdio_config)
        upstream_tool_names = {tool.name for tool in upstream_tools}
        expose_submit_final = "submit_final" in upstream_tool_names or "final_answer" in upstream_tool_names
        exposed_names: set[str] = set()
        for tool in upstream_tools:
            proxy_tool = self._build_proxy_tool(
                tool_name=tool.name, input_schema=tool.inputSchema, session=persistent_session
            )
            description = (tool.description or "").strip() or f"Proxy call to upstream MCP tool {tool.name!r}."
            exposed_name = (
                "submit_final"
                if tool.name == "final_answer" and "submit_final" not in upstream_tool_names
                else tool.name
            )
            if exposed_name in exposed_names:
                raise ProblemEvaluationError(f"Duplicate exposed MCP tool name: {exposed_name!r}")
            exposed_names.add(exposed_name)
            server.add_tool(
                proxy_tool,
                name=exposed_name,
                title=tool.title,
                description=description,
            )

        if not expose_submit_final:

            def submit_final(answer: str, justification: str | None = None) -> dict[str, object]:
                """Submit one free-text final answer.

                Args:
                    answer: Free-text final answer string.
                    justification: Optional rationale for the submission.

                Returns:
                    MCP-ready submission payload for the provided answer.

                Raises:
                    ValueError: If the answer is empty after trimming whitespace.
                """
                normalized_answer = answer.strip()
                if not normalized_answer:
                    raise ValueError("answer must be a non-empty string.")
                return {
                    "problem_id": self.metadata.problem_id,
                    "problem_kind": self.metadata.kind.value,
                    "answer": normalized_answer,
                    "justification": None if justification is None else justification.strip() or None,
                }

            server.add_tool(
                submit_final,
                name="submit_final",
                title="Submit Final Answer",
                description="Submit a free-text final answer for this design brief.",
            )

        async def aclose_upstream_session() -> None:
            """Close the proxied upstream MCP session for this server instance."""
            await persistent_session.aclose()

        def close_upstream_session() -> None:
            """Close the proxied session when no upstream session has been opened.

            If tool calls have already initialized the upstream session, callers
            must use ``await server.aclose_upstream_session()`` on the same event
            loop used for those tool calls.
            """
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                if persistent_session.has_active_session:
                    raise RuntimeError(
                        "An upstream session is active. "
                        "Use await server.aclose_upstream_session() from the same event loop used for tool calls."
                    ) from None
                return
            raise RuntimeError(
                "close_upstream_session() cannot be called from an active event loop. "
                "Use await server.aclose_upstream_session() instead."
            )

        server_any = cast(Any, server)
        server_any.aclose_upstream_session = aclose_upstream_session
        server_any.close_upstream_session = close_upstream_session

        return server

    def _discover_upstream_tools(self) -> tuple[MCPTool, ...]:
        """List upstream MCP tools using one short-lived discovery session.

        Returns:
            Discovered upstream tool definitions.
        """
        anyio_module, client_session_cls, stdio_module = _import_mcp_client_modules()
        stdio_module_any = cast(Any, stdio_module)
        client_session_cls_any = cast(Any, client_session_cls)
        stdio_client = stdio_module_any.stdio_client
        params = stdio_module_any.StdioServerParameters(
            command=self._stdio_config.command,
            args=list(self._stdio_config.args),
            cwd=self._stdio_config.cwd,
            env=dict(self._stdio_config.env) if self._stdio_config.env else None,
        )

        async def _discover() -> tuple[MCPTool, ...]:
            async with stdio_client(params) as streams:
                read_stream, write_stream = streams
                async with client_session_cls_any(read_stream, write_stream) as session:
                    await cast(Any, session).initialize()
                    listed = await cast(Any, session).list_tools()
                    return tuple(cast(Any, listed).tools)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                "MCP discovery must run outside an active event loop. Call to_mcp_server() from synchronous setup code."
            )
        return tuple(cast(Any, anyio_module).run(_discover))

    def _build_proxy_tool(
        self,
        *,
        tool_name: str,
        input_schema: Mapping[str, object],
        session: _LoopBoundUpstreamSession,
    ) -> Any:
        """Build one proxy tool wrapper from an upstream schema.

        Args:
            tool_name: Upstream tool name.
            input_schema: Upstream JSON schema for tool inputs.
            session: Shared persistent upstream session handle.

        Returns:
            Proxy function suitable for ``server.add_tool``.
        """
        signature = _proxy_signature(tool_name=tool_name, input_schema=input_schema)

        optional_none_keys = tuple(
            parameter.name for parameter in signature.parameters.values() if parameter.default is None
        )

        async def proxy_tool(**kwargs: object) -> dict[str, object]:
            """Call the upstream tool and normalize the response payload."""
            forwarded = dict(kwargs)
            for key in optional_none_keys:
                if forwarded.get(key) is None:
                    forwarded.pop(key, None)

            result = await session.call_tool(tool_name, forwarded)
            if result.isError:
                message = _upstream_error_message(result)
                raise ValueError(f"Upstream MCP tool {tool_name!r} failed: {message}")

            structured = result.structuredContent
            if isinstance(structured, dict):
                normalized = to_json_value(structured)
                return cast(dict[str, object], normalized)

            return {
                "tool_name": tool_name,
                "structured_content": to_json_value(structured),
                "content": [_serialize_content_block(block) for block in result.content],
                "is_error": False,
            }

        proxy_tool.__name__ = f"proxy_{_safe_identifier(tool_name)}"
        proxy_tool_any = cast(Any, proxy_tool)
        proxy_tool_any.__signature__ = signature
        return proxy_tool


def _import_mcp_client_modules() -> tuple[Any, Any, Any]:
    """Import MCP client modules lazily.

    Returns:
        Tuple of imported modules/classes for anyio + MCP client stdio support.

    Raises:
        MissingOptionalDependencyError: If optional MCP dependencies are missing.
    """
    anyio_module = import_optional_module(
        "anyio",
        required_for="MCP server export and ingestion proxying",
        extras=("mcp",),
        dependency_label="anyio",
    )
    session_module = import_optional_module(
        "mcp.client.session",
        required_for="MCP server export and ingestion proxying",
        extras=("mcp",),
        dependency_label="mcp",
    )
    stdio_module = import_optional_module(
        "mcp.client.stdio",
        required_for="MCP server export and ingestion proxying",
        extras=("mcp",),
        dependency_label="mcp",
    )
    return anyio_module, session_module.ClientSession, stdio_module


def _proxy_signature(*, tool_name: str, input_schema: Mapping[str, object]) -> inspect.Signature:
    """Build an inspect signature from one upstream MCP tool schema.

    Args:
        tool_name: Upstream tool name.
        input_schema: Upstream JSON schema payload.

    Returns:
        Keyword-only signature for proxy tool registration.

    Raises:
        ProblemEvaluationError: If the schema is unsupported.
    """
    schema_type = input_schema.get("type")
    if schema_type not in (None, "object"):
        raise ProblemEvaluationError(
            f"Unsupported input schema for upstream tool {tool_name!r}: "
            "expected an object schema with named properties."
        )

    properties = input_schema.get("properties")
    if not isinstance(properties, Mapping):
        raise ProblemEvaluationError(
            f"Unsupported input schema for upstream tool {tool_name!r}: missing object-style named properties."
        )

    required_raw = input_schema.get("required", ())
    if required_raw is None:
        required_raw = ()
    if isinstance(required_raw, str | bytes) or not isinstance(required_raw, Sequence):
        raise ProblemEvaluationError(
            f"Unsupported input schema for upstream tool {tool_name!r}: required must be a sequence of property names."
        )

    required_names: set[str] = set()
    for item in required_raw:
        if not isinstance(item, str):
            raise ProblemEvaluationError(
                f"Unsupported input schema for upstream tool {tool_name!r}: required entries must be strings."
            )
        required_names.add(item)

    property_names = {str(name) for name in properties}
    unknown_required = required_names - property_names
    if unknown_required:
        raise ProblemEvaluationError(
            f"Unsupported input schema for upstream tool {tool_name!r}: "
            f"required contains unknown properties {sorted(unknown_required)!r}."
        )

    parameters: list[inspect.Parameter] = []
    for raw_name, schema in properties.items():
        if not isinstance(raw_name, str):
            raise ProblemEvaluationError(
                f"Unsupported input schema for upstream tool {tool_name!r}: property names must be strings."
            )
        if not raw_name.isidentifier():
            raise ProblemEvaluationError(
                f"Unsupported input schema for upstream tool {tool_name!r}: "
                f"property name {raw_name!r} is not a valid Python identifier."
            )

        annotation = _annotation_from_schema(schema)
        if raw_name in required_names:
            default = inspect._empty
        else:
            annotation = annotation | None
            default = None

        parameters.append(
            inspect.Parameter(
                raw_name,
                kind=inspect.Parameter.KEYWORD_ONLY,
                annotation=annotation,
                default=default,
            )
        )

    return inspect.Signature(parameters=parameters, return_annotation=dict[str, object])


def _annotation_from_schema(schema: object) -> Any:
    """Map one JSON-schema field descriptor to a Python annotation."""
    if not isinstance(schema, Mapping):
        return object
    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        non_null = [entry for entry in schema_type if entry != "null"]
        schema_type = non_null[0] if non_null else None

    if schema_type == "string":
        return str
    if schema_type == "number":
        return float
    if schema_type == "integer":
        return int
    if schema_type == "boolean":
        return bool
    if schema_type == "array":
        return list[object]
    if schema_type == "object":
        return dict[str, object]
    return object


def _serialize_content_block(block: object) -> object:
    """Convert one upstream MCP content block into JSON-safe data."""
    dump_method = getattr(block, "model_dump", None)
    if callable(dump_method):
        return to_json_value(dump_method(mode="json"))
    return to_json_value(block)


def _upstream_error_message(result: CallToolResult) -> str:
    """Extract a readable upstream error message from one MCP result."""
    structured = result.structuredContent
    if isinstance(structured, Mapping):
        for key in ("message", "error", "detail"):
            value = structured.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for block in result.content:
        text = getattr(block, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return "upstream tool returned an error result without details."


def _safe_identifier(name: str) -> str:
    """Convert one arbitrary string into a Python identifier-like token."""
    token = "".join(char if (char.isalnum() or char == "_") else "_" for char in name)
    return token or "tool"


__all__ = ["MCPProblem", "MCPStdioConfig", "parse_mcp_stdio_parameters"]
