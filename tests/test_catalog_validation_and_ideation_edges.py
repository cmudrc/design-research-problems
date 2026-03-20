from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from design_research_problems import ideation as ideation_module
from design_research_problems._catalog import _validation as validation_module
from design_research_problems.ideation import (
    EvidenceTier,
    IdeationCatalog,
    IdeationPromptFamily,
    IdeationPromptRecord,
    IdeationPromptVariant,
    IdeationStudy,
)
from design_research_problems.problems import Citation, ProblemKind, ProblemMetadata, ProblemTaxonomy


def _taxonomy(
    *,
    deliverable_type: str | None = None,
    timebox_hint_minutes: int | None = None,
    participants: str | None = None,
    tags: tuple[str, ...] = ("alpha",),
    formulation: str | None = "textual",
) -> ProblemTaxonomy:
    return ProblemTaxonomy(
        formulation=formulation,
        convexity=None,
        design_variable_type=None,
        is_dynamic=False,
        orientation="engineering_practical",
        feasibility_ratio_hint=None,
        objective_mode="qualitative",
        constraint_nature="informal",
        bounds_summary=None,
        tags=tags,
        deliverable_type=deliverable_type,
        timebox_hint_minutes=timebox_hint_minutes,
        participants=participants,
    )


def _metadata(
    problem_id: str,
    *,
    kind: ProblemKind = ProblemKind.TEXT,
    title: str = "Demo Title",
    summary: str = "Demo summary",
    taxonomy: ProblemTaxonomy | None = None,
    capabilities: tuple[str, ...] = ("statement-markdown",),
    study_suitability: tuple[str, ...] = ("ideation-friendly",),
    citations: tuple[Citation, ...] = (),
) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title=title,
        summary=summary,
        kind=kind,
        taxonomy=taxonomy or _taxonomy(),
        citations=citations,
        assets=(),
        capabilities=capabilities,
        study_suitability=study_suitability,
    )


