from __future__ import annotations

import types
from dataclasses import dataclass

import pytest

from design_research_problems import get_problem, integration


def test_packaged_problem_id_resolves_to_problem_binding() -> None:
    binding = integration.resolve_problem_binding("decision_laptop_design_profit_maximization")
    problem = get_problem("decision_laptop_design_profit_maximization")

    assert binding.problem_id == "decision_laptop_design_profit_maximization"
    assert binding.family == problem.metadata.kind.value
    assert binding.problem_object.metadata.problem_id == problem.metadata.problem_id
    assert binding.metadata["title"] == problem.metadata.title
    assert problem.metadata.title in binding.brief


def test_problem_binding_brief_prefers_render_brief_then_statement_then_metadata() -> None:
    class RenderBriefProblem:
        def __init__(self) -> None:
            self.metadata = types.SimpleNamespace(
                problem_id="render-brief",
                kind=types.SimpleNamespace(value="decision"),
                title="Rendered",
                summary="summary",
                capabilities=("prompt-packet",),
                study_suitability=("intervention-ready",),
                feature_flags=("prompt-packet", "intervention-ready"),
                implementation="pkg:Problem",
            )
            self.statement_markdown = "ignored statement"

        def render_brief(self) -> str:
            return "# Rendered Brief"

    binding = integration.resolve_problem_binding(RenderBriefProblem())

    assert binding.brief == "# Rendered Brief"
    assert binding.metadata["capabilities"] == ("prompt-packet",)
    assert binding.metadata["study_suitability"] == ("intervention-ready",)


def test_evaluate_problem_output_normalizes_dataclass_metrics() -> None:
    @dataclass(frozen=True)
    class _Evaluation:
        objective_value: float
        is_feasible: bool
        higher_is_better: bool = False

    class EvaluatedProblem:
        problem_id = "evaluated"
        family = "optimization"
        brief = "brief"

        def evaluate(self, candidate: list[float]) -> _Evaluation:
            return _Evaluation(objective_value=sum(candidate), is_feasible=True)

    binding = integration.resolve_problem_binding(EvaluatedProblem())
    rows = integration.evaluate_problem_output(binding, {"candidate": [0.25, 0.75]})

    assert rows == [
        {
            "evaluator_id": "problem_evaluator",
            "metric_name": "objective_value",
            "metric_value": 1.0,
            "metric_unit": "unitless",
            "aggregation_level": "run",
            "notes_json": {},
        },
        {
            "evaluator_id": "problem_evaluator",
            "metric_name": "is_feasible",
            "metric_value": True,
            "metric_unit": "unitless",
            "aggregation_level": "run",
            "notes_json": {},
        },
    ]


def test_problem_binding_rejects_non_callable_evaluators() -> None:
    class BadEvaluatorProblem:
        problem_id = "bad"
        family = "decision"
        brief = "bad"
        evaluate = 42

    with pytest.raises(ValueError, match="callable"):
        integration.resolve_problem_binding(BadEvaluatorProblem())
