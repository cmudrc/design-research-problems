"""Series-parallel battery-pack grammar problem."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._grammar import GrammarProblem
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems.grammar._battery_core import (
    BatteryCellPlacement,
    BatteryMetricSummary,
    BatteryRequirements,
    candidate_frontier_coordinates,
    compute_metric_summary,
    coordinate_is_in_bounds,
    grid_index_limits,
    import_pybamm,
    next_cell_id,
    occupied_coordinates,
    simulate_series_parallel_pack,
    sort_cell_placements,
    validate_rectangular_topology,
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
    """Whether the PyBaMM adapter executed."""
    pybamm_pack_end_voltage: float | None
    """Pack end voltage inferred from PyBaMM, when available."""
    pybamm_delivered_capacity_ah: float | None
    """Delivered pack capacity inferred from PyBaMM, when available."""
    pybamm_feasible: bool
    """Whether the PyBaMM adapter accepted the state."""
    is_feasible: bool
    """Overall feasibility after deterministic and PyBaMM checks."""
    failure_reason: str | None = None
    """Human-readable infeasibility reason, when present."""


def _coerce_int(value: object, default: int) -> int:
    """Return an integer manifest value with a fallback default.

    Args:
        value: Raw manifest parameter value.
        default: Fallback integer value.

    Returns:
        Parsed integer value.
    """
    if value is None:
        return default
    return int(cast(int, value))


def _coerce_float(value: object, default: float) -> float:
    """Return a float manifest value with a fallback default.

    Args:
        value: Raw manifest parameter value.
        default: Fallback float value.

    Returns:
        Parsed float value.
    """
    if value is None:
        return default
    return float(cast(float, value))


def _sort_coordinate_key(coordinate: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the deterministic enumeration key for one coordinate.

    Args:
        coordinate: Grid coordinate to sort.

    Returns:
        Deterministic sort key.
    """
    x_value, y_value, z_value = coordinate
    return (z_value, y_value, x_value)


def _coerce_state(state: object) -> SeriesParallelBatteryState:
    """Validate and return the typed battery state.

    Args:
        state: Candidate grammar state.

    Returns:
        Typed battery state.

    Raises:
        TypeError: If ``state`` is not a battery state.
    """
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
) -> SeriesParallelBatteryEvaluation:
    """Build one structured evaluation object from computed metrics.

    Args:
        state: Battery pack state that was evaluated.
        summary: Deterministic metric summary for the state.
        pybamm_ran: Whether the PyBaMM adapter ran.
        pybamm_pack_end_voltage: Inferred pack end voltage from PyBaMM.
        pybamm_delivered_capacity_ah: Inferred delivered capacity from PyBaMM.
        pybamm_feasible: Whether the PyBaMM adapter accepted the state.
        is_feasible: Overall feasibility flag.
        failure_reason: Optional infeasibility reason.

    Returns:
        Structured evaluation result.
    """
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
    )


class BatteryPack18650SeriesParallelProblem(GrammarProblem):
    """Co-design grammar for a constrained 18650 series-parallel battery pack."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        requirements: BatteryRequirements | None = None,
    ) -> None:
        """Store the fixed benchmark requirements.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            requirements: Optional benchmark requirements override.
        """
        super().__init__(metadata=metadata, statement_markdown=statement_markdown)
        self.requirements = requirements or BatteryRequirements(
            target_voltage_v=14.8,
            minimum_capacity_ah=10.0,
            minimum_current_a=60.0,
            max_width_mm=500.0,
            max_depth_mm=500.0,
            max_height_mm=250.0,
            voltage_tolerance_v=0.1,
        )

    @classmethod
    def from_manifest(
        cls,
        manifest: ProblemManifest,
        statement_markdown: str,
    ) -> BatteryPack18650SeriesParallelProblem:
        """Build the benchmark from packaged manifest parameters.

        Args:
            manifest: Parsed packaged manifest.
            statement_markdown: Human-readable problem statement.

        Returns:
            Initialized battery grammar problem.
        """
        requirements = BatteryRequirements(
            target_voltage_v=_coerce_float(manifest.parameters.get("target_voltage_v"), 14.8),
            minimum_capacity_ah=_coerce_float(manifest.parameters.get("minimum_capacity_ah"), 10.0),
            minimum_current_a=_coerce_float(manifest.parameters.get("minimum_current_a"), 60.0),
            max_width_mm=_coerce_float(manifest.parameters.get("max_width_mm"), 500.0),
            max_depth_mm=_coerce_float(manifest.parameters.get("max_depth_mm"), 500.0),
            max_height_mm=_coerce_float(manifest.parameters.get("max_height_mm"), 250.0),
            voltage_tolerance_v=_coerce_float(manifest.parameters.get("voltage_tolerance_v"), 0.1),
        )
        return cls(
            metadata=manifest.metadata,
            statement_markdown=statement_markdown,
            requirements=requirements,
        )

    def initial_state(self) -> SeriesParallelBatteryState:
        """Return a minimal valid 1S1P state.

        Returns:
            Canonical starting battery state.
        """
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
        """Return deterministic move and group-edit actions.

        Args:
            state: Current grammar state.

        Returns:
            Available actions in deterministic order.
        """
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
        """Apply one move or group-edit action and return the new state.

        Args:
            state: Current grammar state.
            action: One action returned by :meth:`enumerate_actions`.

        Returns:
            Updated grammar state.

        Raises:
            TypeError: If the state or action type is unsupported.
            ValueError: If the action violates topology or placement rules.
        """
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
        """Validate coordinates used by one grouped add action.

        Args:
            state: Current grammar state.
            placements: Candidate coordinates for a grouped add.

        Raises:
            ValueError: If any placement is duplicated, out of bounds, or occupied.
        """
        if len(set(placements)) != len(placements):
            raise ValueError("Grouped placement coordinates must be unique.")
        occupied = occupied_coordinates(state.cells)
        for placement in placements:
            if not coordinate_is_in_bounds(placement, self.requirements):
                raise ValueError("Grouped placement lies outside the legal battery grid.")
            if placement in occupied:
                raise ValueError("Grouped placement collides with an occupied coordinate.")

    def evaluate(self, state: object) -> SeriesParallelBatteryEvaluation:
        """Evaluate one battery-pack state using deterministic checks and PyBaMM.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Structured battery evaluation result.
        """
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

        pybamm_module = import_pybamm()
        pack_end_voltage, delivered_capacity_ah, pybamm_feasible = simulate_series_parallel_pack(
            pybamm_module=pybamm_module,
            requirements=self.requirements,
            series_count=typed_state.series_count,
            parallel_count=typed_state.parallel_count,
        )
        if not pybamm_feasible:
            return _evaluation_from_summary(
                typed_state,
                summary,
                pybamm_ran=True,
                pybamm_pack_end_voltage=pack_end_voltage,
                pybamm_delivered_capacity_ah=delivered_capacity_ah,
                pybamm_feasible=False,
                is_feasible=False,
                failure_reason="PyBaMM did not confirm the required discharge performance.",
            )

        return _evaluation_from_summary(
            typed_state,
            summary,
            pybamm_ran=True,
            pybamm_pack_end_voltage=pack_end_voltage,
            pybamm_delivered_capacity_ah=delivered_capacity_ah,
            pybamm_feasible=True,
            is_feasible=True,
            failure_reason=None,
        )

    def legal_grid_shape(self) -> tuple[int, int, int]:
        """Return the maximum legal grid indices for this packaged benchmark.

        Returns:
            Maximum legal ``(x, y, z)`` grid indices.
        """
        return grid_index_limits(self.requirements)