def _manifest(
    metadata: ProblemMetadata,
    *,
    parameters: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(metadata=metadata, parameters=parameters or {}, statement_markdown=f"# {metadata.title}")


def test_validate_catalog_reports_loader_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        validation_module,
        "load_problem_manifests",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    report = validation_module.validate_catalog()
    assert report.errors == ("Problem manifest load failed: boom",)
    assert report.warnings == ()
    assert report.is_valid is False

    monkeypatch.setattr(validation_module, "load_problem_manifests", lambda: {})
    monkeypatch.setattr(
        validation_module,
        "load_ideation_catalog",
        lambda: (_ for _ in ()).throw(RuntimeError("bad ideation")),
    )
    report = validation_module.validate_catalog()
    assert report.errors == ("Ideation catalog load failed: bad ideation",)


def test_validate_catalog_collects_problem_and_ideation_edge_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    broken_text = _manifest(
        _metadata(
            "broken_text",
            title="",
            summary="",
            taxonomy=_taxonomy(formulation=None, tags=(), deliverable_type=None, participants=None),
            capabilities=("unknown-capability",),
            study_suitability=("unknown-study",),
            citations=(
                Citation(
                    key="",
                    title="",
                    kind="inline",
                    authors=(),
                    year=None,
                    raw_text="",
                    provisional=True,
                ),
            ),
        )
    )
    bad_statement = _manifest(_metadata("bad_statement", title="Expected Heading"))
    broken_decision = _manifest(_metadata("broken_decision", kind=ProblemKind.DECISION), parameters={"bad": True})
    broken_mcp = _manifest(_metadata("broken_mcp", kind=ProblemKind.MCP), parameters={"bad": True})

    monkeypatch.setattr(
        validation_module,
        "load_problem_manifests",
        lambda: {
            "broken_text": broken_text,
            "bad_statement": bad_statement,
            "broken_decision": broken_decision,
            "broken_mcp": broken_mcp,
        },
    )

    def fake_statement_loader(manifest: Any) -> str:
        if manifest.metadata.problem_id == "bad_statement":
            raise RuntimeError("missing statement")
        return "# Mismatched Heading"

    monkeypatch.setattr(validation_module, "load_statement_text", fake_statement_loader)
    monkeypatch.setattr(
        validation_module,
        "parse_structured_decision_payload",
        lambda payload: (_ for _ in ()).throw(ValueError("invalid decision payload")),
    )
    monkeypatch.setattr(
        validation_module,
        "parse_mcp_stdio_parameters",
        lambda payload: (_ for _ in ()).throw(ValueError("invalid mcp payload")),
    )

    duplicate_prompt = IdeationPromptRecord(
        prompt_id="prompt_dup",
        problem_id="missing_problem",
        family_id="missing_family",
        canonical_brief="Alpha prompt",
        evidence_tier=EvidenceTier.PRIMARY_VERBATIM,
        source_citation_keys=("missing_citation",),
        tags=("alpha",),
        status="needs_primary_fill",
        variant_ids=("missing_variant",),
    )
    duplicate_variant = IdeationPromptVariant(
        variant_id="variant_dup",
        prompt_id="missing_prompt",
        problem_id="missing_problem",
        label="Variant",
        statement_type="canonical",
        evidence_tier=EvidenceTier.PRIMARY_RECONSTRUCTED,
        source_citation_keys=("missing_citation",),
        notes="Needs work",
        status="needs_primary_fill",
    )
    duplicate_family = IdeationPromptFamily(
        family_id="family_dup",
        name="Family",
        group="Group",
        external_aliases=(),
        derived_from_family_id="missing_parent",
        canonical_prompt_ids=(),
        tags=("alpha",),
        notes="",
    )
    duplicate_study = IdeationStudy(
        study_id="study_dup",
        title="Study",
        citation_keys=("missing_citation",),
        prompt_variant_ids=("missing_variant",),
        participant_summary="participants",
        conditions_summary="conditions",
        time_on_task_minutes=15,
        dependent_measures=("novelty",),
        coding_summary="coding",
        materials_summary="materials",
        limitations=("bias",),
        status="needs_primary_fill",
    )
    provisional_ideation_citation = Citation(
        key="",
        title="",
        kind="inline",
        authors=(),
        year=None,
        raw_text="",
        provisional=True,
    )
    monkeypatch.setattr(
        validation_module,
        "load_ideation_catalog",
        lambda: IdeationCatalog(
            citations=(provisional_ideation_citation,),
            prompts=(duplicate_prompt, duplicate_prompt),
            variants=(duplicate_variant, duplicate_variant),
            families=(duplicate_family, duplicate_family),
            studies=(duplicate_study, duplicate_study),
        ),
    )

    report = validation_module.validate_catalog()

    assert any("missing required metadata fields" in error for error in report.errors)
    assert any("could not load embedded statement text" in error for error in report.errors)
    assert any("invalid decision parameters" in error for error in report.errors)
    assert any("invalid mcp parameters" in error for error in report.errors)
    assert any("duplicate prompt IDs" in error for error in report.errors)
    assert any("references unknown family" in error for error in report.errors)
    assert any("references unknown variant" in error for error in report.errors)
    assert any("Ideation citations require key and title" in error for error in report.errors)
    assert any("statement H1 does not match metadata title" in warning for warning in report.warnings)
    assert any("needs primary-source follow-up" in warning for warning in report.warnings)
    assert any("lacks venue/doi/url" in warning for warning in report.warnings)


def test_leading_h1_and_ideation_catalog_edge_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    assert validation_module._leading_h1("\n\n# Heading\nText") == "Heading"
    assert validation_module._leading_h1("Not a heading") is None
    assert validation_module._leading_h1("") is None

    prompt = IdeationPromptRecord(
        prompt_id="prompt_alpha",
        problem_id="problem_alpha",
        family_id="family_alpha",
        canonical_brief="Alpha concept generator",
        evidence_tier=EvidenceTier.PRIMARY_VERBATIM,
        source_citation_keys=("cite_alpha",),
        tags=("alpha", "concept"),
        status="complete",
        variant_ids=("variant_alpha",),
    )
    prompt_without_problem = IdeationPromptRecord(
        prompt_id="prompt_beta",
        problem_id=None,
        family_id="family_alpha",
        canonical_brief="Beta concept generator",
        evidence_tier=EvidenceTier.SECONDARY_CANONICAL,
        source_citation_keys=("cite_alpha",),
        tags=("beta",),
        status="draft",
        variant_ids=("variant_alpha",),
    )
    variant = IdeationPromptVariant(
        variant_id="variant_alpha",
        prompt_id="prompt_alpha",
        problem_id="problem_alpha",
        label="Alpha Variant",
        statement_type="canonical",
        evidence_tier=EvidenceTier.PRIMARY_RECONSTRUCTED,
        source_citation_keys=("cite_alpha",),
        notes="notes",
        status="complete",
    )
    family = IdeationPromptFamily(
        family_id="family_alpha",
        name="Alpha Family",
        group="devices",
        external_aliases=("alias",),
        derived_from_family_id=None,
        canonical_prompt_ids=("prompt_alpha",),
        tags=("alpha",),
        notes="family notes",
    )
    study = IdeationStudy(
        study_id="study_alpha",
        title="Alpha Study",
        citation_keys=("cite_alpha",),
        prompt_variant_ids=("variant_alpha",),
        participant_summary="participants",
        conditions_summary="conditions",
        time_on_task_minutes=20,
        dependent_measures=("novelty",),
        coding_summary="coding",
        materials_summary="materials",
        limitations=("small sample",),
        status="complete",
    )
    catalog = IdeationCatalog(
        citations=(
            Citation(
                key="cite_alpha",
                title="Alpha Source",
                kind="inline",
                authors=("Author",),
                year=2020,
                raw_text="Author (2020). Alpha Source.",
            ),
        ),
        prompts=(prompt, prompt_without_problem),
        variants=(variant,),
        families=(family,),
        studies=(study,),
    )

    class FakeRegistry:
        def get(self, problem_id: str) -> SimpleNamespace:
            if problem_id == "problem_alpha":
                return SimpleNamespace(
                    metadata=_metadata(
                        problem_id,
                        taxonomy=_taxonomy(
                            deliverable_type="concept sketch",
                            timebox_hint_minutes=20,
                            participants="individual",
                        ),
                    )
                )
            return SimpleNamespace(metadata=_metadata(problem_id, taxonomy=_taxonomy(timebox_hint_minutes=None)))

    monkeypatch.setattr(ideation_module, "ProblemRegistry", FakeRegistry)

    with pytest.raises(KeyError, match="Unknown prompt id"):
        catalog.get_prompt("missing")
    with pytest.raises(KeyError, match="Unknown variant id"):
        catalog.get_variant("missing")
    with pytest.raises(KeyError, match="Unknown family id"):
        catalog.get_family("missing")
    with pytest.raises(KeyError, match="Unknown study id"):
        catalog.get_study("missing")

    assert catalog.search_prompts(tags=("missing",)) == ()
    assert catalog.search_prompts(family_ids=("missing",)) == ()
    assert catalog.search_prompts(evidence_tiers=(EvidenceTier.PRIMARY_RECONSTRUCTED,)) == ()
    assert catalog.search_prompts(status="archived") == ()
    assert catalog.search_prompts(text="missing text") == ()
    assert catalog.search_prompts(deliverable_type="physical prototype") == ()
    assert catalog.search_prompts(max_timebox_minutes=10) == ()
    assert catalog.search_prompts(
        deliverable_type="concept sketch",
        max_timebox_minutes=30,
    ) == (prompt,)

    registry = FakeRegistry()
    assert catalog._matches_problem_filters(registry, "problem_alpha", None, None) is True
    assert catalog._matches_problem_filters(registry, None, "concept sketch", None) is False
    assert catalog._matches_problem_filters(registry, "problem_alpha", "physical prototype", None) is False
    assert catalog._matches_problem_filters(registry, "problem_alpha", None, 10) is False
    assert catalog._matches_problem_filters(registry, "problem_without_timebox", None, 10) is False

    with pytest.raises(ValueError, match="Unsupported export format"):
        catalog.export_prompt_index(format="yaml")

    assert catalog._records_to_csv([]) == ""
    csv_payload = catalog._records_to_csv(catalog.prompts_records())
    assert "alpha; concept" in csv_payload
