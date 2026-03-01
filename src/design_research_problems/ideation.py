"""Public ideation catalog types and accessors."""

from __future__ import annotations

import csv
import io
import json
import tomllib
from dataclasses import dataclass
from enum import StrEnum
from importlib.resources import files
from typing import Any, cast

from design_research_problems._catalog._registry import ProblemRegistry
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.problems._metadata import Citation

_PACKAGE = "design_research_problems"
_IDEATION_RESOURCE = "_assets/ideation/catalog.toml"


class EvidenceTier(StrEnum):
    """Evidence strength for prompt wording and provenance."""

    PRIMARY_VERBATIM = "primary_verbatim"
    PRIMARY_RECONSTRUCTED = "primary_reconstructed"
    SECONDARY_CANONICAL = "secondary_canonical"
    FAMILY_STUB = "family_stub"
    PLACEHOLDER = "placeholder"


@dataclass(frozen=True)
class IdeationPromptRecord:
    """Canonical prompt record for one reusable ideation brief."""

    prompt_id: str
    problem_id: str | None
    family_id: str
    canonical_brief: str
    evidence_tier: EvidenceTier
    source_citation_keys: tuple[str, ...]
    tags: tuple[str, ...]
    status: str
    variant_ids: tuple[str, ...]


@dataclass(frozen=True)
class IdeationPromptVariant:
    """Source-specific prompt wording or variant metadata."""

    variant_id: str
    prompt_id: str
    problem_id: str | None
    label: str
    statement_type: str
    evidence_tier: EvidenceTier
    source_citation_keys: tuple[str, ...]
    notes: str
    status: str


@dataclass(frozen=True)
class IdeationPromptFamily:
    """Prompt family grouping and lineage metadata."""

    family_id: str
    name: str
    group: str
    external_aliases: tuple[str, ...]
    derived_from_family_id: str | None
    canonical_prompt_ids: tuple[str, ...]
    tags: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class IdeationStudy:
    """Human-subjects study metadata tied to prompt variants."""

    study_id: str
    title: str
    citation_keys: tuple[str, ...]
    prompt_variant_ids: tuple[str, ...]
    participant_summary: str
    conditions_summary: str
    time_on_task_minutes: int | None
    dependent_measures: tuple[str, ...]
    coding_summary: str
    materials_summary: str
    limitations: tuple[str, ...]
    status: str


