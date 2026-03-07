Problems
========

Problem families are the conceptual center of this package. Each family aligns
with a different kind of design-research question.

Family Guide
------------

.. list-table::
   :header-rows: 1

   * - Family
     - Best for
   * - Text
     - Prompt-based ideation and human-subjects workflows
   * - Decision
     - Structured alternatives with explicit criteria
   * - Optimization
     - Objective/constraint benchmarking and solver comparisons
   * - Grammar
     - Sequential constructive design behavior and transition analysis
   * - MCP
     - Tasks requiring external tool execution backends

Text problems are usually the lightest path for study prototyping. Decision
problems are appropriate when options and criteria should be explicit in the
task definition. Optimization problems are appropriate when algorithmic
performance must be measured under constraints. Grammar problems are useful when
process traces and action sequences matter as much as end-state performance.
MCP-backed problems connect packaged task definitions to external computational
systems such as CAD or domain-specific services.

Family Pages
------------

.. toctree::
   :maxdepth: 1

   ideation
   text
   decision
   optimization
   grammar
   mcp

For the complete generated problem-by-problem inventory, see
:doc:`../problem_catalog/index`.
