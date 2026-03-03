"""Series-parallel battery-pack grammar problem."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems.grammar._battery_circuit import (
    BatteryCellInstance,
    BatteryCircuitState,
    BatteryConnection,
    analyze_battery_topology,
)
from design_research_problems.problems.grammar._battery_core import (
    BatteryCellPlacement,
    BatteryMetricSummary,
    candidate_frontier_coordinates,
    compute_metric_summary,
    coordinate_is_in_bounds,
    next_cell_id,
    occupied_coordinates,
    sort_cell_placements,
    validate_rectangular_topology,
)
from design_research_problems.problems.grammar._battery_layout import DEFAULT_INTERCONNECT_RESISTANCE_OHM
from design_research_problems.problems.grammar._battery_problem_base import (
    BatteryCircuitProblemBase,
    parse_battery_requirements,
)


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
class MoveCell:
    """Move one existing physical cell to a new coordinate."""

    cell_id: int
    """Stable identifier of the cell to move."""
    x: int
    """New grid x-coordinate."""
    y: int
    """New grid y-coordinate."""
    z: int
    """New grid z-coordinate."""


@dataclass(frozen=True)
class AddSeriesStage:
    """Append one new series stage using one placement per existing branch."""

    placements: tuple[tuple[int, int, int], ...]
    """New coordinates for the appended stage, one per branch."""


@dataclass(frozen=True)
class RemoveSeriesStage:
    """Remove the final series stage."""


@dataclass(frozen=True)
class AddParallelBranch:
    """Append one new parallel branch using one placement per existing stage."""

    placements: tuple[tuple[int, int, int], ...]
    """New coordinates for the appended branch, one per stage."""


@dataclass(frozen=True)
class RemoveParallelBranch:
    """Remove the final parallel branch."""


@dataclass(frozen=True)
class SeriesParallelBatteryEvaluation:
    """Structured evaluation for the series-parallel battery grammar."""

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


def _sort_coordinate_key(coordinate: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the deterministic enumeration key for one coordinate."""
    x_value, y_value, z_value = coordinate
    return (z_value, y_value, x_value)


def _coerce_state(state: object) -> SeriesParallelBatteryState:
    """Validate and return the typed battery state."""
    if not isinstance(state, SeriesParallelBatteryState):
        raise TypeError("Expected a SeriesParallelBatteryState.")
    return state


