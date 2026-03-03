"""Shared packaged problem base."""

from __future__ import annotations

import re
import warnings
from typing import TYPE_CHECKING, Literal, TypeVar

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemMetadata

if TYPE_CHECKING:
    from design_research_problems._catalog._manifest import ProblemManifest

_LEADING_H1_PATTERN = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)
_ProblemT = TypeVar("_ProblemT", bound="Problem")


class Problem:
    """Shared documentation and resource container for one packaged problem."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Store the shared packaged metadata and resource handle.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Canonical Markdown statement.
            resource_bundle: Optional package-resource loader for problem assets.
        """
        self.metadata = metadata
        self.statement_markdown = statement_markdown
        self.resource_bundle = resource_bundle

    @staticmethod
    def resource_bundle_from_manifest(manifest: ProblemManifest) -> PackageResourceBundle:
        """Build a package-resource loader rooted at one manifest entry."""
        return PackageResourceBundle("design_research_problems", manifest.resource_dir)

    @classmethod
    def from_manifest(cls: type[_ProblemT], manifest: ProblemManifest) -> _ProblemT:
        """Construct one problem directly from a manifest entry."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    def render_packet(
        self,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> str:
        """Render a human-readable prompt packet."""
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
        """Read an asset by logical asset name."""
        if self.resource_bundle is None:
            raise RuntimeError("Problem has no resource bundle attached.")
        for asset in self.metadata.assets:
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
