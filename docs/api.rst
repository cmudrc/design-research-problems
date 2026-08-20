API
===

The top-level package exports a small curated public API:

- ``__version__``
- ``Citation``
- ``ComputableProblem``
- ``DecisionEvaluation``
- ``DecisionProblem``
- ``EvidenceTier``
- ``GrammarProblem``
- ``GrammarTransition``
- ``MCPProblem``
- ``IdeationCatalog``
- ``IdeationPromptFamily``
- ``IdeationPromptRecord``
- ``IdeationPromptVariant``
- ``IdeationStudy``
- ``MissingOptionalDependencyError``
- ``OptimizationEvaluation``
- ``OptimizationProblem``
- ``Problem``
- ``ProblemAsset``
- ``ProblemCatalogSummary``
- ``ProblemEvaluationError``
- ``ProblemKind``
- ``ProblemMetadata``
- ``ProblemRegistry``
- ``ProblemTaxonomy``
- ``TextProblem``
- ``get_ideation_catalog``
- ``get_problem``
- ``get_problem_as``
- ``list_problems``
- ``search_problem_summaries``
- ``integration``

``integration`` is a public module, not a pair of additional top-level
functions. Call ``integration.resolve_problem_binding(...)`` and
``integration.evaluate_problem_output(...)`` through that module.

See :doc:`reference/index` for the module-level reference pages.
