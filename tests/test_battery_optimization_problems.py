from __future__ import annotations

from typing import Protocol

import numpy
import pytest
from numpy.typing import NDArray

from design_research_problems import (
    MissingOptionalDependencyError,
    OptimizationEvaluation,
    OptimizationProblem,
    get_problem,
)
from design_research_problems.problems._domains.battery_layout import BatteryRequirements
from design_research_problems.problems.grammar._battery_cell_model import BatteryCellModel
from design_research_problems.problems.grammar._battery_circuit import BatteryCircuitState
from design_research_problems.problems.optimization import (
    BatteryGridSizingProblem,
    BatteryOpenEndedCapacityMaxProblem,
)


def _static_cell_model() -> BatteryCellModel:
    return BatteryCellModel(
        soc_grid=(0.0, 1.0),
        open_circuit_voltage_v=(4.2, 4.2),
        series_resistance_ohm=(0.01, 0.01),
        transient_resistance_ohm=(0.0, 0.0),
        transient_capacitance_f=(1.0, 1.0),
    )


def _patch_battery_loaders(monkeypatch: pytest.MonkeyPatch) -> None:
    from design_research_problems.problems.optimization import _battery_grid, _battery_open_ended

    monkeypatch.setattr(_battery_grid, "load_18650_cell_model", _static_cell_model)
    monkeypatch.setattr(_battery_open_ended, "load_18650_cell_model", _static_cell_model)


class _FakePymooProblem(Protocol):
    def _evaluate(self, x: NDArray[numpy.float64], out: dict[str, object]) -> None: ...


def test_battery_grid_seeded_initial_solution_is_deterministic_and_nonbaseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_series_parallel_cost_min")

    baseline = problem.generate_initial_solution()
    x1 = problem.generate_initial_solution(seed=7)
    x2 = problem.generate_initial_solution(seed=7)

    assert x1.shape == (2,)
    assert numpy.allclose(x1, x2)
    assert numpy.all(x1 >= problem.bounds.lb)
    assert numpy.all(x1 <= problem.bounds.ub)
    assert not numpy.allclose(x1, baseline)


def test_battery_grid_objective_components_and_solve_stay_public(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_series_parallel_cost_min")
    assert isinstance(problem, BatteryGridSizingProblem)

    baseline = problem.generate_initial_solution()
    components = problem.objective_components(baseline)
    evaluation = problem.evaluate(baseline)
    result = problem.solve(maxiter=25)
    state = problem.decode_candidate(result.x)

    assert set(components) == {"capacity_ah", "cell_count", "cost_usd", "current_limit_a", "voltage_v"}
    assert components["cost_usd"] == pytest.approx(evaluation.objective_value)
    assert components["cell_count"] == pytest.approx(16.0)
    assert result.success is True
    assert (state.series_count, state.parallel_count) == (4, 4)


def test_open_ended_battery_optimizer_is_registered_and_decodes_seed_state() -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")

    assert isinstance(problem, OptimizationProblem)
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)

    initial = problem.generate_initial_solution()
    state = problem.decode_candidate(initial)

    assert initial.shape == (32,)
    assert isinstance(state, BatteryCircuitState)
    assert len(state.cells) == 24
    assert len(state.connections) == 43


def test_open_ended_battery_optimizer_evaluate_and_solve_use_optimization_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    packaged_problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(packaged_problem, BatteryOpenEndedCapacityMaxProblem)

    requirements = BatteryRequirements(
        target_voltage_v=14.8,
        minimum_capacity_ah=10.0,
        minimum_current_a=240.0,
        max_width_mm=500.0,
        max_depth_mm=500.0,
        max_height_mm=250.0,
        voltage_tolerance_v=0.1,
    )
    problem = type(packaged_problem)(
        metadata=packaged_problem.metadata,
        requirements=requirements,
        max_cell_count=packaged_problem.max_cell_count,
    )

    initial = problem.generate_initial_solution()
    components = problem.objective_components(initial)
    evaluation = problem.evaluate(initial)
    result = problem.solve(maxiter=0)

    assert set(components) == {
        "cell_count",
        "connection_count",
        "delivered_capacity_ah",
        "design_volume_mm3",
        "end_voltage_v",
    }
    assert components["cell_count"] == pytest.approx(24.0)
    assert components["connection_count"] == pytest.approx(43.0)
    assert components["delivered_capacity_ah"] >= problem.requirements.minimum_capacity_ah
    assert isinstance(evaluation, OptimizationEvaluation)
    assert evaluation.x.shape == (32,)
    assert evaluation.is_feasible is True
    assert result.x.shape == (32,)
    assert result.success is (problem.max_constraint_violation(result.x) <= 1.0e-9)
    assert result.message.startswith("Evaluated the explicit battery transition program")


