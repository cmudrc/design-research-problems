"""Shared backend helpers for IoT home cooling grammar states and evaluation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal

import numpy

type IoTHomeProductType = Literal["d", "s", "e", "j"]
"""Supported IoT product type labels.

- ``d``: processor/decision maker
- ``s``: temperature sensor
- ``e``: cooler/effector
- ``j``: junction
"""


@dataclass(frozen=True)
class IoTHouseRoom:
    """One fixed room polygon and envelope constants in the house model."""

    room_id: int
    """1-based room identifier."""
    name: str
    """Human-readable room label."""
    x: tuple[float, ...]
    """Ordered polygon x coordinates in feet."""
    y: tuple[float, ...]
    """Ordered polygon y coordinates in feet."""
    exterior_area_m2: float
    """Exterior wall area exposed to outdoor temperature, in square meters."""
    volume_m3: float
    """Room air volume, in cubic meters."""


@dataclass(frozen=True)
class IoTHouseDoor:
    """One fixed directed door relation between two rooms."""

    door_id: int
    """1-based door identifier."""
    room1_id: int
    """Source room identifier used in the original airflow matrix."""
    room2_id: int
    """Sink room identifier used in the original airflow matrix."""


@dataclass(frozen=True)
class IoTHouseGeometry:
    """Fixed house geometry and linear-flow metadata used for evaluation."""

    rooms: tuple[IoTHouseRoom, ...]
    """Room geometry records in deterministic order."""
    doors: tuple[IoTHouseDoor, ...]
    """Door definitions in deterministic order."""
    airflow_matrix: tuple[tuple[float, ...], ...]
    """Door-flow coefficient matrix used by the linear airflow solve."""
    doors_in_by_room: tuple[tuple[int, ...], ...]
    """Per-room door IDs that are incoming in the directed door graph."""
    doors_out_by_room: tuple[tuple[int, ...], ...]
    """Per-room door IDs that are outgoing in the directed door graph."""
    leak_fraction: tuple[float, ...]
    """Fraction of total leak-out assigned to each room."""


@dataclass(frozen=True)
class IoTHomeProduct:
    """Serializable IoT product record."""

    name: str
    """Stable product identifier."""
    product_type: IoTHomeProductType
    """Product type label."""
    x: float
    """x coordinate in house floorplan units (feet)."""
    y: float
    """y coordinate in house floorplan units (feet)."""
    room_id: int | None = None
    """1-based room index, or ``0`` when outside, or ``None`` to recompute."""
    dm_name: str | None = None
    """Owning decision-maker name for junction products."""
    btus: float = 10_000.0
    """Cooler capacity in BTU/h for effector products."""
    cfm: float = 200.0
    """Cooler volumetric flow rate in CFM for effector products."""
    eff: float = 0.7
    """Cooling effectiveness factor used by the legacy model."""
    target_c: float = 20.0
    """Product-local target temperature in Celsius."""


@dataclass(frozen=True)
class IoTHomeLink:
    """Serializable undirected link between two IoT products."""

    name: str
    """Stable link identifier."""
    init_name: str
    """One endpoint product name."""
    term_name: str
    """Other endpoint product name."""


@dataclass(frozen=True)
class IoTHomeState:
    """Serializable IoT home-cooling grammar state."""

    products: tuple[IoTHomeProduct, ...]
    """All products in the current network design."""
    links: tuple[IoTHomeLink, ...]
    """All links in the current network design."""
    house_geometry: IoTHouseGeometry
    """Fixed house geometry used by the evaluator."""
    external_temps_c: tuple[float, ...]
    """Outdoor-temperature profile over the simulation horizon."""
    decider_cost: float = 10.0
    """Capital cost per processor/decision-maker."""
    sensor_cost: float = 30.0
    """Capital cost per sensor."""
    junction_cost: float = 50.0
    """Capital cost per junction."""
    junction_discount: float = 15.0
    """Capital-cost discount for sensor/cooler connected only through junctions."""
    ac_cost_coefficients: tuple[float, float, float] = (200.0, 0.2, 0.02)
    """Linear cooler capital-cost coefficients ``[base, cfm, btus]``."""
    target_c: float = 20.0
    """Decision threshold for turning coolers on."""
    delta_t_s: float = 360.0
    """Simulation step duration in seconds."""
    cost_of_energy_per_kwh: float = 0.12
    """Electricity price in USD per kWh."""
    eer: float = 10.0
    """Cooling Energy Efficiency Ratio."""
    lifetime_years: float = 10.0
    """Amortization period in years."""


@dataclass(frozen=True)
class IoTHomeEvaluation:
    """Structured evaluation result for one IoT home-cooling design."""

    total_cost: float
    """Total lifecycle cost (capital + operation), in USD."""
    peak_temp_c: float
    """Peak post-warmup room temperature across all rooms, in Celsius."""
    capital_cost: float
    """Capital installation cost, in USD."""
    operation_cost: float
    """Estimated lifetime operating cost, in USD."""
    discomfort: float
    """Max absolute post-warmup temperature deviation from 20C, in Celsius."""
    is_feasible: bool
    """Whether the design passed basic structural validity checks."""
    failure_reason: str | None = None
    """Optional reason when ``is_feasible`` is ``False``."""


@dataclass
class _RuntimeProduct:
    """Mutable product used during one simulation run."""

    name: str
    product_type: IoTHomeProductType
    room_id: int
    dm_name: str | None
    btus: float
    cfm: float
    eff: float
    target_c: float
    temperatures: list[float]
    onoff: int
    strength: float


@dataclass
class _RuntimeRoom:
    """Mutable room state used during one simulation run."""

    temperature: float
    air_flow_in: float
    air_flow_out: float
    air_temp_in: float
    heat_flow_in: float


@dataclass
class _RuntimeDoor:
    """Mutable door state used during one simulation run."""

    air_flow: float


_CONVERT_FOOT_TO_METER = 0.3048
_INITIAL_INTERNAL_TEMPERATURE_C = 30.0
_AIR_DENSITY = 1.225
_AIR_SPECIFIC_HEAT = 1.005
_U_VALUE = 4.0 / 1000.0
_MAX_TEMP_CHANGE_PER_STEP = 1.0
_COOLER_CFM_TO_M3S = 0.0004719474
_COOLER_BTUH_TO_KW = 0.00029307103866


def _default_external_temps() -> tuple[float, ...]:
    """Build the legacy outdoor-temperature profile used by the MATLAB model.

    Returns:
        Deterministic 300-step outdoor-temperature profile.
    """
    steps = numpy.arange(1, int(1.25 * 24 * 10) + 1, dtype=float)
    temps = 25.0 + 5.0 * numpy.sin((steps / (24.0 * 10.0)) * 2.0 * numpy.pi)
    return tuple(float(value) for value in temps)


DEFAULT_EXTERNAL_TEMPS_C = _default_external_temps()
"""Legacy default outdoor-temperature profile."""


def _polygon_area(x_values: tuple[float, ...], y_values: tuple[float, ...]) -> float:
    """Compute polygon area with the shoelace formula.

    Args:
        x_values: Polygon x coordinates.
        y_values: Polygon y coordinates.

    Returns:
        Non-negative polygon area in square feet.
    """
    x_array = numpy.asarray(x_values, dtype=float)
    y_array = numpy.asarray(y_values, dtype=float)
    return 0.5 * abs(
        float(numpy.dot(x_array, numpy.roll(y_array, -1)) - numpy.dot(y_array, numpy.roll(x_array, -1)))
    )


def _segment_contains_point(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    px: float,
    py: float,
    *,
    atol: float = 1e-9,
) -> bool:
    """Return whether a point lies on a line segment within tolerance.

    Args:
        x0: Segment start x.
        y0: Segment start y.
        x1: Segment end x.
        y1: Segment end y.
        px: Point x.
        py: Point y.
        atol: Absolute tolerance for collinearity and bounds checks.

    Returns:
        ``True`` when the point lies on the segment.
    """
    cross = (px - x0) * (y1 - y0) - (py - y0) * (x1 - x0)
    if abs(cross) > atol:
        return False
    dot = (px - x0) * (px - x1) + (py - y0) * (py - y1)
    return dot <= atol


def _point_in_polygon(x: float, y: float, polygon_x: tuple[float, ...], polygon_y: tuple[float, ...]) -> bool:
    """Return whether a point is inside or on the boundary of a polygon.

    Args:
        x: Point x coordinate.
        y: Point y coordinate.
        polygon_x: Polygon x coordinates.
        polygon_y: Polygon y coordinates.

    Returns:
        ``True`` when the point lies inside or on the polygon boundary.
    """
    inside = False
    count = len(polygon_x)
    for index in range(count):
        x0 = polygon_x[index]
        y0 = polygon_y[index]
        x1 = polygon_x[(index + 1) % count]
        y1 = polygon_y[(index + 1) % count]

        if _segment_contains_point(x0, y0, x1, y1, x, y):
            return True

        intersects = (y0 > y) != (y1 > y)
        if not intersects:
            continue
        if abs(y1 - y0) < 1e-12:
            continue
        x_at_y = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
        if x < x_at_y:
            inside = not inside
    return inside


def _build_default_house_geometry() -> IoTHouseGeometry:
    """Build the fixed house geometry used by legacy IoT studies.

    Returns:
        Immutable house geometry with precomputed flow and leak metadata.
    """
    height_ft = 10.0

    room_specs = (
        (1, "Room 3", (0.0, 13.0, 13.0, 0.0), (0.0, 0.0, 12.0, 12.0), 8.0 + 12.0 + 13.0),
        (2, "Room 1", (0.0, 13.0, 13.0, 0.0), (32.0, 32.0, 42.0, 42.0), 13.0 + 10.0),
        (3, "Room 2", (0.0, 13.0, 13.0, 0.0), (12.0, 12.0, 32.0, 32.0), 20.0),
        (4, "Room 4", (13.0, 25.0, 25.0, 13.0), (8.0, 8.0, 22.0, 22.0), 12.0 + 2.0),
        (5, "Room 6", (33.0, 45.0, 45.0, 33.0), (8.0, 8.0, 22.0, 22.0), 12.0 + 2.0),
        (6, "Room 5", (25.0, 33.0, 33.0, 25.0), (10.0, 10.0, 22.0, 22.0), 8.0),
        (7, "Room 7", (13.0, 33.0, 33.0, 13.0), (22.0, 22.0, 42.0, 42.0), 20.0),
        (8, "Room 8", (33.0, 47.0, 47.0, 33.0), (26.0, 26.0, 42.0, 42.0), 14.0),
        (9, "Hallway", (33.0, 51.0, 51.0, 47.0, 47.0, 33.0), (22.0, 22.0, 42.0, 42.0, 26.0, 26.0), 0.0),
        (10, "Room 9", (45.0, 65.0, 65.0, 45.0), (0.0, 0.0, 22.0, 22.0), 8.0 + 20.0 + 22.0),
        (11, "Room 10", (51.0, 65.0, 65.0, 51.0), (22.0, 22.0, 32.0, 32.0), 10.0),
        (12, "Room 11", (51.0, 65.0, 65.0, 51.0), (32.0, 32.0, 42.0, 42.0), 10.0),
        (13, "Room 12", (47.0, 65.0, 65.0, 47.0), (42.0, 42.0, 48.0, 48.0), 18.0 + 6.0 + 6.0),
    )
    rooms: list[IoTHouseRoom] = []
    for room_id, name, x_coords, y_coords, exterior_length_ft in room_specs:
        area_ft2 = _polygon_area(x_coords, y_coords)
        rooms.append(
            IoTHouseRoom(
                room_id=room_id,
                name=name,
                x=x_coords,
                y=y_coords,
                exterior_area_m2=exterior_length_ft * height_ft * (_CONVERT_FOOT_TO_METER**2),
                volume_m3=area_ft2 * height_ft * (_CONVERT_FOOT_TO_METER**3),
            )
        )

    doors = (
        IoTHouseDoor(door_id=1, room1_id=1, room2_id=3),
        IoTHouseDoor(door_id=2, room1_id=2, room2_id=3),
        IoTHouseDoor(door_id=3, room1_id=3, room2_id=7),
        IoTHouseDoor(door_id=4, room1_id=4, room2_id=7),
        IoTHouseDoor(door_id=5, room1_id=7, room2_id=6),
        IoTHouseDoor(door_id=6, room1_id=8, room2_id=7),
        IoTHouseDoor(door_id=7, room1_id=9, room2_id=7),
        IoTHouseDoor(door_id=8, room1_id=5, room2_id=9),
        IoTHouseDoor(door_id=9, room1_id=10, room2_id=9),
        IoTHouseDoor(door_id=10, room1_id=11, room2_id=9),
        IoTHouseDoor(door_id=11, room1_id=12, room2_id=9),
        IoTHouseDoor(door_id=12, room1_id=13, room2_id=9),
    )

    room_count = len(rooms)
    door_count = len(doors)
    matrix = numpy.zeros((room_count, door_count), dtype=float)
    doors_in: list[list[int]] = [[] for _ in rooms]
    doors_out: list[list[int]] = [[] for _ in rooms]
    for door in doors:
        matrix[door.room1_id - 1, door.door_id - 1] = 1.0
        matrix[door.room2_id - 1, door.door_id - 1] = -1.0
        doors_out[door.room1_id - 1].append(door.door_id)
        doors_in[door.room2_id - 1].append(door.door_id)

    volumes = numpy.asarray([room.volume_m3 for room in rooms], dtype=float)
    leak_fraction = volumes / float(numpy.sum(volumes))

    return IoTHouseGeometry(
        rooms=tuple(rooms),
        doors=doors,
        airflow_matrix=tuple(tuple(float(entry) for entry in row) for row in matrix),
        doors_in_by_room=tuple(tuple(entries) for entries in doors_in),
        doors_out_by_room=tuple(tuple(entries) for entries in doors_out),
        leak_fraction=tuple(float(entry) for entry in leak_fraction),
    )


DEFAULT_IOT_HOUSE_GEOMETRY = _build_default_house_geometry()
"""Fixed house geometry used by legacy IoT co-design studies."""


def build_default_iot_home_state() -> IoTHomeState:
    """Build the canonical empty IoT home-cooling state.

    Returns:
        Empty design state with fixed house geometry and legacy constants.
    """
    return IoTHomeState(
        products=(),
        links=(),
        house_geometry=DEFAULT_IOT_HOUSE_GEOMETRY,
        external_temps_c=DEFAULT_EXTERNAL_TEMPS_C,
    )


def find_iot_room_id(house_geometry: IoTHouseGeometry, x: float, y: float) -> int:
    """Return the 1-based room index containing one point.

    Args:
        house_geometry: Fixed house geometry.
        x: Point x coordinate.
        y: Point y coordinate.

    Returns:
        Room index, or ``0`` when the point lies outside the house polygons.
    """
    found_room = 0
    for room in house_geometry.rooms:
        if _point_in_polygon(x, y, room.x, room.y):
            found_room = room.room_id
    return found_room


def iot_link_exists(links: tuple[IoTHomeLink, ...], product_a: str, product_b: str) -> bool:
    """Return whether an undirected link already exists between two products.

    Args:
        links: Existing links.
        product_a: First endpoint name.
        product_b: Second endpoint name.

    Returns:
        ``True`` when a link already connects ``product_a`` and ``product_b``.
    """
    for link in links:
        if (link.init_name == product_a and link.term_name == product_b) or (
            link.init_name == product_b and link.term_name == product_a
        ):
            return True
    return False


def iot_link_pair_is_legal(type_a: IoTHomeProductType, type_b: IoTHomeProductType) -> bool:
    """Return whether a direct link between two product types is legal.

    Args:
        type_a: First product type.
        type_b: Second product type.

    Returns:
        ``True`` when the pair is allowed under original MATLAB link rules.
    """
    pair = {type_a, type_b}
    if pair == {"e", "s"}:
        return False
    if pair == {"s"}:
        return False
    if pair == {"e"}:
        return False
    return pair != {"j"}


def _build_runtime_products(state: IoTHomeState) -> list[_RuntimeProduct]:
    """Build mutable runtime product records from one serialized state.

    Args:
        state: Input design state.

    Returns:
        Mutable runtime records with resolved room assignments.
    """
    runtime: list[_RuntimeProduct] = []
    for product in state.products:
        room_id = product.room_id if product.room_id is not None else 0
        if product.product_type in {"s", "e"} and product.room_id is None:
            room_id = find_iot_room_id(state.house_geometry, product.x, product.y)
        runtime.append(
            _RuntimeProduct(
                name=product.name,
                product_type=product.product_type,
                room_id=room_id,
                dm_name=product.dm_name,
                btus=product.btus,
                cfm=product.cfm,
                eff=product.eff,
                target_c=product.target_c,
                temperatures=[],
                onoff=0,
                strength=0.0,
            )
        )
    return runtime


def _build_runtime_rooms(state: IoTHomeState) -> list[_RuntimeRoom]:
    """Build mutable runtime room records with initial temperatures.

    Args:
        state: Input design state.

    Returns:
        Mutable runtime room records.
    """
    initial_temperature = float(state.external_temps_c[0])
    return [
        _RuntimeRoom(
            temperature=initial_temperature,
            air_flow_in=0.0,
            air_flow_out=0.0,
            air_temp_in=initial_temperature,
            heat_flow_in=0.0,
        )
        for _room in state.house_geometry.rooms
    ]


def _build_runtime_doors(state: IoTHomeState) -> list[_RuntimeDoor]:
    """Build mutable runtime door records.

    Args:
        state: Input design state.

    Returns:
        Mutable runtime door records.
    """
    return [_RuntimeDoor(air_flow=0.0) for _ in state.house_geometry.doors]


def _effector_air_temp_and_flowrate(product: _RuntimeProduct, external_temp_c: float) -> tuple[float, float, float]:
    """Compute effector outlet temperature, flowrate, and effective strength.

    Args:
        product: Runtime effector product.
        external_temp_c: Outdoor temperature at the current step.

    Returns:
        Outlet air temperature in Celsius, volumetric flow in m3/s, and
        strength factor used by the legacy energy model.
    """
    volumetric_flow = product.cfm * _COOLER_CFM_TO_M3S
    mass_flow = volumetric_flow * _AIR_DENSITY
    cooling_kw = product.btus * _COOLER_BTUH_TO_KW
    d_temp = cooling_kw / (_AIR_SPECIFIC_HEAT * mass_flow)

    volumetric_flow *= float(product.onoff)
    outlet_temp = external_temp_c - product.eff * float(product.onoff) * d_temp
    floor_temp = max(0.7 * product.target_c, outlet_temp)

    denominator = outlet_temp - external_temp_c
    strength = 0.0 if abs(denominator) < 1e-12 else (floor_temp - external_temp_c) / denominator

    product.strength = strength
    return floor_temp, volumetric_flow, strength


def _mean_or_nan(values: list[float]) -> float:
    """Return list mean while preserving MATLAB-like empty-list behavior.

    Args:
        values: Numeric values to average.

    Returns:
        Arithmetic mean, or ``nan`` when the list is empty.
    """
    if not values:
        return float("nan")
    return float(numpy.mean(values))


def _update_flow(
    rooms: list[_RuntimeRoom],
    doors: list[_RuntimeDoor],
    house_geometry: IoTHouseGeometry,
) -> None:
    """Update door airflows from room inflow targets.

    Args:
        rooms: Mutable room state records.
        doors: Mutable door state records.
        house_geometry: Fixed house geometry metadata.
    """
    y = numpy.asarray([room.air_flow_in for room in rooms], dtype=float)
    total_inflow = float(numpy.sum(y))

    for room, leak_fraction in zip(rooms, house_geometry.leak_fraction, strict=True):
        room.air_flow_out = total_inflow * leak_fraction

    rhs = numpy.asarray([room.air_flow_in - room.air_flow_out for room in rooms], dtype=float)
    matrix = numpy.asarray(house_geometry.airflow_matrix, dtype=float)
    flow_vector = numpy.linalg.lstsq(matrix, rhs, rcond=None)[0]
    for door, flow in zip(doors, flow_vector, strict=True):
        door.air_flow = float(flow)


def _update_temperatures(
    rooms: list[_RuntimeRoom],
    doors: list[_RuntimeDoor],
    house_geometry: IoTHouseGeometry,
    *,
    delta_t_s: float,
    external_temp_c: float,
) -> None:
    """Advance room temperatures by one simulation timestep.

    Args:
        rooms: Mutable room state records.
        doors: Mutable door state records.
        house_geometry: Fixed house geometry metadata.
        delta_t_s: Timestep in seconds.
        external_temp_c: Outdoor temperature in Celsius.
    """
    next_temps = numpy.zeros(len(rooms), dtype=float)
    for room_index, room in enumerate(rooms):
        geometry = house_geometry.rooms[room_index]
        numerator = 0.0

        if room.air_flow_in > 0.0:
            numerator += _AIR_DENSITY * _AIR_SPECIFIC_HEAT * room.air_flow_in * room.air_temp_in

        numerator += room.heat_flow_in

        for door_id in house_geometry.doors_in_by_room[room_index]:
            door_index = door_id - 1
            door_geometry = house_geometry.doors[door_index]
            door_flow = doors[door_index].air_flow
            source_temperature = rooms[door_geometry.room1_id - 1].temperature if door_flow > 0.0 else room.temperature
            numerator += door_flow * _AIR_SPECIFIC_HEAT * _AIR_DENSITY * source_temperature

        for door_id in house_geometry.doors_out_by_room[room_index]:
            door_index = door_id - 1
            door_geometry = house_geometry.doors[door_index]
            door_flow = doors[door_index].air_flow
            sink_temperature = room.temperature if door_flow > 0.0 else rooms[door_geometry.room2_id - 1].temperature
            numerator -= door_flow * _AIR_SPECIFIC_HEAT * _AIR_DENSITY * sink_temperature

        numerator += _U_VALUE * geometry.exterior_area_m2 * (external_temp_c - room.temperature)
        numerator -= _AIR_DENSITY * _AIR_SPECIFIC_HEAT * room.air_flow_out * room.temperature

        stored_energy = _AIR_DENSITY * _AIR_SPECIFIC_HEAT * geometry.volume_m3 * room.temperature
        capacity = _AIR_DENSITY * _AIR_SPECIFIC_HEAT * geometry.volume_m3
        next_temps[room_index] = (delta_t_s * numerator + stored_energy) / capacity

    for room_index, new_temp in enumerate(next_temps):
        room = rooms[room_index]
        previous = room.temperature
        blended = 0.25 * float(new_temp) + 0.75 * previous
        delta = blended - previous
        if abs(delta) > _MAX_TEMP_CHANGE_PER_STEP:
            blended = previous + _MAX_TEMP_CHANGE_PER_STEP * numpy.sign(delta)
        room.temperature = float(blended)


def _compute_capital_cost(state: IoTHomeState) -> float:
    """Compute MATLAB-parity capital cost for one design state.

    Args:
        state: Input design state.

    Returns:
        Capital cost in USD.
    """
    capital_cost = 0.0
    product_lookup = {product.name: product for product in state.products}
    for product in state.products:
        if product.product_type == "s":
            capital_cost += state.sensor_cost
        elif product.product_type == "j":
            capital_cost += state.junction_cost
        elif product.product_type == "d":
            capital_cost += state.decider_cost
        elif product.product_type == "e":
            base, cfm_coeff, btus_coeff = state.ac_cost_coefficients
            capital_cost += base + cfm_coeff * product.cfm + btus_coeff * product.btus

    for product in state.products:
        if product.product_type not in {"e", "s"}:
            continue
        connected_only_to_junctions = True
        for link in state.links:
            if link.init_name == product.name:
                other = product_lookup.get(link.term_name)
                if other is not None and other.product_type != "j":
                    connected_only_to_junctions = False
                    break
            if link.term_name == product.name:
                other = product_lookup.get(link.init_name)
                if other is not None and other.product_type != "j":
                    connected_only_to_junctions = False
                    break
        if connected_only_to_junctions:
            capital_cost -= state.junction_discount

    return float(capital_cost)


def _infeasible_evaluation(reason: str) -> IoTHomeEvaluation:
    """Build one standardized infeasible IoT evaluation payload.

    Args:
        reason: Human-readable infeasibility reason.

    Returns:
        Infeasible evaluation with infinite objective terms.
    """
    return IoTHomeEvaluation(
        total_cost=float("inf"),
        peak_temp_c=float("inf"),
        capital_cost=float("inf"),
        operation_cost=float("inf"),
        discomfort=float("inf"),
        is_feasible=False,
        failure_reason=reason,
    )


def evaluate_iot_home_state(state: IoTHomeState) -> IoTHomeEvaluation:
    """Evaluate one IoT home-cooling state with MATLAB-parity mechanics.

    Args:
        state: Serializable IoT design state.

    Returns:
        Deterministic lifecycle-cost and thermal-quality metrics.
    """
    if not state.external_temps_c:
        return _infeasible_evaluation("At least one outdoor-temperature step is required.")

    names = [product.name for product in state.products]
    if len(names) != len(set(names)):
        return _infeasible_evaluation("Product names must be unique.")

    known_names = set(names)
    for link in state.links:
        if link.init_name not in known_names or link.term_name not in known_names:
            return _infeasible_evaluation("All links must reference existing products.")

    products = _build_runtime_products(state)
    rooms = _build_runtime_rooms(state)
    doors = _build_runtime_doors(state)

    name_to_index = {product.name: index for index, product in enumerate(products)}
    dm_to_sensors: list[list[int]] = [[] for _ in products]
    dm_to_effects: list[list[int]] = [[] for _ in products]
    dm_to_dm: list[list[int]] = [[] for _ in products]

    for product_index, product in enumerate(products):
        for link in state.links:
            neighbor_name: str | None = None
            if link.init_name == product.name:
                neighbor_name = link.term_name
            if link.term_name == product.name:
                neighbor_name = link.init_name
            if neighbor_name is None:
                continue

            dm_index = name_to_index[neighbor_name]
            dm_candidate = products[dm_index]
            if dm_candidate.product_type == "d":
                if product.product_type == "s":
                    dm_to_sensors[dm_index].append(product_index)
                elif product.product_type == "e":
                    dm_to_effects[dm_index].append(product_index)
                elif product.product_type == "d":
                    dm_to_dm[dm_index].append(product_index)
            elif dm_candidate.product_type == "j" and dm_candidate.dm_name in name_to_index:
                owner_index = name_to_index[dm_candidate.dm_name]
                if product.product_type == "s":
                    dm_to_sensors[owner_index].append(product_index)
                elif product.product_type == "e":
                    dm_to_effects[owner_index].append(product_index)

    temp_history = numpy.zeros((len(state.external_temps_c), len(rooms)), dtype=float)
    energy = 0.0

    for step_index, external_temp in enumerate(state.external_temps_c):
        for product in products:
            product.temperatures = []
            product.onoff = 0

        if products:
            for dm_index, sensor_indices in enumerate(dm_to_sensors):
                for sensor_index in sensor_indices:
                    sensor = products[sensor_index]
                    if sensor.room_id == 0:
                        products[dm_index].temperatures.append(float(external_temp))
                    else:
                        products[dm_index].temperatures.append(rooms[sensor.room_id - 1].temperature)

            if any(dm_to_dm):
                mean_temps = numpy.zeros(len(products), dtype=float)
                for index, product in enumerate(products):
                    if product.product_type == "d":
                        mean_temps[index] = _mean_or_nan(product.temperatures)

                # Preserve legacy indexing behavior from the MATLAB implementation.
                for dm_index, dm_indices in enumerate(dm_to_dm):
                    for neighbor_order, _neighbor in enumerate(dm_indices):
                        products[dm_index].temperatures.append(float(mean_temps[neighbor_order]))

            for dm_index, effector_indices in enumerate(dm_to_effects):
                if not effector_indices:
                    continue
                if _mean_or_nan(products[dm_index].temperatures) > state.target_c:
                    for effector_index in effector_indices:
                        products[effector_index].onoff = 1

            for room in rooms:
                room.air_flow_in = 0.0

            for product in products:
                if product.product_type != "e":
                    continue
                if product.room_id <= 0 or product.room_id > len(rooms):
                    continue
                air_temp_in, air_flow, strength = _effector_air_temp_and_flowrate(product, float(external_temp))
                room = rooms[product.room_id - 1]
                room.air_flow_in = air_flow
                room.air_temp_in = air_temp_in
                if product.onoff and (step_index + 1) > int(0.25 * 24 * 10):
                    energy += (product.btus * strength / state.eer / 1000.0) * (state.delta_t_s / 3600.0)

        if sum(room.air_flow_in for room in rooms) == 0.0:
            rooms[12].air_flow_in = 0.0001
            rooms[12].air_temp_in = float(external_temp)

        _update_flow(rooms, doors, state.house_geometry)
        _update_temperatures(
            rooms,
            doors,
            state.house_geometry,
            delta_t_s=state.delta_t_s,
            external_temp_c=float(external_temp),
        )
        temp_history[step_index, :] = [room.temperature for room in rooms]

    warmup_start = int(0.25 * 24 * 10) - 1
    steady_state_history = temp_history[warmup_start:, :]
    operation_cost = energy * state.cost_of_energy_per_kwh * 365.0 / 2.0 * 0.8
    operation_cost *= state.lifetime_years
    capital_cost = _compute_capital_cost(state)
    total_cost = operation_cost + capital_cost

    return IoTHomeEvaluation(
        total_cost=float(total_cost),
        peak_temp_c=float(numpy.max(steady_state_history)),
        capital_cost=float(capital_cost),
        operation_cost=float(operation_cost),
        discomfort=float(numpy.max(numpy.abs(steady_state_history - 20.0))),
        is_feasible=True,
    )


def resolve_product_room(state: IoTHomeState, product: IoTHomeProduct) -> IoTHomeProduct:
    """Return a product with room metadata resolved for sensors/effectors.

    Args:
        state: Parent state containing house geometry.
        product: Product to resolve.

    Returns:
        Product unchanged for processors/junctions, or with room ID set for
        sensors/effectors.
    """
    if product.product_type not in {"s", "e"}:
        return product
    return replace(product, room_id=find_iot_room_id(state.house_geometry, product.x, product.y))


__all__ = [
    "DEFAULT_EXTERNAL_TEMPS_C",
    "DEFAULT_IOT_HOUSE_GEOMETRY",
    "IoTHomeEvaluation",
    "IoTHomeLink",
    "IoTHomeProduct",
    "IoTHomeProductType",
    "IoTHomeState",
    "IoTHouseDoor",
    "IoTHouseGeometry",
    "IoTHouseRoom",
    "build_default_iot_home_state",
    "evaluate_iot_home_state",
    "find_iot_room_id",
    "iot_link_exists",
    "iot_link_pair_is_legal",
    "resolve_product_room",
]
