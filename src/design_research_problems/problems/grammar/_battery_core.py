"""Compatibility facade for shared battery helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from design_research_problems.problems._domains.battery_cell_model import (
    BatteryCellModel,
    import_pybamm,
    interpolate_cell_model,
    load_18650_cell_model,
)
from design_research_problems.problems._domains.battery_layout import (
    CELL_SPEC_18650,
    BatteryCellPlacement,
    BatteryCellSpec,
    BatteryLayoutSummary,
    BatteryRequirements,
    candidate_frontier_coordinates,
    candidate_frontier_coordinates_from_cells,
    compute_layout_summary,
    coordinate_is_in_bounds,
    coordinate_to_physical_mm,
    grid_index_limits,
    next_cell_id,
    occupied_coordinates,
    sort_cell_placements,
)


class SeriesParallelStateLike(Protocol):
    """Minimal state interface used by the legacy series-parallel helpers."""

    @property
    def series_count(self) -> int:
        """Return the series-stage count."""
        ...

    @property
    def parallel_count(self) -> int:
        """Return the parallel-branch count."""
        ...

    @property
    def cells(self) -> tuple[BatteryCellPlacement, ...]:
        """Return all battery cell placements."""
        ...


@dataclass(frozen=True)
class BatteryMetricSummary:
    """Legacy metric bundle retained for the constrained series-parallel problem."""

    cell_count: int
    """Total number of cells in the pack."""
    num_cells_width: int
    """Span of occupied x indices plus one."""
    num_cells_depth: int
    """Span of occupied y indices plus one."""
    num_cells_height: int
    """Span of occupied z indices plus one."""
    design_width: float
    """Computed pack width in millimeters."""
    design_depth: float
    """Computed pack depth in millimeters."""
    design_height: float
    """Computed pack height in millimeters."""
    design_cost: float
    """Estimated pack cost in US dollars."""
    surface_area: float
    """Bounding-box surface area in square millimeters."""
    design_volume: float
    """Bounding-box volume in cubic millimeters."""
    moment_of_inertia_xx: float
    """Pack moment of inertia about the x-axis."""
    moment_of_inertia_yy: float
    """Pack moment of inertia about the y-axis."""
    moment_of_inertia_zz: float
    """Pack moment of inertia about the z-axis."""
    design_voltage: float
    """Idealized pack voltage in volts."""
    design_capacity: float
    """Idealized pack capacity in amp-hours."""
    analytic_current_limit: float
    """Coarse analytic current limit in amps."""


def validate_rectangular_topology(state: SeriesParallelStateLike) -> str | None:
    """Return a failure reason when the state violates rectangular SxP topology."""
    if state.series_count < 1:
        return "Series count must be at least 1."
    if state.parallel_count < 1:
        return "Parallel count must be at least 1."
    if len(state.cells) != state.series_count * state.parallel_count:
        return "Cell count does not match the required SxP rectangle."
    expected_slots = {
        (stage_index, branch_index)
        for stage_index in range(state.series_count)
        for branch_index in range(state.parallel_count)
    }
    actual_slots = {(cell.stage_index, cell.branch_index) for cell in state.cells}
    if actual_slots != expected_slots:
        return "Cells do not fill the complete SxP slot rectangle."
    return None


def compute_metric_summary(
    state: SeriesParallelStateLike,
    requirements: BatteryRequirements,
) -> BatteryMetricSummary:
    """Compute deterministic legacy metrics for one rectangular series-parallel pack."""
    layout = compute_layout_summary(state.cells)
    design_voltage = float(state.series_count) * CELL_SPEC_18650.nominal_voltage_v
    design_capacity = float(state.parallel_count) * CELL_SPEC_18650.nominal_capacity_ah
    analytic_current_limit = compute_analytic_current_limit(layout, parallel_count=state.parallel_count)
    del requirements
    return BatteryMetricSummary(
        cell_count=layout.cell_count,
        num_cells_width=layout.num_cells_width,
        num_cells_depth=layout.num_cells_depth,
        num_cells_height=layout.num_cells_height,
        design_width=layout.design_width,
        design_depth=layout.design_depth,
        design_height=layout.design_height,
        design_cost=layout.design_cost,
        surface_area=layout.surface_area,
        design_volume=layout.design_volume,
        moment_of_inertia_xx=layout.moment_of_inertia_xx,
        moment_of_inertia_yy=layout.moment_of_inertia_yy,
        moment_of_inertia_zz=layout.moment_of_inertia_zz,
        design_voltage=design_voltage,
        design_capacity=design_capacity,
        analytic_current_limit=analytic_current_limit,
    )


def compute_analytic_current_limit(
    layout: BatteryLayoutSummary,
    *,
    parallel_count: int,
) -> float:
    """Return the legacy coarse thermal current estimate."""
    if layout.cell_count <= 0:
        return 0.0
    max_thermal = layout.surface_area * 1e-6 * 10000.0
    max_thermal_per_cell = max_thermal / float(layout.cell_count)
    sqrt_arg = max_thermal_per_cell / CELL_SPEC_18650.internal_resistance_ohm
    max_current_per_cell: float = float(max(0.0, sqrt_arg) ** 0.5)
    return max_current_per_cell * float(parallel_count)


def simulate_series_parallel_pack(
    pybamm_module: object,
    requirements: BatteryRequirements,
    series_count: int,
    parallel_count: int,
) -> tuple[float, float, bool]:
    """Compatibility wrapper that evaluates a canonical rectangular pack with the shared solver."""
    del pybamm_module
    from design_research_problems.problems._domains.battery_circuit import (
        BatteryCellInstance,
        BatteryCircuitState,
        BatteryConnection,
        evaluate_battery_circuit,
    )

    cells: list[BatteryCellInstance] = []
    connections: list[BatteryConnection] = []
    next_connection = 0
    next_terminal = 0
    bus_members: list[list[int]] = [[] for _ in range(series_count + 1)]
    for stage_index in range(series_count):
        for branch_index in range(parallel_count):
            negative_terminal_id = next_terminal
            positive_terminal_id = next_terminal + 1
            next_terminal += 2
            cells.append(
                BatteryCellInstance(
                    cell_id=len(cells),
                    negative_terminal_id=negative_terminal_id,
                    positive_terminal_id=positive_terminal_id,
                    x=stage_index,
                    y=branch_index,
                    z=0,
                )
            )
            bus_members[stage_index].append(negative_terminal_id)
            bus_members[stage_index + 1].append(positive_terminal_id)

    for members in bus_members:
        if not members:
            continue
        anchor = members[0]
        for member in members[1:]:
            connections.append(
                BatteryConnection(
                    connection_id=next_connection,
                    from_terminal_id=anchor,
                    to_terminal_id=member,
                )
            )
            next_connection += 1

    state = BatteryCircuitState(
        cells=tuple(cells),
        connections=tuple(connections),
        pack_negative_terminal_id=bus_members[0][0],
        pack_positive_terminal_id=bus_members[-1][0],
    )
    evaluation = evaluate_battery_circuit(
        state=state,
        requirements=requirements,
        load_cell_model=load_18650_cell_model,
    )
    return (
        0.0 if evaluation.pack_terminal_voltage_end is None else evaluation.pack_terminal_voltage_end,
        0.0 if evaluation.delivered_capacity_ah is None else evaluation.delivered_capacity_ah,
        evaluation.is_feasible,
    )


__all__ = [
    "CELL_SPEC_18650",
    "BatteryCellModel",
    "BatteryCellPlacement",
    "BatteryCellSpec",
    "BatteryLayoutSummary",
    "BatteryMetricSummary",
    "BatteryRequirements",
    "candidate_frontier_coordinates",
    "candidate_frontier_coordinates_from_cells",
    "compute_analytic_current_limit",
    "compute_layout_summary",
    "compute_metric_summary",
    "coordinate_is_in_bounds",
    "coordinate_to_physical_mm",
    "grid_index_limits",
    "import_pybamm",
    "interpolate_cell_model",
    "load_18650_cell_model",
    "next_cell_id",
    "occupied_coordinates",
    "simulate_series_parallel_pack",
    "sort_cell_placements",
    "validate_rectangular_topology",
]
