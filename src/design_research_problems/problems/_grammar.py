"""Base class for grammar-driven discrete problems."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._computable import ComputableProblem
from design_research_problems.problems._metadata import ProblemMetadata


@dataclass(frozen=True)
class GrammarTransition[StateT]:
    """One deterministic grammar transition produced by a concrete rule method."""

    rule_name: str
    """Concrete public method name used to produce the transition."""
    parameters: tuple[tuple[str, object], ...]
    """Ordered keyword arguments that fully specify the rule call."""
    next_state: StateT
    """State returned by applying the rule."""


class GrammarProblem[StateT, EvaluationT](ComputableProblem[StateT, EvaluationT], ABC):
    """Abstract base for grammar-defined discrete design problems."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Store shared metadata for one grammar problem.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )

    @abstractmethod
    def initial_state(self) -> StateT:
        """Return the canonical starting state.

        Returns:
            Library-defined initial design state.
        """

    @abstractmethod
    def enumerate_transitions(self, state: StateT) -> tuple[GrammarTransition[StateT], ...]:
        """Return deterministic legal transitions for the given state.

        Args:
            state: Current grammar state.

        Returns:
            Fully specified legal transitions in deterministic order.
        """

    def enumerate_next_states(self, state: StateT) -> tuple[StateT, ...]:
        """Return the legal successor states for the given state.

        This convenience method supports generic grammar-family tooling that
        only needs the next design states, not the richer transition metadata.

        Args:
            state: Current grammar state.

        Returns:
            Deterministic next states in the same order as
            :meth:`enumerate_transitions`.
        """
        return tuple(transition.next_state for transition in self.enumerate_transitions(state))

    @abstractmethod
    def evaluate(self, state: StateT) -> EvaluationT:
        """Evaluate one design state.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Problem-specific evaluation result.
        """


__all__ = ["GrammarProblem", "GrammarTransition"]
