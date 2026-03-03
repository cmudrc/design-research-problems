"""Discrete-option decision problem implementation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from itertools import product
from typing import TYPE_CHECKING

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems._decision import DecisionOption, DecisionOptionEvaluation, DecisionProblem

if TYPE_CHECKING:
    from design_research_problems._catalog._manifest import ProblemManifest


class DiscreteOptionDecisionProblem(DecisionProblem[DecisionOption | Mapping[str, float], DecisionOptionEvaluation]):
    """Decision problem with an explicit discrete option space."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> DiscreteOptionDecisionProblem:
        """Construct the problem directly from a packaged manifest."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            parameters=manifest.parameters,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    def iter_options(self) -> Iterator[DecisionOption]:
        """Yield the full Cartesian product of the discrete option space."""
        if not self.option_factors:
            return
        factor_keys = tuple(factor.key for factor in self.option_factors)
        level_domains = tuple(factor.levels for factor in self.option_factors)
        for combination in product(*level_domains):
            yield DecisionOption(values=dict(zip(factor_keys, combination, strict=True)))

    def iter_option_evaluations(self) -> Iterator[DecisionOptionEvaluation]:
        """Yield evaluations for every explicit option."""
        for option in self.iter_options():
            yield self.evaluate(option)

    def best_option(self) -> DecisionOptionEvaluation:
        """Return the best-scoring explicit option in iteration order."""
        best: DecisionOptionEvaluation | None = None
        for evaluation in self.iter_option_evaluations():
            if best is None or evaluation.objective_value > best.objective_value:
                best = evaluation
        if best is None:
            raise ProblemEvaluationError("No discrete option space is available to evaluate.")
        return best

    def evaluate(self, candidate: DecisionOption | Mapping[str, float]) -> DecisionOptionEvaluation:
        """Evaluate one explicit discrete option."""
        return self._evaluate_option(candidate)