def _evaluation_from_summary(
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
    """Build one structured evaluation object from computed metrics."""
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


def _build_circuit_state_from_series_parallel(state: SeriesParallelBatteryState) -> BatteryCircuitState:
    """Translate the rectangular SxP state into the shared explicit-circuit representation."""
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


class BatteryPack18650SeriesParallelProblem(BatteryCircuitProblemBase):
    """Co-design grammar for a constrained 18650 series-parallel battery pack."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryPack18650SeriesParallelProblem:
        """Build the benchmark from packaged manifest parameters."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
        )

    def initial_state(self) -> SeriesParallelBatteryState:
        """Return a minimal valid 1S1P state."""
        return SeriesParallelBatteryState(
            series_count=1,
            parallel_count=1,
            cells=(
                BatteryCellPlacement(
                    cell_id=0,
                    stage_index=0,
                    branch_index=0,
                    x=0,
                    y=0,
                    z=0,
                ),
            ),
        )

    def enumerate_actions(self, state: object) -> tuple[object, ...]:
        """Return deterministic move and group-edit actions."""
        typed_state = _coerce_state(state)
        actions: list[object] = []
        frontier = candidate_frontier_coordinates(typed_state, self.requirements)
        occupied = occupied_coordinates(typed_state.cells)

        for cell in typed_state.cells:
            current_coordinate = (cell.x, cell.y, cell.z)
            for coordinate in frontier:
                if coordinate == current_coordinate:
                    continue
                if coordinate in occupied:
                    continue
                actions.append(
                    MoveCell(
                        cell_id=cell.cell_id,
                        x=coordinate[0],
                        y=coordinate[1],
                        z=coordinate[2],
                    )
                )

        if len(frontier) >= typed_state.parallel_count:
            for combination in combinations(frontier, typed_state.parallel_count):
                ordered = tuple(sorted(combination, key=_sort_coordinate_key))
                actions.append(AddSeriesStage(placements=ordered))

        if typed_state.series_count > 1:
            actions.append(RemoveSeriesStage())

        if len(frontier) >= typed_state.series_count:
            for combination in combinations(frontier, typed_state.series_count):
                ordered = tuple(sorted(combination, key=_sort_coordinate_key))
                actions.append(AddParallelBranch(placements=ordered))

        if typed_state.parallel_count > 1:
            actions.append(RemoveParallelBranch())

        return tuple(actions)

    def apply_action(self, state: object, action: object) -> SeriesParallelBatteryState:
        """Apply one move or group-edit action and return the new state."""
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        occupied = occupied_coordinates(typed_state.cells)

        if isinstance(action, MoveCell):
            target_coordinate = (action.x, action.y, action.z)
            if not coordinate_is_in_bounds(target_coordinate, self.requirements):
                raise ValueError("Move target lies outside the legal battery grid.")
            replacement_index = None
            for index, cell in enumerate(cells):
                if cell.cell_id == action.cell_id:
                    replacement_index = index
                    current_coordinate = (cell.x, cell.y, cell.z)
                    if target_coordinate != current_coordinate and target_coordinate in occupied:
                        raise ValueError("Move target is already occupied.")
                    cells[index] = BatteryCellPlacement(
                        cell_id=cell.cell_id,
                        stage_index=cell.stage_index,
                        branch_index=cell.branch_index,
                        x=action.x,
                        y=action.y,
                        z=action.z,
                    )
                    break
            if replacement_index is None:
                raise ValueError(f"Unknown cell_id: {action.cell_id}")
            return SeriesParallelBatteryState(
                series_count=typed_state.series_count,
                parallel_count=typed_state.parallel_count,
                cells=sort_cell_placements(cells),
            )

        if isinstance(action, AddSeriesStage):
            if len(action.placements) != typed_state.parallel_count:
                raise ValueError("AddSeriesStage must include one placement per parallel branch.")
            self._validate_new_placements(typed_state, action.placements)
            new_cells = list(cells)
            next_id = next_cell_id(typed_state.cells)
            for branch_index, placement in enumerate(action.placements):
                new_cells.append(
                    BatteryCellPlacement(
                        cell_id=next_id,
                        stage_index=typed_state.series_count,
                        branch_index=branch_index,
                        x=placement[0],
                        y=placement[1],
                        z=placement[2],
                    )
                )
                next_id += 1
            return SeriesParallelBatteryState(
                series_count=typed_state.series_count + 1,
                parallel_count=typed_state.parallel_count,
                cells=sort_cell_placements(new_cells),
            )

        if isinstance(action, RemoveSeriesStage):
            if typed_state.series_count <= 1:
                raise ValueError("Cannot remove the final series stage.")
            kept_cells = [cell for cell in cells if cell.stage_index != (typed_state.series_count - 1)]
            return SeriesParallelBatteryState(
                series_count=typed_state.series_count - 1,
                parallel_count=typed_state.parallel_count,
                cells=sort_cell_placements(kept_cells),
            )

        if isinstance(action, AddParallelBranch):
            if len(action.placements) != typed_state.series_count:
                raise ValueError("AddParallelBranch must include one placement per series stage.")
            self._validate_new_placements(typed_state, action.placements)
            new_cells = list(cells)
            next_id = next_cell_id(typed_state.cells)
            for stage_index, placement in enumerate(action.placements):
                new_cells.append(
                    BatteryCellPlacement(
                        cell_id=next_id,
                        stage_index=stage_index,
                        branch_index=typed_state.parallel_count,
                        x=placement[0],
                        y=placement[1],
                        z=placement[2],
                    )
                )
                next_id += 1
            return SeriesParallelBatteryState(
                series_count=typed_state.series_count,
                parallel_count=typed_state.parallel_count + 1,
                cells=sort_cell_placements(new_cells),
            )

        if isinstance(action, RemoveParallelBranch):
            if typed_state.parallel_count <= 1:
                raise ValueError("Cannot remove the final parallel branch.")
            kept_cells = [cell for cell in cells if cell.branch_index != (typed_state.parallel_count - 1)]
            return SeriesParallelBatteryState(
                series_count=typed_state.series_count,
                parallel_count=typed_state.parallel_count - 1,
                cells=sort_cell_placements(kept_cells),
            )

        raise TypeError(f"Unsupported action type: {type(action).__name__}")

    def _validate_new_placements(
        self,
        state: SeriesParallelBatteryState,
        placements: tuple[tuple[int, int, int], ...],
    ) -> None:
        """Validate coordinates used by one grouped add action."""
        if len(set(placements)) != len(placements):
            raise ValueError("Grouped placement coordinates must be unique.")
        occupied = occupied_coordinates(state.cells)
        for placement in placements:
            if not coordinate_is_in_bounds(placement, self.requirements):
                raise ValueError("Grouped placement lies outside the legal battery grid.")
            if placement in occupied:
                raise ValueError("Grouped placement collides with an occupied coordinate.")

    def evaluate(self, state: object) -> SeriesParallelBatteryEvaluation:
        """Evaluate one battery-pack state using deterministic checks and the shared circuit backend."""
        typed_state = _coerce_state(state)
        summary = compute_metric_summary(typed_state, self.requirements)
        topology_failure = validate_rectangular_topology(typed_state)
        if topology_failure is not None:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason=topology_failure,
            )

        coordinates = [(cell.x, cell.y, cell.z) for cell in typed_state.cells]
        if len(set(coordinates)) != len(coordinates):
            return _evaluation_from_summary(
                typed_state,
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
                return _evaluation_from_summary(
                    typed_state,
                    summary,
                    pybamm_ran=False,
                    pybamm_pack_end_voltage=None,
                    pybamm_delivered_capacity_ah=None,
                    pybamm_feasible=False,
                    is_feasible=False,
                    failure_reason="Cell coordinates must be non-negative.",
                )
            if not coordinate_is_in_bounds(coordinate, self.requirements):
                return _evaluation_from_summary(
                    typed_state,
                    summary,
                    pybamm_ran=False,
                    pybamm_pack_end_voltage=None,
                    pybamm_delivered_capacity_ah=None,
                    pybamm_feasible=False,
                    is_feasible=False,
                    failure_reason="A cell lies outside the legal grid envelope.",
                )

        if summary.design_width > self.requirements.max_width_mm:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Pack width exceeds the maximum allowed width.",
            )
        if summary.design_depth > self.requirements.max_depth_mm:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Pack depth exceeds the maximum allowed depth.",
            )
        if summary.design_height > self.requirements.max_height_mm:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Pack height exceeds the maximum allowed height.",
            )

        voltage_error = abs(summary.design_voltage - self.requirements.target_voltage_v)
        if voltage_error > self.requirements.voltage_tolerance_v:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Pack voltage does not match the required target voltage.",
            )

        if summary.design_capacity < self.requirements.minimum_capacity_ah:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Pack capacity is below the minimum required capacity.",
            )

        if summary.analytic_current_limit < self.requirements.minimum_current_a:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Analytic current limit is below the required continuous current.",
            )

        circuit_state = _build_circuit_state_from_series_parallel(typed_state)
        translated_topology = analyze_battery_topology(circuit_state)
        if (
            translated_topology.topology_kind != "series_parallel"
            or translated_topology.series_count != typed_state.series_count
            or translated_topology.parallel_count != typed_state.parallel_count
        ):
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=False,
                pybamm_pack_end_voltage=None,
                pybamm_delivered_capacity_ah=None,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="Internal series-parallel translation did not preserve the rectangular topology.",
            )

        circuit_evaluation = self.evaluate_circuit_state(circuit_state)
        return _evaluation_from_summary(
            typed_state,
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


__all__ = [
    "AddParallelBranch",
    "AddSeriesStage",
    "BatteryPack18650SeriesParallelProblem",
    "MoveCell",
    "RemoveParallelBranch",
    "RemoveSeriesStage",
    "SeriesParallelBatteryEvaluation",
    "SeriesParallelBatteryState",
]
