from __future__ import annotations

from design_research_problems import ProblemKind, ProblemRegistry, get_problem
from design_research_problems.problems._metadata import (
    KNOWN_PROBLEM_CAPABILITIES,
    KNOWN_STUDY_SUITABILITY,
)


def test_registry_metadata_matches_the_downstream_contract() -> None:
    registry = ProblemRegistry()

    for metadata in registry.list():
        assert metadata.problem_id
        assert metadata.title
        assert metadata.summary
        assert isinstance(metadata.kind, ProblemKind)
        assert isinstance(metadata.capabilities, tuple)
        assert isinstance(metadata.study_suitability, tuple)
        assert isinstance(metadata.feature_flags, tuple)
        assert metadata.feature_flags == tuple(
            sorted({*metadata.capabilities, *metadata.study_suitability})
        )
        assert set(metadata.capabilities).issubset(KNOWN_PROBLEM_CAPABILITIES)
        assert set(metadata.study_suitability).issubset(KNOWN_STUDY_SUITABILITY)
        if metadata.implementation is not None:
            assert ":" in metadata.implementation


def test_resolved_problem_metadata_stays_aligned_with_registry_contract() -> None:
    registry = ProblemRegistry()
    registry_entry = registry.list()[0]
    problem = get_problem(registry_entry.problem_id)
    metadata = problem.metadata

    assert metadata.problem_id == registry_entry.problem_id
    assert metadata.title == registry_entry.title
    assert metadata.summary == registry_entry.summary
    assert metadata.kind == registry_entry.kind
    assert metadata.capabilities == registry_entry.capabilities
    assert metadata.study_suitability == registry_entry.study_suitability
    assert metadata.feature_flags == registry_entry.feature_flags
    assert metadata.implementation == registry_entry.implementation