@dataclass(frozen=True)
class IdeationCatalog:
    """Loaded ideation metadata tables."""

    citations: tuple[Citation, ...]
    prompts: tuple[IdeationPromptRecord, ...]
    variants: tuple[IdeationPromptVariant, ...]
    families: tuple[IdeationPromptFamily, ...]
    studies: tuple[IdeationStudy, ...]

    def list_prompts(self) -> tuple[IdeationPromptRecord, ...]:
        """Return all canonical prompt records."""
        return self.prompts

    def list_variants(self) -> tuple[IdeationPromptVariant, ...]:
        """Return all prompt variants."""
        return self.variants

    def list_families(self) -> tuple[IdeationPromptFamily, ...]:
        """Return all prompt families."""
        return self.families

    def list_studies(self) -> tuple[IdeationStudy, ...]:
        """Return all study records."""
        return self.studies

    def get_prompt(self, prompt_id: str) -> IdeationPromptRecord:
        """Return one prompt by ID."""
        for prompt in self.prompts:
            if prompt.prompt_id == prompt_id:
                return prompt
        raise KeyError(f"Unknown prompt id: {prompt_id}")

    def get_variant(self, variant_id: str) -> IdeationPromptVariant:
        """Return one variant by ID."""
        for variant in self.variants:
            if variant.variant_id == variant_id:
                return variant
        raise KeyError(f"Unknown variant id: {variant_id}")

    def get_family(self, family_id: str) -> IdeationPromptFamily:
        """Return one family by ID."""
        for family in self.families:
            if family.family_id == family_id:
                return family
        raise KeyError(f"Unknown family id: {family_id}")

    def get_study(self, study_id: str) -> IdeationStudy:
        """Return one study by ID."""
        for study in self.studies:
            if study.study_id == study_id:
                return study
        raise KeyError(f"Unknown study id: {study_id}")

    def search_prompts(
        self,
        text: str = "",
        tags: tuple[str, ...] = (),
        family_ids: tuple[str, ...] = (),
        evidence_tiers: tuple[EvidenceTier, ...] = (),
        deliverable_type: str | None = None,
        max_timebox_minutes: int | None = None,
        status: str | None = None,
    ) -> tuple[IdeationPromptRecord, ...]:
        """Search canonical prompts across ideation metadata and linked problems."""
        registry = ProblemRegistry()
        tag_set = {tag.lower() for tag in tags}
        family_id_set = set(family_ids)
        evidence_tier_set = {tier.value if isinstance(tier, EvidenceTier) else str(tier) for tier in evidence_tiers}
        text_query = text.strip().lower()
        matches: list[IdeationPromptRecord] = []
        for prompt in self.prompts:
            if tag_set and not tag_set.issubset({tag.lower() for tag in prompt.tags}):
                continue
            if family_id_set and prompt.family_id not in family_id_set:
                continue
            if evidence_tier_set and prompt.evidence_tier.value not in evidence_tier_set:
                continue
            if status is not None and prompt.status != status:
                continue
            if text_query:
                haystack = " ".join((prompt.prompt_id, prompt.canonical_brief, prompt.family_id, *prompt.tags)).lower()
                if text_query not in haystack:
                    continue
            if not self._matches_problem_filters(
                registry=registry,
                problem_id=prompt.problem_id,
                deliverable_type=deliverable_type,
                max_timebox_minutes=max_timebox_minutes,
            ):
                continue
            matches.append(prompt)
        return tuple(matches)

    def export_prompt_index(self, format: str = "json") -> str:
        """Export the canonical prompt index in one of the supported formats."""
        rows = self.prompts_records()
        normalized = format.strip().lower()
        if normalized == "json":
            return json.dumps(rows, indent=2, sort_keys=True)
        if normalized == "csv":
            return self._records_to_csv(rows)
        raise ValueError(f"Unsupported export format: {format!r}")

    def prompts_records(self) -> list[dict[str, object]]:
        """Return canonical prompt rows for export."""
        return [
            {
                "prompt_id": prompt.prompt_id,
                "problem_id": prompt.problem_id,
                "family_id": prompt.family_id,
                "canonical_brief": prompt.canonical_brief,
                "evidence_tier": prompt.evidence_tier.value,
                "status": prompt.status,
                "tags": list(prompt.tags),
            }
            for prompt in self.prompts
        ]

    def variants_records(self) -> list[dict[str, object]]:
        """Return prompt variant rows for export."""
        return [
            {
                "variant_id": variant.variant_id,
                "prompt_id": variant.prompt_id,
                "problem_id": variant.problem_id,
                "label": variant.label,
                "statement_type": variant.statement_type,
                "evidence_tier": variant.evidence_tier.value,
                "status": variant.status,
                "notes": variant.notes,
            }
            for variant in self.variants
        ]

    def families_records(self) -> list[dict[str, object]]:
        """Return family rows for export."""
        return [
            {
                "family_id": family.family_id,
                "name": family.name,
                "group": family.group,
                "derived_from_family_id": family.derived_from_family_id,
                "external_aliases": list(family.external_aliases),
                "canonical_prompt_ids": list(family.canonical_prompt_ids),
                "tags": list(family.tags),
            }
            for family in self.families
        ]

    def studies_records(self) -> list[dict[str, object]]:
        """Return study rows for export."""
        return [
            {
                "study_id": study.study_id,
                "title": study.title,
                "citation_keys": list(study.citation_keys),
                "prompt_variant_ids": list(study.prompt_variant_ids),
                "participant_summary": study.participant_summary,
                "conditions_summary": study.conditions_summary,
                "time_on_task_minutes": study.time_on_task_minutes,
                "dependent_measures": list(study.dependent_measures),
                "coding_summary": study.coding_summary,
                "materials_summary": study.materials_summary,
                "limitations": list(study.limitations),
                "status": study.status,
            }
            for study in self.studies
        ]

    def prompts_dataframe(self) -> Any:
        """Return the canonical prompt table as a pandas DataFrame."""
        return self._records_to_dataframe(self.prompts_records())

    def variants_dataframe(self) -> Any:
        """Return the variant table as a pandas DataFrame."""
        return self._records_to_dataframe(self.variants_records())

    def families_dataframe(self) -> Any:
        """Return the family table as a pandas DataFrame."""
        return self._records_to_dataframe(self.families_records())

    def studies_dataframe(self) -> Any:
        """Return the study table as a pandas DataFrame."""
        return self._records_to_dataframe(self.studies_records())

    def _matches_problem_filters(
        self,
        registry: ProblemRegistry,
        problem_id: str | None,
        deliverable_type: str | None,
        max_timebox_minutes: int | None,
    ) -> bool:
        """Return whether linked problem metadata satisfies optional filters."""
        if deliverable_type is None and max_timebox_minutes is None:
            return True
        if problem_id is None:
            return False
        metadata = registry.get(problem_id).metadata
        if deliverable_type is not None and metadata.taxonomy.deliverable_type != deliverable_type:
            return False
        if (
            max_timebox_minutes is not None
            and metadata.taxonomy.timebox_hint_minutes is not None
            and metadata.taxonomy.timebox_hint_minutes > max_timebox_minutes
        ):
            return False
        return metadata.taxonomy.timebox_hint_minutes is not None or max_timebox_minutes is None

    def _records_to_csv(self, rows: list[dict[str, object]]) -> str:
        """Serialize rows to CSV using a stable field order."""
        if not rows:
            return ""
        buffer = io.StringIO()
        fieldnames = list(rows[0])
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: "; ".join(str(item) for item in value) if isinstance(value, list) else value
                    for key, value in row.items()
                }
            )
        return buffer.getvalue()

    def _records_to_dataframe(self, rows: list[dict[str, object]]) -> Any:
        """Build a pandas DataFrame from records with lazy imports."""
        try:
            import pandas as pandas_module
        except ImportError as exc:
            raise MissingOptionalDependencyError(
                "pandas support requires the optional 'design-research-problems[pandas]' extra."
            ) from exc
        return pandas_module.DataFrame(rows)


