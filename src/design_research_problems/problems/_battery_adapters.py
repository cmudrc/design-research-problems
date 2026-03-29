"""Shared battery representation/evaluation adaptation helpers."""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy

from design_research_problems.problems._domains.battery_benchmark import BatteryEvaluationMode
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    BatteryThermalPriors,
    interpolate_total_resistance,
    load_18650_cell_model,
    load_battery_thermal_priors,
    resolve_battery_backend_config,
)
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    evaluate_battery_circuit,
)
from design_research_problems.problems._domains.battery_core import (
    BatteryMetricSummary,
    compute_metric_summary,
    validate_rectangular_topology,
)
from design_research_problems.problems._domains.battery_geometry import (
    FiniteCylinder,
    axis_unit_vector_from_euler,
    min_distance_between_cylinders,
)
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    MIN_SPACING_MM,
    BatteryCoordinateLike,
    BatteryRequirements,
    coordinate_is_in_bounds,
    coordinate_to_physical_mm,
)
from design_research_problems.problems._domains.battery_series_parallel import (
    SeriesParallelBatteryState,
    build_circuit_state_from_series_parallel,
)
from design_research_problems.problems._domains.battery_tier_metrics import BatteryTierMetrics

THERMAL_MODEL_LUMPED = "lumped"
THERMAL_MODEL_MULTI_NODE = "multi_node_2node"
DEFAULT_THERMAL_MODEL = THERMAL_MODEL_MULTI_NODE
DEFAULT_COOLING_COEFFICIENT = 18.0
DEFAULT_PASSIVE_COOLING = 1.0
DEFAULT_AMBIENT_TEMPERATURE_C = 25.0
DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM = 8.0
DEFAULT_THERMAL_CONTACT_DECAY_MM = 2.0
DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W = 2.5
DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR = 0.25
DEFAULT_THERMAL_AIRFLOW_AXIS = "x"
DEFAULT_THERMAL_REFERENCE_SOC = 0.5


class BatteryThermalPoseLike(Protocol):
    """Pose protocol accepted by the shared thermal adapter."""

    @property
    def x_mm(self) -> float:
        """Return the x-center in millimeters."""
        ...

    @property
    def y_mm(self) -> float:
        """Return the y-center in millimeters."""
        ...

    @property
    def z_mm(self) -> float:
        """Return the z-center in millimeters."""
        ...

    @property
    def angle_x_deg(self) -> float:
        """Return the x-axis rotation in degrees."""
        ...

    @property
    def angle_y_deg(self) -> float:
        """Return the y-axis rotation in degrees."""
        ...

    @property
    def angle_z_deg(self) -> float:
        """Return the z-axis rotation in degrees."""
        ...


@dataclass(frozen=True)
class BatteryThermalPromotionConfig:
    """Deterministic thermal-network defaults used for promoted hybrid scoring."""

    cooling_coefficient_w_per_m2k: float = DEFAULT_COOLING_COEFFICIENT
    passive_cooling_w_per_k: float = DEFAULT_PASSIVE_COOLING
    ambient_temperature_c: float = DEFAULT_AMBIENT_TEMPERATURE_C
    thermal_model: str = DEFAULT_THERMAL_MODEL
    thermal_neighbor_clearance_mm: float = DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM
    thermal_contact_decay_mm: float = DEFAULT_THERMAL_CONTACT_DECAY_MM
    thermal_contact_resistance_k_per_w: float = DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W
    thermal_flow_shadowing_factor: float = DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR
    thermal_airflow_axis: str = DEFAULT_THERMAL_AIRFLOW_AXIS
    thermal_reference_soc: float = DEFAULT_THERMAL_REFERENCE_SOC

    def as_dict(self) -> dict[str, object]:
        """Return a manifest-like payload of the promoted thermal defaults."""
        return {
            "cooling_coefficient_w_per_m2k": float(self.cooling_coefficient_w_per_m2k),
            "passive_cooling_w_per_k": float(self.passive_cooling_w_per_k),
            "ambient_temperature_c": float(self.ambient_temperature_c),
            "thermal_model": self.thermal_model,
            "thermal_neighbor_clearance_mm": float(self.thermal_neighbor_clearance_mm),
            "thermal_contact_decay_mm": float(self.thermal_contact_decay_mm),
            "thermal_contact_resistance_k_per_w": float(self.thermal_contact_resistance_k_per_w),
            "thermal_flow_shadowing_factor": float(self.thermal_flow_shadowing_factor),
            "thermal_airflow_axis": self.thermal_airflow_axis,
            "thermal_reference_soc": float(self.thermal_reference_soc),
        }


