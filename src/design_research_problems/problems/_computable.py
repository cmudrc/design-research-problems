"""Shared computational problem base."""

from __future__ import annotations

from abc import ABC, abstractmethod

from design_research_problems.problems._problem import Problem


class ComputableProblem[CandidateT, EvaluationT](Problem, ABC):
    """Shared base for problems that can evaluate one candidate."""

    @abstractmethod
    def evaluate(self, candidate: CandidateT) -> EvaluationT:
        """Evaluate one candidate in the problem's native representation.

        Args:
            candidate: Candidate value expressed in the problem's native input
                representation.

        Returns:
            Problem-specific evaluation result for ``candidate``.
        """
