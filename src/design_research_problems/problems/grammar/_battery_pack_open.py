"""Open-ended explicit-circuit battery-pack grammar problem."""

from __future__ import annotations

from dataclasses import dataclass

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems.grammar._battery_circuit import (
    BatteryCellInstance,
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    BatteryConnection,
    next_connection_id,
    next_terminal_id,
    sort_battery_cells,
    sort_battery_connections,
    terminal_ids,
)
from design_research_problems.problems.grammar._battery_layout import (
    DEFAULT_INTERCONNECT_RESISTANCE_OHM,
    BatteryRequirements,
    candidate_frontier_coordinates_from_cells,
    coordinate_is_in_bounds,
    occupied_coordinates,
)
from design_research_problems.problems.grammar._battery_pack_sp import MoveCell
from design_research_problems.problems.grammar._battery_problem_base import (
    BatteryCircuitProblemBase,
    _coerce_int,
    parse_battery_requirements,
)


@dataclass(frozen=True)
class AddCell:
    """Add one new connected cell at one free physical coordinate."""

    x: int
    """New grid x-coordinate."""
    y: int
    """New grid y-coordinate."""
    z: int
    """New grid z-coordinate."""
    connect_negative_to_terminal_id: int | None = None
    """Existing terminal to connect to the new negative lead, when explicit."""
    connect_positive_to_terminal_id: int | None = None
    """Existing terminal to connect to the new positive lead, when explicit."""
    use_negative_as_pack_terminal: bool = False
    """Whether the new negative lead replaces the pack negative terminal."""
    use_positive_as_pack_terminal: bool = False
    """Whether the new positive lead replaces the pack positive terminal."""


@dataclass(frozen=True)
class RemoveCell:
    """Remove one existing cell and any incident interconnects."""

    cell_id: int
    """Stable identifier of the cell to remove."""


@dataclass(frozen=True)
class AddConnection:
    """Add one interconnect between two existing terminals."""

    from_terminal_id: int
    """One endpoint terminal identifier."""
    to_terminal_id: int
    """The other endpoint terminal identifier."""


@dataclass(frozen=True)
class RemoveConnection:
    """Remove one existing interconnect."""

    connection_id: int
    """Stable identifier of the connection to remove."""


@dataclass(frozen=True)
class SetPackTerminals:
    """Select the explicit output terminals for the pack."""

    positive_terminal_id: int
    """Pack positive output terminal."""
    negative_terminal_id: int
    """Pack negative output terminal."""


def _coerce_state(state: object) -> BatteryCircuitState:
    """Validate and return the typed explicit battery state."""
    if not isinstance(state, BatteryCircuitState):
        raise TypeError("Expected a BatteryCircuitState.")
    return state


def _connection_pair_key(from_terminal_id: int, to_terminal_id: int) -> tuple[int, int]:
    """Return a canonical unordered terminal-pair key."""
    return (
        (from_terminal_id, to_terminal_id) if from_terminal_id <= to_terminal_id else (to_terminal_id, from_terminal_id)
    )


def _next_cell_id(cells: tuple[BatteryCellInstance, ...]) -> int:
    """Return the next stable cell identifier."""
    next_id = 0
    for cell in cells:
        next_id = max(next_id, cell.cell_id + 1)
    return next_id


