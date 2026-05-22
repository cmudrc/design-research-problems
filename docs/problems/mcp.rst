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

Packaged Problem Server
-----------------------

Any packaged problem that implements ``to_mcp_server()`` can be served directly
from the package CLI. This avoids writing a temporary server script in a
notebook before connecting another agent runtime.

.. code-block:: bash

   python -m design_research_problems.mcp pill_capsule_min_area --no-citation

Use the same module path from a stdio-capable MCP client. For example, a
notebook that uses ``design-research-agents`` can point its toolbox at the
packaged problem server:

.. code-block:: python

   import sys

   import design_research_agents as drag

   toolbox = drag.Toolbox(
       enable_core_tools=False,
       mcp_servers=(
           drag.MCPServerConfig(
               id="drp_problem",
               command=(
                   sys.executable,
                   "-m",
                   "design_research_problems.mcp",
                   "pill_capsule_min_area",
                   "--no-citation",
               ),
           ),
       ),
   )

Install the MCP extra first when the optional dependency is not already present:

.. code-block:: bash

   pip install "design-research-problems[mcp]"
