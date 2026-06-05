from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import cast

import numpy
import pytest

from design_research_problems._exceptions import MissingOptionalDependencyError, ProblemEvaluationError
from design_research_problems.problems import _decision as decision
from design_research_problems.problems._domains import battery_cell_model, battery_circuit, planar_truss, truss_ap
from design_research_problems.problems._domains import build123d_cad as cad
from design_research_problems.problems._domains.battery_layout import BatteryRequirements
from design_research_problems.problems._metadata import ProblemKind, ProblemMetadata, ProblemTaxonomy
from design_research_problems.problems.grammar import _planar_truss as planar_grammar
from design_research_problems.problems.grammar import _truss_ap as truss_grammar


def _metadata(problem_id: str = "internal_edge_problem") -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title="Internal Edge Problem",
        summary="Coverage-only helper metadata.",
        kind=ProblemKind.GRAMMAR,
        taxonomy=ProblemTaxonomy(
            formulation=None,
            convexity=None,
            design_variable_type=None,
            is_dynamic=False,
            orientation=None,
            feasibility_ratio_hint=None,
            objective_mode=None,
            constraint_nature=None,
            bounds_summary=None,
            tags=(),
        ),
        citations=(),
        assets=(),
        capabilities=(),
        study_suitability=(),
        implementation="tests",
    )


def _requirements() -> BatteryRequirements:
    return BatteryRequirements(
        target_voltage_v=3.7,
        minimum_capacity_ah=1.0,
        minimum_current_a=1.0,
        max_width_mm=120.0,
        max_depth_mm=120.0,
        max_height_mm=120.0,
        voltage_tolerance_v=0.2,
    )


