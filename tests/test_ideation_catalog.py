from __future__ import annotations

import json
import sys

import pytest

from design_research_problems import EvidenceTier, MissingOptionalDependencyError, get_ideation_catalog
from design_research_problems._catalog._validation import validate_catalog


def test_ideation_catalog_exposes_expected_table_sizes() -> None:
    catalog = get_ideation_catalog()
    assert len(catalog.list_prompts()) == 70
    assert len(catalog.list_variants()) == 71
    assert len(catalog.list_families()) == 50
    assert len(catalog.list_studies()) == 6


def test_ideation_catalog_cross_references_are_resolved() -> None:
    catalog = get_ideation_catalog()
    prompt_ids = {prompt.prompt_id for prompt in catalog.list_prompts()}
    variant_ids = {variant.variant_id for variant in catalog.list_variants()}
    family_ids = {family.family_id for family in catalog.list_families()}

    for prompt in catalog.list_prompts():
        assert prompt.family_id in family_ids
        assert set(prompt.variant_ids).issubset(variant_ids)

    for variant in catalog.list_variants():
        assert variant.prompt_id in prompt_ids

    peach_family = catalog.get_family("family_peach_picking")
    assert peach_family.derived_from_family_id == "family_book_picking"


def test_ideation_catalog_supports_search_and_export() -> None:
    catalog = get_ideation_catalog()
    matches = catalog.search_prompts(
        tags=("intervention",),
        evidence_tiers=(EvidenceTier.PRIMARY_VERBATIM,),
        max_timebox_minutes=20,
    )
    assert [prompt.prompt_id for prompt in matches] == [
        "prompt_one_handed_lidded_container_opening",
        "prompt_snow_transport_for_novices",
        "prompt_public_belongings_security",
        "prompt_remote_village_rainwater_access",
    ]

    json_payload = catalog.export_prompt_index(format="json")
    rows = json.loads(json_payload)
    assert rows[0]["prompt_id"] == "prompt_travel_exercise_device"

    csv_payload = catalog.export_prompt_index(format="csv")
    assert "prompt_id,problem_id,family_id,canonical_brief,evidence_tier,status,tags" in csv_payload.splitlines()[0]


def test_ideation_catalog_records_have_stable_columns() -> None:
    catalog = get_ideation_catalog()
    assert list(catalog.prompts_records()[0]) == [
        "prompt_id",
        "problem_id",
        "family_id",
        "canonical_brief",
        "evidence_tier",
        "status",
        "tags",
    ]
    assert list(catalog.variants_records()[0]) == [
        "variant_id",
        "prompt_id",
        "problem_id",
        "label",
        "statement_type",
        "evidence_tier",
        "status",
        "notes",
    ]


def test_ideation_catalog_reports_missing_pandas(monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = get_ideation_catalog()
    monkeypatch.setitem(sys.modules, "pandas", None)
    with pytest.raises(MissingOptionalDependencyError):
        catalog.prompts_dataframe()


def test_ideation_catalog_builds_dataframes_when_pandas_is_installed() -> None:
    pandas = pytest.importorskip("pandas")
    catalog = get_ideation_catalog()
    dataframe = catalog.prompts_dataframe()
    assert tuple(dataframe.columns) == (
        "prompt_id",
        "problem_id",
        "family_id",
        "canonical_brief",
        "evidence_tier",
        "status",
        "tags",
    )
    assert len(dataframe) == len(catalog.list_prompts())
    assert isinstance(dataframe, pandas.DataFrame)


def test_catalog_validation_has_no_errors_and_expected_follow_up_warnings() -> None:
    report = validate_catalog()
    assert report.errors == ()
    assert any("needs primary-source follow-up" in warning for warning in report.warnings)
