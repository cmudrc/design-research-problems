"""Study-facing integration helpers for packaged problems."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, cast

from ._catalog import get_problem


@dataclass(slots=True)
class ProblemBinding:
    """Normalized problem binding used by study-orchestration consumers."""

    problem_id: str
    family: str
    brief: str
    metadata: dict[str, Any]
    problem_object: Any


def resolve_problem_binding(problem_ref: Any) -> ProblemBinding:
    """Resolve one packaged problem reference to a stable study-facing binding."""
    if isinstance(problem_ref, ProblemBinding):
        return problem_ref

    if isinstance(problem_ref, str):
        return _binding_from_object(get_problem(problem_ref), fallback_problem_id=problem_ref)

    if isinstance(problem_ref, Mapping):
        problem_object = _extract_problem_object(problem_ref)
        if problem_object is None:
            raise ValueError(
                "Problem mappings passed to `resolve_problem_binding(...)` must expose "
                "`problem_object`, `problem`, or `payload['problem_object']`."
            )
        return _binding_from_object(
            problem_object,
            fallback_problem_id=_normalize_text(problem_ref.get("problem_id")),
        )

    return _binding_from_object(problem_ref)


def evaluate_problem_output(
    binding: ProblemBinding,
    run_output: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate one normalized run output against the packaged problem when possible."""
    evaluator = getattr(binding.problem_object, "evaluate", None)
    if evaluator is None:
        return []
    if not callable(evaluator):
        raise ValueError("Problem evaluator must be callable when present.")

    raw = evaluator(_resolve_evaluator_input(run_output))
    return _normalize_evaluation_payload(raw)


def _binding_from_object(
    problem_obj: Any,
    *,
    fallback_problem_id: str | None = None,
) -> ProblemBinding:
    """Normalize an arbitrary packaged-problem object into one `ProblemBinding`."""
    metadata_object = getattr(problem_obj, "metadata", None)
    problem_id = _stringify_first(
        getattr(metadata_object, "problem_id", None),
        getattr(problem_obj, "problem_id", None),
        fallback_problem_id,
        "problem",
    )
    family = _stringify_first(
        _value_or_enum(getattr(metadata_object, "kind", None)),
        getattr(problem_obj, "family", None),
        problem_obj.__class__.__name__,
    )
    brief = _resolve_problem_brief(problem_obj, fallback=problem_id)

    evaluator = getattr(problem_obj, "evaluate", None)
    if evaluator is not None and not callable(evaluator):
        raise ValueError("Problem evaluator must be callable when present.")

    metadata = {"problem_class": problem_obj.__class__.__name__}
    metadata.update(_extract_problem_metadata(problem_obj))

    return ProblemBinding(
        problem_id=problem_id,
        family=family,
        brief=brief,
        metadata=metadata,
        problem_object=problem_obj,
    )


def _extract_problem_object(problem_ref: Mapping[str, Any]) -> Any | None:
    """Extract one packaged-problem object from a packet-like mapping."""
    direct_problem = problem_ref.get("problem_object", problem_ref.get("problem"))
    if direct_problem is not None:
        return direct_problem
    payload = problem_ref.get("payload")
    if isinstance(payload, Mapping):
        return payload.get("problem_object")
    return None


def _resolve_problem_brief(problem_obj: Any, *, fallback: str) -> str:
    """Resolve the richest available human-readable brief for a problem object."""
    render_brief = getattr(problem_obj, "render_brief", None)
    if callable(render_brief):
        try:
            rendered = render_brief()
        except TypeError:
            rendered = None
        except Exception:
            rendered = None
        normalized = _normalize_text(rendered)
        if normalized is not None:
            return normalized

    for attribute_name in ("statement_markdown", "brief", "prompt"):
        normalized = _normalize_text(getattr(problem_obj, attribute_name, None))
        if normalized is not None:
            return normalized

    metadata_object = getattr(problem_obj, "metadata", None)
    normalized_summary = _normalize_text(getattr(metadata_object, "summary", None))
    if normalized_summary is not None:
        return normalized_summary
    normalized_title = _normalize_text(getattr(metadata_object, "title", None))
    if normalized_title is not None:
        return normalized_title
    return fallback


