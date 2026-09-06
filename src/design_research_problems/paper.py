"""Problem-owned contributions for evidence-backed paper drafting."""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from design_research_problems._catalog._registry import ProblemRegistry
from design_research_problems.ideation import (
    IdeationCatalog,
    IdeationPromptFamily,
    IdeationPromptRecord,
    IdeationPromptVariant,
    IdeationStudy,
    get_ideation_catalog,
)
from design_research_problems.problems._metadata import Citation, ProblemMetadata

PAPER_CONTRIBUTION_VERSION = "0.1.0"
"""Version of the Experiments-compatible component packet emitted here."""


def collect_problem_paper_contributions(problem_id: str) -> dict[str, Any]:
    """Collect deterministic writing support for one packaged problem.

    The returned object is JSON-compatible and follows the component packet
    contract accepted by ``design-research-experiments``. It describes only
    configured problem context; it does not claim that a study was run.

    Args:
        problem_id: Stable catalog identifier for the selected problem.

    Returns:
        Versioned contribution packet with Background and Methods support,
        curated references, provenance, and actionable reporting gaps.

    Raises:
        KeyError: If ``problem_id`` is not in the packaged problem catalog.
    """
    metadata = ProblemRegistry().get(problem_id).metadata
    ideation = get_ideation_catalog()
    prompts = tuple(prompt for prompt in ideation.prompts if prompt.problem_id == problem_id)
    variants = _linked_variants(ideation, prompts, problem_id=problem_id)
    families = _linked_families(ideation, prompts)
    studies = _linked_studies(ideation, variants)
    references = _collect_references(metadata, ideation, prompts, variants, studies)
    provenance = _provenance(metadata, prompts, variants, families, studies)
    source = {
        "package": "design-research-problems",
        "package_version": _package_version(),
        "component_type": "problem",
        "component_id": metadata.problem_id,
    }

    contributions = [
        _background_contribution(metadata, provenance=provenance),
        _methods_contribution(metadata, provenance=provenance),
    ]
    contributions.extend(_ideation_contribution(prompt, ideation=ideation, provenance=provenance) for prompt in prompts)

    return {
        "schema_version": PAPER_CONTRIBUTION_VERSION,
        "source": source,
        "contributions": contributions,
        "references": references,
        "reporting_gaps": _reporting_gaps(
            metadata,
            prompts=prompts,
            variants=variants,
            studies=studies,
            references=references,
        ),
    }


def _package_version() -> str:
    try:
        return version("design-research-problems")
    except PackageNotFoundError:
        return "0+unknown"


def _linked_variants(
    catalog: IdeationCatalog,
    prompts: tuple[IdeationPromptRecord, ...],
    *,
    problem_id: str,
) -> tuple[IdeationPromptVariant, ...]:
    variant_ids = {variant_id for prompt in prompts for variant_id in prompt.variant_ids}
    return tuple(
        variant for variant in catalog.variants if variant.variant_id in variant_ids or variant.problem_id == problem_id
    )


def _linked_families(
    catalog: IdeationCatalog,
    prompts: tuple[IdeationPromptRecord, ...],
) -> tuple[IdeationPromptFamily, ...]:
    direct_ids = {prompt.family_id for prompt in prompts}
    family_by_id = {family.family_id: family for family in catalog.families}
    linked_ids: set[str] = set()
    for family_id in direct_ids:
        current_id: str | None = family_id
        while current_id is not None and current_id not in linked_ids:
            linked_ids.add(current_id)
            current = family_by_id.get(current_id)
            current_id = None if current is None else current.derived_from_family_id
    return tuple(family for family in catalog.families if family.family_id in linked_ids)


def _linked_studies(
    catalog: IdeationCatalog,
    variants: tuple[IdeationPromptVariant, ...],
) -> tuple[IdeationStudy, ...]:
    variant_ids = {variant.variant_id for variant in variants}
    return tuple(study for study in catalog.studies if variant_ids.intersection(study.prompt_variant_ids))


