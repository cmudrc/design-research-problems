"""Manifest types for packaged problem resources."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from design_research_problems.problems._metadata import ProblemMetadata


@dataclass(frozen=True)
class ProblemManifest:
    """Container for one packaged catalog entry."""

    metadata: ProblemMetadata
    """Loaded problem metadata used for registry lookups."""
    resource_dir: str
    """Package-relative directory containing the problem resources."""
    statement_resource: str
    """File name of the packaged Markdown statement."""
    parameters: Mapping[str, object]
    """Implementation-specific manifest parameters."""
