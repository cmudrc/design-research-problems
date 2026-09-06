from __future__ import annotations

import json

import pytest

import design_research_problems as drp


def test_ideation_problem_exports_prompt_lineage_and_multiple_references() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")

    assert packet["schema_version"] == "0.1.0"
    assert packet["source"]["package"] == "design-research-problems"
    assert packet["source"]["component_type"] == "problem"
    assert packet["source"]["component_id"] == "ideation_peanut_shelling"

    assert [item["contribution_id"] for item in packet["contributions"]] == [
        "problems:ideation_peanut_shelling:background",
        "problems:ideation_peanut_shelling:methods",
        "problems:ideation_peanut_shelling:prompt:prompt_peanut_shelling",
    ]
    prompt_contribution = packet["contributions"][2]
    assert prompt_contribution["citation_keys"] == [
        "goucher_lambert_cagan_2019",
        "viswanathan_linsey_2013",
        "linsey_green_murphy_wood_markman_2005",
    ]
    assert prompt_contribution["metadata"]["prompt_ids"] == ["prompt_peanut_shelling"]
    assert prompt_contribution["metadata"]["variant_ids"] == ["variant_peanut_shelling_canonical"]
    assert prompt_contribution["metadata"]["family_ids"] == ["family_peanut_shelling"]
    assert prompt_contribution["metadata"]["evidence_tier"] == "primary_verbatim"

    references = {reference["key"]: reference for reference in packet["references"]}
    assert set(references) == {
        "goucher_lambert_cagan_2019",
        "viswanathan_linsey_2013",
        "linsey_green_murphy_wood_markman_2005",
    }
    assert references["goucher_lambert_cagan_2019"]["authors"]
    assert references["goucher_lambert_cagan_2019"]["provenance"]["problem_id"] == ("ideation_peanut_shelling")


def test_provisional_reference_becomes_visible_reporting_gap() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")

    gaps = {item["gap_id"]: item for item in packet["reporting_gaps"]}
    gap_id = "problems:ideation_peanut_shelling:provisional-citation:linsey_green_murphy_wood_markman_2005"
    assert gaps[gap_id]["section"] == "background"
    assert "source verification" in gaps[gap_id]["message"]


def test_non_ideation_problem_exports_general_background_and_methods() -> None:
    packet = drp.collect_problem_paper_contributions("decision_laptop_design_profit_maximization")

    assert len(packet["contributions"]) == 2
    assert {item["section"] for item in packet["contributions"]} == {
        "background",
        "methods",
    }
    assert [item["key"] for item in packet["references"]] == ["shiau_tseng_heutchy_michalek_2007"]
    methods = packet["contributions"][1]
    assert methods["metadata"]["prompt_ids"] == []
    assert methods["metadata"]["variant_ids"] == []
    assert methods["metadata"]["family_ids"] == []
    assert any(
        "variables, objective, constraints" in requirement
        for requirement in methods["metadata"]["reporting_requirements"]
    )
    assert packet["reporting_gaps"] == []


def test_packet_is_json_compatible_and_citation_keys_resolve() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")

    assert json.loads(json.dumps(packet, sort_keys=True)) == packet
    reference_keys = {reference["key"] for reference in packet["references"]}
    contribution_keys = {key for contribution in packet["contributions"] for key in contribution["citation_keys"]}
    assert contribution_keys <= reference_keys


def test_configured_contributions_do_not_claim_executed_evidence() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")

    assert all(contribution["evidence_basis"] == "configured" for contribution in packet["contributions"])
    assert all(not contribution["evidence_refs"] for contribution in packet["contributions"])


def test_human_subjects_problem_carries_actual_study_reporting_reminder() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")
    methods = packet["contributions"][1]

    assert any(
        "actual participant sample" in requirement for requirement in methods["metadata"]["reporting_requirements"]
    )


def test_public_contract_version_matches_packet() -> None:
    packet = drp.collect_problem_paper_contributions("ideation_peanut_shelling")
    assert packet["schema_version"] == drp.PAPER_CONTRIBUTION_VERSION


def test_unknown_problem_id_is_rejected() -> None:
    with pytest.raises(KeyError, match="Unknown problem id"):
        drp.collect_problem_paper_contributions("not-a-problem")


def test_every_problem_packet_has_stable_source_and_valid_json() -> None:
    for problem_id in drp.list_problems():
        packet = drp.collect_problem_paper_contributions(problem_id)
        assert packet["source"]["component_id"] == problem_id
        assert packet["contributions"]
        json.dumps(packet)
