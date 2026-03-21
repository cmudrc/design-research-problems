"""Open-ended explicit battery-pack capacity maximization problem."""

from __future__ import annotations

import math
from typing import Any, cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._battery_adapters import (
    DEFAULT_COOLING_COEFFICIENT,
    DEFAULT_PASSIVE_COOLING,
    DEFAULT_THERMAL_AIRFLOW_AXIS,
    DEFAULT_THERMAL_CONTACT_DECAY_MM,
    DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W,
    DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR,
    DEFAULT_THERMAL_MODEL,
    DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM,
    DEFAULT_THERMAL_REFERENCE_SOC,
    BatteryEvaluationAdapterOutcome,
    BatteryThermalPromotionConfig,
    coerce_battery_thermal_airflow_axis,
    coerce_battery_thermal_model,
    evaluate_explicit_netlist_state,
)
from design_research_problems.problems._battery_problem_config import (
    parse_battery_backend_config,
    parse_battery_requirements,
    resolve_battery_requirements,
)
from design_research_problems.problems._battery_tier_shared import (
    _DEFAULT_AMBIENT_TEMPERATURE_C,
    _DEFAULT_MAX_TEMPERATURE_C,
    _score_metrics,
)
from design_research_problems.problems._domains.battery_benchmark import (
    BatteryEvaluationMode,
    BatteryRepresentationMode,
    build_battery_evaluation_provenance,
    coerce_battery_evaluation_mode,
    supported_pack_evaluation_modes,
)
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    load_18650_cell_model,
)
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    evaluate_battery_circuit,
)
from design_research_problems.problems._domains.battery_layout import (
    BatteryRequirements,
)
from design_research_problems.problems._domains.battery_tier_metrics import BatteryObjectiveWeights, BatteryTierMetrics
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)
from design_research_problems.problems.grammar._battery_pack_open import BatteryPack18650OpenEndedProblem

_TRANSITION_PROGRAM_LENGTH = 32
_MAX_TRANSITION_TOKEN = 8_192
_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_CELL_TIE_BREAK_SCALE = 1.0e-3
_CONNECTION_TIE_BREAK_SCALE = 1.0e-4
_VOLUME_TIE_BREAK_SCALE = 1.0e-8
_SEARCH_DELTAS = (-64, -16, -4, -1, 1, 4, 16, 64)
_AUTO_SOLVER_ORDER = ("pymoo", "nevergrad", "local")
_T3B_SUPPORTED_EVALUATION_MODES = supported_pack_evaluation_modes(BatteryRepresentationMode.EXPLICIT_NETLIST)


