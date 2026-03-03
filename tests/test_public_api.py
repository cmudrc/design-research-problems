from __future__ import annotations

import design_research_problems as drp

EXPECTED_PUBLIC_API = [
    "__version__",
    "ProblemKind",
    "ProblemMetadata",
    "ProblemTaxonomy",
    "Citation",
    "ProblemAsset",
    "TextProblem",
    "DecisionProblem",
    "OptimizationProblem",
    "GrammarProblem",
    "ProblemRegistry",
    "MissingOptionalDependencyError",
    "ProblemEvaluationError",
    "EvidenceTier",
    "IdeationPromptRecord",
    "IdeationPromptVariant",
    "IdeationPromptFamily",
    "IdeationStudy",
    "IdeationCatalog",
    "get_problem",
    "list_problems",
    "get_ideation_catalog",
]


def test_top_level_exports_match_curated_contract() -> None:
    assert drp.__all__ == EXPECTED_PUBLIC_API


def test_top_level_exports_resolve() -> None:
    for symbol_name in drp.__all__:
        assert getattr(drp, symbol_name) is getattr(drp, symbol_name)
