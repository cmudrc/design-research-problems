"""Shared explicit-circuit backend for battery-domain problems."""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from math import ceil, exp
from typing import Any

import numpy
from numpy.typing import NDArray

from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    BatteryCellModel,
    BatteryThermalPriors,
    _load_lithium_ion_parameter_values,
    import_pybamm,
    interpolate_cell_model,
    load_battery_cell_model,
    load_battery_thermal_priors,
    resolve_battery_backend_config,
)
from design_research_problems.problems._domains.battery_defaults import BATTERY_BACKEND_DEFAULTS
from design_research_problems.problems._domains.battery_layout import (
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
    ideal: bool = False
    """Whether this interconnect should collapse into an ideal zero-drop net."""


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
    total_connection_loss_w: float | None
    """Total Joule loss across explicit interconnect resistors at the final step."""
    max_connection_current_a: float | None
    """Maximum observed absolute current through any explicit interconnect."""
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
    cell_model_mode: str | None = None
    """Resolved backend mode used for this evaluation."""
    cell_model_parameter_set: str | None = None
    """Resolved concrete parameter-set name used for this evaluation."""
    end_cell_temperature_c: float | None = None
    """Final cell temperature used by the backend thermal model."""
    max_cell_temperature_c: float | None = None
    """Maximum cell temperature observed during the simulated trajectory."""
    thermal_mode: str | None = None
    """Resolved thermal mode used during the backend evaluation."""


@dataclass(frozen=True)
class BatteryCircuitSimulationResult:
    """Internal simulation result used to build public evaluations."""

    pack_terminal_voltage_end: float
    """Stored pack terminal voltage end value."""
    required_pack_terminal_voltage_end: float
    """Stored required pack terminal voltage end value."""
    delivered_capacity_ah: float
    """Stored delivered capacity ah value."""
    max_cell_current_a: float
    """Stored max cell current a value."""
    min_cell_voltage_v: float
    """Stored min cell voltage v value."""
    total_connection_loss_w: float
    """Stored total explicit-interconnect Joule loss in watts."""
    max_connection_current_a: float
    """Stored maximum explicit-interconnect current in amps."""
    solver_steps: int
    """Stored solver steps value."""
    is_feasible: bool
    """Whether feasible."""
    failure_reason: str | None
    """Stored failure reason value."""
    end_cell_temperature_c: float
    """Final cell temperature used by the backend thermal model."""
    max_cell_temperature_c: float
    """Maximum cell temperature observed during the simulated trajectory."""
    max_kcl_residual_a: float = 0.0
    """Maximum nodal current-balance residual across all simulated steps."""
    max_kvl_residual_v: float = 0.0
    """Maximum branch voltage-consistency residual across all simulated steps."""
    cumulative_delivered_energy_j: float = 0.0
    """Integrated discharge-side electrical energy delivered at the pack terminals."""
    cumulative_cell_heat_j: float = 0.0
    """Integrated irreversible cell Joule-heating proxy."""
    cumulative_connection_loss_j: float = 0.0
    """Integrated explicit-interconnect Joule loss."""
    end_soc_by_cell_id: tuple[tuple[int, float], ...] = ()
    """Final per-cell state of charge values."""
    end_primary_rc_voltage_by_cell_id: tuple[tuple[int, float], ...] = ()
    """Final per-cell primary RC overpotential state."""
    end_secondary_rc_voltage_by_cell_id: tuple[tuple[int, float], ...] = ()
    """Final per-cell secondary RC overpotential state."""
    end_cell_current_by_cell_id: tuple[tuple[int, float], ...] = ()
    """Final per-cell discharge current values."""
    end_connection_current_by_connection_id: tuple[tuple[int, float], ...] = ()
    """Final explicit-interconnect current values."""
    trace: tuple[BatteryCircuitTracePoint, ...] = ()
    """Per-step trace used by invariant and oracle tests."""


@dataclass(frozen=True)
class BatteryCircuitTracePoint:
    """One recorded simulation point from the internal profile runner."""

    time_s: float
    """Simulation time at the start of the solved interval."""
    pack_current_a: float
    """Applied pack current during the interval."""
    pack_terminal_voltage_v: float
    """Solved pack terminal voltage."""
    min_cell_voltage_v: float
    """Minimum cell terminal voltage at this step."""
    max_cell_current_a: float
    """Maximum absolute cell current at this step."""
    total_connection_loss_w: float
    """Instantaneous interconnect Joule loss."""
    total_cell_heat_w: float
    """Instantaneous cell Joule-heating proxy."""
    cell_temperature_c: float
    """Shared lumped cell temperature used at this step."""
    delivered_capacity_ah: float
    """Delivered discharge capacity accumulated before this interval."""


@dataclass(frozen=True)
class _BatteryCurrentProfileSegment:
    """One piecewise-constant pack-current segment."""

    duration_s: float
    """Duration of the segment in seconds."""
    current_a: float
    """Applied pack current in amps; positive denotes discharge."""


def sort_battery_cells(
    cells: tuple[BatteryCellInstance, ...] | list[BatteryCellInstance],
) -> tuple[BatteryCellInstance, ...]:
    """Return cells sorted deterministically by id and coordinate.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
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
    """Return connections sorted deterministically by id and endpoints.

    Args:
        connections: Value for ``connections``.

    Returns:
        Computed result for this callable.
    """
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
    """Return the next stable terminal identifier.

    Args:
        cells: Value for ``cells``.

    Returns:
        Computed result for this callable.
    """
    next_id = 0
    for cell in cells:
        next_id = max(next_id, cell.positive_terminal_id + 1, cell.negative_terminal_id + 1)
    return next_id


def next_connection_id(connections: Iterable[BatteryConnection]) -> int:
    """Return the next stable connection identifier.

    Args:
        connections: Value for ``connections``.

    Returns:
        Computed result for this callable.
    """
    next_id = 0
    for connection in connections:
        next_id = max(next_id, connection.connection_id + 1)
    return next_id


def terminal_ids(state: BatteryCircuitState) -> tuple[int, ...]:
    """Return all terminal identifiers in deterministic order.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
    ids = {
        terminal_id for cell in state.cells for terminal_id in (cell.negative_terminal_id, cell.positive_terminal_id)
    }
    return tuple(sorted(ids))


def _pair_key(first: int, second: int) -> tuple[int, int]:
    """Return the canonical unordered key for one terminal pair.

    Args:
        first: Value for ``first``.
        second: Value for ``second``.

    Returns:
        Computed result for this callable.
    """
    return (first, second) if first <= second else (second, first)


class _DisjointSet:
    """Minimal disjoint-set implementation for connection-net reduction."""

    def __init__(self, items: Iterable[int]) -> None:
        """Implement init.

        Args:
            items: Value for ``items``.
        """
        self._parent = {item: item for item in items}

    def find(self, item: int) -> int:
        """Return the representative for one item.

        Args:
            item: Value for ``item``.

        Returns:
            Computed result for this callable.
        """
        parent = self._parent[item]
        if parent != item:
            parent = self.find(parent)
            self._parent[item] = parent
        return parent

    def union(self, first: int, second: int) -> None:
        """Merge two representatives.

        Args:
            first: Value for ``first``.
            second: Value for ``second``.
        """
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            self._parent[second_root] = first_root


def _build_connection_sets(state: BatteryCircuitState) -> tuple[_DisjointSet, dict[int, set[int]]]:
    """Return wire-equivalence classes and adjacency from explicit connections.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
    ids = terminal_ids(state)
    dsu = _DisjointSet(ids)
    adjacency: dict[int, set[int]] = {terminal_id: set() for terminal_id in ids}
    for connection in state.connections:
        adjacency[connection.from_terminal_id].add(connection.to_terminal_id)
        adjacency[connection.to_terminal_id].add(connection.from_terminal_id)
        dsu.union(connection.from_terminal_id, connection.to_terminal_id)
    return (dsu, adjacency)


def _build_ideal_connection_sets(state: BatteryCircuitState) -> tuple[_DisjointSet, dict[int, set[int]]]:
    """Return ideal-wire equivalence classes and adjacency.

    Args:
        state: Value for ``state``.

    Returns:
        Ideal-wire disjoint-set plus ideal-only adjacency.
    """
    ids = terminal_ids(state)
    dsu = _DisjointSet(ids)
    adjacency: dict[int, set[int]] = {terminal_id: set() for terminal_id in ids}
    for connection in state.connections:
        if not connection.ideal:
            continue
        adjacency[connection.from_terminal_id].add(connection.to_terminal_id)
        adjacency[connection.to_terminal_id].add(connection.from_terminal_id)
        dsu.union(connection.from_terminal_id, connection.to_terminal_id)
    return (dsu, adjacency)


def _reachable_nodes(
    adjacency: dict[int, set[int]],
    start: int,
) -> set[int]:
    """Return all nodes reachable from ``start``.

    Args:
        adjacency: Value for ``adjacency``.
        start: Value for ``start``.

    Returns:
        Computed result for this callable.
    """
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
    """Return undirected terminal adjacency including cells and interconnects.

    Args:
        state: Value for ``state``.
        skip_cell_id: Identifier for skip cell.

    Returns:
        Computed result for this callable.
    """
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
    """Return the shortest directed cell-path length from pack negative to pack positive.

    Args:
        state: Value for ``state``.
        dsu: Value for ``dsu``.

    Returns:
        Computed result for this callable.
    """
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
    """Classify the reduced circuit topology.

    Args:
        state: Value for ``state``.

    Returns:
        Computed result for this callable.
    """
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
        next_ordered_node: int | None = ordered_nodes[index + 1] if index < len(ordered_nodes) - 1 else None
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
    """Return a deterministic validation failure, or ``None`` when valid.

    Args:
        state: Value for ``state``.
        requirements: Value for ``requirements``.

    Returns:
        Computed result for this callable.
    """
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


def _series_combined_conductance(first_w_per_k: float, second_w_per_k: float) -> float:
    """Return the equivalent conductance for two thermal paths in series."""
    first = max(first_w_per_k, 1.0e-9)
    second = max(second_w_per_k, 1.0e-9)
    return float((first * second) / (first + second))


def _effective_lumped_pack_conductance_w_per_k(
    thermal_priors: BatteryThermalPriors,
    *,
    cell_count: int,
) -> float:
    """Return the pack-level one-state conductance to ambient."""
    cell_to_jig_total = max(float(cell_count), 1.0) * thermal_priors.cell_to_jig_conductance_w_per_k
    return _series_combined_conductance(cell_to_jig_total, thermal_priors.jig_to_ambient_conductance_w_per_k)


def _effective_lumped_pack_thermal_mass_j_per_k(
    thermal_priors: BatteryThermalPriors,
    *,
    cell_count: int,
) -> float:
    """Return the pack-level one-state thermal mass."""
    return (
        max(float(cell_count), 1.0) * thermal_priors.cell_thermal_mass_j_per_k + thermal_priors.jig_thermal_mass_j_per_k
    )


def _validate_pybamm_direct_state(
    state: BatteryCircuitState,
    analysis: BatteryTopologyAnalysis,
) -> str | None:
    """Return a validation message when PyBaMM-direct evaluation is unsupported."""
    if analysis.topology_kind != "series_parallel" or analysis.series_count is None or analysis.parallel_count is None:
        return "pybamm_direct currently supports only ideal series-parallel pack topologies."
    if any(not connection.ideal for connection in state.connections):
        return "pybamm_direct currently requires ideal interconnects and does not model explicit resistive busbars."
    if not state.cells:
        return "pybamm_direct requires at least one active cell."
    return None


def _load_pybamm_direct_temperature_trace_c(
    solution: Any,
    sample_times_s: NDArray[numpy.float64],
) -> NDArray[numpy.float64]:
    """Return the best available cell-temperature trace in Celsius."""
    for variable_name in (
        "X-averaged cell temperature [K]",
        "Volume-averaged cell temperature [K]",
        "Cell temperature [K]",
    ):
        try:
            values = numpy.array(solution[variable_name](sample_times_s), dtype=float, copy=False)
        except Exception:
            continue
        if values.ndim > 1:
            values = numpy.array(values.reshape(values.shape[0], -1).mean(axis=1), dtype=float, copy=False)
        return numpy.array(values - 273.15, dtype=float, copy=False)
    raise KeyError("No supported PyBaMM cell temperature variable was available.")


def _load_pybamm_direct_heat_trace_w(
    solution: Any,
    sample_times_s: NDArray[numpy.float64],
) -> NDArray[numpy.float64]:
    """Return the best available single-cell heat trace in watts."""
    for variable_name in (
        "Total heating [W]",
        "Irreversible electrochemical heating [W]",
        "Ohmic heating [W]",
    ):
        try:
            values = numpy.array(solution[variable_name](sample_times_s), dtype=float, copy=False)
        except Exception:
            continue
        return numpy.array(values.reshape(-1), dtype=float, copy=False)
    return numpy.zeros(len(sample_times_s), dtype=float)


def _simulate_battery_circuit_pybamm_direct(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
    analysis: BatteryTopologyAnalysis,
    *,
    simulate_to_failure: bool,
    backend_config: BatteryBackendConfig,
) -> tuple[BatteryCircuitSimulationResult, str, str | None]:
    """Run one high-cost direct PyBaMM evaluation for ideal series-parallel packs."""
    validation_message = _validate_pybamm_direct_state(state, analysis)
    if validation_message is not None:
        raise ValueError(validation_message)

    resolved_parameter_set = backend_config.parameterization.resolved_parameter_set()
    parameter_values, current_scale, _ambient_temperature_k = _load_lithium_ion_parameter_values(
        model_family="spm",
        resolved_parameter_set=resolved_parameter_set,
        ambient_temperature_c=backend_config.ambient_temp_c,
    )
    pybamm_module = import_pybamm()
    thermal_mode = backend_config.thermal_mode or BATTERY_BACKEND_DEFAULTS.thermal.default_mode
    if thermal_mode not in {"isothermal", "lumped"}:
        raise ValueError(f"pybamm_direct does not support thermal_mode={thermal_mode!r}.")
    model_options = {"thermal": "lumped"} if thermal_mode == "lumped" else None
    spm_model = (
        pybamm_module.lithium_ion.SPM(options=model_options)
        if model_options is not None
        else pybamm_module.lithium_ion.SPM()
    )

    if analysis.parallel_count is None or analysis.series_count is None:
        raise ValueError("pybamm_direct requires a resolved series-parallel topology.")
    parallel_count = max(analysis.parallel_count, 1)
    series_count = max(analysis.series_count, 1)
    per_cell_pack_current_a = requirements.minimum_current_a / float(parallel_count)
    pybamm_cell_current_a = per_cell_pack_current_a * current_scale
    duration_seconds = (requirements.minimum_capacity_ah / requirements.minimum_current_a) * 3600.0
    required_steps = max(1, ceil(duration_seconds))
    hard_step_cap = required_steps
    if simulate_to_failure and requirements.minimum_current_a > 0.0:
        capacity_limited_seconds = (
            float(parallel_count) * CELL_SPEC_18650.nominal_capacity_ah / requirements.minimum_current_a
        ) * 3600.0
        hard_step_cap = max(required_steps, ceil(capacity_limited_seconds))

    experiment = pybamm_module.Experiment([f"Discharge at {pybamm_cell_current_a:.6f} A for {hard_step_cap} seconds"])
    simulation = pybamm_module.Simulation(spm_model, experiment=experiment, parameter_values=parameter_values)
    solution = simulation.solve(initial_soc=1.0)

    executed_steps = min(hard_step_cap, max(0, int(numpy.floor(float(solution.t[-1]) + 1.0e-9))))
    sample_step_count = max(executed_steps, 1)
    sample_times_s = numpy.arange(0.0, float(sample_step_count), 1.0, dtype=float)
    cell_voltage_v = numpy.asarray(solution["Voltage [V]"](sample_times_s), dtype=float).reshape(-1)
    pack_voltage_v = float(series_count) * cell_voltage_v
    try:
        cell_temperature_c = _load_pybamm_direct_temperature_trace_c(solution, sample_times_s)
    except KeyError:
        fallback_temperature_c = (
            BATTERY_BACKEND_DEFAULTS.thermal.ambient_temperature_c
            if backend_config.ambient_temp_c is None
            else float(backend_config.ambient_temp_c)
        )
        cell_temperature_c = numpy.full(len(sample_times_s), fallback_temperature_c, dtype=float)
    total_cell_heat_w = _load_pybamm_direct_heat_trace_w(solution, sample_times_s) * float(len(state.cells))

    trace_points = [
        BatteryCircuitTracePoint(
            time_s=float(index),
            pack_current_a=requirements.minimum_current_a,
            pack_terminal_voltage_v=float(pack_voltage_v[index]),
            min_cell_voltage_v=float(cell_voltage_v[index]),
            max_cell_current_a=abs(per_cell_pack_current_a),
            total_connection_loss_w=0.0,
            total_cell_heat_w=float(total_cell_heat_w[index]),
            cell_temperature_c=float(cell_temperature_c[index]),
            delivered_capacity_ah=(requirements.minimum_current_a * float(index)) / 3600.0,
        )
        for index in range(len(sample_times_s))
    ]

    delivered_capacity_ah = (requirements.minimum_current_a * float(executed_steps)) / 3600.0
    cumulative_delivered_energy_j = float(
        requirements.minimum_current_a * float(numpy.sum(pack_voltage_v[:executed_steps]))
    )
    cumulative_cell_heat_j = float(numpy.sum(total_cell_heat_w[:executed_steps]))
    required_pack_terminal_voltage_end = (
        float(pack_voltage_v[required_steps - 1]) if required_steps <= len(pack_voltage_v) else 0.0
    )
    terminated_early = executed_steps < hard_step_cap
    termination_text = str(getattr(solution, "termination", ""))
    hit_minimum_voltage = "Minimum voltage" in termination_text
    failure_reason = None
    is_feasible = True
    if hit_minimum_voltage and executed_steps < required_steps and not simulate_to_failure:
        is_feasible = False
        failure_reason = "A cell dropped below the minimum allowable voltage."
    elif terminated_early and executed_steps < required_steps and not simulate_to_failure:
        is_feasible = False
        failure_reason = "PyBaMM direct evaluation terminated before the required discharge duration completed."
    elif hit_minimum_voltage and simulate_to_failure and executed_steps < required_steps:
        is_feasible = False
        failure_reason = "A cell dropped below the minimum allowable voltage."

    result = _build_simulation_result(
        pack_terminal_voltage_end=float(pack_voltage_v[min(len(pack_voltage_v), max(executed_steps, 1)) - 1]),
        required_pack_terminal_voltage_end=required_pack_terminal_voltage_end,
        delivered_capacity_ah=delivered_capacity_ah,
        max_cell_current_a=abs(per_cell_pack_current_a),
        min_cell_voltage_v=float(numpy.min(cell_voltage_v)),
        total_connection_loss_w=0.0,
        max_connection_current_a=0.0,
        solver_steps=executed_steps,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        end_cell_temperature_c=float(cell_temperature_c[min(len(cell_temperature_c), max(executed_steps, 1)) - 1]),
        max_cell_temperature_c=float(numpy.max(cell_temperature_c)),
        max_kcl_residual_a=0.0,
        max_kvl_residual_v=0.0,
        cumulative_delivered_energy_j=cumulative_delivered_energy_j,
        cumulative_cell_heat_j=cumulative_cell_heat_j,
        cumulative_connection_loss_j=0.0,
        soc_by_cell_id={
            cell.cell_id: max(
                0.0,
                1.0 - (delivered_capacity_ah / (float(parallel_count) * CELL_SPEC_18650.nominal_capacity_ah)),
            )
            for cell in state.cells
        },
        primary_rc_voltage_by_cell_id={cell.cell_id: 0.0 for cell in state.cells},
        secondary_rc_voltage_by_cell_id={cell.cell_id: 0.0 for cell in state.cells},
        cell_current_by_cell_id={cell.cell_id: per_cell_pack_current_a for cell in state.cells},
        connection_current_by_connection_id={connection.connection_id: 0.0 for connection in state.connections},
        trace_points=trace_points,
    )
    return (result, "pybamm_spm_direct", resolved_parameter_set)


def simulate_battery_circuit(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
    cell_model: BatteryCellModel,
    *,
    simulate_to_failure: bool = False,
    backend_config: BatteryBackendConfig | None = None,
    thermal_priors: BatteryThermalPriors | None = None,
) -> BatteryCircuitSimulationResult:
    """Run a constant-current discharge simulation for one explicit battery circuit.

    Args:
        state: Value for ``state``.
        requirements: Value for ``requirements``.
        cell_model: Value for ``cell_model``.
        simulate_to_failure: Value for ``simulate_to_failure``.
        backend_config: Resolved backend configuration for thermal handling.
        thermal_priors: Optional lumped thermal prior bundle.

    Returns:
        Computed result for this callable.
    """
    capacity_ah = CELL_SPEC_18650.nominal_capacity_ah
    duration_seconds = (requirements.minimum_capacity_ah / requirements.minimum_current_a) * 3600.0
    required_steps = max(1, ceil(duration_seconds))
    hard_step_cap = required_steps
    if simulate_to_failure and requirements.minimum_current_a > 0.0:
        capacity_limited_seconds = (float(len(state.cells)) * capacity_ah / requirements.minimum_current_a) * 3600.0
        hard_step_cap = max(required_steps, ceil(capacity_limited_seconds))
    return _simulate_battery_circuit_current_profile(
        state,
        cell_model,
        profile_segments=(
            _BatteryCurrentProfileSegment(
                duration_s=float(hard_step_cap),
                current_a=requirements.minimum_current_a,
            ),
        ),
        required_step_index=required_steps,
        simulate_to_failure=simulate_to_failure,
        backend_config=backend_config,
        thermal_priors=thermal_priors,
    )


def _simulate_battery_circuit_current_profile(
    state: BatteryCircuitState,
    cell_model: BatteryCellModel,
    *,
    profile_segments: tuple[_BatteryCurrentProfileSegment, ...],
    required_step_index: int | None = None,
    simulate_to_failure: bool = False,
    backend_config: BatteryBackendConfig | None = None,
    thermal_priors: BatteryThermalPriors | None = None,
) -> BatteryCircuitSimulationResult:
    """Run one internal piecewise-constant current profile."""
    ideal_dsu, _ = _build_ideal_connection_sets(state)
    node_ids = sorted({ideal_dsu.find(node_id) for node_id in terminal_ids(state)})
    reference_id = ideal_dsu.find(state.pack_negative_terminal_id)
    pack_positive_net_id = ideal_dsu.find(state.pack_positive_terminal_id)
    solve_node_ids = [node_id for node_id in node_ids if node_id != reference_id]
    node_index = {node_id: index for index, node_id in enumerate(solve_node_ids)}
    resolved_backend_config = resolve_battery_backend_config(backend_config)
    thermal_mode = resolved_backend_config.thermal_mode or BATTERY_BACKEND_DEFAULTS.thermal.default_mode
    ambient_temperature_c = (
        BATTERY_BACKEND_DEFAULTS.thermal.ambient_temperature_c
        if resolved_backend_config.ambient_temp_c is None
        else float(resolved_backend_config.ambient_temp_c)
    )
    capacity_ah = CELL_SPEC_18650.nominal_capacity_ah
    total_profile_steps = sum(_segment_step_count(segment.duration_s) for segment in profile_segments)
    required_step_count = total_profile_steps if required_step_index is None else max(1, int(required_step_index))
    cell_temperature_c = ambient_temperature_c
    max_cell_temperature_c = ambient_temperature_c
    soc_by_cell_id = {cell.cell_id: 1.0 for cell in state.cells}
    primary_rc_voltage_by_cell_id = {cell.cell_id: 0.0 for cell in state.cells}
    secondary_rc_voltage_by_cell_id = {cell.cell_id: 0.0 for cell in state.cells}
    max_cell_current_a = 0.0
    min_cell_voltage_v = float("inf")
    last_pack_voltage = 0.0
    required_pack_voltage = 0.0
    last_total_connection_loss_w = 0.0
    max_connection_current_a = 0.0
    max_kcl_residual_a = 0.0
    max_kvl_residual_v = 0.0
    delivered_capacity_ah = 0.0
    cumulative_delivered_energy_j = 0.0
    cumulative_cell_heat_j = 0.0
    cumulative_connection_loss_j = 0.0
    trace_points: list[BatteryCircuitTracePoint] = []
    last_cell_currents = {cell.cell_id: 0.0 for cell in state.cells}
    last_connection_currents = {connection.connection_id: 0.0 for connection in state.connections}
    elapsed_steps = 0

    for segment in profile_segments:
        segment_steps = _segment_step_count(segment.duration_s)
        for _ in range(segment_steps):
            pack_current_a = float(segment.current_a)
            matrix = numpy.zeros((len(solve_node_ids), len(solve_node_ids)))
            current_vector = numpy.zeros(len(solve_node_ids))

            for connection in state.connections:
                if connection.ideal:
                    continue
                from_node_id = ideal_dsu.find(connection.from_terminal_id)
                to_node_id = ideal_dsu.find(connection.to_terminal_id)
                if from_node_id == to_node_id:
                    continue
                conductance = 1.0 / max(connection.resistance_ohm, 1.0e-12)
                _stamp_resistor(
                    matrix,
                    current_vector,
                    node_index,
                    reference_id,
                    from_node_id,
                    to_node_id,
                    conductance,
                )

            cell_parameters: dict[int, tuple[float, float, float, float, float, float]] = {}
            for cell in state.cells:
                (
                    open_circuit_voltage_v,
                    series_resistance_ohm,
                    transient_resistance_ohm,
                    transient_capacitance_f,
                    secondary_transient_resistance_ohm,
                    secondary_transient_capacitance_f,
                ) = interpolate_cell_model(
                    cell_model,
                    soc_by_cell_id[cell.cell_id],
                    temperature_c=cell_temperature_c,
                )
                series_resistance_ohm = max(1.0e-6, series_resistance_ohm)
                effective_open_circuit_voltage = (
                    open_circuit_voltage_v
                    - primary_rc_voltage_by_cell_id[cell.cell_id]
                    - secondary_rc_voltage_by_cell_id[cell.cell_id]
                )
                cell_parameters[cell.cell_id] = (
                    open_circuit_voltage_v,
                    series_resistance_ohm,
                    transient_resistance_ohm,
                    transient_capacitance_f,
                    secondary_transient_resistance_ohm,
                    secondary_transient_capacitance_f,
                )
                positive_node_id = ideal_dsu.find(cell.positive_terminal_id)
                negative_node_id = ideal_dsu.find(cell.negative_terminal_id)
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
                current_a=pack_current_a,
            )

            try:
                solved_voltages = numpy.linalg.solve(matrix, current_vector)
            except numpy.linalg.LinAlgError:
                return _build_simulation_result(
                    pack_terminal_voltage_end=last_pack_voltage,
                    required_pack_terminal_voltage_end=required_pack_voltage,
                    delivered_capacity_ah=delivered_capacity_ah,
                    max_cell_current_a=max_cell_current_a,
                    min_cell_voltage_v=min_cell_voltage_v,
                    total_connection_loss_w=last_total_connection_loss_w,
                    max_connection_current_a=max_connection_current_a,
                    solver_steps=elapsed_steps,
                    is_feasible=False,
                    failure_reason="Battery circuit solve failed because the netlist is singular.",
                    end_cell_temperature_c=cell_temperature_c,
                    max_cell_temperature_c=max_cell_temperature_c,
                    max_kcl_residual_a=max_kcl_residual_a,
                    max_kvl_residual_v=max_kvl_residual_v,
                    cumulative_delivered_energy_j=cumulative_delivered_energy_j,
                    cumulative_cell_heat_j=cumulative_cell_heat_j,
                    cumulative_connection_loss_j=cumulative_connection_loss_j,
                    soc_by_cell_id=soc_by_cell_id,
                    primary_rc_voltage_by_cell_id=primary_rc_voltage_by_cell_id,
                    secondary_rc_voltage_by_cell_id=secondary_rc_voltage_by_cell_id,
                    cell_current_by_cell_id=last_cell_currents,
                    connection_current_by_connection_id=last_connection_currents,
                    trace_points=trace_points,
                )

            node_voltage = {reference_id: 0.0}
            for node_id, index in node_index.items():
                node_voltage[node_id] = float(solved_voltages[index])

            if len(solved_voltages) > 0:
                max_kcl_residual_a = max(
                    max_kcl_residual_a,
                    float(numpy.max(numpy.abs((matrix @ solved_voltages) - current_vector))),
                )

            last_pack_voltage = node_voltage[pack_positive_net_id] - node_voltage[reference_id]
            if (elapsed_steps + 1) == required_step_count:
                required_pack_voltage = last_pack_voltage

            last_total_connection_loss_w = 0.0
            connection_current_by_connection_id: dict[int, float] = {}
            for connection in state.connections:
                if connection.ideal:
                    connection_current_by_connection_id[connection.connection_id] = 0.0
                    continue
                from_node_id = ideal_dsu.find(connection.from_terminal_id)
                to_node_id = ideal_dsu.find(connection.to_terminal_id)
                if from_node_id == to_node_id:
                    connection_current_by_connection_id[connection.connection_id] = 0.0
                    continue
                connection_current_a = (node_voltage[from_node_id] - node_voltage[to_node_id]) / max(
                    connection.resistance_ohm,
                    1.0e-12,
                )
                connection_current_by_connection_id[connection.connection_id] = connection_current_a
                max_connection_current_a = max(max_connection_current_a, abs(connection_current_a))
                last_total_connection_loss_w += (connection_current_a**2) * connection.resistance_ohm

            total_cell_heat_w = 0.0
            step_min_cell_voltage_v = float("inf")
            step_max_cell_current_a = 0.0
            cell_current_by_cell_id: dict[int, float] = {}
            cell_voltage_failure = False
            for cell in state.cells:
                (
                    open_circuit_voltage_v,
                    series_resistance_ohm,
                    transient_resistance_ohm,
                    transient_capacitance_f,
                    secondary_transient_resistance_ohm,
                    secondary_transient_capacitance_f,
                ) = cell_parameters[cell.cell_id]
                del transient_capacitance_f, secondary_transient_capacitance_f
                positive_node_id = ideal_dsu.find(cell.positive_terminal_id)
                negative_node_id = ideal_dsu.find(cell.negative_terminal_id)
                terminal_voltage = node_voltage[positive_node_id] - node_voltage[negative_node_id]
                effective_open_circuit_voltage = (
                    open_circuit_voltage_v
                    - primary_rc_voltage_by_cell_id[cell.cell_id]
                    - secondary_rc_voltage_by_cell_id[cell.cell_id]
                )
                current_positive_to_negative = (
                    terminal_voltage - effective_open_circuit_voltage
                ) / series_resistance_ohm
                discharge_current = -current_positive_to_negative
                cell_current_by_cell_id[cell.cell_id] = discharge_current
                max_cell_current_a = max(max_cell_current_a, abs(discharge_current))
                step_max_cell_current_a = max(step_max_cell_current_a, abs(discharge_current))
                min_cell_voltage_v = min(min_cell_voltage_v, terminal_voltage)
                step_min_cell_voltage_v = min(step_min_cell_voltage_v, terminal_voltage)
                total_cell_heat_w += (discharge_current**2) * max(
                    series_resistance_ohm + transient_resistance_ohm + secondary_transient_resistance_ohm,
                    1.0e-9,
                )
                max_kvl_residual_v = max(
                    max_kvl_residual_v,
                    abs(
                        terminal_voltage
                        - (effective_open_circuit_voltage - (discharge_current * series_resistance_ohm))
                    ),
                )
                if terminal_voltage + 1.0e-9 < CELL_SPEC_18650.min_voltage_v:
                    cell_voltage_failure = True

            trace_points.append(
                BatteryCircuitTracePoint(
                    time_s=float(elapsed_steps),
                    pack_current_a=pack_current_a,
                    pack_terminal_voltage_v=last_pack_voltage,
                    min_cell_voltage_v=(
                        step_min_cell_voltage_v
                        if step_min_cell_voltage_v != float("inf")
                        else CELL_SPEC_18650.nominal_voltage_v
                    ),
                    max_cell_current_a=step_max_cell_current_a,
                    total_connection_loss_w=last_total_connection_loss_w,
                    total_cell_heat_w=total_cell_heat_w,
                    cell_temperature_c=cell_temperature_c,
                    delivered_capacity_ah=delivered_capacity_ah,
                )
            )

            if cell_voltage_failure:
                delivered_after_step = delivered_capacity_ah + max(pack_current_a, 0.0) / 3600.0
                return _build_simulation_result(
                    pack_terminal_voltage_end=last_pack_voltage,
                    required_pack_terminal_voltage_end=required_pack_voltage,
                    delivered_capacity_ah=delivered_after_step,
                    max_cell_current_a=max_cell_current_a,
                    min_cell_voltage_v=min_cell_voltage_v,
                    total_connection_loss_w=last_total_connection_loss_w,
                    max_connection_current_a=max_connection_current_a,
                    solver_steps=elapsed_steps + 1,
                    is_feasible=(simulate_to_failure and (elapsed_steps + 1) > required_step_count),
                    failure_reason=(
                        None
                        if simulate_to_failure and (elapsed_steps + 1) > required_step_count
                        else "A cell dropped below the minimum allowable voltage."
                    ),
                    end_cell_temperature_c=cell_temperature_c,
                    max_cell_temperature_c=max_cell_temperature_c,
                    max_kcl_residual_a=max_kcl_residual_a,
                    max_kvl_residual_v=max_kvl_residual_v,
                    cumulative_delivered_energy_j=cumulative_delivered_energy_j,
                    cumulative_cell_heat_j=cumulative_cell_heat_j,
                    cumulative_connection_loss_j=cumulative_connection_loss_j,
                    soc_by_cell_id=soc_by_cell_id,
                    primary_rc_voltage_by_cell_id=primary_rc_voltage_by_cell_id,
                    secondary_rc_voltage_by_cell_id=secondary_rc_voltage_by_cell_id,
                    cell_current_by_cell_id=cell_current_by_cell_id,
                    connection_current_by_connection_id=connection_current_by_connection_id,
                    trace_points=trace_points,
                )

            depleted = False
            next_soc_by_cell_id = dict(soc_by_cell_id)
            next_primary_rc_voltage_by_cell_id = dict(primary_rc_voltage_by_cell_id)
            next_secondary_rc_voltage_by_cell_id = dict(secondary_rc_voltage_by_cell_id)
            for cell in state.cells:
                (
                    _open_circuit_voltage_v,
                    _series_resistance_ohm,
                    transient_resistance_ohm,
                    transient_capacitance_f,
                    secondary_transient_resistance_ohm,
                    secondary_transient_capacitance_f,
                ) = cell_parameters[cell.cell_id]
                discharge_current = cell_current_by_cell_id[cell.cell_id]
                soc_delta = discharge_current / (capacity_ah * 3600.0)
                next_soc = min(1.0, max(0.0, soc_by_cell_id[cell.cell_id] - soc_delta))
                next_soc_by_cell_id[cell.cell_id] = next_soc
                next_primary_rc_voltage_by_cell_id[cell.cell_id] = _advance_rc_branch_voltage(
                    primary_rc_voltage_by_cell_id[cell.cell_id],
                    discharge_current,
                    transient_resistance_ohm,
                    transient_capacitance_f,
                )
                next_secondary_rc_voltage_by_cell_id[cell.cell_id] = _advance_rc_branch_voltage(
                    secondary_rc_voltage_by_cell_id[cell.cell_id],
                    discharge_current,
                    secondary_transient_resistance_ohm,
                    secondary_transient_capacitance_f,
                )
                depleted = depleted or (next_soc <= 1.0e-9)

            delivered_capacity_ah += max(pack_current_a, 0.0) / 3600.0
            cumulative_delivered_energy_j += max(pack_current_a * last_pack_voltage, 0.0)
            cumulative_cell_heat_j += total_cell_heat_w
            cumulative_connection_loss_j += last_total_connection_loss_w
            soc_by_cell_id = next_soc_by_cell_id
            primary_rc_voltage_by_cell_id = next_primary_rc_voltage_by_cell_id
            secondary_rc_voltage_by_cell_id = next_secondary_rc_voltage_by_cell_id
            last_cell_currents = cell_current_by_cell_id
            last_connection_currents = connection_current_by_connection_id

            if depleted:
                return _build_simulation_result(
                    pack_terminal_voltage_end=last_pack_voltage,
                    required_pack_terminal_voltage_end=required_pack_voltage,
                    delivered_capacity_ah=delivered_capacity_ah,
                    max_cell_current_a=max_cell_current_a,
                    min_cell_voltage_v=min_cell_voltage_v,
                    total_connection_loss_w=last_total_connection_loss_w,
                    max_connection_current_a=max_connection_current_a,
                    solver_steps=elapsed_steps + 1,
                    is_feasible=((elapsed_steps + 1) >= required_step_count),
                    failure_reason=(
                        None
                        if (elapsed_steps + 1) >= required_step_count
                        else "A cell depleted before the required discharge duration completed."
                    ),
                    end_cell_temperature_c=cell_temperature_c,
                    max_cell_temperature_c=max_cell_temperature_c,
                    max_kcl_residual_a=max_kcl_residual_a,
                    max_kvl_residual_v=max_kvl_residual_v,
                    cumulative_delivered_energy_j=cumulative_delivered_energy_j,
                    cumulative_cell_heat_j=cumulative_cell_heat_j,
                    cumulative_connection_loss_j=cumulative_connection_loss_j,
                    soc_by_cell_id=soc_by_cell_id,
                    primary_rc_voltage_by_cell_id=primary_rc_voltage_by_cell_id,
                    secondary_rc_voltage_by_cell_id=secondary_rc_voltage_by_cell_id,
                    cell_current_by_cell_id=cell_current_by_cell_id,
                    connection_current_by_connection_id=connection_current_by_connection_id,
                    trace_points=trace_points,
                )

            if thermal_mode == "lumped" and thermal_priors is not None:
                pack_conductance_w_per_k = _effective_lumped_pack_conductance_w_per_k(
                    thermal_priors,
                    cell_count=len(state.cells),
                )
                pack_thermal_mass_j_per_k = _effective_lumped_pack_thermal_mass_j_per_k(
                    thermal_priors,
                    cell_count=len(state.cells),
                )
                total_pack_heat_w = total_cell_heat_w + last_total_connection_loss_w
                cell_temperature_c += (
                    total_pack_heat_w - (pack_conductance_w_per_k * (cell_temperature_c - ambient_temperature_c))
                ) / max(pack_thermal_mass_j_per_k, 1.0)
                max_cell_temperature_c = max(max_cell_temperature_c, cell_temperature_c)

            elapsed_steps += 1

    return _build_simulation_result(
        pack_terminal_voltage_end=last_pack_voltage,
        required_pack_terminal_voltage_end=required_pack_voltage,
        delivered_capacity_ah=delivered_capacity_ah,
        max_cell_current_a=max_cell_current_a,
        min_cell_voltage_v=min_cell_voltage_v,
        total_connection_loss_w=last_total_connection_loss_w,
        max_connection_current_a=max_connection_current_a,
        solver_steps=total_profile_steps,
        is_feasible=True,
        failure_reason=None,
        end_cell_temperature_c=cell_temperature_c,
        max_cell_temperature_c=max_cell_temperature_c,
        max_kcl_residual_a=max_kcl_residual_a,
        max_kvl_residual_v=max_kvl_residual_v,
        cumulative_delivered_energy_j=cumulative_delivered_energy_j,
        cumulative_cell_heat_j=cumulative_cell_heat_j,
        cumulative_connection_loss_j=cumulative_connection_loss_j,
        soc_by_cell_id=soc_by_cell_id,
        primary_rc_voltage_by_cell_id=primary_rc_voltage_by_cell_id,
        secondary_rc_voltage_by_cell_id=secondary_rc_voltage_by_cell_id,
        cell_current_by_cell_id=last_cell_currents,
        connection_current_by_connection_id=last_connection_currents,
        trace_points=trace_points,
    )


def _segment_step_count(duration_s: float) -> int:
    """Return the integer step count used for one profile segment."""
    return max(1, ceil(float(duration_s)))


def _advance_rc_branch_voltage(
    rc_voltage_v: float,
    current_a: float,
    resistance_ohm: float,
    capacitance_f: float,
) -> float:
    """Advance one RC overpotential state over a one-second interval."""
    if resistance_ohm <= 1.0e-12 or capacitance_f <= 1.0e-12:
        return 0.0
    tau_seconds = resistance_ohm * capacitance_f
    alpha = 0.0 if tau_seconds <= 1.0e-12 else exp(-1.0 / tau_seconds)
    return (alpha * rc_voltage_v) + ((1.0 - alpha) * current_a * resistance_ohm)


def _build_simulation_result(
    *,
    pack_terminal_voltage_end: float,
    required_pack_terminal_voltage_end: float,
    delivered_capacity_ah: float,
    max_cell_current_a: float,
    min_cell_voltage_v: float,
    total_connection_loss_w: float,
    max_connection_current_a: float,
    solver_steps: int,
    is_feasible: bool,
    failure_reason: str | None,
    end_cell_temperature_c: float,
    max_cell_temperature_c: float,
    max_kcl_residual_a: float,
    max_kvl_residual_v: float,
    cumulative_delivered_energy_j: float,
    cumulative_cell_heat_j: float,
    cumulative_connection_loss_j: float,
    soc_by_cell_id: dict[int, float],
    primary_rc_voltage_by_cell_id: dict[int, float],
    secondary_rc_voltage_by_cell_id: dict[int, float],
    cell_current_by_cell_id: dict[int, float],
    connection_current_by_connection_id: dict[int, float],
    trace_points: list[BatteryCircuitTracePoint],
) -> BatteryCircuitSimulationResult:
    """Build one normalized simulation result payload."""
    return BatteryCircuitSimulationResult(
        pack_terminal_voltage_end=pack_terminal_voltage_end,
        required_pack_terminal_voltage_end=required_pack_terminal_voltage_end,
        delivered_capacity_ah=delivered_capacity_ah,
        max_cell_current_a=max_cell_current_a,
        min_cell_voltage_v=0.0 if min_cell_voltage_v == float("inf") else min_cell_voltage_v,
        total_connection_loss_w=total_connection_loss_w,
        max_connection_current_a=max_connection_current_a,
        solver_steps=solver_steps,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        end_cell_temperature_c=end_cell_temperature_c,
        max_cell_temperature_c=max_cell_temperature_c,
        max_kcl_residual_a=max_kcl_residual_a,
        max_kvl_residual_v=max_kvl_residual_v,
        cumulative_delivered_energy_j=cumulative_delivered_energy_j,
        cumulative_cell_heat_j=cumulative_cell_heat_j,
        cumulative_connection_loss_j=cumulative_connection_loss_j,
        end_soc_by_cell_id=tuple(sorted(soc_by_cell_id.items())),
        end_primary_rc_voltage_by_cell_id=tuple(sorted(primary_rc_voltage_by_cell_id.items())),
        end_secondary_rc_voltage_by_cell_id=tuple(sorted(secondary_rc_voltage_by_cell_id.items())),
        end_cell_current_by_cell_id=tuple(sorted(cell_current_by_cell_id.items())),
        end_connection_current_by_connection_id=tuple(sorted(connection_current_by_connection_id.items())),
        trace=tuple(trace_points),
    )


def evaluate_battery_circuit(
    state: BatteryCircuitState,
    requirements: BatteryRequirements,
    load_cell_model: Callable[[], BatteryCellModel],
    *,
    simulate_to_failure: bool = False,
    backend_config: BatteryBackendConfig | None = None,
) -> BatteryCircuitEvaluation:
    """Evaluate one explicit battery circuit using deterministic checks and the shared solver.

    Args:
        state: Value for ``state``.
        requirements: Value for ``requirements``.
        load_cell_model: Value for ``load_cell_model``.
        simulate_to_failure: Value for ``simulate_to_failure``.
        backend_config: Value for ``backend_config``.

    Returns:
        Computed result for this callable.
    """
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
            cell_model_mode=None,
            cell_model_parameter_set=None,
            simulation=None,
            is_feasible=False,
            failure_reason=validation_failure,
            thermal_mode=None,
        )

    resolved_backend_config = resolve_battery_backend_config(backend_config)
    cell_model_source: str | None
    cell_model_warning: str | None
    cell_model_mode: str | None
    cell_model_parameter_set: str | None
    if resolved_backend_config.cell_model_mode == "pybamm_direct":
        simulation, cell_model_source, cell_model_parameter_set = _simulate_battery_circuit_pybamm_direct(
            state,
            requirements,
            analysis,
            simulate_to_failure=simulate_to_failure,
            backend_config=resolved_backend_config,
        )
        cell_model_warning = None
        cell_model_mode = resolved_backend_config.cell_model_mode
    else:
        cell_model = load_cell_model() if backend_config is None else load_battery_cell_model(resolved_backend_config)
        thermal_priors = (
            load_battery_thermal_priors(resolved_backend_config)
            if resolved_backend_config.thermal_mode == "lumped"
            else None
        )
        simulation = simulate_battery_circuit(
            state,
            requirements,
            cell_model,
            simulate_to_failure=simulate_to_failure,
            backend_config=resolved_backend_config,
            thermal_priors=thermal_priors,
        )
        cell_model_source = cell_model.source
        cell_model_warning = cell_model.warning_message
        cell_model_mode = cell_model.resolved_mode
        cell_model_parameter_set = cell_model.resolved_parameter_set
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
    if is_feasible and simulation.required_pack_terminal_voltage_end + 1.0e-9 < required_voltage_floor:
        is_feasible = False
        failure_reason = "Pack terminal voltage fell below the minimum required floor."

    return _evaluation_from_parts(
        layout=layout,
        state=state,
        analysis=analysis,
        pack_nominal_voltage=pack_nominal_voltage,
        pybamm_ran=True,
        cell_model_source=cell_model_source,
        cell_model_warning=cell_model_warning,
        cell_model_mode=cell_model_mode,
        cell_model_parameter_set=cell_model_parameter_set,
        simulation=simulation,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        thermal_mode=resolved_backend_config.thermal_mode,
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
    cell_model_mode: str | None,
    cell_model_parameter_set: str | None,
    simulation: BatteryCircuitSimulationResult | None,
    is_feasible: bool,
    failure_reason: str | None,
    thermal_mode: str | None,
) -> BatteryCircuitEvaluation:
    """Build a public evaluation object from layout and simulation pieces.

    Args:
        layout: Value for ``layout``.
        state: Value for ``state``.
        analysis: Value for ``analysis``.
        pack_nominal_voltage: Value for ``pack_nominal_voltage``.
        pybamm_ran: Value for ``pybamm_ran``.
        cell_model_source: Value for ``cell_model_source``.
        cell_model_warning: Value for ``cell_model_warning``.
        cell_model_mode: Value for ``cell_model_mode``.
        cell_model_parameter_set: Value for ``cell_model_parameter_set``.
        simulation: Value for ``simulation``.
        is_feasible: Whether to feasible.
        failure_reason: Value for ``failure_reason``.
        thermal_mode: Resolved thermal mode used for the evaluation.

    Returns:
        Computed result for this callable.
    """
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
        total_connection_loss_w=None if simulation is None else simulation.total_connection_loss_w,
        max_connection_current_a=None if simulation is None else simulation.max_connection_current_a,
        solver_steps=0 if simulation is None else simulation.solver_steps,
        pybamm_ran=pybamm_ran,
        topology_kind=analysis.topology_kind,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
        cell_model_source=cell_model_source,
        cell_model_warning=cell_model_warning,
        cell_model_mode=cell_model_mode,
        cell_model_parameter_set=cell_model_parameter_set,
        end_cell_temperature_c=None if simulation is None else simulation.end_cell_temperature_c,
        max_cell_temperature_c=None if simulation is None else simulation.max_cell_temperature_c,
        thermal_mode=thermal_mode,
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
    """Stamp one resistor into the conductance matrix.

    Args:
        matrix: Value for ``matrix``.
        current_vector: Value for ``current_vector``.
        node_index: Value for ``node_index``.
        reference_id: Identifier for reference.
        node_a: Value for ``node_a``.
        node_b: Value for ``node_b``.
        conductance: Value for ``conductance``.
    """
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
    """Stamp one current source into the RHS vector.

    Args:
        current_vector: Value for ``current_vector``.
        node_index: Value for ``node_index``.
        reference_id: Identifier for reference.
        from_node: Value for ``from_node``.
        to_node: Value for ``to_node``.
        current_a: Value for ``current_a``.
    """
    if from_node != reference_id:
        current_vector[node_index[from_node]] -= current_a
    if to_node != reference_id:
        current_vector[node_index[to_node]] += current_a