@dataclass(frozen=True)
class BatteryThermalPose:
    """Simple thermal pose record used by promoted hybrid evaluators."""

    x_mm: float
    y_mm: float
    z_mm: float
    angle_x_deg: float = 0.0
    angle_y_deg: float = 0.0
    angle_z_deg: float = 0.0


@dataclass(frozen=True)
class BatteryThermalNetworkResult:
    """Reduced thermal-network solution used for promoted hybrid metrics."""

    max_core_temperature_c: float
    max_surface_temperature_c: float
    coolant_temperature_c: float
    max_core_surface_delta_c: float


@dataclass(frozen=True)
class BatteryEvaluationAdapterOutcome:
    """Shared evaluation outcome used to build tier metrics and provenance."""

    metrics: BatteryTierMetrics
    electrical_path: str
    thermal_path: str
    honored_backend_fields: tuple[str, ...] = ()
    cell_model_source: str | None = None
    thermal_prior_source: str | None = None
    assumed_defaults: dict[str, object] | None = None
    adaptation_notes: tuple[str, ...] = ()


def coerce_battery_thermal_model(thermal_model: str) -> str:
    """Return one validated thermal-network mode."""
    model = thermal_model.strip().lower()
    if model not in {THERMAL_MODEL_LUMPED, THERMAL_MODEL_MULTI_NODE}:
        raise ValueError(
            "battery thermal_model must be one of "
            f"{THERMAL_MODEL_LUMPED!r} or {THERMAL_MODEL_MULTI_NODE!r}, received {thermal_model!r}."
        )
    return model


def coerce_battery_thermal_airflow_axis(axis: str) -> str:
    """Return one validated airflow-axis label."""
    value = axis.strip().lower()
    if value not in {"x", "y", "z"}:
        raise ValueError(f"battery thermal_airflow_axis must be one of 'x', 'y', 'z', received {axis!r}.")
    return value


def resolved_backend_field_names(config: BatteryBackendConfig | None) -> tuple[str, ...]:
    """Return normalized backend field names honored by one backend-based path."""
    return tuple(sorted(resolve_battery_backend_config(config).as_dict()))


def promoted_hybrid_defaults_payload(
    config: BatteryThermalPromotionConfig,
    *,
    cell_pose_model: str | None = None,
) -> dict[str, object]:
    """Return the deterministic promoted-only defaults used by hybrid scoring."""
    defaults = config.as_dict()
    if cell_pose_model is not None:
        defaults["cell_pose_model"] = cell_pose_model
    return defaults


def infer_parallel_equivalent_from_cell_current(
    *,
    load_current_a: float,
    max_cell_current_a: float | None,
) -> float:
    """Infer one effective parallel support value from a solved cell current."""
    if max_cell_current_a is None or max_cell_current_a <= 1.0e-9:
        return 1.0
    return float(max(load_current_a / max_cell_current_a, 1.0))


def build_upright_thermal_poses_from_grid_cells(
    cells: Iterable[BatteryCoordinateLike],
) -> tuple[BatteryThermalPose, ...]:
    """Return upright-cylinder thermal poses for integer-grid cell placements."""
    return tuple(BatteryThermalPose(*coordinate_to_physical_mm((cell.x, cell.y, cell.z))) for cell in cells)


def minimum_clearance_mm_from_grid_cells(cells: Sequence[BatteryCoordinateLike]) -> float:
    """Return the minimum upright-cylinder clearance for grid-placed cells."""
    poses = build_upright_thermal_poses_from_grid_cells(cells)
    return minimum_clearance_mm_from_poses(poses)