class BatteryPack18650OpenEndedProblem(BatteryCircuitProblemBase):
    """Open-ended 18650 battery grammar with explicit cells and interconnects."""

    def __init__(
        self,
        *,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 16,
    ) -> None:
        """Store the shared requirements and open-ended cell-count bound."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
        )
        self.max_cell_count = max_cell_count

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryPack18650OpenEndedProblem:
        """Build the open-ended benchmark from packaged manifest parameters."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=_coerce_int(manifest.parameters.get("max_cell_count"), 16),
        )

    def initial_state(self) -> BatteryCircuitState:
        """Return a one-cell explicit-circuit starting state."""
        return BatteryCircuitState(
            cells=(
                BatteryCellInstance(
                    cell_id=0,
                    positive_terminal_id=1,
                    negative_terminal_id=0,
                    x=0,
                    y=0,
                    z=0,
                ),
            ),
            connections=(),
            pack_positive_terminal_id=1,
            pack_negative_terminal_id=0,
        )

    def enumerate_actions(self, state: object) -> tuple[object, ...]:
        """Return deterministic open-ended cell, wire, and terminal actions."""
        typed_state = _coerce_state(state)
        actions: list[object] = []
        frontier = candidate_frontier_coordinates_from_cells(typed_state.cells, self.requirements)
        occupied = occupied_coordinates(typed_state.cells)

        if len(typed_state.cells) < self.max_cell_count:
            for coordinate in frontier:
                actions.append(AddCell(x=coordinate[0], y=coordinate[1], z=coordinate[2]))
                actions.append(
                    AddCell(
                        x=coordinate[0],
                        y=coordinate[1],
                        z=coordinate[2],
                        connect_negative_to_terminal_id=typed_state.pack_positive_terminal_id,
                        use_positive_as_pack_terminal=True,
                    )
                )
                actions.append(
                    AddCell(
                        x=coordinate[0],
                        y=coordinate[1],
                        z=coordinate[2],
                        connect_positive_to_terminal_id=typed_state.pack_negative_terminal_id,
                        use_negative_as_pack_terminal=True,
                    )
                )

        for cell in typed_state.cells:
            current_coordinate = (cell.x, cell.y, cell.z)
            if len(typed_state.cells) > 1:
                actions.append(RemoveCell(cell_id=cell.cell_id))
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

        direct_pairs = {
            _connection_pair_key(connection.from_terminal_id, connection.to_terminal_id)
            for connection in typed_state.connections
        }
        ids = terminal_ids(typed_state)
        for first_index, first_terminal_id in enumerate(ids):
            for second_terminal_id in ids[first_index + 1 :]:
                if _connection_pair_key(first_terminal_id, second_terminal_id) in direct_pairs:
                    continue
                actions.append(
                    AddConnection(
                        from_terminal_id=first_terminal_id,
                        to_terminal_id=second_terminal_id,
                    )
                )

        for connection in typed_state.connections:
            actions.append(RemoveConnection(connection_id=connection.connection_id))

        for positive_terminal_id in ids:
            for negative_terminal_id in ids:
                if positive_terminal_id == negative_terminal_id:
                    continue
                actions.append(
                    SetPackTerminals(
                        positive_terminal_id=positive_terminal_id,
                        negative_terminal_id=negative_terminal_id,
                    )
                )

        return tuple(actions)

    def apply_action(self, state: object, action: object) -> BatteryCircuitState:
        """Apply one explicit-circuit action and return the new state."""
        typed_state = _coerce_state(state)
        cells = list(typed_state.cells)
        connections = list(typed_state.connections)

        if isinstance(action, AddCell):
            coordinate = (action.x, action.y, action.z)
            if len(cells) >= self.max_cell_count:
                raise ValueError("Cannot exceed the configured maximum cell count.")
            if not coordinate_is_in_bounds(coordinate, self.requirements):
                raise ValueError("AddCell target lies outside the legal battery grid.")
            if coordinate in occupied_coordinates(cells):
                raise ValueError("AddCell target is already occupied.")
            if action.use_negative_as_pack_terminal and action.use_positive_as_pack_terminal:
                raise ValueError("AddCell cannot replace both pack terminals at once.")

            terminal_id_set = set(terminal_ids(typed_state))
            connect_negative_to_terminal_id = action.connect_negative_to_terminal_id
            connect_positive_to_terminal_id = action.connect_positive_to_terminal_id

            if connect_negative_to_terminal_id is None and not action.use_negative_as_pack_terminal:
                connect_negative_to_terminal_id = typed_state.pack_negative_terminal_id
            if connect_positive_to_terminal_id is None and not action.use_positive_as_pack_terminal:
                connect_positive_to_terminal_id = typed_state.pack_positive_terminal_id

            if (connect_negative_to_terminal_id is not None and action.use_negative_as_pack_terminal) or (
                connect_positive_to_terminal_id is not None and action.use_positive_as_pack_terminal
            ):
                raise ValueError("Each AddCell lead can either connect to the circuit or become a pack terminal.")

            if connect_negative_to_terminal_id is None and connect_positive_to_terminal_id is None:
                raise ValueError("AddCell must connect at least one new lead to the existing circuit.")

            if (
                connect_negative_to_terminal_id is not None and connect_negative_to_terminal_id not in terminal_id_set
            ) or (
                connect_positive_to_terminal_id is not None and connect_positive_to_terminal_id not in terminal_id_set
            ):
                raise ValueError("AddCell must reference existing terminal ids.")

            if (
                connect_negative_to_terminal_id is not None
                and connect_positive_to_terminal_id is not None
                and connect_negative_to_terminal_id == connect_positive_to_terminal_id
            ):
                raise ValueError("AddCell cannot connect both new leads to the same terminal.")

            next_terminal = next_terminal_id(cells)
            new_negative_terminal_id = next_terminal
            new_positive_terminal_id = next_terminal + 1
            cells.append(
                BatteryCellInstance(
                    cell_id=_next_cell_id(typed_state.cells),
                    positive_terminal_id=new_positive_terminal_id,
                    negative_terminal_id=new_negative_terminal_id,
                    x=action.x,
                    y=action.y,
                    z=action.z,
                )
            )
            if connect_negative_to_terminal_id is not None:
                negative_pair = _connection_pair_key(connect_negative_to_terminal_id, new_negative_terminal_id)
                connections.append(
                    BatteryConnection(
                        connection_id=next_connection_id(connections),
                        from_terminal_id=negative_pair[0],
                        to_terminal_id=negative_pair[1],
                        resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                    )
                )
            if connect_positive_to_terminal_id is not None:
                positive_pair = _connection_pair_key(connect_positive_to_terminal_id, new_positive_terminal_id)
                connections.append(
                    BatteryConnection(
                        connection_id=next_connection_id(connections),
                        from_terminal_id=positive_pair[0],
                        to_terminal_id=positive_pair[1],
                        resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                    )
                )
            return BatteryCircuitState(
                cells=sort_battery_cells(cells),
                connections=sort_battery_connections(connections),
                pack_positive_terminal_id=(
                    new_positive_terminal_id
                    if action.use_positive_as_pack_terminal
                    else typed_state.pack_positive_terminal_id
                ),
                pack_negative_terminal_id=(
                    new_negative_terminal_id
                    if action.use_negative_as_pack_terminal
                    else typed_state.pack_negative_terminal_id
                ),
            )

        if isinstance(action, RemoveCell):
            if len(cells) <= 1:
                raise ValueError("Cannot remove the final battery cell.")
            removed_cell = None
            kept_cells: list[BatteryCellInstance] = []
            for cell in cells:
                if cell.cell_id == action.cell_id:
                    removed_cell = cell
                    continue
                kept_cells.append(cell)
            if removed_cell is None:
                raise ValueError(f"Unknown cell_id: {action.cell_id}")
            removed_terminal_ids = {removed_cell.negative_terminal_id, removed_cell.positive_terminal_id}
            kept_connections = [
                connection
                for connection in connections
                if connection.from_terminal_id not in removed_terminal_ids
                and connection.to_terminal_id not in removed_terminal_ids
            ]
            sorted_cells = sort_battery_cells(kept_cells)
            default_cell = sorted_cells[0]
            pack_positive_terminal_id = typed_state.pack_positive_terminal_id
            pack_negative_terminal_id = typed_state.pack_negative_terminal_id
            if pack_positive_terminal_id in removed_terminal_ids:
                pack_positive_terminal_id = default_cell.positive_terminal_id
            if pack_negative_terminal_id in removed_terminal_ids:
                pack_negative_terminal_id = default_cell.negative_terminal_id
            return BatteryCircuitState(
                cells=sorted_cells,
                connections=sort_battery_connections(kept_connections),
                pack_positive_terminal_id=pack_positive_terminal_id,
                pack_negative_terminal_id=pack_negative_terminal_id,
            )

        if isinstance(action, MoveCell):
            coordinate = (action.x, action.y, action.z)
            if not coordinate_is_in_bounds(coordinate, self.requirements):
                raise ValueError("Move target lies outside the legal battery grid.")
            replacement_index = None
            occupied = occupied_coordinates(cells)
            for index, cell in enumerate(cells):
                if cell.cell_id != action.cell_id:
                    continue
                replacement_index = index
                current_coordinate = (cell.x, cell.y, cell.z)
                if coordinate != current_coordinate and coordinate in occupied:
                    raise ValueError("Move target is already occupied.")
                cells[index] = BatteryCellInstance(
                    cell_id=cell.cell_id,
                    positive_terminal_id=cell.positive_terminal_id,
                    negative_terminal_id=cell.negative_terminal_id,
                    x=action.x,
                    y=action.y,
                    z=action.z,
                    cell_model_key=cell.cell_model_key,
                )
                break
            if replacement_index is None:
                raise ValueError(f"Unknown cell_id: {action.cell_id}")
            return BatteryCircuitState(
                cells=sort_battery_cells(cells),
                connections=sort_battery_connections(connections),
                pack_positive_terminal_id=typed_state.pack_positive_terminal_id,
                pack_negative_terminal_id=typed_state.pack_negative_terminal_id,
            )

        if isinstance(action, AddConnection):
            ids = set(terminal_ids(typed_state))
            if action.from_terminal_id == action.to_terminal_id:
                raise ValueError("Connections must join two distinct terminals.")
            if action.from_terminal_id not in ids or action.to_terminal_id not in ids:
                raise ValueError("Connections must reference existing terminals.")
            pair_key = _connection_pair_key(action.from_terminal_id, action.to_terminal_id)
            for connection in connections:
                if _connection_pair_key(connection.from_terminal_id, connection.to_terminal_id) == pair_key:
                    raise ValueError("Duplicate direct connections are not allowed.")
            connections.append(
                BatteryConnection(
                    connection_id=next_connection_id(connections),
                    from_terminal_id=pair_key[0],
                    to_terminal_id=pair_key[1],
                    resistance_ohm=DEFAULT_INTERCONNECT_RESISTANCE_OHM,
                )
            )
            return BatteryCircuitState(
                cells=sort_battery_cells(cells),
                connections=sort_battery_connections(connections),
                pack_positive_terminal_id=typed_state.pack_positive_terminal_id,
                pack_negative_terminal_id=typed_state.pack_negative_terminal_id,
            )

        if isinstance(action, RemoveConnection):
            kept_connections = [
                connection for connection in connections if connection.connection_id != action.connection_id
            ]
            if len(kept_connections) == len(connections):
                raise ValueError(f"Unknown connection_id: {action.connection_id}")
            return BatteryCircuitState(
                cells=sort_battery_cells(cells),
                connections=sort_battery_connections(kept_connections),
                pack_positive_terminal_id=typed_state.pack_positive_terminal_id,
                pack_negative_terminal_id=typed_state.pack_negative_terminal_id,
            )

        if isinstance(action, SetPackTerminals):
            ids = set(terminal_ids(typed_state))
            if action.positive_terminal_id == action.negative_terminal_id:
                raise ValueError("Pack positive and negative terminals must be distinct.")
            if action.positive_terminal_id not in ids or action.negative_terminal_id not in ids:
                raise ValueError("Pack terminals must reference existing terminals.")
            return BatteryCircuitState(
                cells=sort_battery_cells(cells),
                connections=sort_battery_connections(connections),
                pack_positive_terminal_id=action.positive_terminal_id,
                pack_negative_terminal_id=action.negative_terminal_id,
            )

        raise TypeError(f"Unsupported action type: {type(action).__name__}")

    def evaluate(self, state: object) -> BatteryCircuitEvaluation:
        """Evaluate one explicit open-ended battery circuit."""
        return self.evaluate_circuit_state(_coerce_state(state))


__all__ = [
    "AddCell",
    "AddConnection",
    "BatteryPack18650OpenEndedProblem",
    "RemoveCell",
    "RemoveConnection",
    "SetPackTerminals",
]