class BatteryOpenEndedCapacityMaxProblem(OptimizationProblem):
    """Transition-program optimizer over the open-ended explicit battery grammar."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        backend_config: BatteryBackendConfig | None = None,
    ) -> None:
        """Initialize the packaged open-ended capacity-maximization benchmark.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            requirements: Optional battery-pack requirements override.
            max_cell_count: Maximum allowed cell count in generated states.
            backend_config: Optional backend fidelity configuration.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.requirements = resolve_battery_requirements(requirements)
        self.max_cell_count = max_cell_count
        self.backend_config = backend_config
        self.bounds = Bounds(
            lb=numpy.zeros(_TRANSITION_PROGRAM_LENGTH, dtype=float),
            ub=numpy.full(_TRANSITION_PROGRAM_LENGTH, float(_MAX_TRANSITION_TOKEN), dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._backend_feasibility_margin),
        ]
        self._grammar_helper = BatteryPack18650OpenEndedProblem(
            metadata=metadata,
            requirements=self.requirements,
            max_cell_count=self.max_cell_count,
            backend_config=self.backend_config,
        )
        self._state_cache: dict[tuple[int, ...], BatteryCircuitState] = {}
        self._evaluation_cache: dict[tuple[int, ...], BatteryCircuitEvaluation] = {}
        self._baseline_program = self._build_canonical_seed_program()
        self._seed_prefix_length = sum(1 for gene in self._baseline_program if gene != 0)

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryOpenEndedCapacityMaxProblem:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized open-ended battery optimization problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, manifest.parameters.get("max_cell_count", 24))),
            backend_config=parse_battery_backend_config(manifest),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the canonical 4S6P build program, optionally with seeded tail noise.

        Args:
            seed: Optional seed used to randomize the unused tail tokens.

        Returns:
            Fixed-length transition-program vector.
        """
        baseline = numpy.array(self._baseline_program, dtype=float)
        if seed is None:
            return baseline

        rng = numpy.random.default_rng(seed)
        tail_length = _TRANSITION_PROGRAM_LENGTH - self._seed_prefix_length
        if tail_length > 0:
            baseline[self._seed_prefix_length :] = rng.integers(0, _MAX_TRANSITION_TOKEN + 1, size=tail_length)
        return baseline

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> BatteryCircuitState:
        """Decode one transition program into an explicit battery circuit state.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Decoded explicit battery-circuit state.
        """
        return self._state_from_genes(self._normalized_genes(variables))

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the main reported performance metrics for one transition program.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Reported scalar metrics for the decoded battery design.
        """
        evaluation = self._evaluation_from_variables(variables)
        return {
            "delivered_capacity_ah": (
                0.0 if evaluation.delivered_capacity_ah is None else evaluation.delivered_capacity_ah
            ),
            "end_voltage_v": (
                0.0 if evaluation.pack_terminal_voltage_end is None else evaluation.pack_terminal_voltage_end
            ),
            "cell_count": float(evaluation.cell_count),
            "connection_count": float(evaluation.connection_count),
            "design_volume_mm3": evaluation.design_volume,
        }

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the scalarized capacity-maximization objective.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Scalar minimization objective for the candidate.
        """
        evaluation = self._evaluation_from_variables(variables)
        delivered_capacity = 0.0 if evaluation.delivered_capacity_ah is None else evaluation.delivered_capacity_ah
        penalty = _INFEASIBILITY_PENALTY_SCALE * self.constraint_violation(self._normalize_vector(variables))
        simplicity_tie_break = (
            (_CELL_TIE_BREAK_SCALE * float(evaluation.cell_count))
            + (_CONNECTION_TIE_BREAK_SCALE * float(evaluation.connection_count))
            + (_VOLUME_TIE_BREAK_SCALE * evaluation.design_volume)
        )
        return (-delivered_capacity) + penalty + simplicity_tie_break

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
        solver_backend: str = "auto",
    ) -> OptimizationResult:
        """Solve the transition-program search with optional external backends.

        Args:
            initial_solution: Optional starting transition program.
            seed: Optional random seed for stochastic backends.
            maxiter: Maximum optimization iterations or evaluations.
            solver_backend: Requested solver backend or ``"auto"``.

        Returns:
            Best optimization result returned by the selected backend.

        Raises:
            ValueError: If ``solver_backend`` is unsupported.
        """
        start = (
            self.generate_initial_solution(seed=seed)
            if initial_solution is None
            else self._normalize_vector(initial_solution)
        )
        if maxiter <= 0:
            return self._build_result(
                x=start,
                fun=self.objective(start),
                nit=0,
                nfev=1,
                solver_backend="local",
            )

        normalized_backend = solver_backend.strip().lower()
        if normalized_backend == "auto":
            for candidate_backend in _AUTO_SOLVER_ORDER:
                try:
                    return self._solve_with_backend(
                        solver_backend=candidate_backend,
                        initial_solution=start,
                        initial_solution_supplied=initial_solution is not None,
                        seed=seed,
                        maxiter=maxiter,
                    )
                except MissingOptionalDependencyError:
                    continue
            return self._solve_with_backend(
                solver_backend="local",
                initial_solution=start,
                initial_solution_supplied=initial_solution is not None,
                seed=seed,
                maxiter=maxiter,
            )

        if normalized_backend not in {"local", "pymoo", "nevergrad"}:
            raise ValueError(
                "Unsupported solver backend "
                f"{solver_backend!r}. Expected one of 'auto', 'local', 'pymoo', or 'nevergrad'."
            )
        return self._solve_with_backend(
            solver_backend=normalized_backend,
            initial_solution=start,
            initial_solution_supplied=initial_solution is not None,
            seed=seed,
            maxiter=maxiter,
        )

    def _solve_with_backend(
        self,
        *,
        solver_backend: str,
        initial_solution: NDArray[numpy.float64],
        initial_solution_supplied: bool,
        seed: int | None,
        maxiter: int,
    ) -> OptimizationResult:
        """Dispatch to one concrete solver backend.

        Args:
            solver_backend: Concrete backend name.
            initial_solution: Starting transition program.
            initial_solution_supplied: Whether the caller explicitly supplied the start.
            seed: Optional random seed.
            maxiter: Optimization budget.

        Returns:
            Optimization result from the selected backend.
        """
        if solver_backend == "pymoo":
            return self._solve_with_pymoo(
                initial_solution=initial_solution,
                initial_solution_supplied=initial_solution_supplied,
                seed=seed,
                maxiter=maxiter,
            )
        if solver_backend == "nevergrad":
            return self._solve_with_nevergrad(
                initial_solution=initial_solution,
                initial_solution_supplied=initial_solution_supplied,
                seed=seed,
                maxiter=maxiter,
            )
        return self._solve_with_local_search(initial_solution=initial_solution, maxiter=maxiter)

    def _solve_with_local_search(
        self,
        *,
        initial_solution: NDArray[numpy.float64],
        maxiter: int,
    ) -> OptimizationResult:
        """Run the built-in deterministic hill-climbing baseline.

        Args:
            initial_solution: Starting transition program.
            maxiter: Maximum hill-climbing sweeps.

        Returns:
            Best result found by the local baseline.
        """
        current = initial_solution.copy()
        current_score = self.objective(current)
        nfev = 1
        nit = 0
        tolerance = 1.0e-12

        for _ in range(max(0, maxiter)):
            nit += 1
            best_candidate: NDArray[numpy.float64] | None = None
            best_score = current_score
            for index in range(_TRANSITION_PROGRAM_LENGTH):
                for delta in _SEARCH_DELTAS:
                    candidate = current.copy()
                    candidate[index] = float(
                        numpy.clip(candidate[index] + float(delta), self.bounds.lb[index], self.bounds.ub[index])
                    )
                    score = self.objective(candidate)
                    nfev += 1
                    if score + tolerance < best_score:
                        best_candidate = candidate
                        best_score = score
            if best_candidate is None:
                break
            current = best_candidate
            current_score = best_score
        return self._build_result(
            x=current,
            fun=current_score,
            nit=nit,
            nfev=nfev,
            solver_backend="local",
        )

    def _solve_with_pymoo(
        self,
        *,
        initial_solution: NDArray[numpy.float64],
        initial_solution_supplied: bool,
        seed: int | None,
        maxiter: int,
    ) -> OptimizationResult:
        """Run a mixed-integer `pymoo` genetic baseline when available.

        Args:
            initial_solution: Starting transition program.
            initial_solution_supplied: Whether the caller explicitly supplied the start.
            seed: Optional random seed.
            maxiter: Optimization budget.

        Returns:
            Best result found by the pymoo baseline.
        """
        elementwise_problem_cls, ga_cls, rounding_repair_cls, minimize = self._import_pymoo_namespace()

        def _problem_init(instance: object) -> None:
            """Initialize one pymoo elementwise problem wrapper.

            Args:
                instance: Dynamically created pymoo problem instance.
            """
            elementwise_problem_cls.__init__(
                instance,
                n_var=_TRANSITION_PROGRAM_LENGTH,
                n_obj=1,
                n_ieq_constr=len(self.constraints),
                xl=self.bounds.lb,
                xu=self.bounds.ub,
                vtype=int,
            )

        def _problem_evaluate(
            instance: object,
            x: NDArray[numpy.float64],
            out: dict[str, object],
            *args: object,
            **kwargs: object,
        ) -> None:
            """Evaluate one transition program for the pymoo adapter.

            Args:
                instance: Dynamically created pymoo problem instance.
                x: Candidate transition-program vector.
                out: Mutable pymoo output mapping.
                *args: Unused positional adapter arguments.
                **kwargs: Unused keyword adapter arguments.
            """
            del instance, args, kwargs
            candidate = self._normalize_vector(numpy.asarray(x, dtype=float))
            out["F"] = self.objective(candidate)
            out["G"] = numpy.array(
                [-constraint.evaluate(candidate) for constraint in self.constraints],
                dtype=float,
            )

        transition_problem_cls = cast(
            type[Any],
            type(
                "_TransitionProgramProblem",
                (elementwise_problem_cls,),
                {
                    "__init__": _problem_init,
                    "_evaluate": _problem_evaluate,
                },
            ),
        )

        pop_size = max(8, min(32, maxiter))
        generations = max(1, math.ceil(maxiter / pop_size))
        algorithm = ga_cls(
            pop_size=pop_size,
            eliminate_duplicates=True,
            repair=rounding_repair_cls(),
        )
        raw_result = minimize(
            transition_problem_cls(),
            algorithm,
            ("n_gen", generations),
            seed=seed,
            verbose=False,
        )
        best_x, best_fun, nfev = self._solver_incumbent(
            initial_solution=initial_solution,
            initial_solution_supplied=initial_solution_supplied,
        )
        raw_x = getattr(raw_result, "X", None)
        if raw_x is not None:
            candidate = self._normalize_vector(numpy.asarray(raw_x, dtype=float))
            candidate_fun = self.objective(candidate)
            nfev += 1
            if candidate_fun < best_fun:
                best_x = candidate
                best_fun = candidate_fun
        evaluator = getattr(getattr(raw_result, "algorithm", None), "evaluator", None)
        if evaluator is not None:
            nfev += int(getattr(evaluator, "n_eval", 0) or 0)
        nit = int(getattr(getattr(raw_result, "algorithm", None), "n_gen", 0) or generations)
        return self._build_result(
            x=best_x,
            fun=best_fun,
            nit=nit,
            nfev=nfev,
            solver_backend="pymoo",
        )

    def _solve_with_nevergrad(
        self,
        *,
        initial_solution: NDArray[numpy.float64],
        initial_solution_supplied: bool,
        seed: int | None,
        maxiter: int,
    ) -> OptimizationResult:
        """Run a derivative-free `nevergrad` baseline when available.

        Args:
            initial_solution: Starting transition program.
            initial_solution_supplied: Whether the caller explicitly supplied the start.
            seed: Optional random seed.
            maxiter: Evaluation budget.

        Returns:
            Best result found by the Nevergrad baseline.
        """
        nevergrad: Any = self._import_nevergrad_namespace()
        parametrization = (
            nevergrad.p.Array(shape=(_TRANSITION_PROGRAM_LENGTH,))
            .set_bounds(0.0, float(_MAX_TRANSITION_TOKEN))
            .set_integer_casting()
        )
        optimizer = nevergrad.optimizers.NGOpt(
            parametrization=parametrization,
            budget=maxiter,
            num_workers=1,
        )
        random_state = getattr(getattr(optimizer, "parametrization", None), "random_state", None)
        if seed is not None and random_state is not None:
            random_state.seed(seed)

        best_x, best_fun, nfev = self._solver_incumbent(
            initial_solution=initial_solution,
            initial_solution_supplied=initial_solution_supplied,
        )
        for _ in range(maxiter):
            candidate = optimizer.ask()
            candidate_x = self._normalize_vector(numpy.asarray(candidate.value, dtype=float))
            candidate_fun = self.objective(candidate_x)
            optimizer.tell(candidate, candidate_fun)
            nfev += 1
            if candidate_fun < best_fun:
                best_x = candidate_x
                best_fun = candidate_fun
        recommendation = optimizer.provide_recommendation()
        recommended_x = self._normalize_vector(numpy.asarray(recommendation.value, dtype=float))
        recommended_fun = self.objective(recommended_x)
        nfev += 1
        if recommended_fun < best_fun:
            best_x = recommended_x
            best_fun = recommended_fun
        return self._build_result(
            x=best_x,
            fun=best_fun,
            nit=maxiter,
            nfev=nfev,
            solver_backend="nevergrad",
        )

    def _build_result(
        self,
        *,
        x: NDArray[numpy.float64],
        fun: float,
        nit: int,
        nfev: int,
        solver_backend: str,
    ) -> OptimizationResult:
        """Return one normalized optimization result with a backend-specific message.

        Args:
            x: Candidate transition program.
            fun: Objective value at ``x``.
            nit: Iteration count reported by the backend.
            nfev: Objective evaluations consumed.
            solver_backend: Backend label used for messaging.

        Returns:
            Normalized optimization result payload.
        """
        best_x = self._normalize_vector(x)
        best_fun = float(fun)
        max_violation = self.max_constraint_violation(best_x)
        evaluation = self._evaluation_from_variables(best_x)
        delivered_capacity = 0.0 if evaluation.delivered_capacity_ah is None else evaluation.delivered_capacity_ah
        action = "Evaluated" if nit == 0 else "Optimized"
        backend_label = {
            "local": "the built-in deterministic local baseline",
            "pymoo": "the pymoo genetic baseline",
            "nevergrad": "the Nevergrad NGOpt baseline",
        }[solver_backend]
        if max_violation <= 1.0e-9:
            message = (
                f"{action} the explicit battery transition program with {backend_label} "
                f"(delivered capacity {delivered_capacity:.3f} Ah)."
            )
        else:
            message = (
                f"{action} the explicit battery transition program with {backend_label} and returned "
                f"a best-effort design (delivered capacity {delivered_capacity:.3f} Ah, "
                f"max violation {max_violation:.3g})."
            )
        return OptimizationResult(
            x=best_x.copy(),
            fun=best_fun,
            success=max_violation <= 1.0e-9,
            message=message,
            nit=nit,
            nfev=nfev,
        )

    def _solver_incumbent(
        self,
        *,
        initial_solution: NDArray[numpy.float64],
        initial_solution_supplied: bool,
    ) -> tuple[NDArray[numpy.float64], float, int]:
        """Return the starting incumbent for optional external solvers.

        Args:
            initial_solution: Starting transition program.
            initial_solution_supplied: Whether the caller explicitly supplied the start.

        Returns:
            Current incumbent vector, objective, and evaluation count.
        """
        incumbent = initial_solution.copy()
        incumbent_fun = self.objective(incumbent)
        nfev = 1
        if initial_solution_supplied:
            return (incumbent, incumbent_fun, nfev)

        baseline = self.generate_initial_solution()
        if not numpy.array_equal(baseline, incumbent):
            baseline_fun = self.objective(baseline)
            nfev += 1
            if baseline_fun < incumbent_fun:
                incumbent = baseline
                incumbent_fun = baseline_fun
        return (incumbent, incumbent_fun, nfev)

    def _import_pymoo_namespace(self) -> tuple[Any, Any, Any, Any]:
        """Import the supported `pymoo` classes lazily.

        Returns:
            Imported pymoo classes and helper function.

        Raises:
            MissingOptionalDependencyError: If pymoo is unavailable or incomplete.
        """
        elementwise_problem_module = import_optional_module(
            "pymoo.core.problem",
            required_for="the open-ended battery genetic baseline",
            extras=("solvers",),
            dependency_label="pymoo",
        )
        ga_module = import_optional_module(
            "pymoo.algorithms.soo.nonconvex.ga",
            required_for="the open-ended battery genetic baseline",
            extras=("solvers",),
            dependency_label="pymoo",
        )
        rounding_repair_module = import_optional_module(
            "pymoo.operators.repair.rounding",
            required_for="the open-ended battery genetic baseline",
            extras=("solvers",),
            dependency_label="pymoo",
        )
        optimize_module = import_optional_module(
            "pymoo.optimize",
            required_for="the open-ended battery genetic baseline",
            extras=("solvers",),
            dependency_label="pymoo",
        )
        try:
            elementwise_problem = elementwise_problem_module.ElementwiseProblem
            ga = ga_module.GA
            rounding_repair = rounding_repair_module.RoundingRepair
            minimize = optimize_module.minimize
        except AttributeError as exc:
            raise MissingOptionalDependencyError(
                "pymoo is required for the open-ended battery genetic baseline. "
                "Install it with: pip install design-research-problems[solvers]"
            ) from exc

        return (elementwise_problem, ga, rounding_repair, minimize)

    def _import_nevergrad_namespace(self) -> Any:
        """Import `nevergrad` lazily for the derivative-free baseline.

        Returns:
            Imported ``nevergrad`` module namespace.

        Raises:
            MissingOptionalDependencyError: If nevergrad is unavailable.
        """
        return import_optional_module(
            "nevergrad",
            required_for="the open-ended battery derivative-free baseline",
            extras=("solvers",),
            dependency_label="nevergrad",
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return a clipped fixed-length transition vector.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Clipped fixed-length transition vector.

        Raises:
            ValueError: If ``variables`` has the wrong shape.
        """
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != (_TRANSITION_PROGRAM_LENGTH,):
            raise ValueError(
                f"Expected a {_TRANSITION_PROGRAM_LENGTH}-variable design vector, received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _normalized_genes(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        """Return the rounded integer transition program represented by ``variables``.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Rounded integer transition genes.
        """
        normalized = self._normalize_vector(variables)
        return tuple(
            int(
                max(
                    0,
                    min(_MAX_TRANSITION_TOKEN, round(float(value))),
                )
            )
            for value in normalized
        )

    def _state_from_genes(self, genes: tuple[int, ...]) -> BatteryCircuitState:
        """Decode one normalized transition program into a cached explicit state.

        Args:
            genes: Rounded transition-program genes.

        Returns:
            Decoded explicit battery-circuit state.
        """
        cached = self._state_cache.get(genes)
        if cached is not None:
            return cached

        state = self._grammar_helper.initial_state()
        for gene in genes:
            if gene == 0:
                break
            try:
                transitions = self._grammar_helper.enumerate_transitions(state)
            except ValueError:
                break
            if not transitions:
                break
            state = transitions[(gene - 1) % len(transitions)].next_state

        self._state_cache[genes] = state
        return state

    def _evaluate_state(self, state: BatteryCircuitState) -> BatteryCircuitEvaluation:
        """Evaluate one explicit battery state using the shared backend.

        Args:
            state: Explicit battery-circuit state.

        Returns:
            Shared-backend evaluation for the state.
        """
        return evaluate_battery_circuit(
            state=state,
            requirements=self.requirements,
            load_cell_model=load_18650_cell_model,
            simulate_to_failure=True,
            backend_config=self.backend_config,
        )

    def _evaluation_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryCircuitEvaluation:
        """Return the cached evaluation for one transition program.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Cached or freshly computed backend evaluation.
        """
        genes = self._normalized_genes(variables)
        cached = self._evaluation_cache.get(genes)
        if cached is not None:
            return cached

        state = self._state_from_genes(genes)
        evaluation = self._evaluate_state(state)
        self._evaluation_cache[genes] = evaluation
        return evaluation

    def _build_canonical_seed_program(self) -> tuple[int, ...]:
        """Return the exact public-transition 4S6P canonical build program.

        Returns:
            Canonical fixed-length transition-program genes.

        Raises:
            RuntimeError: If the canonical build no longer has the expected length.
        """
        state = self._grammar_helper.initial_state()
        genes: list[int] = []
        global_negative_terminal_id = state.pack_negative_terminal_id
        stage_output_terminal_id = state.pack_positive_terminal_id

        for branch_index in range(1, 6):
            gene, state = self._apply_add_cell_transition(
                state,
                x=0,
                y=branch_index,
                z=0,
            )
            genes.append(gene)

        for stage_index in range(1, 4):
            previous_stage_output_terminal_id = stage_output_terminal_id
            gene, state = self._apply_add_cell_transition(
                state,
                x=stage_index,
                y=0,
                z=0,
                connect_negative_to_terminal_id=previous_stage_output_terminal_id,
                use_positive_as_pack_terminal=True,
            )
            genes.append(gene)
            stage_output_terminal_id = state.pack_positive_terminal_id
            gene, state = self._apply_set_pack_terminals_transition(
                state,
                positive_terminal_id=stage_output_terminal_id,
                negative_terminal_id=previous_stage_output_terminal_id,
            )
            genes.append(gene)
            for branch_index in range(1, 6):
                gene, state = self._apply_add_cell_transition(
                    state,
                    x=stage_index,
                    y=branch_index,
                    z=0,
                )
                genes.append(gene)
        gene, state = self._apply_set_pack_terminals_transition(
            state,
            positive_terminal_id=stage_output_terminal_id,
            negative_terminal_id=global_negative_terminal_id,
        )
        genes.append(gene)

        if len(genes) != 27:
            raise RuntimeError(f"Expected a 27-step canonical build program, received {len(genes)} steps.")
        return tuple(genes + ([0] * (_TRANSITION_PROGRAM_LENGTH - len(genes))))

    def _apply_add_cell_transition(
        self,
        state: BatteryCircuitState,
        *,
        x: int,
        y: int,
        z: int,
        connect_negative_to_terminal_id: int | None = None,
        connect_positive_to_terminal_id: int | None = None,
        use_negative_as_pack_terminal: bool = False,
        use_positive_as_pack_terminal: bool = False,
    ) -> tuple[int, BatteryCircuitState]:
        """Return the gene that selects one exact add-cell transition and the resulting state.

        Args:
            state: Current battery-circuit state.
            x: Cell x-index.
            y: Cell y-index.
            z: Cell z-index.
            connect_negative_to_terminal_id: Optional negative-terminal connection.
            connect_positive_to_terminal_id: Optional positive-terminal connection.
            use_negative_as_pack_terminal: Whether to promote the negative terminal.
            use_positive_as_pack_terminal: Whether to promote the positive terminal.

        Returns:
            Transition gene and the resulting next state.

        Raises:
            RuntimeError: If the requested transition cannot be found.
        """
        parameters = (
            ("x", x),
            ("y", y),
            ("z", z),
            ("connect_negative_to_terminal_id", connect_negative_to_terminal_id),
            ("connect_positive_to_terminal_id", connect_positive_to_terminal_id),
            ("use_negative_as_pack_terminal", use_negative_as_pack_terminal),
            ("use_positive_as_pack_terminal", use_positive_as_pack_terminal),
        )
        transitions = self._grammar_helper.enumerate_transitions(state)
        for index, transition in enumerate(transitions, start=1):
            if transition.rule_name == "add_cell" and transition.parameters == parameters:
                return (index, transition.next_state)
        raise RuntimeError(f"Unable to find the requested add_cell transition for parameters {parameters!r}.")

    def _voltage_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining nominal-voltage tolerance margin.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Remaining voltage margin relative to the packaged tolerance.
        """
        evaluation = self._evaluation_from_variables(variables)
        voltage_error = abs(evaluation.pack_nominal_voltage - self.requirements.target_voltage_v)
        return self.requirements.voltage_tolerance_v - voltage_error

    def _apply_set_pack_terminals_transition(
        self,
        state: BatteryCircuitState,
        *,
        positive_terminal_id: int,
        negative_terminal_id: int,
    ) -> tuple[int, BatteryCircuitState]:
        """Return the gene that selects one exact pack-terminal reassignment.

        Args:
            state: Current battery-circuit state.
            positive_terminal_id: Requested positive terminal id.
            negative_terminal_id: Requested negative terminal id.

        Returns:
            Transition gene and the resulting next state.

        Raises:
            RuntimeError: If the requested transition cannot be found.
        """
        parameters = (
            ("positive_terminal_id", positive_terminal_id),
            ("negative_terminal_id", negative_terminal_id),
        )
        transitions = self._grammar_helper.enumerate_transitions(state)
        for index, transition in enumerate(transitions, start=1):
            if transition.rule_name == "set_pack_terminals" and transition.parameters == parameters:
                return (index, transition.next_state)
        raise RuntimeError(f"Unable to find the requested set_pack_terminals transition for {parameters!r}.")

    def _capacity_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return the remaining delivered-capacity margin in amp-hours.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            Remaining delivered-capacity margin.
        """
        delivered_capacity = self._evaluation_from_variables(variables).delivered_capacity_ah
        return (0.0 if delivered_capacity is None else delivered_capacity) - self.requirements.minimum_capacity_ah

    def _backend_feasibility_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return a binary margin indicating whether the shared backend accepted the design.

        Args:
            variables: Candidate transition-program vector.

        Returns:
            ``1.0`` for feasible designs and ``-1.0`` otherwise.
        """
        return 1.0 if self._evaluation_from_variables(variables).is_feasible else -1.0


class Battery18650T3BNetlistExplicitOptimizationProblem(BatteryOpenEndedCapacityMaxProblem):
    """Public tier-3B explicit-netlist battery benchmark."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
        backend_config: BatteryBackendConfig | None = None,
        objective_weights: BatteryObjectiveWeights | None = None,
        cooling_coefficient_w_per_m2k: float = DEFAULT_COOLING_COEFFICIENT,
        passive_cooling_w_per_k: float = DEFAULT_PASSIVE_COOLING,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        load_current_a: float | None = None,
        thermal_model: str = DEFAULT_THERMAL_MODEL,
        thermal_neighbor_clearance_mm: float = DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM,
        thermal_contact_decay_mm: float = DEFAULT_THERMAL_CONTACT_DECAY_MM,
        thermal_contact_resistance_k_per_w: float = DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W,
        thermal_flow_shadowing_factor: float = DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR,
        thermal_airflow_axis: str = DEFAULT_THERMAL_AIRFLOW_AXIS,
        thermal_reference_soc: float = DEFAULT_THERMAL_REFERENCE_SOC,
        evaluation_mode: str | BatteryEvaluationMode = BatteryEvaluationMode.EXPLICIT_CIRCUIT.value,
    ) -> None:
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
            requirements=requirements,
            max_cell_count=max_cell_count,
            backend_config=backend_config,
        )
        self.objective_weights = objective_weights or BatteryObjectiveWeights(volume=0.40, cost=0.30, temperature=0.30)
        self.cooling_coefficient_w_per_m2k = float(cooling_coefficient_w_per_m2k)
        self.passive_cooling_w_per_k = max(1.0e-9, float(passive_cooling_w_per_k))
        self.ambient_temperature_c = float(ambient_temperature_c)
        self.maximum_temperature_c = max(float(maximum_temperature_c), self.ambient_temperature_c + 1.0)
        self.load_current_a = (
            float(self.requirements.minimum_current_a) if load_current_a is None else float(load_current_a)
        )
        self.thermal_model = coerce_battery_thermal_model(thermal_model)
        self.thermal_neighbor_clearance_mm = max(0.0, float(thermal_neighbor_clearance_mm))
        self.thermal_contact_decay_mm = max(1.0e-6, float(thermal_contact_decay_mm))
        self.thermal_contact_resistance_k_per_w = max(1.0e-6, float(thermal_contact_resistance_k_per_w))
        self.thermal_flow_shadowing_factor = float(numpy.clip(thermal_flow_shadowing_factor, 0.0, 1.0))
        self.thermal_airflow_axis = coerce_battery_thermal_airflow_axis(thermal_airflow_axis)
        self.thermal_reference_soc = float(numpy.clip(thermal_reference_soc, 0.0, 1.0))
        self.evaluation_mode = coerce_battery_evaluation_mode(
            evaluation_mode,
            default=BatteryEvaluationMode.EXPLICIT_CIRCUIT,
            supported=_T3B_SUPPORTED_EVALUATION_MODES,
        )
        self._outcome_cache: dict[tuple[int, ...], BatteryEvaluationAdapterOutcome] = {}
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._voltage_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._capacity_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._backend_feasibility_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._current_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._temperature_margin),
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T3BNetlistExplicitOptimizationProblem:
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, parameters.get("max_cell_count", 24))),
            backend_config=parse_battery_backend_config(manifest),
            objective_weights=BatteryObjectiveWeights.from_mapping(
                parameters.get("objective_weights"),
                default_volume=0.40,
                default_cost=0.30,
                default_temperature=0.30,
            ),
            cooling_coefficient_w_per_m2k=float(
                cast(float, parameters.get("cooling_coefficient_w_per_m2k", DEFAULT_COOLING_COEFFICIENT))
            ),
            passive_cooling_w_per_k=float(
                cast(float, parameters.get("passive_cooling_w_per_k", DEFAULT_PASSIVE_COOLING))
            ),
            ambient_temperature_c=float(
                cast(float, parameters.get("ambient_temperature_c", _DEFAULT_AMBIENT_TEMPERATURE_C))
            ),
            maximum_temperature_c=float(
                cast(float, parameters.get("maximum_temperature_c", _DEFAULT_MAX_TEMPERATURE_C))
            ),
            load_current_a=cast(float | None, parameters.get("load_current_a")),
            thermal_model=str(cast(str, parameters.get("thermal_model", DEFAULT_THERMAL_MODEL))),
            thermal_neighbor_clearance_mm=float(
                cast(float, parameters.get("thermal_neighbor_clearance_mm", DEFAULT_THERMAL_NEIGHBOR_CLEARANCE_MM))
            ),
            thermal_contact_decay_mm=float(
                cast(float, parameters.get("thermal_contact_decay_mm", DEFAULT_THERMAL_CONTACT_DECAY_MM))
            ),
            thermal_contact_resistance_k_per_w=float(
                cast(
                    float,
                    parameters.get(
                        "thermal_contact_resistance_k_per_w",
                        DEFAULT_THERMAL_CONTACT_RESISTANCE_K_PER_W,
                    ),
                )
            ),
            thermal_flow_shadowing_factor=float(
                cast(float, parameters.get("thermal_flow_shadowing_factor", DEFAULT_THERMAL_FLOW_SHADOWING_FACTOR))
            ),
            thermal_airflow_axis=str(cast(str, parameters.get("thermal_airflow_axis", DEFAULT_THERMAL_AIRFLOW_AXIS))),
            thermal_reference_soc=float(
                cast(float, parameters.get("thermal_reference_soc", DEFAULT_THERMAL_REFERENCE_SOC))
            ),
            evaluation_mode=cast(
                str | BatteryEvaluationMode,
                parameters.get("evaluation_mode", BatteryEvaluationMode.EXPLICIT_CIRCUIT.value),
            ),
        )

    def _thermal_config(self) -> BatteryThermalPromotionConfig:
        return BatteryThermalPromotionConfig(
            cooling_coefficient_w_per_m2k=float(self.cooling_coefficient_w_per_m2k),
            passive_cooling_w_per_k=float(self.passive_cooling_w_per_k),
            ambient_temperature_c=float(self.ambient_temperature_c),
            thermal_model=self.thermal_model,
            thermal_neighbor_clearance_mm=float(self.thermal_neighbor_clearance_mm),
            thermal_contact_decay_mm=float(self.thermal_contact_decay_mm),
            thermal_contact_resistance_k_per_w=float(self.thermal_contact_resistance_k_per_w),
            thermal_flow_shadowing_factor=float(self.thermal_flow_shadowing_factor),
            thermal_airflow_axis=self.thermal_airflow_axis,
            thermal_reference_soc=float(self.thermal_reference_soc),
        )

    def _outcome_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryEvaluationAdapterOutcome:
        genes = self._normalized_genes(variables)
        cached = self._outcome_cache.get(genes)
        if cached is not None:
            return cached
        outcome = evaluate_explicit_netlist_state(
            self._state_from_genes(genes),
            requirements=self.requirements,
            backend_config=self.backend_config,
            evaluation_mode=self.evaluation_mode,
            load_current_a=self.load_current_a,
            thermal_config=self._thermal_config(),
        )
        self._outcome_cache[genes] = outcome
        return outcome

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryTierMetrics:
        return self._outcome_from_variables(variables).metrics

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        return self._metrics_from_variables(variables).as_dict()

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        normalized = self._normalize_vector(variables)
        metrics = self._metrics_from_variables(normalized)
        return _score_metrics(
            metrics=metrics,
            requirements=self.requirements,
            max_cell_count=self.max_cell_count,
            max_temperature_c=self.maximum_temperature_c,
            ambient_temperature_c=self.ambient_temperature_c,
            weights=self.objective_weights,
            total_violation=self.constraint_violation(normalized),
        )

    def _current_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).current_limit_a - self.requirements.minimum_current_a

    def _temperature_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self.maximum_temperature_c - self._metrics_from_variables(variables).max_temperature_c

    def _voltage_margin(self, variables: NDArray[numpy.float64]) -> float:
        metrics = self._metrics_from_variables(variables)
        return self.requirements.voltage_tolerance_v - abs(metrics.voltage_v - self.requirements.target_voltage_v)

    def _capacity_margin(self, variables: NDArray[numpy.float64]) -> float:
        return self._metrics_from_variables(variables).capacity_ah - self.requirements.minimum_capacity_ah

    def _backend_feasibility_margin(self, variables: NDArray[numpy.float64]) -> float:
        return 1.0 if self._metrics_from_variables(variables).is_feasible else -1.0

    def evaluation_provenance(self, variables: NDArray[numpy.float64]) -> object:
        outcome = self._outcome_from_variables(self._normalize_vector(variables))
        return build_battery_evaluation_provenance(
            representation_mode=BatteryRepresentationMode.EXPLICIT_NETLIST,
            evaluation_mode=self.evaluation_mode,
            evaluator_implementation=f"{type(self).__module__}:{type(self).__name__}",
            requested_backend_config=self.backend_config,
            honored_backend_fields=outcome.honored_backend_fields,
            electrical_path=outcome.electrical_path,
            thermal_path=outcome.thermal_path,
            cell_model_source=outcome.cell_model_source,
            thermal_prior_source=outcome.thermal_prior_source,
            assumed_defaults=outcome.assumed_defaults,
            adaptation_notes=outcome.adaptation_notes,
        )

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
        solver_backend: str = "auto",
    ) -> OptimizationResult:
        result = super().solve(
            initial_solution=initial_solution,
            seed=seed,
            maxiter=maxiter,
            solver_backend=solver_backend,
        )
        return OptimizationResult(
            x=result.x,
            fun=result.fun,
            success=result.success,
            message=(
                "Evaluated explicit-netlist battery benchmark and found a feasible design."
                if result.success
                else "Evaluated explicit-netlist battery benchmark and returned a best-effort design."
            ),
            nit=result.nit,
            nfev=result.nfev,
        )


__all__ = [
    "Battery18650T3BNetlistExplicitOptimizationProblem",
    "BatteryOpenEndedCapacityMaxProblem",
]