def minimum_clearance_mm_from_poses(cells: Sequence[BatteryThermalPoseLike]) -> float:
    """Return the minimum finite-cylinder surface clearance across all cells."""
    if len(cells) < 2:
        return float(MIN_SPACING_MM)
    minimum_clearance = math.inf
    for first_index in range(len(cells)):
        first = _thermal_cylinder_from_cell(cells[first_index])
        for second_index in range(first_index + 1, len(cells)):
            second = _thermal_cylinder_from_cell(cells[second_index])
            summary = min_distance_between_cylinders(first, second)
            minimum_clearance = min(minimum_clearance, float(summary.clearance_true_mm))
    return float(MIN_SPACING_MM if math.isinf(minimum_clearance) else minimum_clearance)


def solve_battery_thermal_network(
    cells: Sequence[BatteryThermalPoseLike],
    *,
    cell_count: int,
    parallel_equivalent: float,
    load_current_a: float,
    thermal_priors: BatteryThermalPriors,
    config: BatteryThermalPromotionConfig,
    total_surface_area_mm2: float,
) -> BatteryThermalNetworkResult:
    """Solve the shared lumped or multi-node thermal network for one pack."""
    if cell_count <= 0:
        return BatteryThermalNetworkResult(
            max_core_temperature_c=float(config.ambient_temperature_c),
            max_surface_temperature_c=float(config.ambient_temperature_c),
            coolant_temperature_c=float(config.ambient_temperature_c),
            max_core_surface_delta_c=0.0,
        )
    per_cell_current = float(load_current_a) / max(float(parallel_equivalent), 1.0e-9)
    effective_resistance = interpolate_total_resistance(thermal_priors, float(config.thermal_reference_soc))
    per_cell_heat_w = (per_cell_current**2) * max(float(effective_resistance), 1.0e-9)
    if config.thermal_model == THERMAL_MODEL_LUMPED:
        return _solve_lumped_thermal_network(
            cell_count=cell_count,
            per_cell_heat_w=per_cell_heat_w,
            cooling_coefficient_w_per_m2k=float(config.cooling_coefficient_w_per_m2k),
            passive_cooling_w_per_k=float(config.passive_cooling_w_per_k),
            ambient_temperature_c=float(config.ambient_temperature_c),
            thermal_priors=thermal_priors,
            total_surface_area_mm2=float(total_surface_area_mm2),
        )
    return _solve_multi_node_thermal_network(
        cells=cells,
        cell_count=cell_count,
        per_cell_heat_w=per_cell_heat_w,
        cooling_coefficient_w_per_m2k=float(config.cooling_coefficient_w_per_m2k),
        passive_cooling_w_per_k=float(config.passive_cooling_w_per_k),
        ambient_temperature_c=float(config.ambient_temperature_c),
        thermal_priors=thermal_priors,
        thermal_neighbor_clearance_mm=float(config.thermal_neighbor_clearance_mm),
        thermal_contact_decay_mm=float(config.thermal_contact_decay_mm),
        thermal_contact_resistance_k_per_w=float(config.thermal_contact_resistance_k_per_w),
        thermal_flow_shadowing_factor=float(config.thermal_flow_shadowing_factor),
        thermal_airflow_axis=config.thermal_airflow_axis,
    )


