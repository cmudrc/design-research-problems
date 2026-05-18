"""Command-line entrypoint for serving packaged problems over MCP stdio."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from design_research_problems import MissingOptionalDependencyError, get_problem


def build_parser() -> argparse.ArgumentParser:
    """Build the problem MCP server CLI parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="python -m design_research_problems.mcp",
        description="Serve one packaged design-research problem as an MCP stdio server.",
    )
    parser.add_argument("problem_id", help="Packaged problem id to expose.")
    parser.add_argument(
        "--server-name",
        default=None,
        help="Optional MCP server name. Defaults to the problem's package-provided name.",
    )
    parser.add_argument(
        "--no-citation",
        action="store_true",
        help="Omit citation text from the served problem brief when supported.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio",),
        default="stdio",
        help="MCP transport to run. Only stdio is supported.",
    )
    return parser


def create_problem_server(
    problem_id: str,
    *,
    server_name: str | None = None,
    include_citation: bool = True,
) -> Any:
    """Create a FastMCP server for one packaged problem.

    Args:
        problem_id: Packaged problem id to load.
        server_name: Optional MCP server name override.
        include_citation: Whether to include citation text in the problem brief.

    Returns:
        Configured FastMCP server.
    """
    problem = get_problem(problem_id)
    return problem.to_mcp_server(server_name=server_name, include_citation=include_citation)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the packaged problem MCP server CLI.

    Args:
        argv: Optional argument sequence excluding the executable name.

    Returns:
        Process-style exit code. Real server runs usually block until the stdio
        transport closes.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        server = create_problem_server(
            args.problem_id,
            server_name=args.server_name,
            include_citation=not args.no_citation,
        )
    except MissingOptionalDependencyError as exc:
        parser.exit(
            2,
            f"{exc}\nInstall optional MCP support with: pip install 'design-research-problems[mcp]'\n",
        )

    server.run(transport=args.transport)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
