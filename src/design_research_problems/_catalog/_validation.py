"""Validation helpers for packaged catalog assets."""

from __future__ import annotations

from dataclasses import dataclass

from design_research_problems._catalog._loader import load_problem_manifests, load_statement_text
from design_research_problems.ideation import load_ideation_catalog
from design_research_problems.problems._metadata import KNOWN_PROBLEM_CAPABILITIES, KNOWN_STUDY_SUITABILITY


@dataclass(frozen=True)
class CatalogValidationReport:
    """Structured validation output for the packaged catalog."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def is_valid(self) -> bool:
        """Return whether the packaged catalog has no validation errors."""
        return not self.errors


def validate_catalog() -> CatalogValidationReport:
    """Validate packaged problem and ideation metadata."""
    errors: list[str] = []
    warnings: list[str] = []

    try:
        manifests = load_problem_manifests()
    except Exception as exc:  # pragma: no cover - catastrophic parse failure path
        return CatalogValidationReport(errors=(f"Problem manifest load failed: {exc}",), warnings=())

    for problem_id, manifest in manifests.items():
        metadata = manifest.metadata
        if not metadata.problem_id or not metadata.title or not metadata.summary:
            errors.append(f"{problem_id}: missing required metadata fields")
        try:
            statement = load_statement_text(manifest)
        except Exception as exc:
            errors.append(f"{problem_id}: could not load embedded statement text: {exc}")
            continue
        heading = _leading_h1(statement)
        if heading is not None and heading != metadata.title:
            warnings.append(f"{problem_id}: statement H1 does not match metadata title")
        if not set(metadata.capabilities).issubset(KNOWN_PROBLEM_CAPABILITIES):
            errors.append(f"{problem_id}: unknown capability values")
        if not set(metadata.study_suitability).issubset(KNOWN_STUDY_SUITABILITY):
            errors.append(f"{problem_id}: unknown study-suitability values")
        if metadata.taxonomy.formulation is None:
            errors.append(f"{problem_id}: taxonomy.formulation is required")
        if not metadata.taxonomy.tags:
            errors.append(f"{problem_id}: taxonomy.tags must not be empty")
        if metadata.kind.value == "text":
            if metadata.taxonomy.deliverable_type is None:
                errors.append(f"{problem_id}: text problems require taxonomy.deliverable_type")
            if metadata.taxonomy.participants is None:
                errors.append(f"{problem_id}: text problems require taxonomy.participants")
        for citation in metadata.citations:
            if not citation.key or not citation.title:
                errors.append(f"{problem_id}: citation entries require key and title")
            if citation.provisional and not any((citation.venue, citation.doi, citation.url)):
                warnings.append(f"{problem_id}: provisional citation {citation.key!r} lacks venue/doi/url")

    try:
        ideation = load_ideation_catalog()
    except Exception as exc:  # pragma: no cover - catastrophic parse failure path
        errors.append(f"Ideation catalog load failed: {exc}")
        return CatalogValidationReport(errors=tuple(errors), warnings=tuple(warnings))

    prompt_ids = {prompt.prompt_id for prompt in ideation.prompts}
    variant_ids = {variant.variant_id for variant in ideation.variants}
    family_ids = {family.family_id for family in ideation.families}
    study_ids = {study.study_id for study in ideation.studies}
    citation_keys = {citation.key for citation in ideation.citations}

    if len(prompt_ids) != len(ideation.prompts):
        errors.append("Ideation catalog contains duplicate prompt IDs")
    if len(variant_ids) != len(ideation.variants):
        errors.append("Ideation catalog contains duplicate variant IDs")
    if len(family_ids) != len(ideation.families):
        errors.append("Ideation catalog contains duplicate family IDs")
    if len(study_ids) != len(ideation.studies):
        errors.append("Ideation catalog contains duplicate study IDs")

    for prompt in ideation.prompts:
        if prompt.family_id not in family_ids:
            errors.append(f"{prompt.prompt_id}: references unknown family {prompt.family_id!r}")
        if prompt.problem_id is not None and prompt.problem_id not in manifests:
            errors.append(f"{prompt.prompt_id}: references unknown problem {prompt.problem_id!r}")
        for variant_id in prompt.variant_ids:
            if variant_id not in variant_ids:
                errors.append(f"{prompt.prompt_id}: references unknown variant {variant_id!r}")
        if prompt.status == "needs_primary_fill":
            warnings.append(f"{prompt.prompt_id}: prompt needs primary-source follow-up")
        for citation_key in prompt.source_citation_keys:
            if citation_key not in citation_keys:
                errors.append(f"{prompt.prompt_id}: references unknown citation {citation_key!r}")

    for variant in ideation.variants:
        if variant.prompt_id not in prompt_ids:
            errors.append(f"{variant.variant_id}: references unknown prompt {variant.prompt_id!r}")
        if variant.problem_id is not None and variant.problem_id not in manifests:
            errors.append(f"{variant.variant_id}: references unknown problem {variant.problem_id!r}")
        for citation_key in variant.source_citation_keys:
            if citation_key not in citation_keys:
                errors.append(f"{variant.variant_id}: references unknown citation {citation_key!r}")
        if variant.status == "needs_primary_fill":
            warnings.append(f"{variant.variant_id}: variant needs primary-source follow-up")

    for family in ideation.families:
        if family.derived_from_family_id is not None and family.derived_from_family_id not in family_ids:
            errors.append(
                f"{family.family_id}: references unknown parent family {family.derived_from_family_id!r}"
            )
        for prompt_id in family.canonical_prompt_ids:
            if prompt_id not in prompt_ids:
                errors.append(f"{family.family_id}: references unknown prompt {prompt_id!r}")
        if not family.canonical_prompt_ids:
            warnings.append(f"{family.family_id}: family_stub placeholder has no canonical prompts")

    for study in ideation.studies:
        for variant_id in study.prompt_variant_ids:
            if variant_id not in variant_ids:
                errors.append(f"{study.study_id}: references unknown variant {variant_id!r}")
        for citation_key in study.citation_keys:
            if citation_key not in citation_keys:
                errors.append(f"{study.study_id}: references unknown citation {citation_key!r}")
        if study.status == "needs_primary_fill":
            warnings.append(f"{study.study_id}: study needs primary-source follow-up")

    for citation in ideation.citations:
        if not citation.key or not citation.title:
            errors.append("Ideation citations require key and title")
        if citation.provisional and not any((citation.venue, citation.doi, citation.url)):
            warnings.append(f"ideation citation {citation.key!r} lacks venue/doi/url")

    return CatalogValidationReport(errors=tuple(errors), warnings=tuple(warnings))


def _leading_h1(statement: str) -> str | None:
    """Return the first H1 text when present."""
    for line in statement.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            return stripped[2:].strip()
        return None
    return None
