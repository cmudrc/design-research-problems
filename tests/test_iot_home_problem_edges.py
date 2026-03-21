from __future__ import annotations

from dataclasses import replace

import pytest

from design_research_problems import get_problem
from design_research_problems.problems._domains.iot_home import (
    IoTHomeLink,
    IoTHomeProduct,
    IoTHomeState,
    find_iot_room_id,
    resolve_product_room,
)


def _pick_unused_point(problem: object, state: IoTHomeState, *, indoor: bool | None = None) -> tuple[float, float]:
    occupied = {(product.x, product.y) for product in state.products}
    for x_value, y_value in problem.candidate_points:
        if (x_value, y_value) in occupied:
            continue
        room_id = find_iot_room_id(state.house_geometry, x_value, y_value)
        if indoor is True and room_id == 0:
            continue
        if indoor is False and room_id != 0:
            continue
        return (x_value, y_value)
    raise AssertionError("Unable to locate a suitable candidate point for the IoT home test.")


def _build_rich_state() -> tuple[object, IoTHomeState]:
    problem = get_problem("iot_home_cooling_system_design")
    state = problem.initial_state()

    d0_x, d0_y = _pick_unused_point(problem, state)
    state = problem.add_processor(state, x=d0_x, y=d0_y, name="d0")

    d1_x, d1_y = _pick_unused_point(problem, state)
    state = problem.add_processor(state, x=d1_x, y=d1_y, name="d1")

    s0_x, s0_y = _pick_unused_point(problem, state)
    state = problem.add_sensor(state, dm_name="d0", x=s0_x, y=s0_y, name="s0", link_name="l0")

    e0_x, e0_y = _pick_unused_point(problem, state, indoor=True)
    state = problem.add_cooler(
        state,
        dm_name="d0",
        x=e0_x,
        y=e0_y,
        btus=10_000.0,
        cfm=200.0,
        name="e0",
        link_name="l1",
    )
    return (problem, state)


def test_iot_home_enumerate_transitions_exposes_all_public_operations() -> None:
    problem, state = _build_rich_state()

    transitions = problem.enumerate_transitions(state)
    rule_names = {transition.rule_name for transition in transitions}

    assert {
        "add_processor",
        "add_sensor",
        "add_cooler",
        "move_product",
        "delete_product",
        "add_link",
        "delete_link",
        "tune_cooler",
    }.issubset(rule_names)


def test_iot_home_operations_cover_validation_and_junction_rewiring() -> None:
    problem, state = _build_rich_state()
    occupied_x = state.products[0].x
    occupied_y = state.products[0].y
    free_x, free_y = _pick_unused_point(problem, state)
    free_indoor_x, free_indoor_y = _pick_unused_point(problem, state, indoor=True)

    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_processor(state, x=occupied_x, y=occupied_y)
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_processor(state, x=free_x, y=free_y, name="d0")

    with pytest.raises(ValueError, match="existing processor"):
        problem.add_sensor(state, dm_name="missing", x=free_x, y=free_y)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_sensor(state, dm_name="d0", x=occupied_x, y=occupied_y)
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_sensor(state, dm_name="d0", x=free_x, y=free_y, name="d0")

    with pytest.raises(ValueError, match="existing processor"):
        problem.add_cooler(state, dm_name="missing", x=free_indoor_x, y=free_indoor_y, btus=10_000.0, cfm=200.0)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_cooler(state, dm_name="d0", x=occupied_x, y=occupied_y, btus=10_000.0, cfm=200.0)
    with pytest.raises(ValueError, match="outside the home"):
        problem.add_cooler(state, dm_name="d0", x=79.0, y=17.0, btus=10_000.0, cfm=200.0)
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_cooler(
            state,
            dm_name="d0",
            x=free_indoor_x,
            y=free_indoor_y,
            btus=10_000.0,
            cfm=200.0,
            name="e0",
        )

    with pytest.raises(ValueError, match="Unknown product name"):
        problem.move_product(state, product_name="missing", x=free_x, y=free_y)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.move_product(state, product_name="s0", x=occupied_x, y=occupied_y)
    with pytest.raises(ValueError, match="outside the home"):
        problem.move_product(state, product_name="e0", x=79.0, y=17.0)

    with pytest.raises(ValueError, match="Unknown product name"):
        problem.delete_product(state, product_name="missing")

    with pytest.raises(ValueError, match="cannot connect a product to itself"):
        problem.add_link(state, init_name="d0", term_name="d0")
    with pytest.raises(ValueError, match="existing products"):
        problem.add_link(state, init_name="missing", term_name="s0")
    with pytest.raises(ValueError, match="already exists"):
        problem.add_link(state, init_name="d0", term_name="s0")
    with pytest.raises(ValueError, match="not allowed"):
        problem.add_link(state, init_name="s0", term_name="e0")
    with pytest.raises(ValueError, match="Link name already exists"):
        problem.add_link(state, init_name="d1", term_name="s0", link_name="l0")

    with pytest.raises(ValueError, match="Unknown link name"):
        problem.delete_link(state, link_name="missing")

    with pytest.raises(ValueError, match="At least one cooler setting"):
        problem.tune_cooler(state, cooler_name="e0")
    with pytest.raises(ValueError, match="Unsupported BTU/h setting"):
        problem.tune_cooler(state, cooler_name="e0", btus=9_999.0)
    with pytest.raises(ValueError, match="Unsupported CFM setting"):
        problem.tune_cooler(state, cooler_name="e0", cfm=123.0)
    with pytest.raises(ValueError, match="Unknown cooler name"):
        problem.tune_cooler(state, cooler_name="missing", btus=problem.cooler_btus_options[0])
    with pytest.raises(ValueError, match="Only coolers can be tuned"):
        problem.tune_cooler(state, cooler_name="d0", btus=problem.cooler_btus_options[0])

    base_state = problem.initial_state()
    d0_x, d0_y = _pick_unused_point(problem, base_state)
    d0 = IoTHomeProduct(name="d0", product_type="d", x=d0_x, y=d0_y)
    j0_x, j0_y = _pick_unused_point(problem, replace(base_state, products=(d0,)))
    j0 = IoTHomeProduct(name="j0", product_type="j", x=j0_x, y=j0_y, dm_name="d0")
    s0_x, s0_y = _pick_unused_point(problem, replace(base_state, products=(d0, j0)), indoor=True)
    s0 = resolve_product_room(base_state, IoTHomeProduct(name="s0", product_type="s", x=s0_x, y=s0_y))
    junction_state = replace(
        base_state,
        products=(d0, j0, s0),
        links=(
            IoTHomeLink(name="l0", init_name="d0", term_name="j0"),
            IoTHomeLink(name="l1", init_name="j0", term_name="s0"),
        ),
    )
    rewired = problem.delete_product(junction_state, product_name="j0")
    assert any({link.init_name, link.term_name} == {"d0", "s0"} for link in rewired.links)
