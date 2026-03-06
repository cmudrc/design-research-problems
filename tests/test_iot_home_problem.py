from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from design_research_problems import GrammarProblem, get_problem, list_problems
from design_research_problems.problems._domains.iot_home import (
    IoTHomeLink,
    IoTHomeProduct,
    IoTHomeState,
    resolve_product_room,
)

_FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "iot_octave_parity.json"


def _load_octave_fixture() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _state_from_fixture_entry(base_state: IoTHomeState, entry: dict[str, Any]) -> IoTHomeState:
    products: list[IoTHomeProduct] = []
    for record in entry["products"]:
        product = IoTHomeProduct(
            name=str(record["name"]),
            product_type=str(record["type"]),
            x=float(record["x"]),
            y=float(record["y"]),
            dm_name=record["dm"],
            btus=float(record["btus"]),
            cfm=float(record["cfm"]),
        )
        products.append(resolve_product_room(base_state, product))

    links = tuple(
        IoTHomeLink(
            name=str(record["name"]),
            init_name=str(record["init_name"]),
            term_name=str(record["term_name"]),
        )
        for record in entry["links"]
    )
    return replace(base_state, products=tuple(products), links=links)


def test_registry_exposes_iot_home_cooling_problem() -> None:
    assert "iot_home_cooling_system_design" in list_problems()
    problem = get_problem("iot_home_cooling_system_design")
    assert isinstance(problem, GrammarProblem)
    state = problem.initial_state()
    assert isinstance(state, IoTHomeState)
    assert problem.metadata.problem_id == "iot_home_cooling_system_design"


def test_iot_home_evaluator_matches_octave_fixture() -> None:
    fixture = _load_octave_fixture()
    problem = get_problem("iot_home_cooling_system_design")
    base_state = problem.initial_state()

    for entry in fixture["entries"]:
        state = _state_from_fixture_entry(base_state, entry)
        evaluation = problem.evaluate(state)
        expected = entry["octave"]
        assert evaluation.total_cost == pytest.approx(float(expected["total_cost"]), abs=1e-6)
        assert evaluation.peak_temp_c == pytest.approx(float(expected["peak_temp_c"]), abs=1e-6)
        assert evaluation.capital_cost == pytest.approx(float(expected["capital_cost"]), abs=1e-6)
        assert evaluation.operation_cost == pytest.approx(float(expected["operation_cost"]), abs=1e-6)


def test_iot_home_grammar_rejects_invalid_links_and_moves() -> None:
    problem = get_problem("iot_home_cooling_system_design")
    state = problem.initial_state()

    state = problem.add_processor(state, x=-8.708087, y=29.342105)
    state = problem.add_sensor(state, dm_name="d0", x=3.651551, y=26.568279)
    state = problem.add_cooler(state, dm_name="d0", x=6.947455, y=35.999289, btus=10_000.0, cfm=200.0)

    with pytest.raises(ValueError):
        problem.add_link(state, init_name="s0", term_name="e0")

    with pytest.raises(ValueError):
        problem.add_link(state, init_name="d0", term_name="s0")

    with pytest.raises(ValueError):
        problem.move_product(state, product_name="e0", x=79.091123, y=16.952347)


def test_iot_home_delete_product_cleans_connected_links() -> None:
    problem = get_problem("iot_home_cooling_system_design")
    state = problem.initial_state()

    state = problem.add_processor(state, x=-8.708087, y=29.342105)
    state = problem.add_sensor(state, dm_name="d0", x=3.651551, y=26.568279)
    state = problem.add_cooler(state, dm_name="d0", x=6.947455, y=35.999289, btus=10_000.0, cfm=200.0)
    assert len(state.links) == 2

    state = problem.delete_product(state, product_name="d0")
    assert len(state.products) == 2
    assert state.links == ()


def test_iot_home_evaluation_is_deterministic() -> None:
    fixture = _load_octave_fixture()
    problem = get_problem("iot_home_cooling_system_design")
    base_state = problem.initial_state()
    state = _state_from_fixture_entry(base_state, fixture["entries"][4])

    first = problem.evaluate(state)
    second = problem.evaluate(state)
    assert first == second


def test_iot_home_evaluator_rejects_empty_external_temperature_profile() -> None:
    problem = get_problem("iot_home_cooling_system_design")
    state = replace(problem.initial_state(), external_temps_c=())

    evaluation = problem.evaluate(state)
    assert not evaluation.is_feasible
    assert evaluation.failure_reason == "At least one outdoor-temperature step is required."
