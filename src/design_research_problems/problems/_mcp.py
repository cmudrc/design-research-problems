"""Shared helpers for exposing problems through FastMCP."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Any, cast

import numpy

from design_research_problems._exceptions import MissingOptionalDependencyError

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from design_research_problems.problems._problem import Problem

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


def import_fastmcp() -> type[FastMCP]:
    """Import and return ``FastMCP`` lazily.

    Returns:
        FastMCP class object from the optional MCP dependency.

    Raises:
        MissingOptionalDependencyError: If the MCP dependency is unavailable.
    """
    try:
        module = import_module("mcp.server.fastmcp")
    except ImportError as exc:
        raise MissingOptionalDependencyError(
            "mcp is required for MCP server export. Install it with: pip install design-research-problems[mcp]"
        ) from exc
    return cast(type[Any], module.FastMCP)


def create_fastmcp_server(problem: Problem, *, server_name: str | None = None) -> FastMCP:
    """Create one FastMCP server instance for a problem.

    Args:
        problem: Problem instance to expose.
        server_name: Optional explicit MCP server name.

    Returns:
        Configured FastMCP server instance.
    """
    fastmcp_cls = import_fastmcp()
    return fastmcp_cls(server_name or problem.metadata.problem_id)


def register_design_brief_resource(server: FastMCP, *, brief_text: str) -> None:
    """Register the standard design-brief resource on one server.

    Args:
        server: Target FastMCP server.
        brief_text: Text payload returned by the resource.
    """

    @server.resource(
        "problem://design-brief",
        name="design-brief",
        title="Design Brief",
        description="Human-readable design brief for this problem.",
        mime_type="text/markdown",
    )
    def design_brief() -> str:
        """Return the canonical design brief."""
        return brief_text


def to_json_value(value: object) -> JsonValue:
    """Convert Python/domain values into JSON-safe data.

    Args:
        value: Arbitrary value to convert.

    Returns:
        JSON-safe scalar, list, or dictionary representation.
    """
    if value is None or isinstance(value, bool | int | float | str):
        return value

    if isinstance(value, numpy.generic):
        scalar = value.item()
        return to_json_value(scalar)

    if isinstance(value, numpy.ndarray):
        return [to_json_value(item) for item in value.tolist()]

    if is_dataclass(value) and not isinstance(value, type):
        return to_json_value(asdict(value))

    if isinstance(value, dict):
        return {str(key): to_json_value(item) for key, item in value.items()}

    if isinstance(value, list | tuple | set | frozenset):
        return [to_json_value(item) for item in value]

    if isinstance(value, Mapping):
        mapping = value.items()
        return {str(key): to_json_value(item) for key, item in mapping}

    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")

    return str(value)


def normalized_optional_text(value: str | None) -> str | None:
    """Normalize an optional user-provided text field.

    Args:
        value: Raw optional text.

    Returns:
        Stripped text or ``None`` when missing/empty.
    """
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None
