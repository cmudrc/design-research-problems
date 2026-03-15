from __future__ import annotations

import design_research_problems as drp
from design_research_problems.problems import grammar, optimization

EXPECTED_PUBLIC_API = [
    "__version__",
    "Problem",
    "ComputableProblem",
    "ProblemKind",
    "ProblemMetadata",
    "ProblemTaxonomy",
    "Citation",
    "ProblemAsset",
    "TextProblem",
    "DecisionEvaluation",
    "DecisionProblem",
    "OptimizationProblem",
    "OptimizationEvaluation",
    "GrammarProblem",
    "GrammarTransition",
    "MCPProblem",
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
    "get_problem_as",
    "list_problems",
    "get_ideation_catalog",
]


def test_top_level_exports_match_curated_contract() -> None:
    assert drp.__all__ == EXPECTED_PUBLIC_API


def test_top_level_exports_resolve() -> None:
    for symbol_name in drp.__all__:
        assert getattr(drp, symbol_name) is getattr(drp, symbol_name)


def test_family_subpackage_exports_resolve() -> None:
    assert grammar.IoTHomeCoolingGrammarProblem is grammar.IoTHomeCoolingGrammarProblem
    assert grammar.IoTHomeState is grammar.IoTHomeState
    assert grammar.SpaceTrussSpanProblem is grammar.SpaceTrussSpanProblem
    assert grammar.SpaceTrussState is grammar.SpaceTrussState
    assert grammar.TrussAPGrammarProblem is grammar.TrussAPGrammarProblem
    assert grammar.TrussAPState is grammar.TrussAPState
    assert (
        optimization.PlanarTrussEngineeringOptimizationProblem is optimization.PlanarTrussEngineeringOptimizationProblem
    )
    assert optimization.GMPBOptimizationProblem is optimization.GMPBOptimizationProblem
    assert (
        optimization.SpaceTrussEngineeringOptimizationProblem is optimization.SpaceTrussEngineeringOptimizationProblem
    )
    assert optimization.CompetingProjectsWorkerHoursProblem is optimization.CompetingProjectsWorkerHoursProblem
    assert optimization.WindFarmLayoutOptimizationProblem is optimization.WindFarmLayoutOptimizationProblem
    assert (
        optimization.UnrestrictedWindFarmLayoutOptimizationProblem
        is optimization.UnrestrictedWindFarmLayoutOptimizationProblem
    )
