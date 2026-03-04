"""Open-ended explicit battery-pack capacity maximization problem."""

from __future__ import annotations

from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.battery_cell_model import load_18650_cell_model
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    evaluate_battery_circuit,
)
from design_research_problems.problems._domains.battery_layout import BatteryRequirements
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)
from design_research_problems.problems.grammar._battery_pack_open import BatteryPack18650OpenEndedProblem
from design_research_problems.problems.grammar._battery_problem_base import parse_battery_requirements

_TRANSITION_PROGRAM_LENGTH = 32
_MAX_TRANSITION_TOKEN = 8_192
_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_CELL_TIE_BREAK_SCALE = 1.0e-3
_CONNECTION_TIE_BREAK_SCALE = 1.0e-4
_VOLUME_TIE_BREAK_SCALE = 1.0e-8
_SEARCH_DELTAS = (-64, -16, -4, -1, 1, 4, 16, 64)


class BatteryOpenEndedCapacityMaxProblem(OptimizationProblem):
    """Transition-program optimizer over the open-ended explicit battery grammar."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        max_cell_count: int = 24,
    ) -> None:
        """Initialize the packaged open-ended capacity-maximization benchmark."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.requirements = requirements or BatteryRequirements(
            target_voltage_v=14.8,
            minimum_capacity_ah=10.0,
            minimum_current_a=60.0,
            max_width_mm=500.0,
            max_depth_mm=500.0,
            max_height_mm=250.0,
            voltage_tolerance_v=0.1,
        )
        self.max_cell_count = max_cell_count
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
        )
        self._state_cache: dict[tuple[int, ...], BatteryCircuitState] = {}
        self._evaluation_cache: dict[tuple[int, ...], BatteryCircuitEvaluation] = {}
        self._baseline_program = self._build_canonical_seed_program()
        self._seed_prefix_length = sum(1 for gene in self._baseline_program if gene != 0)

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryOpenEndedCapacityMaxProblem:
        """Construct an instance from packaged manifest data."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, manifest.parameters.get("max_cell_count", 24))),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the canonical 4S6P build program, optionally with seeded tail noise."""
        baseline = numpy.array(self._baseline_program, dtype=float)
        if seed is None:
            return baseline

        rng = numpy.random.default_rng(seed)
        tail_length = _TRANSITION_PROGRAM_LENGTH - self._seed_prefix_length
        if tail_length > 0:
            baseline[self._seed_prefix_length :] = rng.integers(0, _MAX_TRANSITION_TOKEN + 1, size=tail_length)
        return baseline

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> BatteryCircuitState:
        """Decode one transition program into an explicit battery circuit state."""
        return self._state_from_genes(self._normalized_genes(variables))

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the main reported performance metrics for one transition program."""
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
        """Return the scalarized capacity-maximization objective."""
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
    ) -> OptimizationResult:
        """Run a deterministic hill-climbing search over transition programs."""
        current = (
            self.generate_initial_solution(seed=seed)
            if initial_solution is None
            else self._normalize_vector(initial_solution)
        )
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

        max_violation = self.max_constraint_violation(current)
        evaluation = self._evaluation_from_variables(current)
        delivered_capacity = 0.0 if evaluation.delivered_capacity_ah is None else evaluation.delivered_capacity_ah
        action = "Evaluated" if nit == 0 else "Improved"
        if max_violation <= 1.0e-9:
            message = (
                f"{action} the explicit battery transition program to a feasible design "
                f"(delivered capacity {delivered_capacity:.3f} Ah)."
            )
        else:
            message = (
                f"{action} the explicit battery transition program and returned a best-effort design "
                f"(delivered capacity {delivered_capacity:.3f} Ah, max violation {max_violation:.3g})."
            )
        return OptimizationResult(
            x=current.copy(),
            fun=current_score,
            success=max_violation <= 1.0e-9,
            message=message,
            nit=nit,
            nfev=nfev,
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return a clipped fixed-length transition vector."""
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != (_TRANSITION_PROGRAM_LENGTH,):
            raise ValueError(
                f"Expected a {_TRANSITION_PROGRAM_LENGTH}-variable design vector, received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _normalized_genes(self, variables: NDArray[numpy.float64]) -> tuple[int, ...]:
        """Return the rounded integer transition program represented by ``variables``."""
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
        """Decode one normalized transition program into a cached explicit state."""
        cached = self._state_cache.get(genes)
        if cached is not None:
            return cached

        state = self._grammar_helper.initial_state()
        for gene in genes:
            if gene == 0:
                break
            transitions = self._grammar_helper.enumerate_transitions(state)
            if not transitions:
                break
            state = transitions[(gene - 1) % len(transitions)].next_state

        self._state_cache[genes] = state
        return state

    def _evaluate_state(self, state: BatteryCircuitState) -> BatteryCircuitEvaluation:
        """Evaluate one explicit battery state using the shared backend."""
        return evaluate_battery_circuit(
            state=state,
            requirements=self.requirements,
            load_cell_model=load_18650_cell_model,
            simulate_to_failure=True,
        )

    def _evaluation_from_variables(self, variables: NDArray[numpy.float64]) -> BatteryCircuitEvaluation:
        """Return the cached evaluation for one transition program."""
        genes = self._normalized_genes(variables)
        cached = self._evaluation_cache.get(genes)
        if cached is not None:
            return cached

        state = self._state_from_genes(genes)
        evaluation = self._evaluate_state(state)
        self._evaluation_cache[genes] = evaluation
        return evaluation

    def _build_canonical_seed_program(self) -> tuple[int, ...]:
        """Return the exact public-transition 4S6P canonical build program."""
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
        """Return the gene that selects one exact add-cell transition and the resulting state."""
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
        """Return the remaining nominal-voltage tolerance margin."""
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
        """Return the gene that selects one exact pack-terminal reassignment."""
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
        """Return the remaining delivered-capacity margin in amp-hours."""
        delivered_capacity = self._evaluation_from_variables(variables).delivered_capacity_ah
        return (0.0 if delivered_capacity is None else delivered_capacity) - self.requirements.minimum_capacity_ah

    def _backend_feasibility_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return a binary margin indicating whether the shared backend accepted the design."""
        return 1.0 if self._evaluation_from_variables(variables).is_feasible else -1.0


__all__ = ["BatteryOpenEndedCapacityMaxProblem"]
