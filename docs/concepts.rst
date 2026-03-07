Concepts
========

What Is A Problem?
------------------

A problem is a typed research task definition with a stable identifier,
metadata, and optional evaluation behavior. Problems can be descriptive (prompt
packets) or executable (candidate generation and scoring).

Problem Families
----------------

.. list-table::
   :header-rows: 1

   * - Family
     - Use when
   * - Text
     - Prompt-driven ideation or human-subjects tasks
   * - Decision
     - Options, criteria, and explicit evaluation rules are central
   * - Optimization
     - Objective/constraint benchmarking is required
   * - Grammar
     - Sequential constructive action and state transitions are central
   * - MCP
     - The task must interact with external tool backends

Text problems support lightweight and human-readable study tasks. Decision
problems are useful when alternatives and criteria are explicit. Optimization
problems support algorithmic benchmarking. Grammar problems support process-level
analysis of constructive behavior. MCP-backed problems bridge packaged task
contracts to external runtime systems.

Computable Problems
-------------------

``ComputableProblem`` extends the base ``Problem`` contract with executable
operations such as ``evaluate`` and ``solve``. These methods provide comparable
interfaces across families while preserving domain-specific logic.

Evaluators and Solution Objects
-------------------------------

Evaluators normalize performance outputs into explicit metrics. Solution objects
capture candidate structure so generated outputs and scores can be audited or
replayed.

Metadata and Citations
----------------------

Problem metadata is treated as first-class data, including taxonomy and citation
records. This supports transparent reporting and reproducibility.

Feature Flags and Capability Discovery
--------------------------------------

Some families require optional dependencies. Feature flags and package extras
make capability availability explicit at runtime.
