"""Series-parallel battery-pack grammar problem."""

from __future__ import annotations

from itertools import combinations

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._domains.battery_core import (
    BatteryCellPlacement,
    candidate_frontier_coordinates,
    coordinate_is_in_bounds,
    next_cell_id,
    occupied_coordinates,
    sort_cell_placements,
)
from design_research_problems.problems._domains.battery_series_parallel import (
    SeriesParallelBatteryEvaluation,
    SeriesParallelBatteryState,
    evaluate_series_parallel_state,
)
from design_research_problems.problems._grammar import GrammarTransition
from design_research_problems.problems.grammar._battery_problem_base import (
    BatteryCircuitProblemBase,
    parse_battery_requirements,
)


def _sort_coordinate_key(coordinate: tuple[int, int, int]) -> tuple[int, int, int]:
    """Return the deterministic enumeration key for one coordinate.

    Args:
        coordinate: Value for ``coordinate``.

    Returns:
        Computed result for this callable.
    """
    x_value, y_value, z_value = coordinate
    return (z_value, y_value, x_value)


def _coerce_state(state: object) -> SeriesParallelBatteryState:
    """Validate and return the typed battery state.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    if not isinstance(state, SeriesParallelBatteryState):
        raise TypeError("Expected a SeriesParallelBatteryState.")
    return state


class BatteryPack18650SeriesParallelProblem(
    BatteryCircuitProblemBase[SeriesParallelBatteryState, SeriesParallelBatteryEvaluation]
):
    """Co-design grammar for a constrained 18650 series-parallel battery pack."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryPack18650SeriesParallelProblem:
        """Build the benchmark from packaged manifest parameters.

        Args:
            manifest: Value for ``manifest``.

        Returns:
            Computed result for this callable.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
        )

    def initial_state(self) -> SeriesParallelBatteryState:
        """Return a minimal valid 1S1P state.

        Returns:
            Computed result for this callable.
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

    def enumerate_transitions(
        self, state: SeriesParallelBatteryState
    ) -> tuple[GrammarTransition[SeriesParallelBatteryState], ...]:
        """Return deterministic move and group-edit transitions.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        typed_state = _coerce_state(state)
        transitions: list[GrammarTransition[SeriesParallelBatteryState]] = []
        frontier = candidate_frontier_coordinates(typed_state, self.requirements)
        occupied = occupied_coordinates(typed_state.cells)

        for cell in typed_state.cells:
            current_coordinate = (cell.x, cell.y, cell.z)
            for coordinate in frontier:
                if coordinate == current_coordinate:
                    continue
                if coordinate in occupied:
                    continue
                parameters = (
                    ("cell_id", cell.cell_id),
                    ("x", coordinate[0]),
                    ("y", coordinate[1]),
                    ("z", coordinate[2]),
                )
                transitions.append(
                    GrammarTransition(
                        rule_name="move_cell",
                        parameters=parameters,
                        next_state=self.move_cell(
                            typed_state,
                            cell_id=cell.cell_id,
                            x=coordinate[0],
                            y=coordinate[1],
                            z=coordinate[2],
                        ),
                    )
                )

        if len(frontier) >= typed_state.parallel_count:
            for combination in combinations(frontier, typed_state.parallel_count):
                ordered = tuple(sorted(combination, key=_sort_coordinate_key))
                transitions.append(
                    GrammarTransition(
                        rule_name="add_series_stage",
                        parameters=(("placements", ordered),),
                        next_state=self.add_series_stage(typed_state, placements=ordered),
                    )
                )

        if typed_state.series_count > 1:
            transitions.append(
                GrammarTransition(
                    rule_name="remove_series_stage",
                    parameters=(),
                    next_state=self.remove_series_stage(typed_state),
                )
            )

        if len(frontier) >= typed_state.series_count:
            for combination in combinations(frontier, typed_state.series_count):
                ordered = tuple(sorted(combination, key=_sort_coordinate_key))
                transitions.append(
                    GrammarTransition(
                        rule_name="add_parallel_branch",
                        parameters=(("placements", ordered),),
                        next_state=self.add_parallel_branch(typed_state, placements=ordered),
                    )
                )

        if typed_state.parallel_count > 1:
            transitions.append(
                GrammarTransition(
                    rule_name="remove_parallel_branch",
                    parameters=(),
                    next_state=self.remove_parallel_branch(typed_state),
                )
            )

        return tuple(transitions)

    def move_cell(
        self,
        state: SeriesParallelBatteryState,
        *,
        cell_id: int,
        x: int,
        y: int,
        z: int,
    ) -> SeriesParallelBatteryState:
        """Move one existing cell to a new coordinate.

        Args:
            state: Value for ``state``.
            cell_id: Identifier for cell.
            x: Value for ``x``.
            y: Value for ``y``.
            z: Value for ``z``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        occupied = occupied_coordinates(typed_state.cells)
        target_coordinate = (x, y, z)
        if not coordinate_is_in_bounds(target_coordinate, self.requirements):
            raise ValueError("Move target lies outside the legal battery grid.")
        replacement_index = None
        for index, cell in enumerate(cells):
            if cell.cell_id == cell_id:
                replacement_index = index
                current_coordinate = (cell.x, cell.y, cell.z)
                if target_coordinate != current_coordinate and target_coordinate in occupied:
                    raise ValueError("Move target is already occupied.")
                cells[index] = BatteryCellPlacement(
                    cell_id=cell.cell_id,
                    stage_index=cell.stage_index,
                    branch_index=cell.branch_index,
                    x=x,
                    y=y,
                    z=z,
                )
                break
        if replacement_index is None:
            raise ValueError(f"Unknown cell_id: {cell_id}")
        return SeriesParallelBatteryState(
            series_count=typed_state.series_count,
            parallel_count=typed_state.parallel_count,
            cells=sort_cell_placements(cells),
        )

    def add_series_stage(
        self,
        state: SeriesParallelBatteryState,
        *,
        placements: tuple[tuple[int, int, int], ...],
    ) -> SeriesParallelBatteryState:
        """Append one new series stage using one placement per branch.

        Args:
            state: Value for ``state``.
            placements: Value for ``placements``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        if len(placements) != typed_state.parallel_count:
            raise ValueError("AddSeriesStage must include one placement per parallel branch.")
        self._validate_new_placements(typed_state, placements)
        next_id = next_cell_id(typed_state.cells)
        for branch_index, placement in enumerate(placements):
            cells.append(
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
            cells=sort_cell_placements(cells),
        )

    def remove_series_stage(self, state: SeriesParallelBatteryState) -> SeriesParallelBatteryState:
        """Remove the final series stage.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        if typed_state.series_count <= 1:
            raise ValueError("Cannot remove the final series stage.")
        kept_cells = [cell for cell in cells if cell.stage_index != (typed_state.series_count - 1)]
        return SeriesParallelBatteryState(
            series_count=typed_state.series_count - 1,
            parallel_count=typed_state.parallel_count,
            cells=sort_cell_placements(kept_cells),
        )

    def add_parallel_branch(
        self,
        state: SeriesParallelBatteryState,
        *,
        placements: tuple[tuple[int, int, int], ...],
    ) -> SeriesParallelBatteryState:
        """Append one new parallel branch using one placement per stage.

        Args:
            state: Value for ``state``.
            placements: Value for ``placements``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        if len(placements) != typed_state.series_count:
            raise ValueError("AddParallelBranch must include one placement per series stage.")
        self._validate_new_placements(typed_state, placements)
        next_id = next_cell_id(typed_state.cells)
        for stage_index, placement in enumerate(placements):
            cells.append(
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
            cells=sort_cell_placements(cells),
        )

    def remove_parallel_branch(self, state: SeriesParallelBatteryState) -> SeriesParallelBatteryState:
        """Remove the final parallel branch.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        if typed_state.parallel_count <= 1:
            raise ValueError("Cannot remove the final parallel branch.")
        kept_cells = [cell for cell in cells if cell.branch_index != (typed_state.parallel_count - 1)]
        return SeriesParallelBatteryState(
            series_count=typed_state.series_count,
            parallel_count=typed_state.parallel_count - 1,
            cells=sort_cell_placements(kept_cells),
        )

    def _validate_new_placements(
        self,
        state: SeriesParallelBatteryState,
        placements: tuple[tuple[int, int, int], ...],
    ) -> None:
        """Validate coordinates used by one grouped add action.

        Args:
            state: Value for ``state``.
            placements: Value for ``placements``.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
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
        """Evaluate one battery-pack state using deterministic checks and the shared circuit backend.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        typed_state = _coerce_state(state)
        return evaluate_series_parallel_state(
            typed_state,
            self.requirements,
            self.evaluate_circuit_state,
        )


__all__ = [
    "BatteryPack18650SeriesParallelProblem",
    "SeriesParallelBatteryEvaluation",
    "SeriesParallelBatteryState",
]
