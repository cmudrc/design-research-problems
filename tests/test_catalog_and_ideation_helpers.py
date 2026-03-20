from __future__ import annotations

from types import SimpleNamespace

import pytest

import design_research_problems
from design_research_problems._catalog import _registry as registry_module
from design_research_problems._catalog import _validation as validation_module
from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.ideation import (
    EvidenceTier,
    IdeationCatalog,
    IdeationPromptFamily,
    IdeationPromptRecord,
    IdeationPromptVariant,
    IdeationStudy,
    get_ideation_catalog,
)
from design_research_problems.problems import ProblemKind


def _fake_manifest(*, problem_id: str, kind: str, metadata: SimpleNamespace | None = None) -> SimpleNamespace:
    if metadata is None:
        metadata = SimpleNamespace(
            problem_id=problem_id,
            title=f"{problem_id} title",
            summary=f"{problem_id} summary",
            capabilities=("statement-markdown",),
            study_suitability=("human-subjects-ready",),
            taxonomy=SimpleNamespace(
                formulation="explicit",
                tags=("tag",),
                deliverable_type="brief",
                participants="designers",
                timebox_hint_minutes=15,
            ),
            kind=SimpleNamespace(value=kind),
            citations=(),
            implementation=None,
        )
    return SimpleNamespace(metadata=metadata, parameters={}, statement_markdown="# Statement")


def test_registry_helper_error_paths_and_custom_implementations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = registry_module.ProblemRegistry()

    with pytest.raises(ProblemEvaluationError, match="Invalid implementation path"):
        registry_module._resolve_object("broken-import-path")

    with pytest.raises(KeyError):
        registry.get("missing")

    with pytest.raises(KeyError):
        registry.feature_flags("missing")

    with pytest.raises(KeyError):
        registry.capabilities("missing")

    with pytest.raises(KeyError):
        registry.study_suitability("missing")

    with pytest.raises(TypeError, match="expected GrammarProblem"):
        registry.get_as(
            "ideation_peanut_shelling_fu_cagan_kotovsky_2010",
            design_research_problems.GrammarProblem,
        )

    direct_manifest = _fake_manifest(
        problem_id="custom_direct",
        kind="grammar",
        metadata=SimpleNamespace(
            implementation="custom:factory",
            kind=ProblemKind.GRAMMAR,
            problem_id="custom_direct",
        ),
    )
    monkeypatch.setattr(registry_module, "_resolve_object", lambda _: (lambda manifest: {"manifest": manifest}))
    monkeypatch.setattr(registry, "_catalog", lambda: {"custom_direct": direct_manifest})
    assert registry.get("custom_direct") == {"manifest": direct_manifest}

    not_callable_manifest = _fake_manifest(
        problem_id="custom_bad",
        kind="grammar",
        metadata=SimpleNamespace(
            implementation="custom:not_callable",
            kind=ProblemKind.GRAMMAR,
            problem_id="custom_bad",
        ),
    )
    monkeypatch.setattr(registry_module, "_resolve_object", lambda _: object())
    monkeypatch.setattr(registry, "_catalog", lambda: {"custom_bad": not_callable_manifest})
    with pytest.raises(ProblemEvaluationError, match="is not callable"):
        registry.get("custom_bad")

    missing_impl_manifest = _fake_manifest(
        problem_id="custom_missing_impl",
        kind="grammar",
        metadata=SimpleNamespace(
            implementation=None,
            kind=ProblemKind.GRAMMAR,
            problem_id="custom_missing_impl",
        ),
    )
    monkeypatch.setattr(registry, "_catalog", lambda: {"custom_missing_impl": missing_impl_manifest})
    with pytest.raises(ProblemEvaluationError, match="missing an implementation path"):
        registry.get("custom_missing_impl")


def test_registry_search_negative_filters_return_no_matches() -> None:
    registry = design_research_problems.ProblemRegistry()

    assert registry.search(tags=("definitely-missing-tag",)) == ()
    assert registry.search(feature_flags=("not-a-real-feature",)) == ()
    assert registry.search(capabilities=("not-a-real-capability",)) == ()
    assert registry.search(study_suitability=("not-a-real-study-flag",)) == ()
    assert registry.search(text="definitely not a packaged problem id") == ()


