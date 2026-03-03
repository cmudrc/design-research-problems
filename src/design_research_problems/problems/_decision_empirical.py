"""Empirical-choice decision problem implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems._decision import (
    ChoiceMetric,
    DecisionChoiceEvaluation,
    DecisionProblem,
)

if TYPE_CHECKING:
    from design_research_problems._catalog._manifest import ProblemManifest


class EmpiricalChoiceDecisionProblem(DecisionProblem[str, DecisionChoiceEvaluation]):
    """Decision problem backed by empirical categorical choice benchmarks."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> EmpiricalChoiceDecisionProblem:
        """Construct the problem directly from a packaged manifest."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            parameters=manifest.parameters,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    @property
    def choice_options(self) -> tuple[str, ...]:
        """Return the canonical empirical choice keys in source order."""
        return tuple(benchmark.key for benchmark in self.choice_benchmarks)

    def evaluate(self, choice: str) -> DecisionChoiceEvaluation:
        """Evaluate one empirical choice using the default metric."""
        return self._evaluate_choice(choice)

    def evaluate_with_metric(
        self,
        choice: str,
        metric: ChoiceMetric | None = None,
    ) -> DecisionChoiceEvaluation:
        """Evaluate one empirical choice using an explicit metric override."""
        return self._evaluate_choice(choice, metric=metric)

    def rank_choices(
        self,
        metric: ChoiceMetric | None = None,
    ) -> tuple[DecisionChoiceEvaluation, ...]:
        """Return all empirical choices ranked by one metric."""
        return self._rank_choice_evaluations(metric=metric)

    def best_choice(
        self,
        metric: ChoiceMetric | None = None,
    ) -> DecisionChoiceEvaluation:
        """Return the best-scoring empirical categorical choice."""
        ranked = self.rank_choices(metric=metric)
        if not ranked:
            raise ProblemEvaluationError("Decision problem does not define empirical choice benchmarks.")
        return ranked[0]
