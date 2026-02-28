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
    "OptimizationProblem",
    "GrammarProblem",
    "ProblemRegistry",
    "MissingOptionalDependencyError",
    "ProblemEvaluationError",
    "get_problem",
    "list_problems",
]


def test_top_level_exports_match_curated_contract() -> None:
    assert drp.__all__ == EXPECTED_PUBLIC_API


def test_top_level_exports_resolve() -> None:
    for symbol_name in drp.__all__:
        assert getattr(drp, symbol_name) is getattr(drp, symbol_name)
