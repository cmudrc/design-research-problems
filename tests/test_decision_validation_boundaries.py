from __future__ import annotations

from collections.abc import Callable

import pytest

from design_research_problems.problems import _decision as decision


@pytest.mark.parametrize(
    "factory",
    [
        lambda: decision.DecisionVariableSpec(" ", "label", None, 0, 1),
        lambda: decision.DecisionVariableSpec("x", " ", None, 0, 1),
        lambda: decision.DecisionVariableSpec("x", "label", None, 2, 1),
        lambda: decision.DecisionFactor(" ", "label", None, (1,), ()),
        lambda: decision.DecisionFactor("x", " ", None, (1,), ()),
        lambda: decision.DecisionFactor("x", "label", None, (), ()),
        lambda: decision.DecisionFactor("x", "label", None, (1, 1), ()),
        lambda: decision.DecisionFactor("x", "label", None, (1, 2), (1,)),
        lambda: decision.DecisionProfile(" ", {}),
        lambda: decision.DecisionObjectiveSpec(" ", "label", "maximize", "choice", "x", (), True),
        lambda: decision.DecisionObjectiveSpec("x", " ", "maximize", "choice", "x", (), True),
        lambda: decision.DecisionObjectiveSpec("x", "label", " ", "choice", "x", (), True),
        lambda: decision.DecisionObjectiveSpec("x", "label", "maximize", " ", "x", (), True),
        lambda: decision.DecisionObjectiveSpec("x", "label", "maximize", "choice", " ", (), True),
        lambda: decision.DecisionConstraintSpec(" ", "label", "<=", "choice", "x", (), True),
        lambda: decision.DecisionConstraintSpec("x", " ", "<=", "choice", "x", (), True),
        lambda: decision.DecisionConstraintSpec("x", "label", " ", "choice", "x", (), True),
        lambda: decision.DecisionConstraintSpec("x", "label", "<=", " ", "x", (), True),
        lambda: decision.DecisionConstraintSpec("x", "label", "<=", "choice", " ", (), True),
        lambda: decision.DecisionChoiceBenchmark(" ", "label", 0.5, 5, 5, 1),
        lambda: decision.DecisionChoiceBenchmark("x", " ", 0.5, 5, 5, 1),
        lambda: decision.DecisionChoiceBenchmark("x", "label", 1.1, 5, 5, 1),
        lambda: decision.DecisionChoiceBenchmark("x", "label", 0.5, 5, 5, -1),
    ],
)
def test_decision_value_objects_reject_invalid_definitions(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError):
        factory()


