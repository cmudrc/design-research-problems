from __future__ import annotations

from dataclasses import replace

import pytest

from design_research_problems import get_problem
from design_research_problems.problems._domains.iot_home import (
    IoTHomeLink,
    IoTHomeProduct,
    resolve_product_room,
)
from design_research_problems.problems.grammar import _iot_home as iot_home_module


def test_iot_home_helper_functions_and_initial_transition_surface() -> None:
    assert iot_home_module._coerce_float_tuple((1, 2)) == (1.0, 2.0)
    assert iot_home_module._coerce_points(((1, 2),)) == ((1.0, 2.0),)
    assert iot_home_module._next_name({"d0", "d1"}, "d") == "d2"

    with pytest.raises(TypeError, match="list or tuple of floats"):
        iot_home_module._coerce_float_tuple("bad")

    with pytest.raises(TypeError, match="list or tuple of 2-item coordinate pairs"):
        iot_home_module._coerce_points("bad")

    with pytest.raises(TypeError, match="exactly two values"):
        iot_home_module._coerce_points(((1,),))

    with pytest.raises(TypeError, match="IoTHomeState"):
        iot_home_module._coerce_state(object())

    problem = get_problem("iot_home_cooling_system_design")
    transitions = problem.enumerate_transitions(problem.initial_state())
    assert transitions
    assert {transition.rule_name for transition in transitions} == {"add_processor"}


def test_iot_home_operations_cover_transition_and_validation_edges() -> None:
    problem = get_problem("iot_home_cooling_system_design")
    state = problem.initial_state()

    state = problem.add_processor(state, x=-8.708087, y=29.342105, name="d0")
    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_processor(state, x=-8.708087, y=29.342105)
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_processor(state, x=20.0, y=20.0, name="d0")

    state = problem.add_sensor(state, dm_name="d0", x=3.651551, y=26.568279, name="s0", link_name="l0")
    with pytest.raises(ValueError, match="existing processor"):
        problem.add_sensor(state, dm_name="missing", x=4.0, y=4.0)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_sensor(state, dm_name="d0", x=-8.708087, y=29.342105)
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_sensor(state, dm_name="d0", x=4.0, y=4.0, name="s0")

    state = problem.add_cooler(
        state,
        dm_name="d0",
        x=6.947455,
        y=35.999289,
        btus=10_000.0,
        cfm=200.0,
        name="e0",
        link_name="l1",
    )
    with pytest.raises(ValueError, match="existing processor"):
        problem.add_cooler(state, dm_name="missing", x=8.0, y=8.0, btus=10_000.0, cfm=200.0)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.add_cooler(
            state,
            dm_name="d0",
            x=6.947455,
            y=35.999289,
            btus=10_000.0,
            cfm=200.0,
        )
    with pytest.raises(ValueError, match="outside the home"):
        problem.add_cooler(
            state,
            dm_name="d0",
            x=79.091123,
            y=16.952347,
            btus=10_000.0,
            cfm=200.0,
        )
    with pytest.raises(ValueError, match="name already exists"):
        problem.add_cooler(
            state,
            dm_name="d0",
            x=8.0,
            y=8.0,
            btus=10_000.0,
            cfm=200.0,
            name="e0",
        )

    state_with_second_processor = problem.add_processor(state, x=20.0, y=5.0, name="d1")
    transition_names = {
        transition.rule_name for transition in problem.enumerate_transitions(state_with_second_processor)
    }
    assert {"add_link", "delete_link", "delete_product", "move_product", "tune_cooler"} <= transition_names

    linked_state = problem.add_link(state_with_second_processor, init_name="d0", term_name="d1", link_name="l2")
    assert any(link.name == "l2" for link in linked_state.links)

    with pytest.raises(ValueError, match="cannot connect a product to itself"):
        problem.add_link(state, init_name="d0", term_name="d0")
    with pytest.raises(ValueError, match="reference existing products"):
        problem.add_link(state, init_name="d0", term_name="missing")
    with pytest.raises(ValueError, match="already exists"):
        problem.add_link(state, init_name="d0", term_name="s0")
    with pytest.raises(ValueError, match="not allowed"):
        problem.add_link(state, init_name="s0", term_name="e0")
    with pytest.raises(ValueError, match="Link name already exists"):
        problem.add_link(state_with_second_processor, init_name="d0", term_name="d1", link_name="l0")

    moved_state = problem.move_product(state, product_name="s0", x=10.0, y=10.0)
    assert any(product.name == "s0" and product.x == 10.0 and product.y == 10.0 for product in moved_state.products)

    with pytest.raises(ValueError, match="Unknown product name"):
        problem.move_product(state, product_name="missing", x=1.0, y=1.0)
    with pytest.raises(ValueError, match="occupies that location"):
        problem.move_product(state, product_name="s0", x=-8.708087, y=29.342105)
    with pytest.raises(ValueError, match="outside the home"):
        problem.move_product(state, product_name="e0", x=79.091123, y=16.952347)

    deleted_link_state = problem.delete_link(linked_state, link_name="l2")
    assert all(link.name != "l2" for link in deleted_link_state.links)
    with pytest.raises(ValueError, match="Unknown link name"):
        problem.delete_link(state, link_name="missing")

    tuned_state = problem.tune_cooler(state, cooler_name="e0", btus=15_000.0, cfm=300.0)
    tuned_cooler = next(product for product in tuned_state.products if product.name == "e0")
    assert tuned_cooler.btus == 15_000.0
    assert tuned_cooler.cfm == 300.0

    with pytest.raises(ValueError, match="At least one cooler setting"):
        problem.tune_cooler(state, cooler_name="e0")
    with pytest.raises(ValueError, match="Unsupported BTU/h setting"):
        problem.tune_cooler(state, cooler_name="e0", btus=12_345.0)
    with pytest.raises(ValueError, match="Unsupported CFM setting"):
        problem.tune_cooler(state, cooler_name="e0", cfm=123.0)
    with pytest.raises(ValueError, match="Unknown cooler name"):
        problem.tune_cooler(state, cooler_name="missing", btus=10_000.0)
    with pytest.raises(ValueError, match="Only coolers can be tuned"):
        problem.tune_cooler(state, cooler_name="d0", btus=10_000.0)
    with pytest.raises(ValueError, match="Unknown product name"):
        problem.delete_product(state, product_name="missing")


def test_iot_home_delete_product_rewires_junction_links() -> None:
    problem = get_problem("iot_home_cooling_system_design")
    base_state = problem.initial_state()

    processor = resolve_product_room(
        base_state,
        IoTHomeProduct(name="d0", product_type="d", x=-8.708087, y=29.342105),
    )
    junction = resolve_product_room(
        base_state,
        IoTHomeProduct(name="j0", product_type="j", x=0.0, y=0.0),
    )
    sensor = resolve_product_room(
        base_state,
        IoTHomeProduct(name="s0", product_type="s", x=3.651551, y=26.568279, dm_name="d0"),
    )
    state = replace(
        base_state,
        products=(processor, junction, sensor),
        links=(
            IoTHomeLink(name="l0", init_name="d0", term_name="j0"),
            IoTHomeLink(name="l1", init_name="j0", term_name="s0"),
        ),
    )

    rewired = problem.delete_product(state, product_name="j0")

    assert {product.name for product in rewired.products} == {"d0", "s0"}
    assert rewired.links == (IoTHomeLink(name="d0.s0", init_name="d0", term_name="s0"),)