def _single_cell_circuit_state() -> battery_circuit.BatteryCircuitState:
    return battery_circuit.BatteryCircuitState(
        cells=(
            battery_circuit.BatteryCellInstance(
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


def test_decision_value_objects_validate_normalization_edges() -> None:
    variable = decision.DecisionVariableSpec(" x ", " Label ", " unit ", 1, 2)
    assert (variable.symbol, variable.label, variable.unit) == ("x", "Label", "unit")
    assert variable.lower_bound == pytest.approx(1.0)

    invalid_variable_kwargs = (
        {"symbol": " ", "label": "Label", "unit": None, "lower_bound": 0, "upper_bound": 1},
        {"symbol": "x", "label": " ", "unit": None, "lower_bound": 0, "upper_bound": 1},
        {"symbol": "x", "label": "Label", "unit": None, "lower_bound": 2, "upper_bound": 1},
    )
    for kwargs in invalid_variable_kwargs:
        with pytest.raises(ValueError):
            decision.DecisionVariableSpec(**kwargs)

    factor = decision.DecisionFactor(" key ", " Factor ", " ", (1, 2), (0.1, 0.2))
    assert (factor.key, factor.label, factor.unit) == ("key", "Factor", None)

    invalid_factor_kwargs = (
        {"key": " ", "label": "Label", "unit": None, "levels": (1,), "part_worths": ()},
        {"key": "k", "label": " ", "unit": None, "levels": (1,), "part_worths": ()},
        {"key": "k", "label": "Label", "unit": None, "levels": (), "part_worths": ()},
        {"key": "k", "label": "Label", "unit": None, "levels": (1, 1), "part_worths": ()},
        {"key": "k", "label": "Label", "unit": None, "levels": (1, 2), "part_worths": (0.1,)},
    )
    for kwargs in invalid_factor_kwargs:
        with pytest.raises(ValueError):
            decision.DecisionFactor(**kwargs)

    with pytest.raises(ValueError):
        decision.DecisionProfile(" ", {"x": 1.0})

    valid_objective = {
        "key": "profit",
        "label": "Profit",
        "sense": "maximize",
        "domain": "discrete-option",
        "expression": "profit(x)",
        "variables": ("x",),
        "executable": True,
    }
    valid_constraint = {
        "key": "budget",
        "label": "Budget",
        "relation": "<=",
        "domain": "continuous-design",
        "expression": "x <= 1",
        "variables": ("x",),
        "executable": False,
    }
    for field in ("key", "label", "sense", "domain", "expression"):
        payload = {**valid_objective, field: " "}
        with pytest.raises(ValueError):
            decision.DecisionObjectiveSpec(**payload)
    with pytest.raises(ValueError):
        decision.DecisionObjectiveSpec(**{**valid_objective, "variables": (" ",)})

    for field in ("key", "label", "relation", "domain", "expression"):
        payload = {**valid_constraint, field: " "}
        with pytest.raises(ValueError):
            decision.DecisionConstraintSpec(**payload)
    with pytest.raises(ValueError):
        decision.DecisionConstraintSpec(**{**valid_constraint, "variables": (" ",)})

    assert decision.DecisionChoiceBenchmark(" KEY ", " Label ", 0.25, 7, 7, 1).key == "key"
    for kwargs in (
        {"key": " ", "label": "Label", "top_choice_share": 0, "mean_rating": 0, "median_rating": 0, "std_rating": 0},
        {"key": "k", "label": " ", "top_choice_share": 0, "mean_rating": 0, "median_rating": 0, "std_rating": 0},
        {"key": "k", "label": "Label", "top_choice_share": -0.1, "mean_rating": 0, "median_rating": 0, "std_rating": 0},
        {"key": "k", "label": "Label", "top_choice_share": 1.1, "mean_rating": 0, "median_rating": 0, "std_rating": 0},
        {"key": "k", "label": "Label", "top_choice_share": 0, "mean_rating": 0, "median_rating": 0, "std_rating": -1},
    ):
        with pytest.raises(ValueError):
            decision.DecisionChoiceBenchmark(**kwargs)

    for kwargs in (
        {
            "candidate_kind": "discrete-option",
            "candidate": decision.DecisionOption({"a": 1}),
            "candidate_label": " ",
            "objective_value": 1,
            "objective_metric": "share",
        },
        {
            "candidate_kind": "discrete-option",
            "candidate": decision.DecisionOption({"a": 1}),
            "candidate_label": "A",
            "objective_value": 1,
            "objective_metric": " ",
        },
        {
            "candidate_kind": "not-supported",
            "candidate": "x",
            "candidate_label": "A",
            "objective_value": 1,
            "objective_metric": "share",
        },
        {
            "candidate_kind": "empirical-choice",
            "candidate": "x",
            "candidate_label": "A",
            "objective_value": 1,
            "objective_metric": "share",
            "choice_key": " ",
        },
        {
            "candidate_kind": "empirical-choice",
            "candidate": "x",
            "candidate_label": "A",
            "objective_value": 1,
            "objective_metric": "share",
            "choice_label": " ",
        },
        {
            "candidate_kind": "empirical-choice",
            "candidate": "x",
            "candidate_label": "A",
            "objective_value": 1,
            "objective_metric": "share",
            "response_count": -1,
        },
    ):
        with pytest.raises(ValueError):
            decision.DecisionEvaluation(**kwargs)


def test_decision_parser_and_spline_helpers_cover_failure_edges() -> None:
    assert dict(decision._freeze_numeric_mapping({" a ": "2.5"})) == {"a": 2.5}
    with pytest.raises(ValueError):
        decision._freeze_numeric_mapping({" ": 1.0})

    assert decision._normalize_string_tuple([" a ", 2], context="items") == ("a", "2")
    with pytest.raises(ValueError):
        decision._normalize_string_tuple([""], context="items")

    assert decision._list_of_mappings(None, field_name="field") == ()
    assert decision._list_of_mappings(({"a": 1},), field_name="field") == ({"a": 1},)
    for value in ("bad", [1]):
        with pytest.raises(ValueError):
            decision._list_of_mappings(value, field_name="field")

    assert decision._sequence([1, 2], field_name="field") == (1, 2)
    with pytest.raises(ValueError):
        decision._sequence("bad", field_name="field")

    assert decision._coerce_int("4", field_name="count") == 4
    with pytest.raises(ValueError):
        decision._coerce_int("4.2", field_name="count")
    assert decision._coerce_float(True, field_name="flag") == pytest.approx(1.0)
    assert decision._coerce_float(" 1.25 ", field_name="value") == pytest.approx(1.25)
    with pytest.raises(ValueError):
        decision._coerce_float(" ", field_name="value")
    with pytest.raises(ValueError):
        decision._coerce_float(object(), field_name="value")

    for x_values, y_values in (((0.0,), (1.0, 2.0)), ((), ()), ((0.0, 0.0), (1.0, 2.0))):
        with pytest.raises(ValueError):
            decision._NaturalCubicSpline.from_points(x_values, y_values)
    one_point = decision._NaturalCubicSpline.from_points((1.0,), (3.0,))
    assert one_point.evaluate(99.0) == pytest.approx(3.0)
    line = decision._NaturalCubicSpline.from_points((0.0, 1.0), (0.0, 2.0))
    assert line.evaluate(-1.0) == pytest.approx(-2.0)
    assert line.evaluate(2.0) == pytest.approx(4.0)
    curve = decision._NaturalCubicSpline.from_points((0.0, 0.5, 1.0), (0.0, 1.0, 0.0))
    assert curve.evaluate(0.25) > 0.0
    assert decision._solve_tridiagonal((), (), (), ()) == ()
    with pytest.raises(ValueError):
        decision._solve_tridiagonal((0.0,), (1.0,), (0.0,), ())
    with pytest.raises(ValueError):
        decision._solve_tridiagonal((0.0,), (0.0,), (0.0,), (1.0,))
    with pytest.raises(ValueError):
        decision._solve_tridiagonal((0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (1.0, 1.0))


def test_decision_problem_private_method_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    option_parameters: dict[str, object] = {
        "option_factors": ({"key": "price", "label": "Price", "levels": (1, 2), "part_worths": (0.2, 0.1)},),
        "competitor_profiles": ({"name": "Peer", "values": {"price": 1.5}},),
        "objective_specs": (
            {
                "key": "share",
                "label": "Share",
                "sense": "maximize",
                "domain": "discrete-option",
                "expression": "share(price)",
                "variables": ("price",),
                "executable": True,
            },
        ),
    }
    problem = decision.DecisionProblem(metadata=_metadata("decision_private_edges"), parameters=option_parameters)
    assert problem._coerce_option({"price": "1"}).values["price"] == pytest.approx(1.0)
    for option in (object(), {"other": 1.0}, {"price": 3.0}):
        with pytest.raises(ValueError):
            problem._coerce_option(option)
    with pytest.raises(ProblemEvaluationError):
        problem._coerce_choice("steel")
    with pytest.raises(ProblemEvaluationError):
        problem._factor_part_worth(decision.DecisionFactor("x", "X", None, (1.0,), ()), 1.0)
    without_executable = decision.DecisionProblem(
        metadata=_metadata("decision_no_executable"),
        parameters={**option_parameters, "objective_specs": ()},
    )
    with pytest.raises(ProblemEvaluationError):
        without_executable._executable_objective()

    choice_parameters: dict[str, object] = {
        "choice_options": (
            {
                "key": "steel",
                "label": "Steel",
                "top_choice_share": 0.2,
                "mean_rating": 6.0,
                "median_rating": 5.0,
                "std_rating": 1.0,
            },
        ),
        "objective_specs": (
            {
                "key": "rating",
                "label": "Rating",
                "sense": "maximize",
                "domain": "empirical-choice",
                "expression": "mean(material)",
                "variables": ("material",),
                "executable": True,
            },
        ),
        "response_count": 5,
    }
    choice_problem = decision.DecisionProblem(metadata=_metadata("choice_private_edges"), parameters=choice_parameters)
    benchmark = choice_problem._coerce_choice("Steel")
    assert choice_problem._choice_metric_value(benchmark, "mean-rating") == pytest.approx(6.0)
    assert choice_problem._choice_metric_value(benchmark, "median-rating") == pytest.approx(5.0)
    with pytest.raises(ValueError):
        choice_problem._coerce_choice(" ")
    with pytest.raises(ValueError):
        choice_problem._normalize_choice_metric("bad")
    with pytest.raises(ValueError):
        choice_problem._choice_metric_value(benchmark, "bad")
    with pytest.raises(TypeError):
        choice_problem.evaluate({"price": 1.0})

    monkeypatch.setattr(decision, "pairwise", lambda _values: iter(()))
    broken = decision._NaturalCubicSpline(
        x_values=(0.0, 1.0),
        y_values=(0.0, 1.0),
        second_derivatives=(0.0, 0.0),
    )
    with pytest.raises(RuntimeError):
        broken.evaluate(0.5)


def test_decision_structured_payload_validation_edges() -> None:
    option_parameters: dict[str, object] = {
        "option_factors": ({"key": "price", "label": "Price", "levels": (1, 2), "part_worths": (0.2, 0.1)},),
        "competitor_profiles": ({"name": "Peer", "values": {"price": 1.5}},),
        "objective_specs": (
            {
                "key": "share",
                "label": "Share",
                "sense": "maximize",
                "domain": "discrete-option",
                "expression": "share(price)",
                "variables": ("price",),
                "executable": True,
            },
        ),
    }
    parsed = decision.parse_structured_decision_payload(option_parameters)
    assert parsed.default_choice_metric == "top-choice-share"

    choice_parameters: dict[str, object] = {
        "choice_options": (
            {
                "key": "steel",
                "label": "Steel",
                "top_choice_share": 0.2,
                "mean_rating": 6.0,
                "median_rating": 6.0,
                "std_rating": 1.0,
            },
        ),
        "objective_specs": (
            {
                "key": "rating",
                "label": "Rating",
                "sense": "maximize",
                "domain": "empirical-choice",
                "expression": "mean(material)",
                "variables": ("material",),
                "executable": True,
            },
        ),
        "default_choice_metric": "mean-rating",
        "response_count": 5,
    }
    assert decision.parse_structured_decision_payload(choice_parameters).response_count == 5

    invalid_payloads: tuple[dict[str, object], ...] = (
        {
            **option_parameters,
            "objective_specs": (
                {
                    "key": "share",
                    "label": "Share",
                    "sense": "minimize",
                    "domain": "discrete-option",
                    "expression": "share(price)",
                    "variables": ("price",),
                    "executable": True,
                },
            ),
        },
        {
            "objective_specs": (
                {
                    "key": "share",
                    "label": "Share",
                    "sense": "maximize",
                    "domain": "discrete-option",
                    "expression": "share(price)",
                    "variables": ("price",),
                    "executable": True,
                },
            ),
        },
        {
            "option_factors": ({"key": "price", "label": "Price", "levels": (1, 2), "part_worths": ()},),
            "competitor_profiles": option_parameters["competitor_profiles"],
            "objective_specs": option_parameters["objective_specs"],
        },
        {
            **option_parameters,
            "objective_specs": (
                {
                    "key": "share",
                    "label": "Share",
                    "sense": "maximize",
                    "domain": "discrete-option",
                    "expression": "share(price)",
                    "variables": ("missing",),
                    "executable": True,
                },
            ),
        },
        {
            "objective_specs": (
                {
                    "key": "rating",
                    "label": "Rating",
                    "sense": "maximize",
                    "domain": "empirical-choice",
                    "expression": "mean(material)",
                    "variables": ("material",),
                    "executable": True,
                },
            ),
        },
        {
            **choice_parameters,
            "objective_specs": (
                {
                    "key": "rating",
                    "label": "Rating",
                    "sense": "maximize",
                    "domain": "empirical-choice",
                    "expression": "mean(material)",
                    "variables": ("other",),
                    "executable": True,
                },
            ),
        },
        {
            **choice_parameters,
            "objective_specs": (
                {
                    "key": "rating",
                    "label": "Rating",
                    "sense": "maximize",
                    "domain": "other",
                    "expression": "mean(material)",
                    "variables": ("material",),
                    "executable": True,
                },
            ),
        },
        {
            **option_parameters,
            "objective_specs": (
                {
                    "key": "note",
                    "label": "Note",
                    "sense": "maximize",
                    "domain": "continuous-design",
                    "expression": "missing",
                    "variables": ("missing",),
                    "executable": False,
                },
            ),
        },
        {
            "decision_variable_specs": (
                {"symbol": "x", "label": "X", "lower_bound": 0, "upper_bound": 1},
                {"symbol": "x", "label": "X again", "lower_bound": 0, "upper_bound": 1},
            ),
        },
        {
            "option_factors": (
                {"key": "price", "label": "Price", "levels": (1,), "part_worths": ()},
                {"key": "price", "label": "Price again", "levels": (1,), "part_worths": ()},
            ),
        },
        {
            "choice_options": (
                {
                    "key": "steel",
                    "label": "Steel",
                    "top_choice_share": 0.2,
                    "mean_rating": 6.0,
                    "median_rating": 6.0,
                    "std_rating": 1.0,
                },
                {
                    "key": "other-steel",
                    "label": "Steel",
                    "top_choice_share": 0.1,
                    "mean_rating": 5.0,
                    "median_rating": 5.0,
                    "std_rating": 1.0,
                },
            ),
            "response_count": 5,
        },
        {
            "competitor_profiles": (
                {"name": "Peer", "values": {"price": 1.5}},
                {"name": "Peer", "values": {"price": 1.6}},
            ),
        },
        {
            "competitor_profiles": ({"name": "Peer", "values": ()},),
        },
        {"response_count": -1},
        {
            "choice_options": choice_parameters["choice_options"],
            "response_count": 0,
            "objective_specs": choice_parameters["objective_specs"],
        },
        {**choice_parameters, "default_choice_metric": "bad"},
        {
            **option_parameters,
            "objective_specs": (
                *cast(tuple[object, ...], option_parameters["objective_specs"]),
                cast(tuple[object, ...], option_parameters["objective_specs"])[0],
            ),
        },
        {
            **option_parameters,
            "constraint_specs": (
                {
                    "key": "c",
                    "label": "Constraint",
                    "relation": "<=",
                    "domain": "continuous-design",
                    "expression": "x <= 1",
                    "variables": ("missing",),
                    "executable": False,
                },
            ),
        },
        {
            "competitor_profiles": option_parameters["competitor_profiles"],
        },
        {
            **option_parameters,
            "competitor_profiles": ({"name": "Peer", "values": {"other": 1.0}},),
        },
    )
    for payload in invalid_payloads:
        with pytest.raises(ValueError):
            decision.parse_structured_decision_payload(payload)


def test_build123d_internal_geometry_and_script_sandbox_edges(monkeypatch: pytest.MonkeyPatch) -> None:
    assert cad._base_hole_centers_xy(cad.MountingBracketSpec(base_hole_count=1)) == [(0.0, 0.0)]
    assert len(cad._base_hole_centers_xy(cad.MountingBracketSpec(base_hole_count=2))) == 2
    assert cad._flange_hole_centers_z(cad.MountingBracketSpec(flange_hole_count=1)) == [26.0]
    assert len(cad._flange_hole_centers_z(cad.MountingBracketSpec(flange_hole_count=3))) == 3
    assert cad._fillet_candidates_mm(1.25)[-1] == pytest.approx(0.5)

    fake_module = SimpleNamespace(Public=object(), _private=object())
    monkeypatch.setattr(cad, "import_module", lambda _name: fake_module)
    namespace = cad._script_build123d_namespace()
    assert namespace["Public"] is fake_module.Public
    assert "_private" not in namespace

    with pytest.raises(ImportError):
        cad._safe_script_import("os")
    with pytest.raises(ImportError):
        cad._safe_script_import("math", level=1)

    forbidden_scripts = (
        "def",
        "import os",
        "from os import path",
        "from . import thing",
        "from build123d import *",
        "result = open('x')",
        "result = (1).__class__",
        "result = object.__subclasses__()",
        "global result\nresult = 1",
        "def outer():\n    x = 1\n    def inner():\n        nonlocal x\n        return x\n",
        "__builtins__ = {}",
    )
    for script in forbidden_scripts:
        with pytest.raises(ValueError):
            cad._validate_build123d_script(script)


def test_build123d_fake_backend_executes_volume_path(monkeypatch: pytest.MonkeyPatch) -> None:
    fillet_attempts: list[float] = []

    class _Center:
        Y = -14.0
        Z = 6.0

    class _Edge:
        def center(self) -> _Center:
            return _Center()

    class _BuildPart:
        part = SimpleNamespace(volume=321.0)

        def __enter__(self) -> _BuildPart:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def edges(self) -> list[_Edge]:
            return [_Edge()]

    class _Locations:
        def __init__(self, *_args: object) -> None:
            pass

        def __enter__(self) -> _Locations:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def _fillet(_edges: list[_Edge], radius: float) -> None:
        fillet_attempts.append(radius)
        if radius >= 4.0:
            raise ValueError("too large")

    fake_module = SimpleNamespace(
        Align=SimpleNamespace(CENTER="center", MIN="min"),
        Mode=SimpleNamespace(SUBTRACT="subtract"),
        BuildPart=_BuildPart,
        Box=lambda *_args, **_kwargs: None,
        Cylinder=lambda *_args, **_kwargs: None,
        Location=lambda *_args: ("location", _args),
        Locations=_Locations,
        fillet=_fillet,
    )
    monkeypatch.setattr(cad, "import_module", lambda _name: fake_module)

    volume, applied_fillet, warning = cad._build123d_bracket_volume_mm3(cad.MountingBracketSpec())
    assert volume == pytest.approx(321.0)
    assert applied_fillet == pytest.approx(3.5)
    assert warning is not None
    assert fillet_attempts[:2] == [4.0, 3.5]

    class _NoEdgeBuildPart(_BuildPart):
        def edges(self) -> list[_Edge]:
            return []

    fake_module.BuildPart = _NoEdgeBuildPart
    _volume, applied_none, no_edge_warning = cad._build123d_bracket_volume_mm3(cad.MountingBracketSpec())
    assert applied_none is None
    assert no_edge_warning == "No internal-corner edge was available for filleting."


def test_planar_truss_internal_symmetry_and_builder_edges() -> None:
    base_state = planar_truss.build_seed_planar_truss_state(10.0, 5.0, 900.0)
    assert planar_truss.mirrored_joint_id(base_state, 0) == 0

    roof_state = planar_truss.build_seed_planar_truss_state(
        10.0,
        5.0,
        900.0,
        roof_load_x_fractions=(0.25, 0.5, 0.75),
        enforce_symmetry=True,
    )
    assert roof_state.load_joint_id == 2
    assert len(roof_state.additional_loads) == 2
    assert roof_state.load_vector == (0.0, -300.0, 0.0)

    assert planar_truss.mirrored_joint_id(roof_state, 999) is None
    assert planar_truss.mirrored_edge(roof_state, (0, 999)) is None

    expanded = planar_truss.expand_planar_truss_candidate_joints(
        base_state,
        ((2.5, 2.0), (5.0, 2.5), (2.5, 2.0)),
    )
    assert len(expanded.joints) == len(base_state.joints) + 2

    symmetric_expanded = planar_truss.expand_planar_truss_candidate_joints(
        roof_state,
        ((2.5, 2.0), (7.5, 2.0), (5.0, 2.5), (2.5, 2.0)),
    )
    assert len(symmetric_expanded.joints) == len(roof_state.joints) + 3
    candidate_edges = planar_truss.enumerate_planar_truss_candidate_edges(symmetric_expanded)
    assert candidate_edges
    assert all(
        edge == min(edge, cast(tuple[int, int], planar_truss.mirrored_edge(symmetric_expanded, edge)))
        for edge in candidate_edges
    )

    with pytest.raises(ValueError):
        planar_truss.build_planar_truss_state_from_edges(base_state, ((0, 999),))

    broken_symmetric = replace(
        symmetric_expanded,
        joints=tuple(joint for joint in symmetric_expanded.joints if joint.x != 7.5),
    )
    with pytest.raises(ValueError):
        planar_truss.build_planar_truss_state_from_edges(broken_symmetric, ((0, 5),))

    built = planar_truss.build_planar_truss_state_from_edges(symmetric_expanded, (candidate_edges[0],))
    assert built.members
    assert all(member.start_joint_id in {joint.joint_id for joint in built.joints} for member in built.members)


def test_planar_truss_grammar_validation_edges() -> None:
    with pytest.raises(TypeError):
        planar_grammar._coerce_float_tuple(object())
    with pytest.raises(TypeError):
        planar_grammar._coerce_fractional_points(object())
    with pytest.raises(TypeError):
        planar_grammar._coerce_fractional_points((1.0,))
    with pytest.raises(TypeError):
        planar_grammar._coerce_state(object())

    symmetric = planar_grammar.PlanarTrussSpanProblem(
        _metadata("symmetric_planar"),
        span=10.0,
        max_height=5.0,
        load_magnitude=1000.0,
        candidate_point_fractions=((0.25, 0.5), (0.50, 0.5), (0.75, 0.5)),
        enforce_symmetry=True,
    )
    state = symmetric.initial_state()
    transitions = symmetric.enumerate_transitions(state)
    assert {transition.rule_name for transition in transitions} >= {"add_joint", "add_joint_pair", "add_member"}

    with pytest.raises(ValueError):
        symmetric.add_joint(state, x=2.5, y=1.0)
    axis_state = symmetric.add_joint(state, x=5.0, y=2.5)
    with pytest.raises(ValueError):
        symmetric.add_joint(axis_state, x=5.0, y=2.5)
    with pytest.raises(ValueError):
        symmetric.add_joint_pair(axis_state, left_x=2.0, left_y=1.0, right_x=9.0, right_y=1.0)
    with pytest.raises(ValueError):
        symmetric.add_joint_pair(axis_state, left_x=5.0, left_y=2.5, right_x=5.0, right_y=2.5)

    paired_state = symmetric.add_joint_pair(state, left_x=2.5, left_y=2.5, right_x=7.5, right_y=2.5)
    with pytest.raises(ValueError):
        symmetric.add_member(paired_state, start_joint_id=0, end_joint_id=0)
    with pytest.raises(ValueError):
        symmetric.add_member(paired_state, start_joint_id=0, end_joint_id=999)
    member_state = symmetric.add_member(paired_state, start_joint_id=0, end_joint_id=3)
    with pytest.raises(ValueError):
        symmetric.add_member(member_state, start_joint_id=0, end_joint_id=3)
    with pytest.raises(ValueError):
        symmetric.remove_member(member_state, member_id=999)
    assert len(symmetric.remove_member(member_state, member_id=0).members) == 0

    nonsymmetric = planar_grammar.PlanarTrussSpanProblem(_metadata("plain_planar"))
    plain_state = nonsymmetric.initial_state()
    with pytest.raises(ValueError):
        nonsymmetric.add_joint_pair(plain_state, left_x=2.0, left_y=1.0, right_x=8.0, right_y=1.0)


def test_truss_ap_domain_validation_and_restricted_zone_edges() -> None:
    square = ((0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0))
    assert truss_ap._point_in_polygon(1.0, 1.0, square)
    assert truss_ap._point_in_polygon(0.0, 1.0, square)
    assert not truss_ap._point_in_polygon(3.0, 1.0, square)
    assert truss_ap._segments_intersect(0, 0, 2, 2, 0, 2, 2, 0)
    assert truss_ap._segments_intersect(0, 0, 2, 0, 1, 0, 3, 0)
    assert truss_ap._segments_intersect(0, 0, 2, 0, 2, 0, 2, 2)
    assert not truss_ap._segments_intersect(0, 0, 1, 0, 2, 0, 3, 0)
    assert truss_ap._segment_intersects_polygon((-1.0, 1.0), (3.0, 1.0), square)
    assert not truss_ap._segment_intersects_polygon((-1.0, -1.0), (-2.0, -1.0), square)

    state = truss_ap.build_default_truss_ap_state()
    invalid_states = (
        replace(state, required_support_joint_ids=(1, 2)),
        replace(state, support_enabled=(True, True)),
        replace(
            state,
            loads=(
                truss_ap.TrussAPLoad(
                    joint_id=4,
                    direction=cast(truss_ap.TrussLoadDirection, "bad"),
                    magnitude_n=1.0,
                ),
            ),
        ),
        replace(state, loads=(truss_ap.TrussAPLoad(joint_id=999, direction="down", magnitude_n=1.0),)),
        replace(state, loads=(truss_ap.TrussAPLoad(joint_id=4, direction="down", magnitude_n=numpy.inf),)),
        replace(state, members=(truss_ap.TrussAPMember(1, 1, 1, 5),)),
        replace(state, members=(truss_ap.TrussAPMember(1, 1, 999, 5),)),
        replace(state, members=(truss_ap.TrussAPMember(1, 1, 2, 99),)),
        replace(state, size_index_max=20, members=(truss_ap.TrussAPMember(1, 1, 2, 11),)),
        replace(
            state,
            members=(truss_ap.TrussAPMember(1, 1, 2, 5), truss_ap.TrussAPMember(2, 2, 1, 5)),
        ),
        replace(state, joints=(*state.joints, replace(state.joints[0], joint_id=2))),
    )
    for invalid_state in invalid_states:
        assert not truss_ap.evaluate_truss_ap_state(invalid_state).is_stable

    movable_inside = replace(
        state,
        enforce_bad_zone=True,
        joints=(*state.joints, truss_ap.TrussAPJoint(6, -0.75, 0.0, is_fixed=False)),
    )
    assert truss_ap.evaluate_truss_ap_state(movable_inside).failure_reason == (
        "A movable joint is inside the restricted zone."
    )

    member_crossing = replace(state, enforce_bad_zone=True, members=(truss_ap.TrussAPMember(1, 1, 2, 5),))
    assert truss_ap.evaluate_truss_ap_state(member_crossing).failure_reason == (
        "A member intersects the restricted zone."
    )


def test_truss_ap_grammar_validation_edges() -> None:
    with pytest.raises(TypeError):
        truss_grammar._coerce_points(object())
    with pytest.raises(TypeError):
        truss_grammar._coerce_points((1.0,))
    with pytest.raises(TypeError):
        truss_grammar._coerce_float_tuple(object())
    with pytest.raises(TypeError):
        truss_grammar._coerce_state(object())

    problem = truss_grammar.TrussAPGrammarProblem(
        _metadata("truss_ap_edges"),
        candidate_points=((0.0, 1.0), (1.0, 1.0)),
        max_editable_joints=1,
        default_member_size_index=5,
        load_magnitude_options_n=(50_000.0, 200_000.0),
    )
    state = problem.initial_state()
    transition_names = {transition.rule_name for transition in problem.enumerate_transitions(state)}
    assert {"add_joint", "add_member", "set_support_enabled", "set_load", "clear_load"} <= transition_names

    added = problem.add_joint(state, x=0.0, y=1.0)
    with pytest.raises(ValueError):
        problem.add_joint(added, x=1.0, y=1.0)
    with pytest.raises(ValueError):
        problem.add_joint(state, x=99.0, y=1.0)
    with pytest.raises(ValueError):
        problem.add_joint(state, x=state.joints[0].x, y=state.joints[0].y)

    moved = problem.move_joint(added, joint_id=6, x=1.0, y=1.0)
    assert moved.joints[-1].x == pytest.approx(1.0)
    with pytest.raises(ValueError):
        problem.move_joint(added, joint_id=999, x=1.0, y=1.0)
    with pytest.raises(ValueError):
        problem.move_joint(added, joint_id=1, x=1.0, y=1.0)
    with pytest.raises(ValueError):
        problem.move_joint(added, joint_id=6, x=99.0, y=1.0)
    with pytest.raises(ValueError):
        problem.move_joint(added, joint_id=6, x=state.joints[0].x, y=state.joints[0].y)

    with pytest.raises(ValueError):
        problem.delete_joint(added, joint_id=999)
    with pytest.raises(ValueError):
        problem.delete_joint(added, joint_id=1)
    assert all(joint.joint_id != 6 for joint in problem.delete_joint(added, joint_id=6).joints)

    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=1, end_joint_id=1, size_index=5)
    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=1, end_joint_id=999, size_index=5)
    with pytest.raises(ValueError):
        problem.add_member(state, start_joint_id=1, end_joint_id=2, size_index=99)
    member_state = problem.add_member(state, start_joint_id=1, end_joint_id=2, size_index=5)
    with pytest.raises(ValueError):
        problem.add_member(member_state, start_joint_id=2, end_joint_id=1, size_index=5)
    with pytest.raises(ValueError):
        problem.delete_member(state, member_id=999)
    assert problem.delete_member(member_state, member_id=1).members == ()

    resized = problem.set_member_size(member_state, member_id=1, size_index=4)
    assert resized.members[0].size_index == 4
    with pytest.raises(ValueError):
        problem.set_member_size(member_state, member_id=1, size_index=99)
    with pytest.raises(ValueError):
        problem.set_member_size(member_state, member_id=999, size_index=4)

    assert problem.set_support_enabled(state, support_id=1, enabled=False).support_enabled[0] is False
    with pytest.raises(ValueError):
        problem.set_support_enabled(state, support_id=99, enabled=True)

    loaded = problem.set_load(state, joint_id=1, direction="left", magnitude_n=50_000.0)
    assert any(load.joint_id == 1 and load.direction == "left" for load in loaded.loads)
    with pytest.raises(ValueError):
        problem.set_load(state, joint_id=999, direction="left", magnitude_n=50_000.0)
    with pytest.raises(ValueError):
        problem.set_load(state, joint_id=1, direction=cast(truss_ap.TrussLoadDirection, "bad"), magnitude_n=50_000.0)
    with pytest.raises(ValueError):
        problem.set_load(state, joint_id=1, direction="left", magnitude_n=123.0)
    assert all(load.joint_id != 4 for load in problem.clear_load(state, joint_id=4, direction="down").loads)
    with pytest.raises(ValueError):
        problem.clear_load(state, joint_id=999, direction="down")
    with pytest.raises(ValueError):
        problem.clear_load(state, joint_id=4, direction=cast(truss_ap.TrussLoadDirection, "bad"))


def test_battery_circuit_validation_and_direct_trace_edges() -> None:
    requirements = _requirements()
    valid = _single_cell_circuit_state()
    assert battery_circuit.validate_battery_circuit_state(valid, requirements) is None

    invalid_states = (
        replace(valid, cells=()),
        replace(valid, cells=(*valid.cells, replace(valid.cells[0], positive_terminal_id=3))),
        replace(valid, cells=(replace(valid.cells[0], positive_terminal_id=0),)),
        replace(valid, cells=(replace(valid.cells[0], x=999),)),
        replace(
            valid,
            cells=(
                *valid.cells,
                replace(valid.cells[0], cell_id=1, positive_terminal_id=3, negative_terminal_id=2),
            ),
        ),
        replace(valid, pack_positive_terminal_id=0),
        replace(valid, pack_positive_terminal_id=999),
        replace(valid, connections=(battery_circuit.BatteryConnection(0, 0, 0),)),
        replace(valid, connections=(battery_circuit.BatteryConnection(0, 0, 999),)),
        replace(valid, connections=(battery_circuit.BatteryConnection(0, 0, 1, resistance_ohm=0.0),)),
        replace(
            valid,
            connections=(
                battery_circuit.BatteryConnection(0, 0, 1),
                battery_circuit.BatteryConnection(0, 0, 1),
            ),
        ),
        replace(valid, connections=(battery_circuit.BatteryConnection(0, 0, 1),)),
    )
    for invalid in invalid_states:
        assert battery_circuit.validate_battery_circuit_state(invalid, requirements) is not None

    general = replace(valid, pack_positive_terminal_id=1, pack_negative_terminal_id=0)
    analysis = battery_circuit.analyze_battery_topology(general)
    assert analysis.topology_kind == "series_parallel"
    assert battery_circuit._validate_pybamm_direct_state(valid, analysis) is None
    assert battery_circuit._validate_pybamm_direct_state(replace(valid, cells=()), analysis) is not None
    assert (
        battery_circuit._validate_pybamm_direct_state(
            replace(valid, connections=(battery_circuit.BatteryConnection(0, 0, 1, ideal=False),)),
            analysis,
        )
        is not None
    )
    assert (
        battery_circuit._validate_pybamm_direct_state(
            valid,
            battery_circuit.BatteryTopologyAnalysis("general", None, None, None),
        )
        is not None
    )

    sample_times = numpy.asarray([0.0, 1.0])

    class _Solution:
        def __getitem__(self, name: str) -> object:
            if name == "Volume-averaged cell temperature [K]":
                return lambda _times: numpy.asarray([[298.15, 300.15], [299.15, 301.15]])
            if name == "Ohmic heating [W]":
                return lambda _times: numpy.asarray([1.0, 2.0])
            raise KeyError(name)

    assert battery_circuit._load_pybamm_direct_temperature_trace_c(_Solution(), sample_times).shape == (2,)
    assert battery_circuit._load_pybamm_direct_heat_trace_w(_Solution(), sample_times).tolist() == [1.0, 2.0]
    assert battery_circuit._load_pybamm_direct_heat_trace_w(object(), sample_times).tolist() == [0.0, 0.0]
    with pytest.raises(KeyError):
        battery_circuit._load_pybamm_direct_temperature_trace_c(object(), sample_times)


def test_battery_circuit_fake_pybamm_direct_path(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _single_cell_circuit_state()
    analysis = battery_circuit.BatteryTopologyAnalysis(
        topology_kind="series_parallel",
        series_count=1,
        parallel_count=1,
        minimum_series_cells=1,
    )
    requirements = BatteryRequirements(
        target_voltage_v=3.7,
        minimum_capacity_ah=1.0 / 3600.0,
        minimum_current_a=1.0,
        max_width_mm=120.0,
        max_depth_mm=120.0,
        max_height_mm=120.0,
        voltage_tolerance_v=0.2,
    )

    monkeypatch.setattr(
        battery_circuit,
        "_load_lithium_ion_parameter_values",
        lambda **_kwargs: ({}, 1.0, 298.15),
    )

    class _Solution:
        t = numpy.asarray([0.0, 1.0])
        termination = "final time"

        def __getitem__(self, name: str) -> object:
            if name == "Voltage [V]":
                return lambda times: numpy.full(len(numpy.asarray(times).reshape(-1)), 4.0)
            raise KeyError(name)

    class _Simulation:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def solve(self, *, initial_soc: float) -> _Solution:
            assert initial_soc == pytest.approx(1.0)
            return _Solution()

    fake_pybamm = SimpleNamespace(
        lithium_ion=SimpleNamespace(SPM=lambda **_kwargs: object()),
        Experiment=lambda steps: tuple(steps),
        Simulation=_Simulation,
    )
    monkeypatch.setattr(battery_circuit, "import_pybamm", lambda: fake_pybamm)

    result, mode, warning = battery_circuit._simulate_battery_circuit_pybamm_direct(
        state,
        requirements,
        analysis,
        simulate_to_failure=False,
        backend_config=battery_cell_model.BatteryBackendConfig(
            cell_model_mode="pybamm_direct",
            thermal_mode="lumped",
            ambient_temp_c=25.0,
        ),
    )
    assert mode == "pybamm_spm_direct"
    assert warning is None
    assert result.is_feasible
    assert result.pack_terminal_voltage_end == pytest.approx(4.0)
    assert result.solver_steps == 1
    assert result.trace[0].cell_temperature_c == pytest.approx(25.0)

    with pytest.raises(ValueError):
        battery_circuit._simulate_battery_circuit_pybamm_direct(
            state,
            requirements,
            analysis,
            simulate_to_failure=False,
            backend_config=battery_cell_model.BatteryBackendConfig(
                cell_model_mode="pybamm_direct",
                thermal_mode="unsupported",
                ambient_temp_c=25.0,
            ),
        )


def test_battery_cell_model_config_and_dynamic_helper_edges() -> None:
    assert battery_cell_model.BatteryParameterization(preset="fast").as_dict() == {"preset": "fast"}
    assert battery_cell_model.battery_backend_config_from_mapping(None).cell_model_mode == "auto"
    with pytest.raises(ValueError):
        battery_cell_model.battery_backend_config_from_mapping("bad")
    with pytest.raises(ValueError):
        battery_cell_model.battery_backend_config_from_mapping({"extra": 1})
    with pytest.raises(ValueError):
        battery_cell_model.battery_backend_config_from_mapping({"cell_model_mode": ""})
    with pytest.raises(ValueError):
        battery_cell_model.battery_backend_config_from_mapping({"parameterization": 1})
    with pytest.raises(ValueError):
        battery_cell_model.battery_backend_config_from_mapping({"parameterization": "unknown"})

    fake_parameter_values = {"value": 1.0}
    fake_module = SimpleNamespace(ParameterValues=lambda _name: fake_parameter_values)
    assert (
        battery_cell_model._load_named_parameter_values(pybamm_module=fake_module, parameter_set="x")
        == fake_parameter_values
    )
    with pytest.raises(MissingOptionalDependencyError):
        battery_cell_model._load_named_parameter_values(pybamm_module=object(), parameter_set="x")
    with pytest.raises(MissingOptionalDependencyError):
        battery_cell_model._load_named_parameter_values(
            pybamm_module=SimpleNamespace(ParameterValues=lambda _name: (_ for _ in ()).throw(RuntimeError("boom"))),
            parameter_set="x",
        )

    class _Copyable:
        def copy(self) -> str:
            return "copied"

    assert battery_cell_model._copy_parameter_values(_Copyable()) == "copied"
    assert battery_cell_model._copy_parameter_values(fake_parameter_values) is not fake_parameter_values

    updated: dict[str, float] = {}
    battery_cell_model._try_set_parameter_value(updated, "x", 2.0)
    assert updated["x"] == pytest.approx(2.0)
    battery_cell_model._try_set_parameter_value(
        SimpleNamespace(update=lambda _payload: (_ for _ in ()).throw(RuntimeError())),
        "x",
        2.0,
    )

    assert battery_cell_model._mapping_get({"x": 1}, "x") == 1
    assert battery_cell_model._mapping_get(object(), "x", "fallback") == "fallback"

    parameter_values = SimpleNamespace(evaluate=lambda value: value)
    assert battery_cell_model._evaluate_parameter_function(
        parameter_values=parameter_values,
        function_or_value=lambda _temp, _current, soc: 2.0 * soc,
        ambient_temperature_k=298.15,
        soc=0.5,
        default=1.0,
    ) == pytest.approx(1.0)
    assert battery_cell_model._evaluate_parameter_function(
        parameter_values=parameter_values,
        function_or_value=lambda: 3.0,
        ambient_temperature_k=298.15,
        soc=0.5,
        default=1.0,
    ) == pytest.approx(3.0)
    assert battery_cell_model._evaluate_parameter_function(
        parameter_values=object(),
        function_or_value=lambda _soc: (_ for _ in ()).throw(RuntimeError()),
        ambient_temperature_k=298.15,
        soc=0.5,
        default=7.0,
    ) == pytest.approx(7.0)
    with pytest.raises(MissingOptionalDependencyError):
        battery_cell_model._evaluate_parameter_function(
            parameter_values=object(),
            function_or_value=None,
            ambient_temperature_k=298.15,
            soc=0.5,
            default=7.0,
            strict=True,
            parameter_name="missing",
        )

    model = battery_cell_model.BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(3.0, 4.0),
        series_resistance_ohm=(0.01, 0.02),
        transient_resistance_ohm=(0.03, 0.04),
        transient_capacitance_f=(100.0, 200.0),
    )
    assert battery_cell_model.interpolate_cell_model(model, -1.0)[0] == pytest.approx(3.0)
    assert battery_cell_model.interpolate_cell_model(model, 2.0)[0] == pytest.approx(4.0)
    assert battery_cell_model.interpolate_cell_model(model, 0.5)[0] == pytest.approx(3.5)
    assert battery_cell_model._interpolate_temperature_lookup((), (), 0.5, temperature_c=25.0, default=9.0) == 9.0
    assert (
        battery_cell_model._interpolate_temperature_lookup(
            (25.0,),
            (),
            0.5,
            temperature_c=25.0,
            default=9.0,
        )
        == 9.0
    )


def test_battery_cell_model_two_rc_and_dynamic_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    steps_seen: list[tuple[str, ...]] = []

    class _FakeSolution:
        t = numpy.asarray([0.0, 1.0])

        def __getitem__(self, name: str) -> object:
            def _series(value: object, fill: float) -> float | numpy.ndarray:
                values = numpy.asarray(value)
                if values.ndim == 0:
                    return fill
                return numpy.full(len(values.reshape(-1)), fill)

            if name == "Current [A]":
                return lambda times: _series(times, 1.0)
            if name == "Voltage [V]":
                return lambda times: _series(times, 3.7)
            raise KeyError(name)

    class _FakeSimulation:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def solve(self, *, initial_soc: float) -> _FakeSolution:
            assert 0.0 <= initial_soc <= 1.0
            return _FakeSolution()

    def _experiment(steps: list[str]) -> tuple[str, ...]:
        steps_seen.append(tuple(steps))
        return tuple(steps)

    fake_model = SimpleNamespace(default_parameter_values={"Initial temperature [K]": 298.15})
    fake_pybamm = SimpleNamespace(
        lithium_ion=SimpleNamespace(SPM=lambda: fake_model),
        Experiment=_experiment,
        Simulation=_FakeSimulation,
    )
    monkeypatch.setattr(battery_cell_model, "import_pybamm", lambda: fake_pybamm)
    monkeypatch.setattr(battery_cell_model, "_TWO_RC_IDENTIFICATION_SOC_GRID", (0.5,))
    monkeypatch.setattr(battery_cell_model, "_TWO_RC_IDENTIFICATION_TEMPERATURES_C", (25.0,))

    traces = battery_cell_model._generate_pybamm_two_rc_identification_traces(resolved_parameter_set=None)
    assert len(traces) == 1
    assert traces[0].initial_soc == pytest.approx(0.5)
    assert steps_seen and steps_seen[0][-1] == "Rest for 300 seconds"
    assert len(battery_cell_model._build_two_rc_identification_experiment_steps(include_long_rest=False)) == 8

    simulated = battery_cell_model._simulate_two_rc_trace(
        time_s=(0.0, 1.0, 2.0),
        current_a=(1.0, 1.0, 0.0),
        initial_soc=0.5,
        capacity_ah=1.0,
        open_circuit_voltage_v=tuple(3.0 + soc for soc in battery_cell_model._TWO_RC_REFERENCE_SOC_GRID),
        series_resistance_ohm=0.01,
        transient_resistance_ohm=0.02,
        transient_capacitance_f=100.0,
        secondary_transient_resistance_ohm=0.03,
        secondary_transient_capacitance_f=200.0,
    )
    assert simulated.shape == (3,)
    assert battery_cell_model._advance_rc_voltage(1.0, 1.0, 0.0, 1.0, dt_s=1.0) == pytest.approx(0.0)

    fit_results = (
        battery_cell_model._TwoRcFitResult(
            initial_soc=0.1,
            temperature_c=15.0,
            series_resistance_ohm=0.01,
            transient_resistance_ohm=0.02,
            transient_capacitance_f=100.0,
            secondary_transient_resistance_ohm=0.03,
            secondary_transient_capacitance_f=200.0,
        ),
        battery_cell_model._TwoRcFitResult(
            initial_soc=0.9,
            temperature_c=35.0,
            series_resistance_ohm=0.02,
            transient_resistance_ohm=0.03,
            transient_capacitance_f=120.0,
            secondary_transient_resistance_ohm=0.04,
            secondary_transient_capacitance_f=220.0,
        ),
    )
    two_rc_model = battery_cell_model._build_two_rc_cell_model_from_fit_results(
        parameter_values={"Open-circuit voltage [V]": lambda _temp, _current, soc: 3.0 + soc},
        fit_results=fit_results,
        open_circuit_voltage_v=tuple(3.0 + soc for soc in battery_cell_model._TWO_RC_REFERENCE_SOC_GRID),
        ambient_temperature_k=298.15,
        source="test",
        resolved_parameter_set=None,
    )
    dynamic_values = battery_cell_model.interpolate_cell_model(two_rc_model, 0.5, temperature_c=25.0)
    assert dynamic_values[0] == pytest.approx(3.5)
    assert dynamic_values[1] > 0.0

    assert battery_cell_model._build_reference_ocv_lookup(
        parameter_values={"Open-circuit voltage [V]": lambda _temp, _current, soc: 3.0 + soc},
        resolved_parameter_set=None,
    )[5] == pytest.approx(3.5)
    fallback_ocv = battery_cell_model._build_reference_ocv_lookup(parameter_values={}, resolved_parameter_set=None)
    assert fallback_ocv[0] == pytest.approx(3.7)

    priors = battery_cell_model.BatteryThermalPriors(
        soc_grid=(0.0, 1.0),
        total_resistance_ohm=(0.1, 0.2),
        cell_to_jig_conductance_w_per_k=1.0,
        jig_to_ambient_conductance_w_per_k=1.0,
        cell_thermal_mass_j_per_k=1.0,
        jig_thermal_mass_j_per_k=1.0,
        reference_ambient_temperature_c=25.0,
    )
    assert battery_cell_model.interpolate_total_resistance(priors, -1.0) == pytest.approx(0.1)
    assert battery_cell_model.interpolate_total_resistance(priors, 2.0) == pytest.approx(0.2)
    assert battery_cell_model.interpolate_total_resistance(priors, 0.5) == pytest.approx(0.15)
