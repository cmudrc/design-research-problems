"""Shared battery benchmark metadata and evaluator-provenance helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    resolve_battery_backend_config,
)


class BatteryRepresentationMode(StrEnum):
    """Public battery design-representation modes."""

    RECTANGULAR = "rectangular"
    POSE_LAYOUT = "pose_layout"
    TOPOLOGY_ALLOCATION = "topology_allocation"
    EXPLICIT_NETLIST = "explicit_netlist"
    THERMAL_TOPOLOGY = "thermal_topology"
    FAST_CHARGE_CELL = "fast_charge_cell"


class BatteryEvaluationMode(StrEnum):
    """Public battery evaluator-fidelity modes."""

    ANALYTIC_SURROGATE = "analytic_surrogate"
    EXPLICIT_CIRCUIT = "explicit_circuit"
    HYBRID_THERMAL = "hybrid_thermal"
    ELECTROCHEMICAL_ANCHOR = "electrochemical_anchor"


class BatteryImbalanceModel(StrEnum):
    """Supported stage-imbalance abstractions for surrogate pack metrics."""

    MIN_STAGE = "min_stage"
    HARMONIC_MEAN_STAGE = "harmonic_mean_stage"


@dataclass(frozen=True)
class BatteryEvaluationProvenance:
    """Serializable provenance for one battery benchmark evaluation."""

    representation_mode: str
    evaluation_mode: str
    evaluator_implementation: str
    requested_backend_config: dict[str, object] | None
    resolved_backend_config: dict[str, object] | None
    honored_backend_fields: tuple[str, ...]
    ignored_backend_fields: tuple[str, ...]
    cell_model_source: str | None = None
    thermal_prior_source: str | None = None
    projected_before_scoring: bool = False
    projection_notes: str | None = None
    imbalance_model: str | None = None


def coerce_battery_evaluation_mode(
    value: object,
    *,
    default: BatteryEvaluationMode,
    supported: tuple[BatteryEvaluationMode, ...],
) -> BatteryEvaluationMode:
    """Return one validated battery evaluation mode."""
    raw_value = default.value if value is None else str(value).strip().lower()
    try:
        mode = BatteryEvaluationMode(raw_value)
    except ValueError as exc:
        supported_text = ", ".join(mode.value for mode in supported)
        raise ValueError(f"Unsupported battery evaluation_mode {value!r}. Expected one of: {supported_text}.") from exc
    if mode not in supported:
        supported_text = ", ".join(candidate.value for candidate in supported)
        raise ValueError(f"Unsupported battery evaluation_mode {mode.value!r}. Expected one of: {supported_text}.")
    return mode


def coerce_battery_imbalance_model(
    value: object,
    *,
    default: BatteryImbalanceModel = BatteryImbalanceModel.MIN_STAGE,
) -> BatteryImbalanceModel:
    """Return one validated battery stage-imbalance surrogate mode."""
    raw_value = default.value if value is None else str(value).strip().lower()
    try:
        return BatteryImbalanceModel(raw_value)
    except ValueError as exc:
        supported_text = ", ".join(member.value for member in BatteryImbalanceModel)
        raise ValueError(f"Unsupported battery imbalance_model {value!r}. Expected one of: {supported_text}.") from exc


def build_battery_evaluation_provenance(
    *,
    representation_mode: BatteryRepresentationMode,
    evaluation_mode: BatteryEvaluationMode,
    evaluator_implementation: str,
    requested_backend_config: BatteryBackendConfig | None,
    honored_backend_fields: tuple[str, ...],
    cell_model_source: str | None = None,
    thermal_prior_source: str | None = None,
    projected_before_scoring: bool = False,
    projection_notes: str | None = None,
    imbalance_model: BatteryImbalanceModel | None = None,
) -> BatteryEvaluationProvenance:
    """Build one consistent provenance payload for battery problems."""
    requested_payload = None if requested_backend_config is None else requested_backend_config.as_dict()
    resolved_config = resolve_battery_backend_config(requested_backend_config)
    resolved_payload = resolved_config.as_dict()
    ignored_fields = tuple(sorted(set(resolved_payload) - set(honored_backend_fields)))
    return BatteryEvaluationProvenance(
        representation_mode=representation_mode.value,
        evaluation_mode=evaluation_mode.value,
        evaluator_implementation=evaluator_implementation,
        requested_backend_config=requested_payload,
        resolved_backend_config=resolved_payload,
        honored_backend_fields=tuple(sorted(set(honored_backend_fields))),
        ignored_backend_fields=ignored_fields,
        cell_model_source=cell_model_source,
        thermal_prior_source=thermal_prior_source,
        projected_before_scoring=projected_before_scoring,
        projection_notes=projection_notes,
        imbalance_model=None if imbalance_model is None else imbalance_model.value,
    )


__all__ = [
    "BatteryEvaluationMode",
    "BatteryEvaluationProvenance",
    "BatteryImbalanceModel",
    "BatteryRepresentationMode",
    "build_battery_evaluation_provenance",
    "coerce_battery_evaluation_mode",
    "coerce_battery_imbalance_model",
]
