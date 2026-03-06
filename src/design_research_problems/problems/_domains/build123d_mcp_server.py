"""MCP stdio backend for Build123d-based CAD bracket workflows."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast

from mcp.server.fastmcp import Context, FastMCP

from design_research_problems.problems._domains.build123d_cad import (
    build123d_available,
    build123d_version,
    evaluate_scripted_part,
)


@dataclass
class _BackendState:
    """Per-server mutable state shared across MCP tool calls."""

    last_script_result: dict[str, Any] | None = None


@asynccontextmanager
async def _lifespan(_app: FastMCP[_BackendState]) -> AsyncIterator[_BackendState]:
    """Create one state container per backend server run."""
    yield _BackendState()


def _backend_state(ctx: Context) -> _BackendState:
    """Return the mutable backend state for the current request."""
    return cast(_BackendState, ctx.request_context.lifespan_context)


SERVER = FastMCP("drp-build123d-backend", lifespan=_lifespan)


@SERVER.tool(name="backend_status")
def backend_status(include_install_hint: bool = True) -> dict[str, object]:
    """Return backend availability status."""
    payload: dict[str, object] = {
        "backend": "build123d",
        "available": build123d_available(),
        "version": build123d_version(),
    }
    if include_install_hint:
        payload["install_hint"] = "pip install design-research-problems[cad]"
    return payload


@SERVER.tool(name="evaluate_scripted_part")
def evaluate_scripted_part_tool(
    ctx: Context,
    script: str,
    result_name: str = "result",
    include_script: bool = False,
) -> dict[str, object]:
    """Execute one agent-authored Build123d script and report geometry metrics."""
    report = evaluate_scripted_part(script, result_name=result_name)
    _backend_state(ctx).last_script_result = report
    payload: dict[str, object] = dict(report)
    if not include_script:
        payload.pop("script", None)
    return payload


@SERVER.tool(name="describe_last_script_result")
def describe_last_script_result(ctx: Context, include_script: bool = False) -> dict[str, object]:
    """Return the most recent scripted CAD evaluation."""
    state = _backend_state(ctx)
    if state.last_script_result is None:
        raise ValueError(
            "No script has been evaluated yet. Call evaluate_scripted_part first."
        )

    payload: dict[str, object] = dict(state.last_script_result)
    if not include_script:
        payload.pop("script", None)
    return payload


def main() -> None:
    """Run the Build123d backend on stdio transport."""
    SERVER.run(transport="stdio")


if __name__ == "__main__":
    main()
