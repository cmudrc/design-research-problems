"""Text problem container."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from typing import Literal

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemAsset, ProblemMetadata

_LEADING_H1_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


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

    def render_packet(
        self,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> str:
        """Render a human-readable prompt packet.

        Args:
            include_citation: Whether to append the bundled source citations.
            citation_mode: Citation rendering mode for the ``Sources`` section.

        Returns:
            Markdown packet suitable for display or study materials.
        """
        statement_body = self.statement_markdown.strip()
        if self._starts_with_h1(statement_body):
            sections = [statement_body]
        else:
            sections = [f"# {self.metadata.title}", statement_body]
        if include_citation and self.metadata.citations:
            if citation_mode in {"summary", "summary+raw"}:
                sections.append("## Sources")
                sections.append(self._render_citation_summaries())
            if citation_mode in {"raw", "summary+raw"}:
                sections.append("## BibTeX")
                sections.append(self._render_citation_raw_blocks())
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

    def _starts_with_h1(self, statement_body: str) -> bool:
        """Return whether the statement already includes a top-level title."""
        first_nonempty = next((line for line in statement_body.splitlines() if line.strip()), "")
        match = _LEADING_H1_PATTERN.match(first_nonempty)
        if match is None:
            return False
        heading = match.group(1).strip()
        if heading != self.metadata.title:
            warnings.warn(
                (
                    f"Statement H1 {heading!r} does not match metadata title "
                    f"{self.metadata.title!r} for {self.metadata.problem_id!r}."
                ),
                stacklevel=2,
            )
        return True

    def _render_citation_summaries(self) -> str:
        """Render the readable citation list."""
        lines: list[str] = []
        for citation in self.metadata.citations:
            summary = citation.summary_text()
            suffixes = [f"DOI: {citation.doi}" for citation in (citation,) if citation.doi]
            if citation.url:
                suffixes.append(citation.url)
            if suffixes:
                summary = f"{summary} ({'; '.join(suffixes)})"
            lines.append(f"- {summary}")
        return "\n".join(lines)

    def _render_citation_raw_blocks(self) -> str:
        """Render raw citation text in fenced blocks."""
        blocks: list[str] = []
        for citation in self.metadata.citations:
            info = "bibtex" if citation.kind == "bibtex" else "text"
            blocks.append(f"```{info}\n{citation.raw_text.strip()}\n```")
        return "\n\n".join(blocks)