def _collect_references(
    metadata: ProblemMetadata,
    catalog: IdeationCatalog,
    prompts: tuple[IdeationPromptRecord, ...],
    variants: tuple[IdeationPromptVariant, ...],
    studies: tuple[IdeationStudy, ...],
) -> list[dict[str, Any]]:
    citation_keys = {key for prompt in prompts for key in prompt.source_citation_keys}
    citation_keys.update(key for variant in variants for key in variant.source_citation_keys)
    citation_keys.update(key for study in studies for key in study.citation_keys)
    citations_by_key = {citation.key: citation for citation in catalog.citations}
    citations_by_key.update({citation.key: citation for citation in metadata.citations})

    selected: dict[str, Citation] = {citation.key: citation for citation in metadata.citations}
    selected.update((key, citations_by_key[key]) for key in sorted(citation_keys) if key in citations_by_key)
    prompt_ids = [prompt.prompt_id for prompt in prompts]
    variant_ids = [variant.variant_id for variant in variants]
    study_ids = [study.study_id for study in studies]
    return [
        {
            **asdict(citation),
            "authors": list(citation.authors),
            "provenance": {
                "problem_id": metadata.problem_id,
                "prompt_ids": prompt_ids,
                "variant_ids": variant_ids,
                "study_ids": study_ids,
            },
        }
        for citation in selected.values()
    ]


def _provenance(
    metadata: ProblemMetadata,
    prompts: tuple[IdeationPromptRecord, ...],
    variants: tuple[IdeationPromptVariant, ...],
    families: tuple[IdeationPromptFamily, ...],
    studies: tuple[IdeationStudy, ...],
) -> dict[str, Any]:
    return {
        "problem_id": metadata.problem_id,
        "prompt_ids": [prompt.prompt_id for prompt in prompts],
        "variant_ids": [variant.variant_id for variant in variants],
        "family_ids": [family.family_id for family in families],
        "family_lineage": [
            {
                "family_id": family.family_id,
                "derived_from_family_id": family.derived_from_family_id,
            }
            for family in families
        ],
        "study_ids": [study.study_id for study in studies],
    }


def _background_contribution(
    metadata: ProblemMetadata,
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contribution_id": f"problems:{metadata.problem_id}:background",
        "section": "background",
        "kind": "paragraph",
        "text": f"{metadata.title}: {metadata.summary}",
        "evidence_basis": "configured",
        "citation_keys": [citation.key for citation in metadata.citations],
        "evidence_refs": [],
        "metadata": {
            **provenance,
            "problem_kind": metadata.kind.value,
            "tags": list(metadata.taxonomy.tags),
            "reporting_requirements": [
                "Cite the source of the selected problem framing.",
                "Describe any changes made to the packaged problem statement or materials.",
            ],
        },
    }