def test_validate_catalog_reports_problem_manifest_loader_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        validation_module,
        "load_problem_manifests",
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    report = validation_module.validate_catalog()

    assert report.errors == ("Problem manifest load failed: boom",)
    assert report.warnings == ()


def test_validate_catalog_reports_ideation_loader_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        validation_module,
        "load_problem_manifests",
        lambda: {"ok_problem": _fake_manifest(problem_id="ok_problem", kind="text")},
    )
    monkeypatch.setattr(validation_module, "load_statement_text", lambda manifest: "# ok_problem title")
    monkeypatch.setattr(
        validation_module,
        "load_ideation_catalog",
        lambda: (_ for _ in ()).throw(RuntimeError("bad ideation")),
    )

    report = validation_module.validate_catalog()

    assert "Ideation catalog load failed: bad ideation" in report.errors


def test_validate_catalog_surfaces_manifest_and_ideation_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text_manifest = _fake_manifest(
        problem_id="text_problem",
        kind="text",
        metadata=SimpleNamespace(
            problem_id="text_problem",
            title="",
            summary="",
            capabilities=("unknown-capability",),
            study_suitability=("unknown-suitability",),
            taxonomy=SimpleNamespace(
                formulation=None,
                tags=(),
                deliverable_type=None,
                participants=None,
                timebox_hint_minutes=30,
            ),
            kind=SimpleNamespace(value="text"),
            citations=(
                SimpleNamespace(
                    key="",
                    title="",
                    provisional=True,
                    venue=None,
                    doi=None,
                    url=None,
                ),
            ),
            implementation=None,
        ),
    )
    statement_manifest = _fake_manifest(problem_id="statement_problem", kind="text")
    decision_manifest = _fake_manifest(problem_id="decision_problem", kind="decision")
    mcp_manifest = _fake_manifest(problem_id="mcp_problem", kind="mcp")

    manifests = {
        "text_problem": text_manifest,
        "statement_problem": statement_manifest,
        "decision_problem": decision_manifest,
        "mcp_problem": mcp_manifest,
    }

    def _statement_text(manifest: SimpleNamespace) -> str:
        if manifest is statement_manifest:
            raise RuntimeError("missing statement body")
        if manifest is text_manifest:
            return "# Wrong heading"
        return f"# {manifest.metadata.problem_id} title"

    monkeypatch.setattr(validation_module, "load_problem_manifests", lambda: manifests)
    monkeypatch.setattr(validation_module, "load_statement_text", _statement_text)
    monkeypatch.setattr(
        validation_module,
        "parse_structured_decision_payload",
        lambda parameters: (_ for _ in ()).throw(ValueError("bad decision payload")),
    )
    monkeypatch.setattr(
        validation_module,
        "parse_mcp_stdio_parameters",
        lambda parameters: (_ for _ in ()).throw(ValueError("bad mcp payload")),
    )

    ideation_catalog = SimpleNamespace(
        prompts=(
            SimpleNamespace(
                prompt_id="prompt_dup",
                family_id="missing_family",
                problem_id="missing_problem",
                variant_ids=("missing_variant",),
                status="needs_primary_fill",
                source_citation_keys=("missing_citation",),
            ),
            SimpleNamespace(
                prompt_id="prompt_dup",
                family_id="family_dup",
                problem_id=None,
                variant_ids=(),
                status="complete",
                source_citation_keys=(),
            ),
        ),
        variants=(
            SimpleNamespace(
                variant_id="variant_dup",
                prompt_id="missing_prompt",
                problem_id="missing_problem",
                status="needs_primary_fill",
                source_citation_keys=("missing_citation",),
            ),
            SimpleNamespace(
                variant_id="variant_dup",
                prompt_id="prompt_dup",
                problem_id=None,
                status="complete",
                source_citation_keys=(),
            ),
        ),
        families=(
            SimpleNamespace(
                family_id="family_dup",
                derived_from_family_id="missing_parent",
                canonical_prompt_ids=(),
            ),
            SimpleNamespace(
                family_id="family_dup",
                derived_from_family_id=None,
                canonical_prompt_ids=("prompt_dup",),
            ),
        ),
        studies=(
            SimpleNamespace(
                study_id="study_dup",
                prompt_variant_ids=("missing_variant",),
                citation_keys=("missing_citation",),
                status="needs_primary_fill",
            ),
            SimpleNamespace(
                study_id="study_dup",
                prompt_variant_ids=(),
                citation_keys=(),
                status="complete",
            ),
        ),
        citations=(
            SimpleNamespace(
                key="",
                title="",
                provisional=True,
                venue=None,
                doi=None,
                url=None,
            ),
        ),
    )
    monkeypatch.setattr(validation_module, "load_ideation_catalog", lambda: ideation_catalog)

    report = validation_module.validate_catalog()
    errors = " | ".join(report.errors)
    warnings = " | ".join(report.warnings)

    assert "text_problem: missing required metadata fields" in errors
    assert "text_problem: unknown capability values" in errors
    assert "text_problem: unknown study-suitability values" in errors
    assert "text_problem: taxonomy.formulation is required" in errors
    assert "text_problem: taxonomy.tags must not be empty" in errors
    assert "text_problem: text problems require taxonomy.deliverable_type" in errors
    assert "text_problem: text problems require taxonomy.participants" in errors
    assert "text_problem: citation entries require key and title" in errors
    assert "statement_problem: could not load embedded statement text: missing statement body" in errors
    assert "decision_problem: invalid decision parameters: bad decision payload" in errors
    assert "mcp_problem: invalid mcp parameters: bad mcp payload" in errors
    assert "Ideation catalog contains duplicate prompt IDs" in errors
    assert "Ideation catalog contains duplicate variant IDs" in errors
    assert "Ideation catalog contains duplicate family IDs" in errors
    assert "Ideation catalog contains duplicate study IDs" in errors
    assert "prompt_dup: references unknown family 'missing_family'" in errors
    assert "prompt_dup: references unknown problem 'missing_problem'" in errors
    assert "prompt_dup: references unknown variant 'missing_variant'" in errors
    assert "variant_dup: references unknown prompt 'missing_prompt'" in errors
    assert "variant_dup: references unknown problem 'missing_problem'" in errors
    assert "family_dup: references unknown parent family 'missing_parent'" in errors
    assert "family_dup: family records must reference at least one prompt" in errors
    assert "study_dup: references unknown variant 'missing_variant'" in errors
    assert "study_dup: references unknown citation 'missing_citation'" in errors
    assert "Ideation citations require key and title" in errors

    assert "text_problem: statement H1 does not match metadata title" in warnings
    assert "text_problem: provisional citation '' lacks venue/doi/url" in warnings
    assert "prompt_dup: prompt needs primary-source follow-up" in warnings
    assert "variant_dup: variant needs primary-source follow-up" in warnings
    assert "study_dup: study needs primary-source follow-up" in warnings
    assert "ideation citation '' lacks venue/doi/url" in warnings