def evaluate_rectangular_battery_state(
    state: SeriesParallelBatteryState,
    *,
    requirements: BatteryRequirements,
    backend_config: BatteryBackendConfig | None,
    evaluation_mode: BatteryEvaluationMode,
    load_current_a: float,
    thermal_config: BatteryThermalPromotionConfig,
) -> BatteryEvaluationAdapterOutcome:
    """Evaluate one rectangular battery state across analytic, explicit, or hybrid modes."""
    summary = compute_metric_summary(state, requirements)
    minimum_clearance = minimum_clearance_mm_from_grid_cells(state.cells)
    failure_reason = _analytic_rectangular_failure_reason(state, requirements, summary)
    if evaluation_mode is BatteryEvaluationMode.ANALYTIC_SURROGATE:
        metrics = BatteryTierMetrics(
            cell_count=float(summary.cell_count),
            connection_count=float(max(0, state.series_count + 1) * max(0, state.parallel_count - 1)),
            cost_usd=float(summary.design_cost),
            design_volume_mm3=float(summary.design_volume),
            max_temperature_c=_thermal_peak_temperature_c(
                cell_count=summary.cell_count,
                parallel_equivalent=float(max(state.parallel_count, 1)),
                surface_area_mm2=float(summary.surface_area),
                load_current_a=float(load_current_a),
                cooling_coefficient_w_per_m2k=float(thermal_config.cooling_coefficient_w_per_m2k),
                passive_cooling_w_per_k=float(thermal_config.passive_cooling_w_per_k),
                ambient_temperature_c=float(thermal_config.ambient_temperature_c),
            ),
            voltage_v=float(summary.design_voltage),
            capacity_ah=float(summary.design_capacity),
            current_limit_a=float(summary.analytic_current_limit),
            min_clearance_mm=minimum_clearance,
            is_feasible=failure_reason is None,
            failure_reason=failure_reason,
        )
        return BatteryEvaluationAdapterOutcome(
            metrics=metrics,
            electrical_path="native",
            thermal_path="native",
        )

    circuit_evaluation = evaluate_battery_circuit(
        state=build_circuit_state_from_series_parallel(state),
        requirements=requirements,
        load_cell_model=load_18650_cell_model,
        simulate_to_failure=True,
        backend_config=backend_config,
    )
    if evaluation_mode is BatteryEvaluationMode.HYBRID_THERMAL:
        thermal_priors = load_battery_thermal_priors(backend_config)
        thermal = solve_battery_thermal_network(
            build_upright_thermal_poses_from_grid_cells(state.cells),
            cell_count=summary.cell_count,
            parallel_equivalent=float(max(state.parallel_count, 1)),
            load_current_a=float(load_current_a),
            thermal_priors=thermal_priors,
            config=thermal_config,
            total_surface_area_mm2=float(summary.surface_area),
        )
        max_temperature_c = thermal.max_core_temperature_c
        thermal_prior_source = thermal_priors.source
        thermal_path = "promoted"
        assumed_defaults = promoted_hybrid_defaults_payload(
            thermal_config,
            cell_pose_model="upright_grid_cylinders",
        )
        adaptation_notes: tuple[str, ...] = (
            "Electrical scoring promotes rectangular SxP counts to a canonical series-parallel circuit.",
            "Hybrid thermal scoring promotes rectangular cells to upright grid cylinders with deterministic defaults.",
        )
    else:
        max_temperature_c = _thermal_peak_temperature_c(
            cell_count=summary.cell_count,
            parallel_equivalent=float(max(state.parallel_count, 1)),
            surface_area_mm2=float(summary.surface_area),
            load_current_a=float(load_current_a),
            cooling_coefficient_w_per_m2k=float(thermal_config.cooling_coefficient_w_per_m2k),
            passive_cooling_w_per_k=float(thermal_config.passive_cooling_w_per_k),
            ambient_temperature_c=float(thermal_config.ambient_temperature_c),
        )
        thermal_prior_source = None
        thermal_path = "native"
        assumed_defaults = None
        adaptation_notes = (
            "Electrical scoring promotes rectangular SxP counts to a canonical series-parallel circuit.",
        )
    metrics = BatteryTierMetrics(
        cell_count=float(summary.cell_count),
        connection_count=float(circuit_evaluation.connection_count),
        cost_usd=float(summary.design_cost),
        design_volume_mm3=float(summary.design_volume),
        max_temperature_c=float(max_temperature_c),
        voltage_v=float(circuit_evaluation.pack_nominal_voltage),
        capacity_ah=_safe_delivered_capacity_ah(circuit_evaluation),
        current_limit_a=float(summary.analytic_current_limit),
        min_clearance_mm=minimum_clearance,
        is_feasible=bool(circuit_evaluation.is_feasible),
        failure_reason=circuit_evaluation.failure_reason,
    )
    return BatteryEvaluationAdapterOutcome(
        metrics=metrics,
        electrical_path="promoted",
        thermal_path=thermal_path,
        honored_backend_fields=resolved_backend_field_names(backend_config),
        cell_model_source=circuit_evaluation.cell_model_source,
        thermal_prior_source=thermal_prior_source,
        assumed_defaults=assumed_defaults,
        adaptation_notes=adaptation_notes,
    )


