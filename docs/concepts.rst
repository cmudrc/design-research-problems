Concepts
========

What Is A Problem?
------------------

A problem is a typed research task definition with a stable identifier,
metadata, and optional evaluation behavior. Problems can be descriptive (prompt
packets) or executable (candidate generation and scoring).

Problem Kinds
-------------

.. list-table::
   :header-rows: 1

   * - Kind
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

The ideation catalog is a curated subset of the ``text`` kind. ``ideation`` is
useful as a catalog tag and study-selection concept, but it is not a sixth
``ProblemKind``.

Computable Problems
-------------------

``ComputableProblem`` extends the base ``Problem`` contract by requiring an
``evaluate`` operation. Some concrete problem types also provide ``solve`` or a
family-specific baseline solver, but ``solve`` is not part of the shared
``ComputableProblem`` contract.

Compatibility Mapping
---------------------

The same five-kind value is derived into two integration fields:

``ProblemMetadata.kind`` → ``ProblemBinding.family`` →
``ProblemPacket.family`` → exported ``problem_family``.

``ProblemBinding.metadata["problem_kind"]`` is a parallel metadata alias, not
an intermediate step in that packet path. The first value is a ``ProblemKind``
enum; all downstream fields carry its string value: ``text``, ``decision``,
``optimization``, ``grammar``, or ``mcp``. Ideation records therefore use
``text`` throughout both compatibility paths.

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

Selected evaluator modes and external-tool workflows require optional
dependencies. Feature flags and package extras make those capabilities explicit
at runtime; generic grammar transitions and analytic-surrogate battery paths
remain available from the base install.
