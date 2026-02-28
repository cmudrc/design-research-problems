"""Base class for grammar-driven discrete problems."""

from __future__ import annotations

from abc import ABC, abstractmethod

from design_research_problems.problems._metadata import ProblemMetadata


class GrammarProblem(ABC):
    """Abstract base for grammar-defined discrete design problems."""

    def __init__(self, metadata: ProblemMetadata, statement_markdown: str = "") -> None:
        """Store shared metadata for one grammar problem.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
        """
        self.metadata = metadata
        self.statement_markdown = statement_markdown

    @abstractmethod
    def initial_state(self) -> object:
        """Return the canonical starting state.

        Returns:
            Library-defined initial design state.
        """

    @abstractmethod
    def enumerate_actions(self, state: object) -> tuple[object, ...]:
        """Return a deterministic action set for the given state.

        Args:
            state: Current grammar state.

        Returns:
            Available actions in deterministic order.
        """

    @abstractmethod
    def apply_action(self, state: object, action: object) -> object:
        """Apply one action and return a new state.

        Args:
            state: Current grammar state.
            action: One action returned by :meth:`enumerate_actions`.

        Returns:
            Updated grammar state.
        """

    @abstractmethod
    def evaluate(self, state: object) -> object:
        """Evaluate one design state.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Problem-specific evaluation result.
        """
