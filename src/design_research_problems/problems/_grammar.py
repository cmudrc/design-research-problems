"""Base class for grammar-driven discrete problems."""

from __future__ import annotations

from abc import ABC, abstractmethod

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._computable import ComputableProblem
from design_research_problems.problems._metadata import ProblemMetadata


class GrammarProblem[StateT, ActionT, EvaluationT](ComputableProblem[StateT, EvaluationT], ABC):
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
    def enumerate_actions(self, state: StateT) -> tuple[ActionT, ...]:
        """Return a deterministic action set for the given state.

        Args:
            state: Current grammar state.

        Returns:
            Available actions in deterministic order.
        """

    @abstractmethod
    def apply_action(self, state: StateT, action: ActionT) -> StateT:
        """Apply one action and return a new state.

        Args:
            state: Current grammar state.
            action: One action returned by :meth:`enumerate_actions`.

        Returns:
            Updated grammar state.
        """

    @abstractmethod
    def evaluate(self, state: StateT) -> EvaluationT:
        """Evaluate one design state.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Problem-specific evaluation result.
        """
