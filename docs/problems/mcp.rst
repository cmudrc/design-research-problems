MCP Problems
============

MCP problems wrap upstream MCP servers as first-class packaged problems.
This family keeps the standard design-brief resource while exposing upstream
tool interfaces for agent-style workflows.

See :doc:`../problem_catalog/mcp` for the generated per-problem catalog pages.

The current implementation supports stdio-ingested upstream servers and proxies
their tools through ``to_mcp_server()`` while preserving upstream session state
within one event loop.

For packaged stdio manifests, ``[parameters].command`` may use the
``__python_executable__`` marker. At runtime, ``MCPProblem`` resolves this marker
to the current Python interpreter path before launching the upstream server.

The catalog currently includes ``mcp_build123d_parametric_mounting_bracket`` for
CAD-oriented agent workflows where the agent writes and evaluates Build123d
scripts through a package-owned backend.