def evaluate_explicit_netlist_state(
    state: BatteryCircuitState,
    *,
    requirements: BatteryRequirements,
    backend_config: BatteryBackendConfig | None,
    evaluation_mode: BatteryEvaluationMode,
    load_current_a: float,
    thermal_config: BatteryThermalPromotionConfig,
) -> BatteryEvaluationAdapterOutcome:
    """Evaluate one explicit battery netlist under the supported public modes."""
    if evaluation_mode is BatteryEvaluationMode.ANALYTIC_SURROGATE:
        raise ValueError(
            "analytic_surrogate is intentionally unsupported for explicit_netlist battery problems; "
            "use explicit_circuit or hybrid_thermal."
        )
    circuit_evaluation = evaluate_battery_circuit(
        state=state,
        requirements=requirements,
        load_cell_model=load_18650_cell_model,
        simulate_to_failure=True,
        backend_config=backend_config,
    )
    effective_parallel = infer_parallel_equivalent_from_cell_current(
        load_current_a=float(load_current_a),
        max_cell_current_a=circuit_evaluation.max_cell_current_a,
    )
    current_limit_a = effective_parallel * CELL_SPEC_18650.nominal_capacity_ah * CELL_SPEC_18650.max_discharge_rate_c
    minimum_clearance = minimum_clearance_mm_from_grid_cells(state.cells)
    if evaluation_mode is BatteryEvaluationMode.HYBRID_THERMAL:
        thermal_priors = load_battery_thermal_priors(backend_config)
        thermal = solve_battery_thermal_network(
            build_upright_thermal_poses_from_grid_cells(state.cells),
            cell_count=circuit_evaluation.cell_count,
            parallel_equivalent=effective_parallel,
            load_current_a=float(load_current_a),
            thermal_priors=thermal_priors,
            config=thermal_config,
            total_surface_area_mm2=float(circuit_evaluation.surface_area),
        )
        max_temperature_c = thermal.max_core_temperature_c
        thermal_prior_source = thermal_priors.source
        thermal_path = "promoted"
        assumed_defaults = promoted_hybrid_defaults_payload(
            thermal_config,
            cell_pose_model="upright_grid_cylinders",
        )
        if circuit_evaluation.topology_kind != "series_parallel":
            adaptation_notes: tuple[str, ...] = (
                "Hybrid thermal scoring promotes explicit grid cells to upright cylinders with deterministic defaults.",
                "General explicit netlists infer effective parallel support from the solved maximum cell current.",
            )
        else:
            adaptation_notes = (
                "Hybrid thermal scoring promotes explicit grid cells to upright cylinders with deterministic defaults.",
            )
    else:
        max_temperature_c = _thermal_peak_temperature_c(
            cell_count=circuit_evaluation.cell_count,
            parallel_equivalent=effective_parallel,
            surface_area_mm2=float(circuit_evaluation.surface_area),
            load_current_a=float(load_current_a),
            cooling_coefficient_w_per_m2k=float(thermal_config.cooling_coefficient_w_per_m2k),
            passive_cooling_w_per_k=float(thermal_config.passive_cooling_w_per_k),
            ambient_temperature_c=float(thermal_config.ambient_temperature_c),
        )
        thermal_prior_source = None
        thermal_path = "native"
        assumed_defaults = None
        adaptation_notes = ()
    metrics = BatteryTierMetrics(
        cell_count=float(circuit_evaluation.cell_count),
        connection_count=float(circuit_evaluation.connection_count),
        cost_usd=float(circuit_evaluation.design_cost),
        design_volume_mm3=float(circuit_evaluation.design_volume),
        max_temperature_c=float(max_temperature_c),
        voltage_v=float(circuit_evaluation.pack_nominal_voltage),
        capacity_ah=_safe_delivered_capacity_ah(circuit_evaluation),
        current_limit_a=float(current_limit_a),
        min_clearance_mm=minimum_clearance,
        is_feasible=bool(circuit_evaluation.is_feasible),
        failure_reason=circuit_evaluation.failure_reason,
    )
    return BatteryEvaluationAdapterOutcome(
        metrics=metrics,
        electrical_path="native",
        thermal_path=thermal_path,
        honored_backend_fields=resolved_backend_field_names(backend_config),
        cell_model_source=circuit_evaluation.cell_model_source,
        thermal_prior_source=thermal_prior_source,
        assumed_defaults=assumed_defaults,
        adaptation_notes=tuple(adaptation_notes),
    )


