"""Shared backend helpers for rectangular series-parallel battery packs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from design_research_problems.problems._domains.battery_circuit import (
    BatteryCellInstance,
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    BatteryConnection,
    analyze_battery_topology,
)
from design_research_problems.problems._domains.battery_core import (
    BatteryCellPlacement,
    BatteryMetricSummary,
    BatteryRequirements,
    compute_metric_summary,
    coordinate_is_in_bounds,
    sort_cell_placements,
    validate_rectangular_topology,
)
from design_research_problems.problems._domains.battery_layout import DEFAULT_INTERCONNECT_RESISTANCE_OHM


@dataclass(frozen=True)
class SeriesParallelBatteryState:
    """Serializable state for one rectangular series-parallel pack."""

    series_count: int
    """Number of series stages in the pack."""
    parallel_count: int
    """Number of parallel branches in the pack."""
    cells: tuple[BatteryCellPlacement, ...]
    """Complete ordered set of cell placements."""


@dataclass(frozen=True)
class SeriesParallelBatteryEvaluation:
    """Structured evaluation for the series-parallel battery backend."""

    series_count: int
    """Evaluated series-stage count."""
    parallel_count: int
    """Evaluated parallel-branch count."""
    cell_count: int
    """Evaluated physical cell count."""
    design_width: float
    """Computed pack width in millimeters."""
    design_depth: float
    """Computed pack depth in millimeters."""
    design_height: float
    """Computed pack height in millimeters."""
    design_cost: float
    """Estimated pack cost in US dollars."""
    design_volume: float
    """Computed pack volume in cubic millimeters."""
    surface_area: float
    """Computed pack surface area in square millimeters."""
    moment_of_inertia_xx: float
    """Moment of inertia about the x-axis."""
    moment_of_inertia_yy: float
    """Moment of inertia about the y-axis."""
    moment_of_inertia_zz: float
    """Moment of inertia about the z-axis."""
    design_voltage: float
    """Idealized nominal pack voltage in volts."""
    design_capacity: float
    """Idealized nominal pack capacity in amp-hours."""
    analytic_current_limit: float
    """Coarse analytic current limit in amps."""
    pybamm_ran: bool
    """Legacy flag tracking whether the post-validation cell-model path executed."""
    pybamm_pack_end_voltage: float | None
    """Pack end voltage inferred from the shared solver, when available."""
    pybamm_delivered_capacity_ah: float | None
    """Delivered pack capacity inferred from the shared solver, when available."""
    pybamm_feasible: bool
    """Whether the shared circuit backend accepted the state."""
    is_feasible: bool
    """Overall feasibility after deterministic and simulated checks."""
    failure_reason: str | None = None
    """Human-readable infeasibility reason, when present."""
    cell_model_source: str | None = None
    """Exact source of the effective single-cell surrogate when the path ran."""
    cell_model_warning: str | None = None
    """Non-fatal warning reported while building the effective surrogate."""


def build_canonical_series_parallel_state(
    series_count: int,
    parallel_count: int,
    *,
    z_layer: int = 0,
) -> SeriesParallelBatteryState:
    """Build the deterministic rectangular state for one ``S x P`` battery pack."""
    cells = tuple(
        BatteryCellPlacement(
            cell_id=(
                stage_index
                if branch_index == 0
                else series_count + ((branch_index - 1) * series_count) + stage_index
            ),
            stage_index=stage_index,
            branch_index=branch_index,
            x=stage_index,
            y=branch_index,
            z=z_layer,
        )
        for stage_index in range(series_count)
        for branch_index in range(parallel_count)
    )
    return SeriesParallelBatteryState(
        series_count=series_count,
        parallel_count=parallel_count,
        cells=sort_cell_placements(cells),
    )


def build_circuit_state_from_series_parallel(state: SeriesParallelBatteryState) -> BatteryCircuitState:
    """Translate a rectangular ``S x P`` state into the shared explicit-circuit representation."""
    ordered_cells = sorted(state.cells, key=lambda cell: (cell.stage_index, cell.branch_index, cell.cell_id))
    circuit_cells: list[BatteryCellInstance] = []
    bus_members: list[list[int]] = [[] for _ in range(state.series_count + 1)]
    next_terminal_id_value = 0
    for cell in ordered_cells:
        negative_terminal_id = next_terminal_id_value
        positive_terminal_id = next_terminal_id_value + 1
        next_terminal_id_value += 2
        circuit_cells.append(
            BatteryCellInstance(
                cell_id=cell.cell_id,
                positive_terminal_id=positive_terminal_id,
                negative_terminal_id=negative_terminal_id,
                x=cell.x,
                y=cell.y,
                z=cell.z,
            )
        )
        bus_members[cell.stage_index].append(negative_terminal_id)
        bus_members[cell.stage_index + 1].append(positive_terminal_id)

    connections: list[BatteryConnection] = []
    next_connection_id_value = 0
    for members in bus_members:
        if not members:
            continue
        anchor = members[0]
        for member in members[1:]:
            connections.append(
                BatteryConnection(
                    connection_id=next_connection_id_value,
                    from_terminal_id=anchor,
                    to_terminal_id=member,
                    resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                )
            )
            next_connection_id_value += 1

    return BatteryCircuitState(
        cells=tuple(circuit_cells),
        connections=tuple(connections),
        pack_positive_terminal_id=bus_members[-1][0],
        pack_negative_terminal_id=bus_members[0][0],
    )


def evaluation_from_summary(
    state: SeriesParallelBatteryState,
    summary: BatteryMetricSummary,
    *,
    pybamm_ran: bool,
    pybamm_pack_end_voltage: float | None,
    pybamm_delivered_capacity_ah: float | None,
    pybamm_feasible: bool,
    is_feasible: bool,
    failure_reason: str | None,
    cell_model_source: str | None = None,
    cell_model_warning: str | None = None,
) -> SeriesParallelBatteryEvaluation:
    """Build one structured evaluation object from computed summary metrics."""
    return SeriesParallelBatteryEvaluation(
        series_count=state.series_count,
        parallel_count=state.parallel_count,
        cell_count=summary.cell_count,
        design_width=summary.design_width,
        design_depth=summary.design_depth,
        design_height=summary.design_height,
        design_cost=summary.design_cost,
        design_volume=summary.design_volume,
        surface_area=summary.surface_area,
        moment_of_inertia_xx=summary.moment_of_inertia_xx,
        moment_of_inertia_yy=summary.moment_of_inertia_yy,
        moment_of_inertia_zz=summary.moment_of_inertia_zz,
        design_voltage=summary.design_voltage,
        design_capacity=summary.design_capacity,
        analytic_current_limit=summary.analytic_current_limit,
        pybamm_ran=pybamm_ran,
        pybamm_pack_end_voltage=pybamm_pack_end_voltage,
        pybamm_delivered_capacity_ah=pybamm_delivered_capacity_ah,
        pybamm_feasible=pybamm_feasible,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        cell_model_source=cell_model_source,
        cell_model_warning=cell_model_warning,
    )


def evaluate_series_parallel_state(
    state: SeriesParallelBatteryState,
    requirements: BatteryRequirements,
    evaluate_circuit_state: Callable[[BatteryCircuitState], BatteryCircuitEvaluation],
) -> SeriesParallelBatteryEvaluation:
    """Evaluate one rectangular ``S x P`` battery pack using the shared circuit backend."""
    summary = compute_metric_summary(state, requirements)
    topology_failure = validate_rectangular_topology(state)
    if topology_failure is not None:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason=topology_failure,
        )

    coordinates = [(cell.x, cell.y, cell.z) for cell in state.cells]
    if len(set(coordinates)) != len(coordinates):
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Duplicate physical coordinates are not allowed.",
        )

    for coordinate in coordinates:
        if any(value < 0 for value in coordinate):
            return evaluation_from_summary(
                state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Cell coordinates must be non-negative.",
            )
        if not coordinate_is_in_bounds(coordinate, requirements):
            return evaluation_from_summary(
                state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="A cell lies outside the legal grid envelope.",
            )

    if summary.design_width > requirements.max_width_mm:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Pack width exceeds the maximum allowed width.",
        )
    if summary.design_depth > requirements.max_depth_mm:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Pack depth exceeds the maximum allowed depth.",
        )
    if summary.design_height > requirements.max_height_mm:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Pack height exceeds the maximum allowed height.",
        )

    voltage_error = abs(summary.design_voltage - requirements.target_voltage_v)
    if voltage_error > requirements.voltage_tolerance_v:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Pack voltage does not match the required target voltage.",
        )

    if summary.design_capacity < requirements.minimum_capacity_ah:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Pack capacity is below the minimum required capacity.",
        )

    if summary.analytic_current_limit < requirements.minimum_current_a:
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Analytic current limit is below the required continuous current.",
        )

    circuit_state = build_circuit_state_from_series_parallel(state)
    translated_topology = analyze_battery_topology(circuit_state)
    if (
        translated_topology.topology_kind != "series_parallel"
        or translated_topology.series_count != state.series_count
        or translated_topology.parallel_count != state.parallel_count
    ):
        return evaluation_from_summary(
            state,
            summary,
            pybamm_ran=False,
            pybamm_pack_end_voltage=None,
            pybamm_delivered_capacity_ah=None,
            pybamm_feasible=False,
            is_feasible=False,
            failure_reason="Internal series-parallel translation did not preserve the rectangular topology.",
        )

    circuit_evaluation = evaluate_circuit_state(circuit_state)
    return evaluation_from_summary(
        state,
        summary,
        pybamm_ran=circuit_evaluation.pybamm_ran,
        pybamm_pack_end_voltage=circuit_evaluation.pack_terminal_voltage_end,
        pybamm_delivered_capacity_ah=circuit_evaluation.delivered_capacity_ah,
        pybamm_feasible=circuit_evaluation.is_feasible,
        is_feasible=circuit_evaluation.is_feasible,
        failure_reason=circuit_evaluation.failure_reason,
        cell_model_source=circuit_evaluation.cell_model_source,
        cell_model_warning=circuit_evaluation.cell_model_warning,
    )


def series_parallel_requirement_violation(
    evaluation: SeriesParallelBatteryEvaluation,
    requirements: BatteryRequirements,
) -> tuple[float, float]:
    """Return total and maximum requirement violation for one series-parallel evaluation."""
    components = [
        max(evaluation.design_width - requirements.max_width_mm, 0.0),
        max(evaluation.design_depth - requirements.max_depth_mm, 0.0),
        max(evaluation.design_height - requirements.max_height_mm, 0.0),
        max(abs(evaluation.design_voltage - requirements.target_voltage_v) - requirements.voltage_tolerance_v, 0.0),
        max(requirements.minimum_capacity_ah - evaluation.design_capacity, 0.0),
        max(requirements.minimum_current_a - evaluation.analytic_current_limit, 0.0),
        0.0 if evaluation.is_feasible else 1.0,
    ]
    return (float(sum(components)), float(max(components, default=0.0)))


__all__ = [
    "SeriesParallelBatteryEvaluation",
    "SeriesParallelBatteryState",
    "build_canonical_series_parallel_state",
    "build_circuit_state_from_series_parallel",
    "evaluate_series_parallel_state",
    "evaluation_from_summary",
    "series_parallel_requirement_violation",
]
