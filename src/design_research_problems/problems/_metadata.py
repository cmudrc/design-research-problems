"""Shared metadata and catalog-facing problem types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProblemKind(StrEnum):
    """Supported high-level problem families."""

    TEXT = "text"
    OPTIMIZATION = "optimization"
    GRAMMAR = "grammar"


@dataclass(frozen=True)
class Citation:
    """Citation metadata for one problem entry."""

    key: str
    """Stable citation key, typically a BibTeX identifier."""
    kind: str
    """Citation format label such as ``bibtex`` or ``inline``."""
    raw_text: str
    """Canonical raw citation text."""
    url: str | None = None
    """Optional canonical source URL."""


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

    formulation: str
    """High-level mathematical or representational formulation."""
    convexity: str
    """Convexity characterization when applicable."""
    design_variable_type: str
    """Variable domain such as continuous, discrete, or mixed."""
    is_dynamic: bool
    """Whether the problem changes over time during evaluation or optimization."""
    orientation: str
    """Problem framing such as engineering-practical or mathematical."""
    feasibility_ratio_hint: float | None
    """Optional rough estimate of the feasible design-space fraction."""
    objective_mode: str
    """Objective structure such as single, multi, or qualitative."""
    constraint_nature: str
    """Constraint strictness label such as hard, soft, or informal."""
    bounds_summary: str
    """Human-readable summary of bounds or design-space limits."""
    tags: tuple[str, ...]
    """Searchable descriptive tags."""


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
    feature_flags: tuple[str, ...]
    """Machine-readable capability flags for this specific problem entry."""
    implementation: str | None = None
    """Optional ``module:attribute`` import path for executable problem types."""

    def has_feature(self, feature_flag: str) -> bool:
        """Return whether this problem advertises one feature flag.

        Args:
            feature_flag: Feature flag name to test.

        Returns:
            ``True`` when the normalized feature flag is present.
        """
        normalized = feature_flag.strip().lower().replace(" ", "-")
        return normalized in self.feature_flags
