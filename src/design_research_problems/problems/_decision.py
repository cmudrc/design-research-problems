"""Decision problem container."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from design_research_problems.problems._text import TextProblem


@dataclass(frozen=True)
class DecisionProblem(TextProblem):
    """Structured text problem for decision-centered design studies."""

    parameters: Mapping[str, object]
    """Structured decision metadata extracted from the source."""

    def __post_init__(self) -> None:
        """Freeze the parameter mapping for safe library-owned access."""
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))

    @property
    def decision_variables(self) -> tuple[str, ...]:
        """Return the curated decision-variable descriptions."""
        return self._string_list("decision_variables")

    @property
    def objectives(self) -> tuple[str, ...]:
        """Return the stated objective descriptions."""
        return self._string_list("objectives")

    @property
    def constraints(self) -> tuple[str, ...]:
        """Return the curated constraint descriptions."""
        return self._string_list("constraints")

    @property
    def assumptions(self) -> tuple[str, ...]:
        """Return the modeling assumptions or caveats."""
        return self._string_list("assumptions")

    def render_brief(
        self,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> str:
        """Render the decision statement plus its extracted structure.

        Args:
            include_citation: Whether to append bundled source citations.
            citation_mode: Citation rendering mode for the ``Sources`` section.

        Returns:
            Markdown brief suitable for review or reuse.
        """
        sections = [self.render_packet(include_citation=False)]

        context_lines: list[str] = []
        for key, label in (
            ("decision_maker", "Decision maker"),
            ("market_segment", "Market segment"),
            ("decision_scope", "Decision scope"),
        ):
            value = self._string_value(key)
            if value is not None:
                context_lines.append(f"- {label}: {value}")
        if context_lines:
            sections.append("## Context")
            sections.append("\n".join(context_lines))

        for heading, values in (
            ("Decision Variables", self.decision_variables),
            ("Objectives", self.objectives),
            ("Constraints", self.constraints),
            ("Assumptions", self.assumptions),
        ):
            if values:
                sections.append(f"## {heading}")
                sections.append(self._render_bullets(values))

        if include_citation and self.metadata.citations:
            if citation_mode in {"summary", "summary+raw"}:
                sections.append("## Sources")
                sections.append(self._render_citation_summaries())
            if citation_mode in {"raw", "summary+raw"}:
                sections.append("## BibTeX")
                sections.append(self._render_citation_raw_blocks())

        return "\n\n".join(sections)

    def _string_value(self, key: str) -> str | None:
        """Return one non-empty string parameter when present."""
        raw_value = self.parameters.get(key)
        if not isinstance(raw_value, str):
            return None
        value = raw_value.strip()
        return value or None

    def _string_list(self, key: str) -> tuple[str, ...]:
        """Return one normalized string-list parameter when present."""
        raw_value = self.parameters.get(key)
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
            return ()
        values: list[str] = []
        for entry in raw_value:
            item = str(entry).strip()
            if item:
                values.append(item)
        return tuple(values)

    def _render_bullets(self, items: tuple[str, ...]) -> str:
        """Render a tuple of strings as a Markdown bullet list."""
        return "\n".join(f"- {item}" for item in items)
