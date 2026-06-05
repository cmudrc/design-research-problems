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


def test_resolve_problem_binding_accepts_existing_binding_and_mapping_payload() -> None:
    class PayloadProblem:
        problem_id = "payload-problem"
        family = "optimization"
        brief = "Payload brief"

    payload_binding = integration.resolve_problem_binding(
        {"payload": {"problem_object": PayloadProblem()}, "problem_id": "ignored-fallback"}
    )

    assert payload_binding.problem_id == "payload-problem"
    assert payload_binding.family == "optimization"

    assert integration.resolve_problem_binding(payload_binding) is payload_binding

    with pytest.raises(ValueError, match="problem_object"):
        integration.resolve_problem_binding({"payload": {"other": object()}})


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


def test_problem_binding_brief_falls_back_across_problem_fields() -> None:
    class TypeErrorBriefProblem:
        problem_id = "type-error-brief"
        family = "decision"
        statement_markdown = "Statement fallback"

        def render_brief(self, _unexpected: object) -> str:
            return "unreachable"

    class ExceptionBriefProblem:
        problem_id = "exception-brief"
        family = "decision"
        prompt = "Prompt fallback"

        def render_brief(self) -> str:
            raise RuntimeError("rendering failed")

    class MetadataSummaryProblem:
        metadata = types.SimpleNamespace(problem_id="", kind=None, summary="Metadata summary", title="Title")

    class MetadataTitleProblem:
        metadata = types.SimpleNamespace(problem_id="", kind=None, summary="", title="Metadata title")

    assert integration.resolve_problem_binding(TypeErrorBriefProblem()).brief == "Statement fallback"
    assert integration.resolve_problem_binding(ExceptionBriefProblem()).brief == "Prompt fallback"
    assert integration.resolve_problem_binding(MetadataSummaryProblem()).brief == "Metadata summary"
    assert integration.resolve_problem_binding(MetadataTitleProblem()).brief == "Metadata title"


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


def test_evaluate_problem_output_covers_input_selection_and_payload_shapes() -> None:
    class ShapeProblem:
        problem_id = "shape"
        family = "optimization"
        brief = "brief"

        def __init__(self) -> None:
            self.inputs: list[object] = []

        def evaluate(self, candidate: object) -> list[object]:
            self.inputs.append(candidate)
            return [
                {"metric_name": "score", "metric_value": 2.5, "metric_unit": "points"},
                {"secondary": 3, "higher_is_better": True, "ignored": {"nested": "value"}},
                types.SimpleNamespace(to_dict=lambda: {"tertiary": 4.0}),
                types.SimpleNamespace(raw=5.0),
                "not-metrics",
            ]

    problem = ShapeProblem()
    binding = integration.resolve_problem_binding(problem)
    rows = integration.evaluate_problem_output(binding, {"state": {"x": 1}, "candidate": {"x": 0}})

    assert problem.inputs == [{"x": 0}]
    assert [row["metric_name"] for row in rows] == ["score", "secondary", "tertiary", "raw"]
    assert rows[0]["metric_value"] == 2.5

    fallback_rows = integration.evaluate_problem_output(binding, {"unstructured": "payload"})
    assert problem.inputs[-1] == {"unstructured": "payload"}
    assert fallback_rows


def test_evaluate_problem_output_handles_missing_and_invalid_evaluators() -> None:
    no_evaluator = integration.ProblemBinding(
        problem_id="none",
        family="decision",
        brief="brief",
        metadata={},
        problem_object=types.SimpleNamespace(),
    )
    assert integration.evaluate_problem_output(no_evaluator, {"answer": "x"}) == []

    invalid_evaluator = integration.ProblemBinding(
        problem_id="invalid",
        family="decision",
        brief="brief",
        metadata={},
        problem_object=types.SimpleNamespace(evaluate=42),
    )
    with pytest.raises(ValueError, match="callable"):
        integration.evaluate_problem_output(invalid_evaluator, {"answer": "x"})


def test_problem_binding_rejects_non_callable_evaluators() -> None:
    class BadEvaluatorProblem:
        problem_id = "bad"
        family = "decision"
        brief = "bad"
        evaluate = 42

    with pytest.raises(ValueError, match="callable"):
        integration.resolve_problem_binding(BadEvaluatorProblem())
