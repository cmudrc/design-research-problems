"""Tour the curated public API through concrete packaged objects."""

from __future__ import annotations

import numpy

import design_research_problems as derp


def main() -> None:
    """Load one example from each family and print typed public-API touchpoints."""
    registry = derp.ProblemRegistry()
    catalog: derp.IdeationCatalog = derp.get_ideation_catalog()

    text_problem = derp.get_problem("ideation_peanut_shelling_fu_cagan_kotovsky_2010")
    typed_text_problem = derp.get_problem_as(
        "ideation_peanut_shelling_fu_cagan_kotovsky_2010",
        derp.TextProblem,
    )
    decision_problem = derp.get_problem_as(
        "decision_laptop_design_profit_maximization",
        derp.DecisionProblem,
    )
    optimization_problem = derp.get_problem_as("gmpb_default_dynamic_min", derp.OptimizationProblem)
    grammar_problem = derp.get_problem_as("iot_home_cooling_system_design", derp.GrammarProblem)
    mcp_problem = derp.get_problem_as("mcp_build123d_parametric_mounting_bracket", derp.MCPProblem)

    loaded_problems: tuple[derp.Problem, ...] = (
        text_problem,
        typed_text_problem,
        decision_problem,
        optimization_problem,
        grammar_problem,
        mcp_problem,
    )
    computable_count = sum(isinstance(problem, derp.ComputableProblem) for problem in loaded_problems)

    metadata: derp.ProblemMetadata = typed_text_problem.metadata
    taxonomy: derp.ProblemTaxonomy = metadata.taxonomy
    citations: tuple[derp.Citation, ...] = metadata.citations
    assets: tuple[derp.ProblemAsset, ...] = metadata.assets

    kinds = {listed_metadata.kind for listed_metadata in registry.list()}
    assert derp.ProblemKind.TEXT in kinds
    assert derp.ProblemKind.DECISION in kinds
    assert derp.ProblemKind.OPTIMIZATION in kinds
    assert derp.ProblemKind.GRAMMAR in kinds
    assert derp.ProblemKind.MCP in kinds

    best_decision: derp.DecisionEvaluation = decision_problem.best_evaluation()

    candidate = numpy.zeros(optimization_problem.bounds.lb.shape, dtype=float)
    optimization_evaluation: derp.OptimizationEvaluation = optimization_problem.evaluate(candidate)

    transition: derp.GrammarTransition = grammar_problem.enumerate_transitions(grammar_problem.initial_state())[0]

    prompt: derp.IdeationPromptRecord = catalog.list_prompts()[0]
    variant: derp.IdeationPromptVariant = catalog.get_variant(prompt.variant_ids[0])
    family: derp.IdeationPromptFamily = catalog.get_family(prompt.family_id)
    study: derp.IdeationStudy = catalog.list_studies()[0]
    evidence_tier: derp.EvidenceTier = prompt.evidence_tier

    try:
        derp.get_problem_as(
            "ideation_peanut_shelling_fu_cagan_kotovsky_2010",
            derp.OptimizationProblem,
        )
    except (TypeError, derp.ProblemEvaluationError) as exc:
        mismatch_error = type(exc).__name__
    else:
        mismatch_error = "no-error"

    handled_optional_error = derp.MissingOptionalDependencyError.__name__

    print("problem-count", len(derp.list_problems()))
    print("kind-count", len(kinds), sorted(kind.value for kind in kinds))
    print("loaded-types", [type(problem).__name__ for problem in loaded_problems])
    print("computable-count", computable_count)
    print("text-kind", metadata.problem_id, metadata.kind.value)
    print("taxonomy-tags", len(taxonomy.tags))
    print("citation-year", citations[0].year)
    print("asset-count", len(assets))
    print("decision-best", round(best_decision.objective_value, 6), best_decision.candidate_label)
    print(
        "optimization-eval",
        optimization_evaluation.is_feasible,
        round(optimization_evaluation.objective_value, 6),
    )
    print("grammar-rule", transition.rule_name)
    print(
        "evaluation-types",
        type(best_decision).__name__,
        type(optimization_evaluation).__name__,
        type(transition).__name__,
    )
    print("mcp-problem", mcp_problem.metadata.problem_id)
    print(
        "ideation-types",
        type(prompt).__name__,
        type(variant).__name__,
        type(family).__name__,
        type(study).__name__,
        evidence_tier.value,
    )
    print(
        "primary-verbatim-prompts",
        len(
            catalog.search_prompts(
                evidence_tiers=(derp.EvidenceTier.PRIMARY_VERBATIM,),
                status="complete",
            )
        ),
    )
    print("handled-errors", handled_optional_error, mismatch_error)


if __name__ == "__main__":
    main()
