"""Run an end-to-end MCP roundtrip for the peanut shelling design brief."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from design_research_problems import MissingOptionalDependencyError, get_problem

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import CallToolResult

PROBLEM_ID = "ideation_peanut_shelling_fu_cagan_kotovsky_2010"
SERVER_NAME = "peanut-sheller-demo"


def create_server() -> FastMCP:
    """Create the MCP server instance for this demo.

    Returns:
        Configured FastMCP server for the peanut shelling text problem.

    Raises:
        MissingOptionalDependencyError: If the optional MCP dependency is not
            installed.
    """
    problem = get_problem(PROBLEM_ID)
    return problem.to_mcp_server(server_name=SERVER_NAME)


def serve_stdio() -> None:
    """Run the demo MCP server on stdio transport.

    Returns:
        None.
    """
    server = create_server()
    server.run(transport="stdio")


def _extract_answer(result: CallToolResult) -> str:
    """Extract one human-readable answer string from a tool response.

    Args:
        result: Tool response from ``final_answer``.

    Returns:
        Submitted answer text when available, or fallback text.
    """
    structured_content = result.structuredContent
    if isinstance(structured_content, dict):
        answer = structured_content.get("answer")
        if isinstance(answer, str):
            return answer

    for item in result.content:
        text = getattr(item, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
    return "<answer not available in tool payload>"


async def run_roundtrip() -> dict[str, object]:
    """Start a subprocess MCP server and call its tools.

    Returns:
        Roundtrip details containing discovered tools and final answer payload.

    Raises:
        ModuleNotFoundError: If MCP client modules are unavailable.
        MissingOptionalDependencyError: If server creation fails due to missing
            optional dependency.
    """
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    create_server()

    example_path = Path(__file__).resolve()
    repo_root = example_path.parents[2]
    src_path = repo_root / "src"

    env = dict(os.environ)
    current_pythonpath = env.get("PYTHONPATH")
    if current_pythonpath:
        env["PYTHONPATH"] = f"{src_path}{os.pathsep}{current_pythonpath}"
    else:
        env["PYTHONPATH"] = str(src_path)

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(example_path), "--serve"],
        cwd=str(repo_root),
        env=env,
    )

    async with stdio_client(server_parameters) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            submitted_answer = "A hand-cranked sheller with adjustable rollers and manual sorting."
            call_result = await session.call_tool("final_answer", {"answer": submitted_answer})

    tool_names = sorted(tool.name for tool in tools_result.tools)
    return {
        "problem_id": PROBLEM_ID,
        "tool_count": len(tool_names),
        "tool_names": tool_names,
        "answer": _extract_answer(call_result),
    }


def main(argv: list[str] | None = None) -> int:
    """Run the end-to-end roundtrip or server-only mode.

    Args:
        argv: Optional CLI argument override.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run server-only mode for stdio MCP transport.",
    )
    args = parser.parse_args(argv)

    if args.serve:
        try:
            serve_stdio()
        except (MissingOptionalDependencyError, ModuleNotFoundError) as exc:
            print(exc)
            print("Install the optional MCP dependency with: pip install design-research-problems[mcp]")
        return 0

    try:
        import anyio

        summary = anyio.run(run_roundtrip)
    except (MissingOptionalDependencyError, ModuleNotFoundError) as exc:
        print(exc)
        print("Install the optional MCP dependency with: pip install design-research-problems[mcp]")
        return 0

    print("Problem id:", summary["problem_id"])
    print("Tool count:", summary["tool_count"])
    print("Tools:", ", ".join(str(name) for name in summary["tool_names"]))
    print("final_answer answer:", summary["answer"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