def _extract_problem_metadata(problem_obj: Any) -> dict[str, Any]:
    """Extract the downstream compatibility-guaranteed problem metadata slice."""
    metadata_object = getattr(problem_obj, "metadata", None)
    metadata: dict[str, Any] = {}

    title = _normalize_text(getattr(metadata_object, "title", None))
    if title is not None:
        metadata["title"] = title

    summary = _normalize_text(getattr(metadata_object, "summary", None))
    if summary is not None:
        metadata["summary"] = summary

    problem_kind = _value_or_enum(getattr(metadata_object, "kind", None))
    normalized_kind = _normalize_text(problem_kind)
    if normalized_kind is not None:
        metadata["problem_kind"] = normalized_kind

    capabilities = _string_sequence(getattr(metadata_object, "capabilities", None))
    if capabilities:
        metadata["capabilities"] = capabilities

    study_suitability = _string_sequence(getattr(metadata_object, "study_suitability", None))
    if study_suitability:
        metadata["study_suitability"] = study_suitability

    feature_flags = _string_sequence(getattr(metadata_object, "feature_flags", None))
    if feature_flags:
        metadata["feature_flags"] = feature_flags

    implementation = _normalize_text(getattr(metadata_object, "implementation", None))
    if implementation is not None:
        metadata["implementation"] = implementation

    return metadata


def _resolve_evaluator_input(run_output: Mapping[str, Any]) -> Any:
    """Resolve the best evaluator input for packaged and external problem evaluators."""
    preferred_keys = ("candidate", "state", "answer", "solution", "final_answer", "x")
    for key in preferred_keys:
        if key in run_output:
            return run_output[key]
    return run_output


def _normalize_evaluation_payload(raw: Any) -> list[dict[str, Any]]:
    """Normalize evaluator payloads into canonical experiment evaluation rows."""
    if isinstance(raw, Mapping):
        if _looks_like_evaluation_row(raw):
            return [_normalize_evaluation_row(raw)]
        return _metric_rows_from_mapping(raw)

    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        rows: list[dict[str, Any]] = []
        for row in raw:
            rows.extend(_normalize_evaluation_payload(row))
        return rows

    mapping = _object_to_mapping(raw)
    if mapping is None:
        return []
    return _metric_rows_from_mapping(mapping)


def _looks_like_evaluation_row(row: Mapping[str, Any]) -> bool:
    """Return whether a mapping already resembles one canonical evaluation row."""
    return any(key in row for key in ("metric_name", "metric_value", "value"))


def _metric_rows_from_mapping(metrics: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Expand a metrics mapping into canonical evaluation rows."""
    rows: list[dict[str, Any]] = []
    for metric_name, metric_value in metrics.items():
        if str(metric_name) == "higher_is_better":
            continue
        if not _is_metric_scalar(metric_value):
            continue
        rows.append(
            {
                "evaluator_id": "problem_evaluator",
                "metric_name": str(metric_name),
                "metric_value": metric_value,
                "metric_unit": "unitless",
                "aggregation_level": "run",
                "notes_json": {},
            }
        )
    return rows


def _object_to_mapping(value: Any) -> Mapping[str, Any] | None:
    """Best-effort conversion of an evaluation object to a flat mapping."""
    if value is None:
        return None
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return {field_info.name: getattr(value, field_info.name) for field_info in fields(value)}
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            candidate = to_dict()
        except Exception:
            candidate = None
        if isinstance(candidate, Mapping):
            return cast(Mapping[str, Any], candidate)
    if hasattr(value, "__dict__"):
        return cast(Mapping[str, Any], vars(value))
    return None


def _normalize_evaluation_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one evaluator row to canonical shape."""
    return {
        "evaluator_id": str(row.get("evaluator_id", "problem_evaluator")),
        "metric_name": str(row.get("metric_name", "score")),
        "metric_value": row.get("metric_value", row.get("value")),
        "metric_unit": str(row.get("metric_unit", "unitless")),
        "aggregation_level": str(row.get("aggregation_level", "run")),
        "notes_json": row.get("notes_json", {}),
    }


def _value_or_enum(value: Any) -> Any:
    """Return an enum's value when present, otherwise the original value."""
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    return value


def _stringify_first(*values: Any) -> str:
    """Return the first non-empty stringified value."""
    for value in values:
        normalized = _normalize_text(value)
        if normalized is not None:
            return normalized
    return ""


def _string_sequence(value: Any) -> tuple[str, ...]:
    """Normalize a loose sequence of values to a stable string tuple."""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value if _normalize_text(item) is not None)


def _normalize_text(value: Any) -> str | None:
    """Normalize one optional value to non-empty text."""
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _is_metric_scalar(value: Any) -> bool:
    """Return whether one value is suitable for scalar metric export."""
    return isinstance(value, bool | int | float)


__all__ = ["ProblemBinding", "evaluate_problem_output", "resolve_problem_binding"]