def _analytic_rectangular_failure_reason(
    state: SeriesParallelBatteryState,
    requirements: BatteryRequirements,
    summary: BatteryMetricSummary,
) -> str | None:
    """Return the first deterministic analytic failure for one rectangular state."""
    failure_reason = validate_rectangular_topology(state)
    if failure_reason is not None:
        return failure_reason
    coordinates = [(cell.x, cell.y, cell.z) for cell in state.cells]
    if len(set(coordinates)) != len(coordinates):
        return "Duplicate physical coordinates are not allowed."
    for coordinate in coordinates:
        if any(value < 0 for value in coordinate):
            return "Cell coordinates must be non-negative."
        if not coordinate_is_in_bounds(coordinate, requirements):
            return "A cell lies outside the legal grid envelope."
    if summary.design_width > requirements.max_width_mm:
        return "Pack width exceeds the maximum allowed width."
    if summary.design_depth > requirements.max_depth_mm:
        return "Pack depth exceeds the maximum allowed depth."
    if summary.design_height > requirements.max_height_mm:
        return "Pack height exceeds the maximum allowed height."
    voltage_error = abs(summary.design_voltage - requirements.target_voltage_v)
    if voltage_error > requirements.voltage_tolerance_v:
        return "Pack voltage does not match the required target voltage."
    if summary.design_capacity < requirements.minimum_capacity_ah:
        return "Pack capacity is below the minimum required capacity."
    if summary.analytic_current_limit < requirements.minimum_current_a:
        return "Analytic current limit is below the required continuous current."
    return None


def _safe_delivered_capacity_ah(evaluation: BatteryCircuitEvaluation) -> float:
    """Return delivered capacity with a zero fallback."""
    return 0.0 if evaluation.delivered_capacity_ah is None else float(evaluation.delivered_capacity_ah)


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


def _thermal_cylinder_from_cell(cell: BatteryThermalPoseLike) -> FiniteCylinder:
    """Return the finite-cylinder proxy used for thermal-neighbor calculations."""
    return FiniteCylinder(
        center_mm=(float(cell.x_mm), float(cell.y_mm), float(cell.z_mm)),
        axis_unit_vector=axis_unit_vector_from_euler(
            float(cell.angle_x_deg),
            float(cell.angle_y_deg),
            float(cell.angle_z_deg),
        ),
        radius_mm=CELL_SPEC_18650.diameter_mm / 2.0,
        half_length_mm=CELL_SPEC_18650.length_mm / 2.0,
    )


def _thermal_interface_gap_mm(summary: Any) -> float:
    """Return the interface-specific gap metric used for thermal coupling."""
    if summary.classification == "axial" and summary.gap_axial_mm is not None:
        return float(summary.gap_axial_mm)
    if summary.classification == "radial" and summary.gap_radial_mm is not None:
        return float(summary.gap_radial_mm)
    return float(summary.clearance_true_mm)


def _solve_lumped_thermal_network(
    *,
    cell_count: int,
    per_cell_heat_w: float,
    cooling_coefficient_w_per_m2k: float,
    passive_cooling_w_per_k: float,
    ambient_temperature_c: float,
    thermal_priors: BatteryThermalPriors,
    total_surface_area_mm2: float,
) -> BatteryThermalNetworkResult:
    """Return the one-node thermal-network solution."""
    total_heat_w = float(cell_count) * per_cell_heat_w
    cooling_area_m2 = max(total_surface_area_mm2, 0.0) * 1.0e-6
    base_path_conductance = 1.0 / (
        (1.0 / max(thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9))
        + (1.0 / max(thermal_priors.jig_to_ambient_conductance_w_per_k, 1.0e-9))
    )
    cooling_conductance = (
        max(passive_cooling_w_per_k, 1.0e-9)
        + max(cooling_coefficient_w_per_m2k, 0.0) * cooling_area_m2
        + base_path_conductance
    )
    coolant_conductance = max(passive_cooling_w_per_k, 1.0e-9) + thermal_priors.jig_to_ambient_conductance_w_per_k
    max_core_temperature_c = float(ambient_temperature_c + (total_heat_w / max(cooling_conductance, 1.0e-9)))
    coolant_temperature_c = float(ambient_temperature_c + (total_heat_w / max(coolant_conductance, 1.0e-9)))
    return BatteryThermalNetworkResult(
        max_core_temperature_c=max_core_temperature_c,
        max_surface_temperature_c=max_core_temperature_c,
        coolant_temperature_c=coolant_temperature_c,
        max_core_surface_delta_c=max(0.0, max_core_temperature_c - coolant_temperature_c),
    )


