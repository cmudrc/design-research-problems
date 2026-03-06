"""Inspect and exercise the MCP-backed Build123d mounting-bracket problem."""

from __future__ import annotations

import json
from collections.abc import Sequence
from textwrap import dedent
from typing import TYPE_CHECKING, Any, cast

import anyio

from design_research_problems import MissingOptionalDependencyError, get_problem

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

PROBLEM_ID = "mcp_build123d_parametric_mounting_bracket"
SERVER_NAME = "build123d-mounting-bracket-demo"
STARTER_SCRIPT = dedent(
    """
    from build123d import Align, BuildPart, Box, Cylinder, Location, Locations, Mode, fillet

    WIDTH = 80.0
    DEPTH = 40.0
    BASE_THICKNESS = 6.0
    FLANGE_HEIGHT = 40.0
    FLANGE_THICKNESS = 6.0
    HOLE_DIAMETER = 6.0

    with BuildPart() as part:
        Box(WIDTH, DEPTH, BASE_THICKNESS, align=(Align.CENTER, Align.CENTER, Align.MIN))
        flange_center_y = -DEPTH / 2.0 + FLANGE_THICKNESS / 2.0
        with Locations((0.0, flange_center_y, BASE_THICKNESS)):
            Box(WIDTH, FLANGE_THICKNESS, FLANGE_HEIGHT, align=(Align.CENTER, Align.CENTER, Align.MIN))

        for x_mm, y_mm in ((-30.0, -10.0), (30.0, -10.0), (-30.0, 10.0), (30.0, 10.0)):
            with Locations((x_mm, y_mm, 0.0)):
                Cylinder(
                    radius=HOLE_DIAMETER / 2.0,
                    height=BASE_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.MIN),
                    mode=Mode.SUBTRACT,
                )

        for z_mm in (16.0, 36.0):
            with Locations(Location((0.0, flange_center_y, z_mm), (90.0, 0.0, 0.0))):
                Cylinder(
                    radius=HOLE_DIAMETER / 2.0,
                    height=FLANGE_THICKNESS,
                    align=(Align.CENTER, Align.CENTER, Align.CENTER),
                    mode=Mode.SUBTRACT,
                )

        target_y = -DEPTH / 2.0 + FLANGE_THICKNESS
        inner_edges = [
            edge
            for edge in part.edges()
            if abs(edge.center().Y - target_y) <= 1e-6 and abs(edge.center().Z - BASE_THICKNESS) <= 1e-6
        ]
        radius = 4.0
        while inner_edges and radius >= 0.5:
            try:
                fillet(inner_edges, radius)
                break
            except ValueError:
                radius -= 0.5

    result = part.part
    """
).strip()


def _extract_structured_payload(payload: object) -> dict[str, object]:
    """Normalize one FastMCP ``call_tool`` payload into a dictionary.

    Args:
        payload: Raw payload returned by ``server.call_tool``.

    Returns:
        Parsed dictionary payload when available.
    """
    if isinstance(payload, tuple):
        _, structured = payload
        if isinstance(structured, dict):
            return cast(dict[str, object], structured)
        return {}

    content = cast(Sequence[Any], payload)
    if not content:
        return {}
    text = getattr(content[0], "text", None)
    if not isinstance(text, str):
        return {}
    parsed = json.loads(text)
    if isinstance(parsed, dict):
        return cast(dict[str, object], parsed)
    return {}


def create_server() -> FastMCP:
    """Create the MCP proxy server for this packaged problem.

    Returns:
        Configured FastMCP server instance.
    """
    problem = get_problem(PROBLEM_ID)
    return problem.to_mcp_server(server_name=SERVER_NAME, include_citation=False)


def _is_expected_build123d_runtime_unavailable_error(exc: BaseException) -> bool:
    """Return whether one exception indicates optional build123d runtime absence.

    Args:
        exc: Exception raised while exercising the Build123d MCP tools.

    Returns:
        ``True`` when the error matches expected optional-backend absence paths.
    """
    message = str(exc).lower()
    return (
        "build123d is not installed" in message
        or "tcl wasn't installed properly" in message
        or "upstream mcp tool 'evaluate_scripted_part' failed" in message
    )


async def run_summary(server: FastMCP) -> dict[str, object]:
    """Collect a short runtime summary from the wrapped MCP server.

    Returns:
        Summary payload with discovered tools, resources, and final-answer echo.
    """
    tools = await server.list_tools()
    resources = await server.list_resources()

    try:
        status_payload = await server.call_tool("backend_status", {})
        status = _extract_structured_payload(status_payload)
        eval_payload = await server.call_tool(
            "evaluate_scripted_part",
            {"script": STARTER_SCRIPT, "result_name": "result", "include_script": False},
        )
        evaluation = _extract_structured_payload(eval_payload)
        last_payload = await server.call_tool("describe_last_script_result", {"include_script": False})
        last_result = _extract_structured_payload(last_payload)
        final_answer_payload = await server.call_tool(
            "final_answer",
            {"answer": "Submitted a Build123d script that generates and validates the bracket geometry."},
        )
        final_answer = _extract_structured_payload(final_answer_payload)
    finally:
        close_upstream = getattr(server, "aclose_upstream_session", None)
        if callable(close_upstream):
            await close_upstream()

    return {
        "problem_id": PROBLEM_ID,
        "tool_count": len(tools),
        "tool_names": sorted(tool.name for tool in tools),
        "resource_uris": sorted(str(resource.uri) for resource in resources),
        "backend_available": status.get("available", False),
        "result_is_valid": evaluation.get("is_valid"),
        "volume_mm3": evaluation.get("volume_mm3"),
        "matches_nominal_envelope": cast(
            dict[str, object], evaluation.get("constraint_checks", {})
        ).get("matches_nominal_envelope"),
        "last_result_name": last_result.get("result_name"),
        "final_answer": final_answer.get("answer", "<missing>"),
    }


def main() -> int:
    """Run the Build123d MCP wrapper demo.

    Returns:
        Process exit code.
    """
    problem = get_problem(PROBLEM_ID)
    print("Problem id:", problem.metadata.problem_id)
    print("Upstream command:", problem.command)

    try:
        server = create_server()
        summary = anyio.run(run_summary, server)
    except (MissingOptionalDependencyError, ModuleNotFoundError) as exc:
        print(exc)
        print("Install the optional MCP dependency with: pip install design-research-problems[mcp]")
        return 0
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"build123d backend startup failed: {exc}")
        return 0
    except Exception as exc:
        if _is_expected_build123d_runtime_unavailable_error(exc):
            print(f"build123d backend startup failed: {exc}")
            return 0
        raise

    print("Tool count:", summary["tool_count"])
    print("Tools:", ", ".join(cast(list[str], summary["tool_names"])))
    print("Resources:", ", ".join(cast(list[str], summary["resource_uris"])))
    print("Backend available:", summary["backend_available"])
    print("Result valid:", summary["result_is_valid"])
    print("Volume (mm^3):", summary["volume_mm3"])
    print("Matches nominal envelope:", summary["matches_nominal_envelope"])
    print("Last result name:", summary["last_result_name"])
    print("final_answer answer:", summary["final_answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
