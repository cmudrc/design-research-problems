Examples
========

The examples in this repository are runnable research-oriented scripts. They are
designed to show not only API usage, but how the library fits into realistic
experimental workflows. The featured examples below list dependencies,
expected scope, and the primary concept they demonstrate.

Featured Examples
-----------------

Peanut Sheller Packet
~~~~~~~~~~~~~~~~~~~~~

Load and render a citation-linked ideation prompt packet.

**Requires:** base install
**Runtime:** short
**Teaches:** text-problem loading, prompt rendering, metadata inspection

Laptop Design Decision
~~~~~~~~~~~~~~~~~~~~~~

Evaluate a structured decision task with explicit criteria.

**Requires:** base install
**Runtime:** short
**Teaches:** decision problem contracts, evaluator output interpretation

Pill Problem Optimization
~~~~~~~~~~~~~~~~~~~~~~~~~

Solve a constrained optimization benchmark from the packaged catalog.

**Requires:** base install
**Runtime:** short
**Teaches:** optimization interfaces, feasibility checks, objective interpretation

Planar Truss Span Grammar
~~~~~~~~~~~~~~~~~~~~~~~~~

Step through a constructive grammar-based truss design task.

**Requires:** ``grammar``
**Runtime:** short to medium
**Teaches:** state transitions, action enumeration, grammar workflow structure

Build123d Parametric Mounting Bracket
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run an MCP-backed CAD-style task with external execution.

**Requires:** ``mcp,cad``
**Runtime:** medium
**Teaches:** MCP task wrapping, external backend interaction, CAD workflow integration

Full Catalog
------------

.. toctree::
   :maxdepth: 2

   catalog/index
   decision/index
   grammar/index
   gui/index
   mcp/index
   optimization/index
   text/index