def _parse_citation(entry: dict[str, Any]) -> Citation:
    """Parse one ideation citation record."""
    return Citation(
        key=str(entry["key"]),
        kind=str(entry.get("kind", "inline")),
        authors=tuple(str(author) for author in cast(list[object], entry.get("authors", []))),
        title=str(entry.get("title", "")),
        year=int(entry["year"]) if "year" in entry else None,
        venue=cast(str | None, entry.get("venue")),
        doi=cast(str | None, entry.get("doi")),
        formatted_text=cast(str | None, entry.get("formatted_text")),
        raw_text=str(entry.get("raw_text", "")),
        url=cast(str | None, entry.get("url")),
        provisional=bool(entry.get("provisional", False)),
    )


def _load_raw_ideation_data() -> dict[str, Any]:
    """Load and parse the packaged ideation catalog TOML."""
    raw_text = files(_PACKAGE).joinpath(*_IDEATION_RESOURCE.split("/")).read_text(encoding="utf-8")
    return cast(dict[str, Any], tomllib.loads(raw_text))


def load_ideation_catalog() -> IdeationCatalog:
    """Load the packaged ideation catalog."""
    raw_data = _load_raw_ideation_data()
    citations = tuple(_parse_citation(entry) for entry in cast(list[dict[str, Any]], raw_data.get("citations", [])))
    prompts = tuple(
        IdeationPromptRecord(
            prompt_id=str(entry["prompt_id"]),
            problem_id=cast(str | None, entry.get("problem_id")),
            family_id=str(entry["family_id"]),
            canonical_brief=str(entry["canonical_brief"]),
            evidence_tier=EvidenceTier(str(entry["evidence_tier"])),
            source_citation_keys=tuple(str(item) for item in entry.get("source_citation_keys", [])),
            tags=tuple(str(item) for item in entry.get("tags", [])),
            status=str(entry.get("status", "complete")),
            variant_ids=tuple(str(item) for item in entry.get("variant_ids", [])),
        )
        for entry in cast(list[dict[str, Any]], raw_data.get("prompts", []))
    )
    variants = tuple(
        IdeationPromptVariant(
            variant_id=str(entry["variant_id"]),
            prompt_id=str(entry["prompt_id"]),
            problem_id=cast(str | None, entry.get("problem_id")),
            label=str(entry["label"]),
            statement_type=str(entry["statement_type"]),
            evidence_tier=EvidenceTier(str(entry["evidence_tier"])),
            source_citation_keys=tuple(str(item) for item in entry.get("source_citation_keys", [])),
            notes=str(entry.get("notes", "")),
            status=str(entry.get("status", "complete")),
        )
        for entry in cast(list[dict[str, Any]], raw_data.get("variants", []))
    )
    families = tuple(
        IdeationPromptFamily(
            family_id=str(entry["family_id"]),
            name=str(entry["name"]),
            group=str(entry["group"]),
            external_aliases=tuple(str(item) for item in entry.get("external_aliases", [])),
            derived_from_family_id=cast(str | None, entry.get("derived_from_family_id")),
            canonical_prompt_ids=tuple(str(item) for item in entry.get("canonical_prompt_ids", [])),
            tags=tuple(str(item) for item in entry.get("tags", [])),
            notes=str(entry.get("notes", "")),
        )
        for entry in cast(list[dict[str, Any]], raw_data.get("families", []))
    )
    studies = tuple(
        IdeationStudy(
            study_id=str(entry["study_id"]),
            title=str(entry["title"]),
            citation_keys=tuple(str(item) for item in entry.get("citation_keys", [])),
            prompt_variant_ids=tuple(str(item) for item in entry.get("prompt_variant_ids", [])),
            participant_summary=str(entry["participant_summary"]),
            conditions_summary=str(entry["conditions_summary"]),
            time_on_task_minutes=int(entry["time_on_task_minutes"]) if "time_on_task_minutes" in entry else None,
            dependent_measures=tuple(str(item) for item in entry.get("dependent_measures", [])),
            coding_summary=str(entry["coding_summary"]),
            materials_summary=str(entry["materials_summary"]),
            limitations=tuple(str(item) for item in entry.get("limitations", [])),
            status=str(entry.get("status", "complete")),
        )
        for entry in cast(list[dict[str, Any]], raw_data.get("studies", []))
    )
    return IdeationCatalog(
        citations=citations,
        prompts=prompts,
        variants=variants,
        families=families,
        studies=studies,
    )


_DEFAULT_IDEATION_CATALOG = load_ideation_catalog()


def get_ideation_catalog() -> IdeationCatalog:
    """Return the packaged ideation catalog."""
    return _DEFAULT_IDEATION_CATALOG
