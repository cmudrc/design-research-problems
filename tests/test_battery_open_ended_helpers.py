from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy
import pytest

from design_research_problems import MissingOptionalDependencyError, get_problem
from design_research_problems.problems._optimization import OptimizationResult
from design_research_problems.problems.optimization import BatteryOpenEndedCapacityMaxProblem
from design_research_problems.problems.optimization import _battery_open_ended as battery_module


def _full_vector(value: float) -> numpy.ndarray[Any, numpy.dtype[numpy.float64]]:
    return numpy.full(32, value, dtype=float)


def test_open_ended_battery_auto_falls_back_to_local_after_missing_optional_backends(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)

    expected = OptimizationResult(
        x=problem.generate_initial_solution(),
        fun=1.0,
        success=True,
        message="local fallback",
        nit=1,
        nfev=1,
    )
    seen_backends: list[str] = []

    def fake_solve_with_backend(**kwargs: object) -> OptimizationResult:
        seen_backends.append(kwargs["solver_backend"])  # type: ignore[index]
        if len(seen_backends) < 4:
            raise MissingOptionalDependencyError("backend unavailable")
        return expected

    monkeypatch.setattr(problem, "_solve_with_backend", fake_solve_with_backend)

    result = problem.solve(maxiter=2, solver_backend="auto")

    assert result is expected
    assert seen_backends == ["pymoo", "nevergrad", "local", "local"]

    with pytest.raises(ValueError, match="Unsupported solver backend"):
        problem.solve(maxiter=1, solver_backend="unknown")


def test_open_ended_battery_helper_import_and_result_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)
    initial = problem.generate_initial_solution()

    monkeypatch.setattr(problem, "max_constraint_violation", lambda x: 0.5)
    monkeypatch.setattr(
        problem,
        "_evaluation_from_variables",
        lambda x: SimpleNamespace(delivered_capacity_ah=None, is_feasible=False),
    )
    result = problem._build_result(x=initial, fun=1.0, nit=3, nfev=4, solver_backend="local")
    assert result.success is False
    assert "best-effort design" in result.message

    monkeypatch.setattr(battery_module, "import_optional_module", lambda *args, **kwargs: SimpleNamespace())
    with pytest.raises(MissingOptionalDependencyError, match="pymoo is required"):
        problem._import_pymoo_namespace()

    sentinel = object()
    monkeypatch.setattr(battery_module, "import_optional_module", lambda *args, **kwargs: sentinel)
    assert problem._import_nevergrad_namespace() is sentinel

    with pytest.raises(ValueError, match="Expected a 32-variable design vector"):
        problem._normalize_vector(numpy.zeros(3, dtype=float))


def test_open_ended_battery_solver_and_state_helpers_cover_edge_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    problem = get_problem("battery_pack_18650_open_ended_capacity_max")
    assert isinstance(problem, BatteryOpenEndedCapacityMaxProblem)

    monkeypatch.setattr(problem, "objective", lambda x: float(numpy.sum(x)))
    initial = _full_vector(5.0)
    incumbent_x, incumbent_fun, incumbent_nfev = problem._solver_incumbent(
        initial_solution=initial,
        initial_solution_supplied=True,
    )
    assert numpy.array_equal(incumbent_x, initial)
    assert incumbent_fun == pytest.approx(160.0)
    assert incumbent_nfev == 1

    monkeypatch.setattr(problem, "_normalize_vector", lambda x: numpy.array(x, dtype=float, copy=True))
    monkeypatch.setattr(problem, "_solver_incumbent", lambda **kwargs: (_full_vector(5.0), 200.0, 1))
    monkeypatch.setattr(problem, "_build_result", lambda **kwargs: kwargs)
    monkeypatch.setattr(problem, "constraints", [])

    class FakeElementwiseProblem:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeGA:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

    class FakeRoundingRepair:
        pass

    class FakePymooResult:
        def __init__(self) -> None:
            self.X = _full_vector(0.0)
            self.algorithm = SimpleNamespace(evaluator=SimpleNamespace(n_eval=2), n_gen=3)

    monkeypatch.setattr(
        problem,
        "_import_pymoo_namespace",
        lambda: (FakeElementwiseProblem, FakeGA, FakeRoundingRepair, lambda *args, **kwargs: FakePymooResult()),
    )
    pymoo_result = problem._solve_with_pymoo(
        initial_solution=_full_vector(5.0),
        initial_solution_supplied=True,
        seed=1,
        maxiter=4,
    )
    assert numpy.array_equal(pymoo_result["x"], _full_vector(0.0))
    assert pymoo_result["fun"] == pytest.approx(0.0)

    class FakeArrayBuilder:
        def __init__(self, *, shape: tuple[int, ...]) -> None:
            self.shape = shape

        def set_bounds(self, lower: float, upper: float) -> FakeArrayBuilder:
            del lower, upper
            return self

        def set_integer_casting(self) -> FakeArrayBuilder:
            return self

    class FakeCandidate:
        def __init__(self, value: numpy.ndarray[Any, numpy.dtype[numpy.float64]]) -> None:
            self.value = value

    class FakeNGOpt:
        def __init__(self, *, parametrization: object, budget: int, num_workers: int) -> None:
            del parametrization, budget, num_workers
            self.parametrization = SimpleNamespace(random_state=None)
            self._candidates = [FakeCandidate(_full_vector(4.0)), FakeCandidate(_full_vector(3.0))]

        def ask(self) -> FakeCandidate:
            return self._candidates.pop(0)

        def tell(self, candidate: FakeCandidate, value: float) -> None:
            del candidate, value

        def provide_recommendation(self) -> FakeCandidate:
            return FakeCandidate(_full_vector(2.0))

    fake_nevergrad = SimpleNamespace(
        p=SimpleNamespace(Array=FakeArrayBuilder),
        optimizers=SimpleNamespace(NGOpt=FakeNGOpt),
    )
    monkeypatch.setattr(problem, "_import_nevergrad_namespace", lambda: fake_nevergrad)
    nevergrad_result = problem._solve_with_nevergrad(
        initial_solution=_full_vector(5.0),
        initial_solution_supplied=True,
        seed=None,
        maxiter=2,
    )
    assert numpy.array_equal(nevergrad_result["x"], _full_vector(2.0))
    assert nevergrad_result["fun"] == pytest.approx(64.0)

    cached_state = object()
    cached_genes = (1,) + (0,) * 31
    problem._state_cache[cached_genes] = cached_state  # type: ignore[assignment]
    assert problem._state_from_genes(cached_genes) is cached_state

    fresh_state = object()

    class ValueErrorGrammar:
        def initial_state(self) -> object:
            return fresh_state

        def enumerate_transitions(self, state: object) -> tuple[object, ...]:
            del state
            raise ValueError("bad transitions")

    monkeypatch.setattr(problem, "_grammar_helper", ValueErrorGrammar())
    assert problem._state_from_genes((2,) + (0,) * 31) is fresh_state

    class EmptyGrammar:
        def initial_state(self) -> object:
            return fresh_state

        def enumerate_transitions(self, state: object) -> tuple[object, ...]:
            del state
            return ()

    monkeypatch.setattr(problem, "_grammar_helper", EmptyGrammar())
    assert problem._state_from_genes((3,) + (0,) * 31) is fresh_state
    with pytest.raises(RuntimeError, match="add_cell transition"):
        problem._apply_add_cell_transition(fresh_state, x=0, y=0, z=0)
    with pytest.raises(RuntimeError, match="set_pack_terminals transition"):
        problem._apply_set_pack_terminals_transition(fresh_state, positive_terminal_id=1, negative_terminal_id=0)
