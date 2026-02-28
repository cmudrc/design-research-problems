"""Text problem container."""

from __future__ import annotations

from dataclasses import dataclass

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemAsset, ProblemMetadata


@dataclass(frozen=True)
class TextProblem:
    """Container for text-only problem prompts and metadata."""

    metadata: ProblemMetadata
    """Shared packaged metadata."""
    statement_markdown: str
    """Canonical Markdown prompt statement."""
    assets: tuple[ProblemAsset, ...]
    """Non-code assets associated with the prompt."""
    resource_bundle: PackageResourceBundle
    """Resource loader for packaged files."""

    def render_packet(self, include_citation: bool = True) -> str:
        """Render a human-readable prompt packet.

        Args:
            include_citation: Whether to append the bundled source citations.

        Returns:
            Markdown packet suitable for display or study materials.
        """
        sections = [f"# {self.metadata.title}", self.statement_markdown.strip()]
        if include_citation and self.metadata.citations:
            sections.append("## Sources")
            for citation in self.metadata.citations:
                sections.append(citation.raw_text.strip())
        return "\n\n".join(sections)

    def read_asset(self, name: str) -> bytes:
        """Read an asset by logical asset name.

        Args:
            name: Logical asset name declared in the manifest.

        Returns:
            Raw asset bytes.

        Raises:
            KeyError: If no asset exists for the requested name.
        """
        for asset in self.assets:
            if asset.name == name:
                return self.resource_bundle.read_bytes(asset.resource_path)
        raise KeyError(f"Unknown asset name: {name}")
