"""Shared packaged problem base."""

from __future__ import annotations

import re
import warnings
from typing import TYPE_CHECKING, Literal, TypeVar

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._mcp import (
    create_fastmcp_server,
    register_design_brief_resource,
)
from design_research_problems.problems._metadata import ProblemMetadata

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

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
        """Build a package-resource loader rooted at one manifest entry.

        Args:
            manifest: Parsed manifest describing the packaged resource location.

        Returns:
            Resource bundle rooted at the manifest's package directory.
        """
        return PackageResourceBundle("design_research_problems", manifest.resource_dir)

    @classmethod
    def from_manifest(cls: type[_ProblemT], manifest: ProblemManifest) -> _ProblemT:
        """Construct one problem directly from a manifest entry.

        Args:
            manifest: Parsed manifest used to initialize the problem instance.

        Returns:
            Problem instance of ``cls`` populated from the manifest data.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    def render_brief(
        self,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> str:
        """Render a human-readable problem brief.

        Args:
            include_citation: Whether to append citation content to the brief.
            citation_mode: Citation rendering mode to include summary text, raw
                citation text, or both.

        Returns:
            Markdown brief ready for display or export.
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

    def to_mcp_server(
        self,
        *,
        server_name: str | None = None,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> FastMCP:
        """Expose the problem through a minimal FastMCP interface.

        This default implementation fits text-style problems:
        one design-brief resource plus one free-text ``submit_final`` tool.

        Args:
            server_name: Optional explicit server name.
            include_citation: Whether the design brief includes citations.
            citation_mode: Citation rendering mode used for the design brief.

        Returns:
            Configured FastMCP server.
        """
        server = create_fastmcp_server(self, server_name=server_name)
        register_design_brief_resource(
            server,
            brief_text=self.render_brief(include_citation=include_citation, citation_mode=citation_mode),
        )

        def submit_final(answer: str, justification: str | None = None) -> dict[str, object]:
            """Submit one free-text final answer.

            Args:
                answer: Free-text final answer string.
                justification: Optional rationale for the submission.

            Returns:
                MCP-ready submission payload for the provided answer.

            Raises:
                ValueError: If the answer is empty after trimming whitespace.
            """
            normalized_answer = answer.strip()
            if not normalized_answer:
                raise ValueError("answer must be a non-empty string.")
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "answer": normalized_answer,
                "justification": None if justification is None else justification.strip() or None,
            }

        server.add_tool(
            submit_final,
            name="submit_final",
            title="Submit Final Answer",
            description="Submit a free-text final answer for this design brief.",
        )
        return server

    def read_asset(self, name: str) -> bytes:
        """Read an asset by logical asset name.

        Args:
            name: Logical asset name declared on the problem metadata.

        Returns:
            Raw bytes for the requested packaged asset.

        Raises:
            RuntimeError: If the problem was created without a resource bundle.
            KeyError: If ``name`` does not match any declared asset.
        """
        if self.resource_bundle is None:
            raise RuntimeError("Problem has no resource bundle attached.")
        for asset in self.metadata.assets:
            if asset.name == name:
                return self.resource_bundle.read_bytes(asset.resource_path)
        raise KeyError(f"Unknown asset name: {name}")

    def _starts_with_h1(self, statement_body: str) -> bool:
        """Return whether the statement already includes a top-level title.

        Args:
            statement_body: Statement Markdown with surrounding whitespace
                already stripped.

        Returns:
            ``True`` when the first non-empty line is a Markdown H1 heading.
        """
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
        """Render the readable citation list.

        Returns:
            Markdown bullet list of human-readable citation summaries.
        """
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
        """Render raw citation text in fenced blocks.

        Returns:
            Markdown fenced-code blocks containing the raw citation payloads.
        """
        blocks: list[str] = []
        for citation in self.metadata.citations:
            info = "bibtex" if citation.kind == "bibtex" else "text"
            blocks.append(f"```{info}\n{citation.raw_text.strip()}\n```")
        return "\n\n".join(blocks)