def test_open_ended_battery_optimizer_auto_prefers_pymoo_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)
    initial = problem.generate_initial_solution()

    class FakeElementwiseProblem:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeGA:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeRoundingRepair:
        pass

    class FakeRawResult:
        def __init__(self, x: NDArray[numpy.float64]) -> None:
            self.X = x
            self.algorithm = type(
                "FakeAlgorithm",
                (),
                {
                    "evaluator": type("FakeEvaluator", (), {"n_eval": 5})(),
                    "n_gen": 2,
                },
            )()

    def fake_minimize(
        pymoo_problem: _FakePymooProblem,
        algorithm: object,
        termination: object,
        seed: int | None,
        verbose: bool,
    ) -> FakeRawResult:
        del algorithm, termination, seed, verbose
        out: dict[str, object] = {}
        pymoo_problem._evaluate(initial, out)
        assert "F" in out
        return FakeRawResult(initial)

    monkeypatch.setattr(
        problem,
        "_import_pymoo_namespace",
        lambda: (FakeElementwiseProblem, FakeGA, FakeRoundingRepair, fake_minimize),
    )
    monkeypatch.setattr(
        problem,
        "_import_nevergrad_namespace",
        lambda: pytest.fail("nevergrad should not be used when pymoo is available"),
    )

    result = problem.solve(maxiter=4, solver_backend="auto")

    assert result.x.shape == (32,)
    assert "pymoo genetic baseline" in result.message


def test_open_ended_battery_optimizer_auto_falls_back_to_nevergrad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)
    initial = problem.generate_initial_solution()

    class FakeArrayBuilder:
        def __init__(self, *, shape: tuple[int, ...]) -> None:
            self.shape = shape

        def set_bounds(self, lower: float, upper: float) -> FakeArrayBuilder:
            del lower, upper
            return self

        def set_integer_casting(self) -> FakeArrayBuilder:
            return self

    class FakeCandidate:
        def __init__(self, value: NDArray[numpy.float64]) -> None:
            self.value = value

    class FakeRandomState:
        def __init__(self) -> None:
            self.seed_value: int | None = None

        def seed(self, value: int) -> None:
            self.seed_value = value

    class FakeNGOpt:
        def __init__(self, *, parametrization: object, budget: int, num_workers: int) -> None:
            del parametrization, budget, num_workers
            self.parametrization = type("FakeParametrization", (), {"random_state": FakeRandomState()})()

        def ask(self) -> FakeCandidate:
            return FakeCandidate(initial)

        def tell(self, candidate: FakeCandidate, value: float) -> None:
            del candidate, value

        def provide_recommendation(self) -> FakeCandidate:
            return FakeCandidate(initial)

    class FakeNevergrad:
        p = type("FakeParameterNamespace", (), {"Array": FakeArrayBuilder})
        optimizers = type("FakeOptimizerNamespace", (), {"NGOpt": FakeNGOpt})

    monkeypatch.setattr(
        problem,
        "_import_pymoo_namespace",
        lambda: (_ for _ in ()).throw(MissingOptionalDependencyError("pymoo missing")),
    )
    monkeypatch.setattr(problem, "_import_nevergrad_namespace", lambda: FakeNevergrad)

    result = problem.solve(maxiter=3, seed=11, solver_backend="auto")

    assert result.x.shape == (32,)
    assert "Nevergrad NGOpt baseline" in result.message


def test_open_ended_battery_optimizer_explicit_missing_backend_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)
    monkeypatch.setattr(
        problem,
        "_import_pymoo_namespace",
        lambda: (_ for _ in ()).throw(MissingOptionalDependencyError("pymoo missing")),
    )

    with pytest.raises(MissingOptionalDependencyError, match="pymoo missing"):
        problem.solve(maxiter=1, solver_backend="pymoo")


def test_open_ended_external_solver_keeps_default_baseline_as_incumbent_when_seeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_battery_loaders(monkeypatch)
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)

    class FakeElementwiseProblem:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeGA:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeRoundingRepair:
        pass

    class FakeRawResult:
        def __init__(self, x: NDArray[numpy.float64]) -> None:
            self.X = x
            self.algorithm = type(
                "FakeAlgorithm",
                (),
                {
                    "evaluator": type("FakeEvaluator", (), {"n_eval": 1})(),
                    "n_gen": 1,
                },
            )()

    seeded_start = problem.generate_initial_solution(seed=1)

    def fake_minimize(
        pymoo_problem: _FakePymooProblem,
        algorithm: object,
        termination: object,
        seed: int | None,
        verbose: bool,
    ) -> FakeRawResult:
        del pymoo_problem, algorithm, termination, seed, verbose
        return FakeRawResult(seeded_start)

    monkeypatch.setattr(
        problem,
        "_import_pymoo_namespace",
        lambda: (FakeElementwiseProblem, FakeGA, FakeRoundingRepair, fake_minimize),
    )

    result = problem.solve(maxiter=2, seed=1, solver_backend="pymoo")

    assert result.success is True
    assert problem.max_constraint_violation(result.x) <= 1.0e-9
    assert result.message.startswith("Optimized the explicit battery transition program with the pymoo genetic")


def test_open_ended_battery_decoder_treats_transition_enumeration_errors_as_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)
    initial_state = problem._grammar_helper.initial_state()

    def broken_enumeration(state: BatteryCircuitState) -> list[object]:
        del state
        raise ValueError("bad transition family")

    monkeypatch.setattr(problem._grammar_helper, "enumerate_transitions", broken_enumeration)

    decoded = problem.decode_candidate(numpy.array([1.0] + ([0.0] * 31), dtype=float))

    assert decoded == initial_state