def _solve_multi_node_thermal_network(
    *,
    cells: Sequence[BatteryThermalPoseLike],
    cell_count: int,
    per_cell_heat_w: float,
    cooling_coefficient_w_per_m2k: float,
    passive_cooling_w_per_k: float,
    ambient_temperature_c: float,
    thermal_priors: BatteryThermalPriors,
    thermal_neighbor_clearance_mm: float,
    thermal_contact_decay_mm: float,
    thermal_contact_resistance_k_per_w: float,
    thermal_flow_shadowing_factor: float,
    thermal_airflow_axis: str,
) -> BatteryThermalNetworkResult:
    """Return the shared multi-node thermal-network solution."""
    node_count = (2 * cell_count) + 1
    matrix = numpy.zeros((node_count, node_count), dtype=float)
    vector = numpy.zeros(node_count, dtype=float)
    coolant_index = 2 * cell_count
    thermal_contact = _pairwise_contact_conductances(
        cells,
        thermal_neighbor_clearance_mm=thermal_neighbor_clearance_mm,
        thermal_contact_decay_mm=thermal_contact_decay_mm,
        thermal_contact_resistance_k_per_w=thermal_contact_resistance_k_per_w,
    )
    shadow_factors = _airflow_shadow_factors(
        cells,
        thermal_airflow_axis=thermal_airflow_axis,
        thermal_flow_shadowing_factor=thermal_flow_shadowing_factor,
    )
    core_surface_conductance = max(2.0 * thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9)
    base_surface_coolant_conductance = max(2.0 * thermal_priors.cell_to_jig_conductance_w_per_k, 1.0e-9)
    cell_radius_m = (CELL_SPEC_18650.diameter_mm / 2.0) * 1.0e-3
    cell_length_m = CELL_SPEC_18650.length_mm * 1.0e-3
    single_cell_surface_area_m2 = (2.0 * math.pi * cell_radius_m * cell_length_m) + (2.0 * math.pi * (cell_radius_m**2))

    for cell_index in range(cell_count):
        core_index = cell_index
        surface_index = cell_count + cell_index
        matrix[core_index, core_index] += core_surface_conductance
        matrix[core_index, surface_index] -= core_surface_conductance
        vector[core_index] += per_cell_heat_w

        matrix[surface_index, core_index] -= core_surface_conductance
        matrix[surface_index, surface_index] += core_surface_conductance
        surface_coolant_conductance = base_surface_coolant_conductance + (
            max(cooling_coefficient_w_per_m2k, 0.0) * single_cell_surface_area_m2 * shadow_factors[cell_index]
        )
        matrix[surface_index, surface_index] += surface_coolant_conductance
        matrix[surface_index, coolant_index] -= surface_coolant_conductance
        matrix[coolant_index, coolant_index] += surface_coolant_conductance
        matrix[coolant_index, surface_index] -= surface_coolant_conductance

    for (first_index, second_index), conductance in thermal_contact.items():
        surface_first = cell_count + first_index
        surface_second = cell_count + second_index
        matrix[surface_first, surface_first] += conductance
        matrix[surface_second, surface_second] += conductance
        matrix[surface_first, surface_second] -= conductance
        matrix[surface_second, surface_first] -= conductance

    coolant_to_ambient = max(passive_cooling_w_per_k, 1.0e-9) + thermal_priors.jig_to_ambient_conductance_w_per_k
    matrix[coolant_index, coolant_index] += coolant_to_ambient
    vector[coolant_index] += coolant_to_ambient * ambient_temperature_c

    try:
        temperatures = numpy.linalg.solve(matrix, vector)
    except numpy.linalg.LinAlgError:
        temperatures = numpy.linalg.lstsq(matrix, vector, rcond=None)[0]

    core_temperatures = temperatures[:cell_count]
    surface_temperatures = temperatures[cell_count : 2 * cell_count]
    coolant_temperature = float(temperatures[coolant_index])
    core_surface_deltas = core_temperatures - surface_temperatures
    return BatteryThermalNetworkResult(
        max_core_temperature_c=float(numpy.max(core_temperatures)),
        max_surface_temperature_c=float(numpy.max(surface_temperatures)),
        coolant_temperature_c=coolant_temperature,
        max_core_surface_delta_c=max(0.0, float(numpy.max(core_surface_deltas))),
    )


