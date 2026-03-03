"""Shared metadata and catalog-facing problem types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProblemKind(StrEnum):
    """Supported high-level problem families."""

    TEXT = "text"
    DECISION = "decision"
    OPTIMIZATION = "optimization"
    GRAMMAR = "grammar"


@dataclass(frozen=True)
class Citation:
    """Citation metadata for one problem entry."""

    key: str
    """Stable citation key, typically a BibTeX identifier."""
    kind: str
    """Citation format label such as ``bibtex`` or ``inline``."""
    authors: tuple[str, ...]
    """Structured author list used for search and summary rendering."""
    title: str
    """Canonical work title."""
    year: int | None
    """Publication year when known."""
    raw_text: str
    """Canonical raw citation text."""
    venue: str | None = None
    """Journal, conference, or source venue when known."""
    doi: str | None = None
    """Digital object identifier when known."""
    formatted_text: str | None = None
    """Optional curated display string."""
    url: str | None = None
    """Optional canonical source URL."""
    provisional: bool = False
    """Whether the record is intentionally incomplete and needs follow-up."""

    def summary_text(self) -> str:
        """Return a short human-readable citation line.

        Returns:
            Curated citation text when available, otherwise a synthesized summary.
        """
        if self.formatted_text:
            return self.formatted_text
        author_text = ", ".join(self.authors) if self.authors else "Unknown author"
        year_text = str(self.year) if self.year is not None else "n.d."
        parts = [f"{author_text} ({year_text}).", self.title]
        if self.venue:
            parts.append(self.venue)
        return " ".join(part.strip() for part in parts if part)


@dataclass(frozen=True)
class ProblemAsset:
    """Metadata for a non-code packaged asset."""

    name: str
    """Logical asset name used by the public API."""
    media_type: str
    """Media type such as ``image/png`` or ``text/plain``."""
    description: str
    """Short human-readable asset description."""
    resource_path: str
    """Path to the packaged resource relative to the problem directory."""


@dataclass(frozen=True)
class ProblemTaxonomy:
    """Shared descriptive taxonomy for all problem families."""

    formulation: str | None
    """High-level mathematical or representational formulation."""
    convexity: str | None
    """Convexity characterization when applicable."""
    design_variable_type: str | None
    """Variable domain such as continuous, discrete, or mixed."""
    is_dynamic: bool
    """Whether the problem changes over time during evaluation or optimization."""
    orientation: str | None
    """Problem framing such as engineering-practical or mathematical."""
    feasibility_ratio_hint: float | None
    """Optional rough estimate of the feasible design-space fraction."""
    objective_mode: str | None
    """Objective structure such as single, multi, or qualitative."""
    constraint_nature: str | None
    """Constraint strictness label such as hard, soft, or informal."""
    bounds_summary: str | None
    """Human-readable summary of bounds or design-space limits."""
    tags: tuple[str, ...]
    """Searchable descriptive tags."""
    deliverable_type: str | None = None
    """Expected participant output such as sketches or concepts."""
    timebox_hint_minutes: int | None = None
    """Typical task duration for the prompt when known."""
    participants: str | None = None
    """Typical participation mode such as individual or team."""
    evaluation_mode: str | None = None
    """Typical study outcome mode such as novelty or requirement coverage."""


@dataclass(frozen=True)
class ProblemMetadata:
    """Packaged metadata for one problem entry."""

    problem_id: str
    """Stable catalog identifier."""
    title: str
    """Display title shown to users."""
    summary: str
    """Short one-paragraph description."""
    kind: ProblemKind
    """High-level problem family."""
    taxonomy: ProblemTaxonomy
    """Shared descriptive taxonomy."""
    citations: tuple[Citation, ...]
    """Canonical source citations."""
    assets: tuple[ProblemAsset, ...]
    """Packaged non-code assets associated with the problem."""
    capabilities: tuple[str, ...]
    """Machine-readable implementation and packaging capabilities."""
    study_suitability: tuple[str, ...]
    """Machine-readable study-use labels for the entry."""
    implementation: str | None = None
    """Optional ``module:attribute`` import path for executable problem types."""

    @property
    def feature_flags(self) -> tuple[str, ...]:
        """Return the compatibility union of capabilities and study-suitability flags.

        Returns:
            Sorted union of both controlled-vocabulary flag sets.
        """
        return tuple(sorted({*self.capabilities, *self.study_suitability}))

    def has_feature(self, feature_flag: str) -> bool:
        """Return whether this problem advertises one feature flag.

        Args:
            feature_flag: Feature flag name to test.

        Returns:
            ``True`` when the normalized feature flag is present.
        """
        normalized = feature_flag.strip().lower().replace(" ", "-")
        return normalized in self.feature_flags


KNOWN_PROBLEM_CAPABILITIES = frozenset(
    {
        "statement-markdown",
        "citation-backed",
        "prompt-packet",
        "packaged-assets",
        "bounded-variables",
        "equality-constraint",
        "baseline-solver",
        "discrete-actions",
        "optional-evaluator",
        "external-adapter",
        "serializable-state",
    }
)
"""Controlled vocabulary for problem capabilities."""

KNOWN_STUDY_SUITABILITY = frozenset(
    {
        "human-subjects-ready",
        "ideation-friendly",
        "requirements-study-ready",
        "variety-study-ready",
        "intervention-ready",
    }
)
"""Controlled vocabulary for study-suitability tags."""
