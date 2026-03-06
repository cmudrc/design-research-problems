"""Python-backed MSEval decision implementation."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping, Sequence
from copy import deepcopy

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._decision import DecisionProblem


class MSEvalEmpiricalChoiceProblem(DecisionProblem):
    """Empirical MSEval material-selection decision problem."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> MSEvalEmpiricalChoiceProblem:
        """Construct an MSEval decision problem from a minimal manifest.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized empirical choice decision problem.
        """
        resource_bundle = PackageResourceBundle("design_research_problems", manifest.resource_dir)
        parameters = cls._materialize_parameters(manifest.parameters, resource_bundle)
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=resource_bundle,
            parameters=parameters,
        )

    @staticmethod
    def _materialize_parameters(
        manifest_parameters: Mapping[str, object],
        resource_bundle: PackageResourceBundle,
    ) -> dict[str, object]:
        """Build the executable parameter payload from minimal manifest metadata.

        Args:
            manifest_parameters: Raw manifest parameters.
            resource_bundle: Resource loader rooted at the packaged problem directory.

        Returns:
            Expanded parameter mapping compatible with ``DecisionProblem``.

        Raises:
            ProblemEvaluationError: If the benchmark asset is malformed.
        """
        parameters = dict(manifest_parameters)
        benchmark_file = str(parameters.get("benchmark_file", "benchmark.toml")).strip() or "benchmark.toml"
        benchmark_payload = tomllib.loads(resource_bundle.read_text(benchmark_file))
        response_count = int(benchmark_payload.get("response_count", 0))
        if response_count <= 0:
            raise ProblemEvaluationError("MSEval benchmark payload must define a positive response_count.")

        raw_choices = benchmark_payload.get("choices")
        if not isinstance(raw_choices, Sequence) or isinstance(raw_choices, (str, bytes)):
            raise ProblemEvaluationError("MSEval benchmark payload must define choices as a sequence of mappings.")

        choice_options: list[dict[str, object]] = []
        for entry in raw_choices:
            if not isinstance(entry, Mapping):
                raise ProblemEvaluationError("MSEval benchmark choice entries must be mappings.")
            choice_options.append(deepcopy(dict(entry)))
        if not choice_options:
            raise ProblemEvaluationError("MSEval benchmark payload must define at least one choice option.")

        parameters.setdefault("default_choice_metric", "top-choice-share")
        parameters["response_count"] = response_count
        parameters["choice_options"] = choice_options
        parameters["objective_specs"] = [
            {
                "key": "expert_agreement",
                "label": "Tie-adjusted expert top-choice share",
                "sense": "maximize",
                "domain": "empirical-choice",
                "expression": "sum_i I(choice in argmax_i)/|argmax_i| / N",
                "variables": ["material"],
                "executable": True,
            }
        ]
        return parameters