def _methods_contribution(
    metadata: ProblemMetadata,
    *,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    taxonomy = metadata.taxonomy
    capability_text = ", ".join(metadata.capabilities) or "none recorded"
    suitability_text = ", ".join(metadata.study_suitability) or "none recorded"
    return {
        "contribution_id": f"problems:{metadata.problem_id}:methods",
        "section": "methods",
        "kind": "paragraph",
        "text": (
            f"The configured task used the packaged {metadata.kind.value} problem "
            f"{metadata.problem_id!r}. Recorded capabilities were {capability_text}; "
            f"study-suitability labels were {suitability_text}."
        ),
        "evidence_basis": "configured",
        "citation_keys": [citation.key for citation in metadata.citations],
        "evidence_refs": [],
        "metadata": {
            **provenance,
            "taxonomy": {
                "formulation": taxonomy.formulation,
                "design_variable_type": taxonomy.design_variable_type,
                "objective_mode": taxonomy.objective_mode,
                "constraint_nature": taxonomy.constraint_nature,
                "deliverable_type": taxonomy.deliverable_type,
                "timebox_hint_minutes": taxonomy.timebox_hint_minutes,
                "participants": taxonomy.participants,
                "evaluation_mode": taxonomy.evaluation_mode,
            },
            "capabilities": list(metadata.capabilities),
            "study_suitability": list(metadata.study_suitability),
            "reporting_requirements": _methods_requirements(metadata),
        },
    }


def _methods_requirements(metadata: ProblemMetadata) -> list[str]:
    requirements = [
        "Report the stable problem ID and package version used by the study.",
        "Treat catalog capabilities as configuration metadata, not evidence that a run occurred.",
    ]
    if "human-subjects-ready" in metadata.study_suitability:
        requirements.append(
            "Report the actual participant sample, assignment, timing, and materials from study evidence."
        )
    if metadata.kind.value in {"decision", "optimization"}:
        requirements.append(
            "Report the selected variables, objective, constraints, and evaluator settings used in the study."
        )
    if metadata.benchmark_card is not None:
        requirements.append("Preserve the benchmark card boundary between physical models and deliberate surrogates.")
    return requirements


def _ideation_contribution(
    prompt: IdeationPromptRecord,
    *,
    ideation: IdeationCatalog,
    provenance: dict[str, Any],
) -> dict[str, Any]:
    family = ideation.get_family(prompt.family_id)
    variants = [ideation.get_variant(variant_id) for variant_id in prompt.variant_ids]
    return {
        "contribution_id": f"problems:{prompt.problem_id}:prompt:{prompt.prompt_id}",
        "section": "methods",
        "kind": "bullet",
        "text": (
            f"The configured ideation prompt was {prompt.canonical_brief!r} "
            f"({prompt.evidence_tier.value}; family {family.name!r})."
        ),
        "evidence_basis": "configured",
        "citation_keys": list(prompt.source_citation_keys),
        "evidence_refs": [],
        "metadata": {
            **provenance,
            "prompt_id": prompt.prompt_id,
            "family_id": prompt.family_id,
            "evidence_tier": prompt.evidence_tier.value,
            "status": prompt.status,
            "variants": [
                {
                    "variant_id": variant.variant_id,
                    "statement_type": variant.statement_type,
                    "evidence_tier": variant.evidence_tier.value,
                    "status": variant.status,
                    "notes": variant.notes,
                }
                for variant in variants
            ],
            "family_notes": family.notes,
            "reporting_requirements": [
                "Report the exact prompt wording and any study-specific variant.",
                "Retain the prompt evidence tier and source lineage when describing materials.",
            ],
        },
    }


def _reporting_gaps(
    metadata: ProblemMetadata,
    *,
    prompts: tuple[IdeationPromptRecord, ...],
    variants: tuple[IdeationPromptVariant, ...],
    studies: tuple[IdeationStudy, ...],
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    if not references:
        gaps.append(
            _gap(
                metadata.problem_id,
                "missing-source-citations",
                "background",
                "The selected problem has no curated source citation; add one before drafting.",
            )
        )
    for reference in references:
        if reference.get("provisional"):
            key = str(reference["key"])
            gaps.append(
                _gap(
                    metadata.problem_id,
                    f"provisional-citation:{key}",
                    "background",
                    f"Citation {key!r} is provisional and needs source verification.",
                )
            )
    if "ideation-friendly" in metadata.study_suitability and not prompts:
        gaps.append(
            _gap(
                metadata.problem_id,
                "missing-ideation-lineage",
                "methods",
                "The problem is marked ideation-friendly but has no linked prompt record.",
            )
        )
    for record_type, records in (("prompt", prompts), ("variant", variants), ("study", studies)):
        for record in records:
            if record.status != "complete":
                record_id = str(getattr(record, f"{record_type}_id"))
                gaps.append(
                    _gap(
                        metadata.problem_id,
                        f"incomplete-{record_type}:{record_id}",
                        "methods",
                        f"Linked {record_type} {record_id!r} has status {record.status!r}.",
                    )
                )
    return gaps


def _gap(problem_id: str, suffix: str, section: str, message: str) -> dict[str, Any]:
    return {
        "gap_id": f"problems:{problem_id}:{suffix}",
        "section": section,
        "message": message,
        "evidence_refs": [],
    }


__all__ = ["PAPER_CONTRIBUTION_VERSION", "collect_problem_paper_contributions"]