def _evaluation(**overrides: object) -> decision.DecisionEvaluation:
    values: dict[str, object] = {
        "candidate_kind": "discrete-option",
        "candidate": decision.DecisionOption({"x": 1}),
        "candidate_label": "candidate",
        "objective_value": 1.0,
        "objective_metric": "utility",
    }
    values.update(overrides)
    return decision.DecisionEvaluation(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "overrides",
    [
        {"candidate_label": " "},
        {"objective_metric": " "},
        {"candidate_kind": "unknown"},
        {"choice_key": " "},
        {"choice_label": " "},
        {"response_count": -1},
    ],
)
def test_decision_evaluation_rejects_invalid_normalized_fields(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _evaluation(**overrides)


def test_decision_evaluation_normalizes_all_optional_metrics() -> None:
    result = _evaluation(
        utility=1,
        predicted_share=0.25,
        expected_demand_units=10,
        choice_key=" Choice ",
        choice_label=" Choice label ",
        top_choice_share=0.5,
        mean_rating=8,
        median_rating=9,
        std_rating=1,
        response_count=12,
    )
    assert result.choice_key == "choice"
    assert result.choice_label == "Choice label"
    assert result.expected_demand_units == 10.0
    assert result.response_count == 12


def test_natural_cubic_spline_validates_points_and_handles_each_interval_kind() -> None:
    with pytest.raises(ValueError, match="same length"):
        decision._NaturalCubicSpline.from_points((0, 1), (0,))
    with pytest.raises(ValueError, match="at least one"):
        decision._NaturalCubicSpline.from_points((), ())
    with pytest.raises(ValueError, match="strictly increasing"):
        decision._NaturalCubicSpline.from_points((0, 0), (0, 1))

    constant = decision._NaturalCubicSpline.from_points((1,), (3,))
    assert constant.evaluate(100) == 3

    linear = decision._NaturalCubicSpline.from_points((0, 1), (0, 2))
    assert linear.evaluate(-1) == pytest.approx(-2)
    assert linear.evaluate(2) == pytest.approx(4)

    curved = decision._NaturalCubicSpline.from_points((0, 1, 2), (0, 1, 0))
    assert curved.evaluate(0.5) > 0


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: decision._freeze_numeric_mapping({" ": 1}), "non-empty keys"),
        (lambda: decision._normalize_string_tuple(("ok", " "), "field"), "non-empty strings"),
        (lambda: decision._list_of_mappings("bad", "field"), "sequence of mappings"),
        (lambda: decision._list_of_mappings((1,), "field"), "entries must be mappings"),
        (lambda: decision._sequence("bad", "field"), "must be a sequence"),
        (lambda: decision._required_float({}, "missing"), "Missing required numeric field"),
        (lambda: decision._coerce_int(1.5, "field"), "must be an integer"),
        (lambda: decision._coerce_float(" ", "field"), "must not be an empty string"),
        (lambda: decision._coerce_float(object(), "field"), "must be numeric"),
        (lambda: decision._solve_tridiagonal((0,), (1,), (), (1,)), "same length"),
        (lambda: decision._solve_tridiagonal((0,), (0,), (0,), (1,)), "zero leading"),
        (lambda: decision._solve_tridiagonal((0, 1), (1, 1), (1, 0), (1, 1)), "singular"),
    ],
)
def test_decision_parsing_helpers_raise_field_specific_errors(
    call: Callable[[], object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        call()


def test_decision_parsing_helpers_cover_defaults_and_scalar_coercion() -> None:
    assert decision._list_of_mappings(None, "field") == ()
    assert decision._optional_string(None) is None
    assert decision._optional_string("  ") is None
    assert decision._coerce_float(True, "field") == 1.0
    assert decision._coerce_float(" 2.5 ", "field") == 2.5
    assert decision._solve_tridiagonal((), (), (), ()) == ()


def _factor(*, part_worths: list[float] | None = None) -> dict[str, object]:
    return {
        "key": "factor",
        "label": "Factor",
        "levels": [0, 1],
        "part_worths": [0, 1] if part_worths is None else part_worths,
    }


def _objective(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "key": "utility",
        "label": "Utility",
        "sense": "maximize",
        "domain": "discrete-option",
        "expression": "factor",
        "variables": ["factor"],
        "executable": True,
    }
    values.update(overrides)
    return values


def _constraint(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "key": "limit",
        "label": "Limit",
        "relation": "<=",
        "domain": "continuous-design",
        "expression": "x <= 1",
        "variables": ["x"],
        "executable": False,
    }
    values.update(overrides)
    return values


def _valid_structured_parameters() -> dict[str, object]:
    return {
        "decision_variable_specs": [
            {"symbol": "x", "label": "X", "lower_bound": 0, "upper_bound": 1},
        ],
        "option_factors": [_factor()],
        "competitor_profiles": [{"name": "baseline", "values": {"factor": 0}}],
        "objective_specs": [_objective()],
        "constraint_specs": [_constraint()],
    }


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda p: p.update(objective_specs=[_objective(), _objective()]), "Duplicate decision objective"),
        (lambda p: p.update(objective_specs=[_objective(sense="minimize")]), "must use sense"),
        (lambda p: p.update(option_factors=[]), "requires option_factors"),
        (lambda p: p.update(competitor_profiles=[]), "requires competitor_profiles"),
        (lambda p: p.update(option_factors=[_factor(part_worths=[])]), "requires factor part_worths"),
        (lambda p: p.update(objective_specs=[_objective(variables=["unknown"])]), "unknown factor keys"),
        (
            lambda p: p.update(
                objective_specs=[_objective(domain="empirical-choice", variables=["material"])],
            ),
            "requires choice_options",
        ),
        (
            lambda p: p.update(
                choice_options=[
                    {
                        "key": "steel",
                        "label": "Steel",
                        "top_choice_share": 0.5,
                        "mean_rating": 7,
                        "median_rating": 7,
                        "std_rating": 1,
                    }
                ],
                response_count=10,
                objective_specs=[_objective(domain="empirical-choice", variables=["unknown"])],
            ),
            "unknown variables",
        ),
        (lambda p: p.update(objective_specs=[_objective(domain="unsupported")]), "must use domain"),
        (
            lambda p: p.update(objective_specs=[_objective(executable=False, variables=["unknown"])]),
            "references unknown variables",
        ),
        (lambda p: p.update(constraint_specs=[_constraint(), _constraint()]), "Duplicate decision constraint"),
        (lambda p: p.update(constraint_specs=[_constraint(variables=["unknown"])]), "references unknown variables"),
        (lambda p: p.update(option_factors=[], objective_specs=[]), "competitor_profiles require option_factors"),
        (
            lambda p: p.update(competitor_profiles=[{"name": "baseline", "values": {"wrong": 0}}]),
            "must include exactly",
        ),
    ],
)
def test_structured_decision_payload_rejects_inconsistent_cross_references(
    mutator: Callable[[dict[str, object]], object],
    message: str,
) -> None:
    parameters = _valid_structured_parameters()
    mutator(parameters)
    with pytest.raises(ValueError, match=message):
        decision.parse_structured_decision_payload(parameters)


def test_structured_decision_parsers_reject_duplicate_and_malformed_entries() -> None:
    variable = {"symbol": "x", "label": "X", "lower_bound": 0, "upper_bound": 1}
    with pytest.raises(ValueError, match="Duplicate decision variable"):
        decision._parse_decision_variable_specs({"decision_variable_specs": [variable, variable]})
    with pytest.raises(ValueError, match="Duplicate option factor"):
        decision._parse_option_factors({"option_factors": [_factor(), _factor()]})

    choice = {
        "key": "steel",
        "label": "Steel",
        "top_choice_share": 0.5,
        "mean_rating": 7,
        "median_rating": 7,
        "std_rating": 1,
    }
    with pytest.raises(ValueError, match="Duplicate choice option key"):
        decision._parse_choice_benchmarks({"choice_options": [choice, choice]})
    with pytest.raises(ValueError, match="Duplicate choice option label"):
        decision._parse_choice_benchmarks({"choice_options": [choice, {**choice, "key": "aluminum", "label": "STEEL"}]})
    with pytest.raises(ValueError, match="values must be mappings"):
        decision._parse_competitor_profiles({"competitor_profiles": [{"name": "x", "values": []}]})
    with pytest.raises(ValueError, match="Duplicate competitor profile"):
        decision._parse_competitor_profiles(
            {"competitor_profiles": [{"name": "x", "values": {}}, {"name": "x", "values": {}}]}
        )
    with pytest.raises(ValueError, match="Unsupported default_choice_metric"):
        decision._parse_default_choice_metric({"default_choice_metric": "unknown"}, False)
    with pytest.raises(ValueError, match="must be positive"):
        decision._parse_response_count({"response_count": 0}, True)
    with pytest.raises(ValueError, match="must be non-negative"):
        decision._parse_response_count({"response_count": -1}, False)
