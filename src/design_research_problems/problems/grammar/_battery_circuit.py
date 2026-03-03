"""Shared explicit-circuit backend for battery grammar problems."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import ceil, exp

import numpy

from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel, interpolate_cell_model
from design_research_problems.problems.grammar._battery_layout import (
    CELL_SPEC_18650,
    DEFAULT_INTERCONNECT_RESISTANCE_OHM,
    BatteryLayoutSummary,
    BatteryRequirements,
    compute_layout_summary,
    coordinate_is_in_bounds,
)


@dataclass(frozen=True)
class BatteryCellInstance:
    """One physical cell with explicit electrical terminals and placement."""

    cell_id: int
    """Stable cell identifier."""
    positive_terminal_id: int
    """Stable positive terminal identifier."""
    negative_terminal_id: int
    """Stable negative terminal identifier."""
    x: int
    """Grid x-coordinate."""
    y: int
    """Grid y-coordinate."""
    z: int
    """Grid z-coordinate."""
    cell_model_key: str = "18650_default"
    """Logical key for the effective cell model."""


@dataclass(frozen=True)
class BatteryConnection:
    """One interconnect between two existing cell terminals."""

    connection_id: int
    """Stable connection identifier."""
    from_terminal_id: int
    """One endpoint terminal identifier."""
    to_terminal_id: int
    """The other endpoint terminal identifier."""
    resistance_ohm: float = DEFAULT_INTERCONNECT_RESISTANCE_OHM
    """Effective interconnect resistance."""


@dataclass(frozen=True)
class BatteryCircuitState:
    """Serializable explicit battery-circuit state."""

    cells: tuple[BatteryCellInstance, ...]
    """All physical cell instances."""
    connections: tuple[BatteryConnection, ...]
    """All explicit interconnects."""
    pack_positive_terminal_id: int
    """Positive pack output terminal."""
    pack_negative_terminal_id: int
    """Negative pack output terminal."""


@dataclass(frozen=True)
class BatteryTopologyAnalysis:
    """Topology analysis derived from a reduced explicit-circuit graph."""

    topology_kind: str
    """Either ``series_parallel`` or ``general``."""
    series_count: int | None
    """Detected series depth when the topology is rectangular."""
    parallel_count: int | None
    """Detected parallel branch count when the topology is rectangular."""
    minimum_series_cells: int | None
    """Shortest directed cell-path length from pack negative to pack positive."""


@dataclass(frozen=True)
class BatteryCircuitEvaluation:
    """Structured evaluation for the explicit battery-circuit grammar."""

    cell_count: int
    """Evaluated physical cell count."""
    connection_count: int
    """Evaluated interconnect count."""
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
    pack_nominal_voltage: float
    """Nominal pack voltage inferred from the reduced topology."""
    pack_terminal_voltage_end: float | None
    """Pack terminal voltage at the final simulated step."""
    delivered_capacity_ah: float | None
    """Delivered capacity before termination."""
    max_cell_current_a: float | None
    """Maximum observed absolute cell current."""
    min_cell_voltage_v: float | None
    """Minimum observed cell terminal voltage."""
    solver_steps: int
    """Number of simulation steps executed."""
    pybamm_ran: bool
    """Legacy flag tracking whether the post-validation cell-model path ran."""
    topology_kind: str
    """Reduced-topology classification label."""
    is_feasible: bool
    """Overall feasibility after deterministic and simulated checks."""
    failure_reason: str | None = None
    """Human-readable infeasibility reason, when present."""
    cell_model_source: str | None = None
    """Exact source of the effective single-cell surrogate when the path ran."""
    cell_model_warning: str | None = None
    """Non-fatal warning reported while building the effective surrogate."""


@dataclass(frozen=True)
class BatteryCircuitSimulationResult:
    """Internal simulation result used to build public evaluations."""

    pack_terminal_voltage_end: float
    delivered_capacity_ah: float
    max_cell_current_a: float
    min_cell_voltage_v: float
    solver_steps: int
    is_feasible: bool
    failure_reason: str | None


def sort_battery_cells(
    cells: tuple[BatteryCellInstance, ...] | list[BatteryCellInstance],
) -> tuple[BatteryCellInstance, ...]:
    """Return cells sorted deterministically by id and coordinate."""
    return tuple(
        sorted(
            cells,
            key=lambda cell: (
                cell.cell_id,
                cell.z,
                cell.y,
                cell.x,
                cell.negative_terminal_id,
                cell.positive_terminal_id,
            ),
        )
    )


def sort_battery_connections(
    connections: tuple[BatteryConnection, ...] | list[BatteryConnection],
) -> tuple[BatteryConnection, ...]:
    """Return connections sorted deterministically by id and endpoints."""
    return tuple(
        sorted(
            connections,
            key=lambda connection: (
                connection.connection_id,
                min(connection.from_terminal_id, connection.to_terminal_id),
                max(connection.from_terminal_id, connection.to_terminal_id),
            ),
        )
    )


def next_terminal_id(cells: Iterable[BatteryCellInstance]) -> int:
    """Return the next stable terminal identifier."""
    next_id = 0
    for cell in cells:
        next_id = max(next_id, cell.positive_terminal_id + 1, cell.negative_terminal_id + 1)
    return next_id


def next_connection_id(connections: Iterable[BatteryConnection]) -> int:
    """Return the next stable connection identifier."""
    next_id = 0
    for connection in connections:
        next_id = max(next_id, connection.connection_id + 1)
    return next_id


def terminal_ids(state: BatteryCircuitState) -> tuple[int, ...]:
    """Return all terminal identifiers in deterministic order."""
    ids = {
        terminal_id for cell in state.cells for terminal_id in (cell.negative_terminal_id, cell.positive_terminal_id)
    }
    return tuple(sorted(ids))


def _pair_key(first: int, second: int) -> tuple[int, int]:
    """Return the canonical unordered key for one terminal pair."""
    return (first, second) if first <= second else (second, first)


class _DisjointSet:
    """Minimal disjoint-set implementation for connection-net reduction."""

    def __init__(self, items: Iterable[int]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: int) -> int:
        """Return the representative for one item."""
        parent = self._parent[item]
        if parent != item:
            parent = self.find(parent)
            self._parent[item] = parent
        return parent

    def union(self, first: int, second: int) -> None:
        """Merge two representatives."""
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            self._parent[second_root] = first_root


def _build_connection_sets(state: BatteryCircuitState) -> tuple[_DisjointSet, dict[int, set[int]]]:
    """Return wire-equivalence classes and adjacency from explicit connections."""
    ids = terminal_ids(state)
    dsu = _DisjointSet(ids)
    adjacency: dict[int, set[int]] = {terminal_id: set() for terminal_id in ids}
    for connection in state.connections:
        adjacency[connection.from_terminal_id].add(connection.to_terminal_id)
        adjacency[connection.to_terminal_id].add(connection.from_terminal_id)
        dsu.union(connection.from_terminal_id, connection.to_terminal_id)
    return (dsu, adjacency)


def _reachable_nodes(
    adjacency: dict[int, set[int]],
    start: int,
) -> set[int]:
    """Return all nodes reachable from ``start``."""
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for neighbor in adjacency[node]:
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append(neighbor)
    return visited


def _full_graph_adjacency(
    state: BatteryCircuitState,
    *,
    skip_cell_id: int | None = None,
) -> dict[int, set[int]]:
    """Return undirected terminal adjacency including cells and interconnects."""
    adjacency: dict[int, set[int]] = {terminal_id: set() for terminal_id in terminal_ids(state)}
    for connection in state.connections:
        adjacency[connection.from_terminal_id].add(connection.to_terminal_id)
        adjacency[connection.to_terminal_id].add(connection.from_terminal_id)
    for cell in state.cells:
        if cell.cell_id == skip_cell_id:
            continue
        adjacency[cell.negative_terminal_id].add(cell.positive_terminal_id)
        adjacency[cell.positive_terminal_id].add(cell.negative_terminal_id)
    return adjacency


def _minimum_series_cells(
    state: BatteryCircuitState,
    dsu: _DisjointSet,
) -> int | None:
    """Return the shortest directed cell-path length from pack negative to pack positive."""
    start_net = dsu.find(state.pack_negative_terminal_id)
    target_net = dsu.find(state.pack_positive_terminal_id)
    reduced_adjacency: dict[int, set[int]] = defaultdict(set)
    for cell in state.cells:
        reduced_adjacency[dsu.find(cell.negative_terminal_id)].add(dsu.find(cell.positive_terminal_id))

    queue: deque[tuple[int, int]] = deque([(start_net, 0)])
    visited = {start_net}
    while queue:
        node, depth = queue.popleft()
        if node == target_net:
            return depth
        for neighbor in sorted(reduced_adjacency.get(node, ())):
            if neighbor in visited:
                continue
            visited.add(neighbor)
            queue.append((neighbor, depth + 1))
    return None


def analyze_battery_topology(state: BatteryCircuitState) -> BatteryTopologyAnalysis:
    """Classify the reduced circuit topology."""
    dsu, _ = _build_connection_sets(state)
    minimum_series_cells = _minimum_series_cells(state, dsu)
    if minimum_series_cells is None:
        return BatteryTopologyAnalysis(
            topology_kind="general",
            series_count=None,
            parallel_count=None,
            minimum_series_cells=None,
        )

    start_net = dsu.find(state.pack_negative_terminal_id)
    target_net = dsu.find(state.pack_positive_terminal_id)
    edges: list[tuple[int, int]] = []
    edge_nodes: set[int] = set()
    outgoing: dict[int, set[int]] = defaultdict(set)
    incoming: dict[int, set[int]] = defaultdict(set)
    counts: dict[tuple[int, int], int] = defaultdict(int)
    for cell in state.cells:
        edge = (dsu.find(cell.negative_terminal_id), dsu.find(cell.positive_terminal_id))
        if edge[0] == edge[1]:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )
        edges.append(edge)
        edge_nodes.update(edge)
        outgoing[edge[0]].add(edge[1])
        incoming[edge[1]].add(edge[0])
        counts[edge] += 1

    ordered_nodes = [start_net]
    current = start_net
    seen = {start_net}
    while current != target_net:
        next_nodes = outgoing.get(current, set())
        if len(next_nodes) != 1:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )
        next_node = next(iter(next_nodes))
        if next_node in seen:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )
        seen.add(next_node)
        ordered_nodes.append(next_node)
        current = next_node

    if edge_nodes - set(ordered_nodes):
        return BatteryTopologyAnalysis(
            topology_kind="general",
            series_count=None,
            parallel_count=None,
            minimum_series_cells=minimum_series_cells,
        )

    parallel_count: int | None = None
    for index, node in enumerate(ordered_nodes):
        previous_node = ordered_nodes[index - 1] if index > 0 else None
        next_ordered_node: int | None = (
            ordered_nodes[index + 1] if index < len(ordered_nodes) - 1 else None
        )
        incoming_nodes = incoming.get(node, set())
        outgoing_nodes = outgoing.get(node, set())
        if previous_node is None:
            if incoming_nodes:
                return BatteryTopologyAnalysis(
                    topology_kind="general",
                    series_count=None,
                    parallel_count=None,
                    minimum_series_cells=minimum_series_cells,
                )
        elif incoming_nodes != {previous_node}:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )
        if next_ordered_node is None:
            if outgoing_nodes:
                return BatteryTopologyAnalysis(
                    topology_kind="general",
                    series_count=None,
                    parallel_count=None,
                    minimum_series_cells=minimum_series_cells,
                )
        elif outgoing_nodes != {next_ordered_node}:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )
        if next_ordered_node is None:
            continue
        layer_count = counts[(node, next_ordered_node)]
        if parallel_count is None:
            parallel_count = layer_count
        elif parallel_count != layer_count:
            return BatteryTopologyAnalysis(
                topology_kind="general",
                series_count=None,
                parallel_count=None,
                minimum_series_cells=minimum_series_cells,
            )

    return BatteryTopologyAnalysis(
        topology_kind="series_parallel",
        series_count=len(ordered_nodes) - 1,
        parallel_count=parallel_count,
        minimum_series_cells=minimum_series_cells,
    )


def validate_battery_circuit_state(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
) -> str | None:
    """Return a deterministic validation failure, or ``None`` when valid."""
    if not state.cells:
        return "At least one battery cell is required."

    cell_ids = [cell.cell_id for cell in state.cells]
    if len(set(cell_ids)) != len(cell_ids):
        return "Cell identifiers must be unique."

    terminal_id_list = [
        terminal_id for cell in state.cells for terminal_id in (cell.negative_terminal_id, cell.positive_terminal_id)
    ]
    if len(set(terminal_id_list)) != len(terminal_id_list):
        return "Terminal identifiers must be unique."

    for cell in state.cells:
        if cell.negative_terminal_id == cell.positive_terminal_id:
            return "A cell cannot reuse the same terminal id for both polarities."
        if not coordinate_is_in_bounds((cell.x, cell.y, cell.z), requirements):
            return "A cell lies outside the legal grid envelope."

    if len({(cell.x, cell.y, cell.z) for cell in state.cells}) != len(state.cells):
        return "Duplicate physical coordinates are not allowed."

    if state.pack_negative_terminal_id == state.pack_positive_terminal_id:
        return "Pack positive and negative terminals must be distinct."

    all_terminal_ids = set(terminal_id_list)
    if (
        state.pack_negative_terminal_id not in all_terminal_ids
        or state.pack_positive_terminal_id not in all_terminal_ids
    ):
        return "Pack terminals must reference existing cell terminals."

    connection_ids = [connection.connection_id for connection in state.connections]
    if len(set(connection_ids)) != len(connection_ids):
        return "Connection identifiers must be unique."

    seen_pairs: set[tuple[int, int]] = set()
    for connection in state.connections:
        if connection.from_terminal_id == connection.to_terminal_id:
            return "Connections must join two distinct terminals."
        if connection.from_terminal_id not in all_terminal_ids or connection.to_terminal_id not in all_terminal_ids:
            return "Connections must reference existing cell terminals."
        if connection.resistance_ohm <= 0.0:
            return "Connections must have positive resistance."
        pair_key = _pair_key(connection.from_terminal_id, connection.to_terminal_id)
        if pair_key in seen_pairs:
            return "Duplicate direct connections are not allowed."
        seen_pairs.add(pair_key)

    dsu, connection_adjacency = _build_connection_sets(state)
    if dsu.find(state.pack_negative_terminal_id) == dsu.find(state.pack_positive_terminal_id):
        return "Pack terminals cannot be shorted by direct interconnects."

    for cell in state.cells:
        if dsu.find(cell.negative_terminal_id) == dsu.find(cell.positive_terminal_id):
            return "A cell cannot have its terminals shorted by direct interconnects."

    if _minimum_series_cells(state, dsu) is None:
        return "Cells do not form a forward conductive path from pack negative to pack positive."

    for cell in state.cells:
        adjacency = _full_graph_adjacency(state, skip_cell_id=cell.cell_id)
        reachable_from_negative = _reachable_nodes(adjacency, state.pack_negative_terminal_id)
        reachable_from_positive = _reachable_nodes(adjacency, state.pack_positive_terminal_id)
        if (
            cell.negative_terminal_id in reachable_from_negative
            and cell.positive_terminal_id in reachable_from_positive
        ) or (
            cell.positive_terminal_id in reachable_from_negative
            and cell.negative_terminal_id in reachable_from_positive
        ):
            continue
        return "Every cell must lie on at least one conductive path between the pack terminals."

    del connection_adjacency
    return None


def simulate_battery_circuit(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
    cell_model: BatteryCellModel,
) -> BatteryCircuitSimulationResult:
    """Run a constant-current discharge simulation for one explicit battery circuit."""
    dsu, _ = _build_connection_sets(state)
    node_ids = sorted({dsu.find(node_id) for node_id in terminal_ids(state)})
    reference_id = dsu.find(state.pack_negative_terminal_id)
    pack_positive_net_id = dsu.find(state.pack_positive_terminal_id)
    solve_node_ids = [node_id for node_id in node_ids if node_id != reference_id]
    node_index = {node_id: index for index, node_id in enumerate(solve_node_ids)}
    capacity_ah = CELL_SPEC_18650.nominal_capacity_ah
    duration_seconds = (requirements.minimum_capacity_ah / requirements.minimum_current_a) * 3600.0
    target_steps = max(1, ceil(duration_seconds))
    soc_by_cell_id = {cell.cell_id: 1.0 for cell in state.cells}
    rc_voltage_by_cell_id = {cell.cell_id: 0.0 for cell in state.cells}
    max_cell_current_a = 0.0
    min_cell_voltage_v = float("inf")
    last_pack_voltage = 0.0

    for step in range(target_steps):
        matrix = numpy.zeros((len(solve_node_ids), len(solve_node_ids)))
        current_vector = numpy.zeros(len(solve_node_ids))

        cell_parameters: dict[int, tuple[float, float, float, float]] = {}
        for cell in state.cells:
            (
                open_circuit_voltage_v,
                series_resistance_ohm,
                transient_resistance_ohm,
                transient_capacitance_f,
            ) = interpolate_cell_model(cell_model, soc_by_cell_id[cell.cell_id])
            series_resistance_ohm = max(1.0e-6, series_resistance_ohm)
            effective_open_circuit_voltage = open_circuit_voltage_v - rc_voltage_by_cell_id[cell.cell_id]
            cell_parameters[cell.cell_id] = (
                open_circuit_voltage_v,
                series_resistance_ohm,
                transient_resistance_ohm,
                transient_capacitance_f,
            )
            positive_node_id = dsu.find(cell.positive_terminal_id)
            negative_node_id = dsu.find(cell.negative_terminal_id)
            conductance = 1.0 / series_resistance_ohm
            _stamp_resistor(
                matrix,
                current_vector,
                node_index,
                reference_id,
                positive_node_id,
                negative_node_id,
                conductance,
            )
            _stamp_current_source(
                current_vector,
                node_index,
                reference_id,
                from_node=negative_node_id,
                to_node=positive_node_id,
                current_a=effective_open_circuit_voltage / series_resistance_ohm,
            )

        _stamp_current_source(
            current_vector,
            node_index,
            reference_id,
            from_node=pack_positive_net_id,
            to_node=reference_id,
            current_a=requirements.minimum_current_a,
        )

        try:
            solved_voltages = numpy.linalg.solve(matrix, current_vector)
        except numpy.linalg.LinAlgError:
            return BatteryCircuitSimulationResult(
                pack_terminal_voltage_end=last_pack_voltage,
                delivered_capacity_ah=(requirements.minimum_current_a * float(step)) / 3600.0,
                max_cell_current_a=max_cell_current_a,
                min_cell_voltage_v=0.0 if min_cell_voltage_v == float("inf") else min_cell_voltage_v,
                solver_steps=step,
                is_feasible=False,
                failure_reason="Battery circuit solve failed because the netlist is singular.",
            )

        node_voltage = {reference_id: 0.0}
        for node_id, index in node_index.items():
            node_voltage[node_id] = float(solved_voltages[index])

        last_pack_voltage = node_voltage[pack_positive_net_id] - node_voltage[reference_id]
        for cell in state.cells:
            (
                open_circuit_voltage_v,
                series_resistance_ohm,
                transient_resistance_ohm,
                transient_capacitance_f,
            ) = cell_parameters[cell.cell_id]
            positive_node_id = dsu.find(cell.positive_terminal_id)
            negative_node_id = dsu.find(cell.negative_terminal_id)
            terminal_voltage = node_voltage[positive_node_id] - node_voltage[negative_node_id]
            effective_open_circuit_voltage = open_circuit_voltage_v - rc_voltage_by_cell_id[cell.cell_id]
            current_positive_to_negative = (terminal_voltage - effective_open_circuit_voltage) / series_resistance_ohm
            discharge_current = -current_positive_to_negative
            max_cell_current_a = max(max_cell_current_a, abs(discharge_current))
            min_cell_voltage_v = min(min_cell_voltage_v, terminal_voltage)
            if terminal_voltage + 1.0e-9 < CELL_SPEC_18650.min_voltage_v:
                delivered_capacity = (requirements.minimum_current_a * float(step + 1)) / 3600.0
                return BatteryCircuitSimulationResult(
                    pack_terminal_voltage_end=last_pack_voltage,
                    delivered_capacity_ah=delivered_capacity,
                    max_cell_current_a=max_cell_current_a,
                    min_cell_voltage_v=min_cell_voltage_v,
                    solver_steps=step + 1,
                    is_feasible=False,
                    failure_reason="A cell dropped below the minimum allowable voltage.",
                )
            soc_delta = discharge_current / (capacity_ah * 3600.0)
            next_soc = min(1.0, max(0.0, soc_by_cell_id[cell.cell_id] - soc_delta))
            soc_by_cell_id[cell.cell_id] = next_soc
            if transient_resistance_ohm > 1.0e-12 and transient_capacitance_f > 1.0e-12:
                tau_seconds = transient_resistance_ohm * transient_capacitance_f
                alpha = 0.0 if tau_seconds <= 1.0e-12 else exp(-1.0 / tau_seconds)
                rc_voltage_by_cell_id[cell.cell_id] = (alpha * rc_voltage_by_cell_id[cell.cell_id]) + (
                    (1.0 - alpha) * discharge_current * transient_resistance_ohm
                )
            else:
                rc_voltage_by_cell_id[cell.cell_id] = 0.0
            if next_soc <= 1.0e-9 and (step + 1) < target_steps:
                delivered_capacity = (requirements.minimum_current_a * float(step + 1)) / 3600.0
                return BatteryCircuitSimulationResult(
                    pack_terminal_voltage_end=last_pack_voltage,
                    delivered_capacity_ah=delivered_capacity,
                    max_cell_current_a=max_cell_current_a,
                    min_cell_voltage_v=min_cell_voltage_v,
                    solver_steps=step + 1,
                    is_feasible=False,
                    failure_reason="A cell depleted before the required discharge duration completed.",
                )

    delivered_capacity_ah = (requirements.minimum_current_a * float(target_steps)) / 3600.0
    return BatteryCircuitSimulationResult(
        pack_terminal_voltage_end=last_pack_voltage,
        delivered_capacity_ah=delivered_capacity_ah,
        max_cell_current_a=max_cell_current_a,
        min_cell_voltage_v=0.0 if min_cell_voltage_v == float("inf") else min_cell_voltage_v,
        solver_steps=target_steps,
        is_feasible=True,
        failure_reason=None,
    )


def evaluate_battery_circuit(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
    load_cell_model: Callable[[], BatteryCellModel],
) -> BatteryCircuitEvaluation:
    """Evaluate one explicit battery circuit using deterministic checks and the shared solver."""
    layout = compute_layout_summary(state.cells)
    analysis = analyze_battery_topology(state)
    validation_failure = validate_battery_circuit_state(state, requirements)
    pack_nominal_voltage = (
        0.0
        if analysis.minimum_series_cells is None
        else float(analysis.minimum_series_cells) * CELL_SPEC_18650.nominal_voltage_v
    )
    if validation_failure is not None:
        return _evaluation_from_parts(
            layout=layout,
            state=state,
            analysis=analysis,
            pack_nominal_voltage=pack_nominal_voltage,
            pybamm_ran=False,
            cell_model_source=None,
            cell_model_warning=None,
            simulation=None,
            is_feasible=False,
            failure_reason=validation_failure,
        )

    cell_model = load_cell_model()
    simulation = simulate_battery_circuit(state, requirements, cell_model)
    required_voltage_floor = (
        0.0
        if analysis.minimum_series_cells is None
        else float(analysis.minimum_series_cells) * CELL_SPEC_18650.min_voltage_v
    )
    failure_reason = simulation.failure_reason
    is_feasible = simulation.is_feasible
    if is_feasible and simulation.delivered_capacity_ah + 1.0e-9 < requirements.minimum_capacity_ah:
        is_feasible = False
        failure_reason = "Delivered capacity is below the minimum required capacity."
    if is_feasible and simulation.pack_terminal_voltage_end + 1.0e-9 < required_voltage_floor:
        is_feasible = False
        failure_reason = "Pack terminal voltage fell below the minimum required floor."

    return _evaluation_from_parts(
        layout=layout,
        state=state,
        analysis=analysis,
        pack_nominal_voltage=pack_nominal_voltage,
        pybamm_ran=True,
        cell_model_source=cell_model.source,
        cell_model_warning=cell_model.warning_message,
        simulation=simulation,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
    )


def _evaluation_from_parts(
    *,
    layout: BatteryLayoutSummary,
    state: BatteryCircuitState,
    analysis: BatteryTopologyAnalysis,
    pack_nominal_voltage: float,
    pybamm_ran: bool,
    cell_model_source: str | None,
    cell_model_warning: str | None,
    simulation: BatteryCircuitSimulationResult | None,
    is_feasible: bool,
    failure_reason: str | None,
) -> BatteryCircuitEvaluation:
    """Build a public evaluation object from layout and simulation pieces."""
    return BatteryCircuitEvaluation(
        cell_count=layout.cell_count,
        connection_count=len(state.connections),
        design_width=layout.design_width,
        design_depth=layout.design_depth,
        design_height=layout.design_height,
        design_cost=layout.design_cost,
        design_volume=layout.design_volume,
        surface_area=layout.surface_area,
        moment_of_inertia_xx=layout.moment_of_inertia_xx,
        moment_of_inertia_yy=layout.moment_of_inertia_yy,
        moment_of_inertia_zz=layout.moment_of_inertia_zz,
        pack_nominal_voltage=pack_nominal_voltage,
        pack_terminal_voltage_end=None if simulation is None else simulation.pack_terminal_voltage_end,
        delivered_capacity_ah=None if simulation is None else simulation.delivered_capacity_ah,
        max_cell_current_a=None if simulation is None else simulation.max_cell_current_a,
        min_cell_voltage_v=None if simulation is None else simulation.min_cell_voltage_v,
        solver_steps=0 if simulation is None else simulation.solver_steps,
        pybamm_ran=pybamm_ran,
        topology_kind=analysis.topology_kind,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        cell_model_source=cell_model_source,
        cell_model_warning=cell_model_warning,
    )


def _stamp_resistor(
    matrix: numpy.ndarray,
    current_vector: numpy.ndarray,
    node_index: dict[int, int],
    reference_id: int,
    node_a: int,
    node_b: int,
    conductance: float,
) -> None:
    """Stamp one resistor into the conductance matrix."""
    del current_vector
    if node_a != reference_id:
        index_a = node_index[node_a]
        matrix[index_a, index_a] += conductance
    if node_b != reference_id:
        index_b = node_index[node_b]
        matrix[index_b, index_b] += conductance
    if node_a != reference_id and node_b != reference_id:
        index_a = node_index[node_a]
        index_b = node_index[node_b]
        matrix[index_a, index_b] -= conductance
        matrix[index_b, index_a] -= conductance


def _stamp_current_source(
    current_vector: numpy.ndarray,
    node_index: dict[int, int],
    reference_id: int,
    *,
    from_node: int,
    to_node: int,
    current_a: float,
) -> None:
    """Stamp one current source into the RHS vector."""
    if from_node != reference_id:
        current_vector[node_index[from_node]] -= current_a
    if to_node != reference_id:
        current_vector[node_index[to_node]] += current_a