def _airflow_shadow_factors(
    cells: Sequence[BatteryThermalPoseLike],
    *,
    thermal_airflow_axis: str,
    thermal_flow_shadowing_factor: float,
) -> list[float]:
    """Return the deterministic airflow shadow factors for one cell set."""
    if not cells:
        return []
    axis_accessor = {
        "x": lambda cell: float(cell.x_mm),
        "y": lambda cell: float(cell.y_mm),
        "z": lambda cell: float(cell.z_mm),
    }[thermal_airflow_axis]
    coordinates = [axis_accessor(cell) for cell in cells]
    minimum = min(coordinates)
    maximum = max(coordinates)
    span = max(maximum - minimum, 1.0e-9)
    factors: list[float] = []
    for coordinate in coordinates:
        position = (coordinate - minimum) / span
        factor = 1.0 - (thermal_flow_shadowing_factor * position)
        factors.append(float(max(0.1, min(1.0, factor))))
    return factors


def _pairwise_contact_conductances(
    cells: Sequence[BatteryThermalPoseLike],
    *,
    thermal_neighbor_clearance_mm: float,
    thermal_contact_decay_mm: float,
    thermal_contact_resistance_k_per_w: float,
) -> dict[tuple[int, int], float]:
    """Return the pairwise thermal contact conductances for one cell set."""
    conductances: dict[tuple[int, int], float] = {}
    for first_index in range(len(cells)):
        first = _thermal_cylinder_from_cell(cells[first_index])
        for second_index in range(first_index + 1, len(cells)):
            second = _thermal_cylinder_from_cell(cells[second_index])
            summary = min_distance_between_cylinders(first, second)
            clearance_mm = _thermal_interface_gap_mm(summary)
            if clearance_mm > thermal_neighbor_clearance_mm:
                continue
            coupling = (1.0 / thermal_contact_resistance_k_per_w) * math.exp(
                -max(clearance_mm, 0.0) / thermal_contact_decay_mm
            )
            if coupling <= 0.0:
                continue
            conductances[(first_index, second_index)] = float(coupling)
    return conductances


__all__ = [
    "DEFAULT_AMBIENT_TEMPERATURE_C",
    "DEFAULT_COOLING_COEFFICIENT",
    "DEFAULT_PASSIVE_COOLING",
    "DEFAULT_THERMAL_AIRFLOW_AXIS",
    "DEFAULT_THERMAL_CONTACT_DECAY_MM",
    "DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W",
    "DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR",
    "DEFAULT_THERMAL_MODEL",
    "DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM",
    "DEFAULT_THERMAL_REFERENCE_SOC",
    "THERMAL_MODEL_LUMPED",
    "THERMAL_MODEL_MULTI_NODE",
    "BatteryEvaluationAdapterOutcome",
    "BatteryThermalNetworkResult",
    "BatteryThermalPose",
    "BatteryThermalPromotionConfig",
    "build_upright_thermal_poses_from_grid_cells",
    "coerce_battery_thermal_airflow_axis",
    "coerce_battery_thermal_model",
    "evaluate_explicit_netlist_state",
    "evaluate_rectangular_battery_state",
    "infer_parallel_equivalent_from_cell_current",
    "minimum_clearance_mm_from_grid_cells",
    "promoted_hybrid_defaults_payload",
    "resolved_backend_field_names",
    "solve_battery_thermal_network",
]
