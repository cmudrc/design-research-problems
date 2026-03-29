"""Shared battery tier dataclasses, defaults, and scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy
from numpy.typing import NDArray

from design_research_problems.problems._battery_adapters import (
    DEFAULT_AMBIENT_TEMPERATURE_C,
    DEFAULT_COOLING_COEFFICIENT,
    DEFAULT_PASSIVE_COOLING,
    DEFAULT_THERMAL_MODEL,
    THERMAL_MODEL_LUMPED,
    THERMAL_MODEL_MULTI_NODE,
    BatteryThermalPromotionConfig,
    coerce_battery_thermal_airflow_axis,
    coerce_battery_thermal_model,
)
from design_research_problems.problems._domains.battery_benchmark import (
    BatteryImbalanceModel,
    BatteryRepresentationMode,
    supported_pack_evaluation_modes,
)
from design_research_problems.problems._domains.battery_circuit import BatteryCircuitEvaluation
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    BatteryRequirements,
)
from design_research_problems.problems._domains.battery_tier_metrics import (
    BatteryObjectiveWeights,
    BatteryTierMetrics,
)

_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_DEFAULT_COOLING_COEFFICIENT = DEFAULT_COOLING_COEFFICIENT
_DEFAULT_PASSIVE_COOLING = DEFAULT_PASSIVE_COOLING
_DEFAULT_AMBIENT_TEMPERATURE_C = DEFAULT_AMBIENT_TEMPERATURE_C
_DEFAULT_MAX_TEMPERATURE_C = 60.0
_DEFAULT_THERMAL_MODEL = DEFAULT_THERMAL_MODEL
_THERMAL_MODEL_LUMPED = THERMAL_MODEL_LUMPED
_THERMAL_MODEL_MULTI_NODE = THERMAL_MODEL_MULTI_NODE

_T1_SUPPORTED_EVALUATION_MODES = supported_pack_evaluation_modes(BatteryRepresentationMode.RECTANGULAR)
_T2_SUPPORTED_EVALUATION_MODES = supported_pack_evaluation_modes(BatteryRepresentationMode.POSE_LAYOUT)
_T3A_SUPPORTED_EVALUATION_MODES = supported_pack_evaluation_modes(BatteryRepresentationMode.TOPOLOGY_ALLOCATION)
_T4_SUPPORTED_EVALUATION_MODES = supported_pack_evaluation_modes(BatteryRepresentationMode.THERMAL_TOPOLOGY)
_CACHE_DECIMALS = 5


@dataclass(frozen=True)
class Tier2DecodedCandidate:
    """Decoded tier-2 candidate."""

    series_count: int
    parallel_count: int
    cell_count: int


@dataclass(frozen=True)
class Tier3DecodedCandidate:
    """Decoded tier-3 candidate."""

    cell_count: int
    series_count: int
    stage_counts: tuple[int, ...]


@dataclass(frozen=True)
class Tier4DecodedCandidate:
    """Decoded tier-4 candidate."""

    base: Tier3DecodedCandidate
    cooling_coefficient_w_per_m2k: float
    passive_cooling_w_per_k: float
    ambient_temperature_c: float


@dataclass(frozen=True)
class Tier4ThermalDiagnostics:
    """Detailed tier-4 thermal diagnostics for non-contract reporting."""

    thermal_model: str
    max_core_temperature_c: float
    max_surface_temperature_c: float
    coolant_temperature_c: float
    max_core_surface_delta_c: float


@dataclass(frozen=True)
class _Tier4NodeThermalSolution:
    """Internal thermal-network solution payload for one candidate."""

    max_core_temperature_c: float
    max_surface_temperature_c: float
    coolant_temperature_c: float
    max_core_surface_delta_c: float


def _thermal_peak_temperature_c(
    *,
    cell_count: int,
    parallel_equivalent: float,
    surface_area_mm2: float,
    load_current_a: float,
    cooling_coefficient_w_per_m2k: float,
    passive_cooling_w_per_k: float,
    ambient_temperature_c: float,
) -> float:
    """Return one steady-state thermal proxy."""
    if cell_count <= 0:
        return float(ambient_temperature_c)
    per_cell_current = load_current_a / max(parallel_equivalent, 1.0e-9)
    total_heat_w = float(cell_count) * (per_cell_current**2) * CELL_SPEC_18650.internal_resistance_ohm
    cooling_area_m2 = surface_area_mm2 * 1.0e-6
    cooling_conductance = max(passive_cooling_w_per_k, 1.0e-9) + (cooling_coefficient_w_per_m2k * cooling_area_m2)
    return float(ambient_temperature_c + (total_heat_w / max(cooling_conductance, 1.0e-9)))


def _score_metrics(
    *,
    metrics: BatteryTierMetrics,
    requirements: BatteryRequirements,
    max_cell_count: int,
    max_temperature_c: float,
    ambient_temperature_c: float,
    weights: BatteryObjectiveWeights,
    total_violation: float,
) -> float:
    """Return weighted scalar objective plus infeasibility penalty."""
    max_pack_volume = max(
        requirements.max_width_mm * requirements.max_depth_mm * requirements.max_height_mm,
        1.0,
    )
    volume_term = metrics.design_volume_mm3 / max_pack_volume
    cost_term = metrics.cell_count / max(float(max_cell_count), 1.0)
    thermal_span = max(max_temperature_c - ambient_temperature_c, 1.0)
    temperature_term = (metrics.max_temperature_c - ambient_temperature_c) / thermal_span
    penalty = _INFEASIBILITY_PENALTY_SCALE * total_violation
    return (
        (weights.volume * volume_term) + (weights.cost * cost_term) + (weights.temperature * temperature_term) + penalty
    )


def _vector_cache_key(variables: NDArray[numpy.float64]) -> tuple[float, ...]:
    """Return a rounded immutable cache key for one design vector."""
    return tuple(float(round(float(value), _CACHE_DECIMALS)) for value in variables)


def _battery_thermal_config(
    *,
    cooling_coefficient_w_per_m2k: float,
    passive_cooling_w_per_k: float,
    ambient_temperature_c: float,
    thermal_model: str,
    thermal_neighbor_clearance_mm: float,
    thermal_contact_decay_mm: float,
    thermal_contact_resistance_k_per_w: float,
    thermal_flow_shadowing_factor: float,
    thermal_airflow_axis: str,
    thermal_reference_soc: float,
) -> BatteryThermalPromotionConfig:
    """Return the shared thermal-promotion config for one pack problem."""
    return BatteryThermalPromotionConfig(
        cooling_coefficient_w_per_m2k=float(cooling_coefficient_w_per_m2k),
        passive_cooling_w_per_k=float(passive_cooling_w_per_k),
        ambient_temperature_c=float(ambient_temperature_c),
        thermal_model=coerce_battery_thermal_model(thermal_model),
        thermal_neighbor_clearance_mm=max(0.0, float(thermal_neighbor_clearance_mm)),
        thermal_contact_decay_mm=max(1.0e-6, float(thermal_contact_decay_mm)),
        thermal_contact_resistance_k_per_w=max(1.0e-6, float(thermal_contact_resistance_k_per_w)),
        thermal_flow_shadowing_factor=float(numpy.clip(thermal_flow_shadowing_factor, 0.0, 1.0)),
        thermal_airflow_axis=coerce_battery_thermal_airflow_axis(thermal_airflow_axis),
        thermal_reference_soc=float(numpy.clip(thermal_reference_soc, 0.0, 1.0)),
    )


def _stage_parallel_equivalent(
    stage_counts: tuple[int, ...],
    imbalance_model: BatteryImbalanceModel,
) -> float:
    """Return the surrogate parallel support implied by one stage-population vector."""
    if not stage_counts:
        return 0.0
    if any(count <= 0 for count in stage_counts):
        return 0.0
    if imbalance_model is BatteryImbalanceModel.MIN_STAGE:
        return float(min(stage_counts))
    reciprocal_sum = sum(1.0 / float(count) for count in stage_counts)
    return float(len(stage_counts) / max(reciprocal_sum, 1.0e-9))


def _safe_delivered_capacity_ah(evaluation: BatteryCircuitEvaluation) -> float:
    """Return delivered capacity with a zero fallback."""
    return 0.0 if evaluation.delivered_capacity_ah is None else float(evaluation.delivered_capacity_ah)


def _tier3_connection_count(decoded: Tier3DecodedCandidate) -> float:
    """Return the surrogate connection-count metric for one tier-3 decode."""
    return float(sum(max(0, count - 1) for count in decoded.stage_counts) + max(0, decoded.series_count - 1))


def _tier3_surrogate_electrical_terms(
    decoded: Tier3DecodedCandidate,
    *,
    imbalance_model: BatteryImbalanceModel,
) -> tuple[float, float, float, float]:
    """Return surrogate parallel, voltage, capacity, and current terms for tier-3/4."""
    parallel_equivalent = _stage_parallel_equivalent(decoded.stage_counts, imbalance_model)
    voltage_v = float(decoded.series_count) * CELL_SPEC_18650.nominal_voltage_v
    capacity_ah = parallel_equivalent * CELL_SPEC_18650.nominal_capacity_ah
    current_limit_a = parallel_equivalent * CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
    return (parallel_equivalent, voltage_v, capacity_ah, current_limit_a)