def test_ideation_catalog_lookup_filter_and_dataframe_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = get_ideation_catalog()

    assert catalog.get_prompt("prompt_travel_exercise_device").prompt_id == "prompt_travel_exercise_device"
    assert catalog.get_variant("variant_travel_exercise_device").variant_id == "variant_travel_exercise_device"
    assert catalog.get_family("family_book_picking").family_id == "family_book_picking"
    assert catalog.get_study("study_s1_hu_booth_reid_2015").study_id == "study_s1_hu_booth_reid_2015"

    with pytest.raises(KeyError, match="Unknown prompt id"):
        catalog.get_prompt("missing")

    with pytest.raises(KeyError, match="Unknown variant id"):
        catalog.get_variant("missing")

    with pytest.raises(KeyError, match="Unknown family id"):
        catalog.get_family("missing")

    with pytest.raises(KeyError, match="Unknown study id"):
        catalog.get_study("missing")

    with pytest.raises(ValueError, match="Unsupported export format"):
        catalog.export_prompt_index("yaml")

    assert catalog._records_to_csv([]) == ""
    assert "family_id" in catalog.families_records()[0]
    assert "study_id" in catalog.studies_records()[0]

    pandas = pytest.importorskip("pandas")
    assert isinstance(catalog.variants_dataframe(), pandas.DataFrame)
    assert isinstance(catalog.families_dataframe(), pandas.DataFrame)
    assert isinstance(catalog.studies_dataframe(), pandas.DataFrame)

    prompt = IdeationPromptRecord(
        prompt_id="prompt_unit",
        problem_id="problem_unit",
        family_id="family_unit",
        canonical_brief="Design a safer device",
        evidence_tier=EvidenceTier.PRIMARY_VERBATIM,
        source_citation_keys=("citation_unit",),
        tags=("safety", "medical"),
        status="complete",
        variant_ids=("variant_unit",),
    )
    variant = IdeationPromptVariant(
        variant_id="variant_unit",
        prompt_id="prompt_unit",
        problem_id="problem_unit",
        label="Canonical",
        statement_type="canonical",
        evidence_tier=EvidenceTier.PRIMARY_VERBATIM,
        source_citation_keys=("citation_unit",),
        notes="",
        status="complete",
    )
    family = IdeationPromptFamily(
        family_id="family_unit",
        name="Unit Family",
        group="unit",
        external_aliases=(),
        derived_from_family_id=None,
        canonical_prompt_ids=("prompt_unit",),
        tags=("safety",),
        notes="",
    )
    study = IdeationStudy(
        study_id="study_unit",
        title="Unit Study",
        citation_keys=("citation_unit",),
        prompt_variant_ids=("variant_unit",),
        participant_summary="n=1",
        conditions_summary="single condition",
        time_on_task_minutes=15,
        dependent_measures=("novelty",),
        coding_summary="manual",
        materials_summary="brief only",
        limitations=("small sample",),
        status="complete",
    )
    unit_catalog = IdeationCatalog(
        citations=(),
        prompts=(prompt,),
        variants=(variant,),
        families=(family,),
        studies=(study,),
    )

    class DummyRegistry:
        def get(self, problem_id: str) -> SimpleNamespace:
            del problem_id
            return SimpleNamespace(
                metadata=SimpleNamespace(
                    taxonomy=SimpleNamespace(
                        deliverable_type="brief",
                        timebox_hint_minutes=15,
                    )
                )
            )

    monkeypatch.setattr("design_research_problems.ideation.ProblemRegistry", DummyRegistry)

    assert unit_catalog.search_prompts(
        text="safer",
        tags=("safety",),
        family_ids=("family_unit",),
        evidence_tiers=(EvidenceTier.PRIMARY_VERBATIM,),
        deliverable_type="brief",
        max_timebox_minutes=20,
        status="complete",
    ) == (prompt,)
    assert unit_catalog.search_prompts(family_ids=("missing_family",)) == ()
    assert unit_catalog.search_prompts(status="draft") == ()
    assert unit_catalog.search_prompts(text="missing term") == ()
    assert unit_catalog.search_prompts(deliverable_type="wireframe") == ()
    assert unit_catalog.search_prompts(max_timebox_minutes=10) == ()

    prompt_without_problem = IdeationPromptRecord(
        prompt_id="prompt_without_problem",
        problem_id=None,
        family_id="family_unit",
        canonical_brief="Prompt without packaged problem",
        evidence_tier=EvidenceTier.PRIMARY_VERBATIM,
        source_citation_keys=(),
        tags=("safety",),
        status="complete",
        variant_ids=(),
    )
    no_problem_catalog = IdeationCatalog(
        citations=(),
        prompts=(prompt_without_problem,),
        variants=(),
        families=(family,),
        studies=(),
    )
    assert no_problem_catalog.search_prompts(deliverable_type="brief") == ()
