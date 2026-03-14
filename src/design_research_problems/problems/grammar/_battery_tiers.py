"""Tiered 18650 battery grammar ladder with paired optimization-compatible metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._domains.battery_benchmark import (
    BatteryEvaluationMode,
    BatteryRepresentationMode,
    build_battery_evaluation_provenance,
    coerce_battery_evaluation_mode,
)
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    resolve_battery_backend_config,
)
from design_research_problems.problems._domains.battery_circuit import BatteryCircuitState
from design_research_problems.problems._domains.battery_layout import CELL_SPEC_18650, MIN_SPACING_MM
from design_research_problems.problems._domains.battery_tier_metrics import (
    BatteryTierMetrics,
)
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems.grammar._battery_pack_open import BatteryPack18650OpenEndedProblem
from design_research_problems.problems.grammar._battery_pack_sp import BatteryPack18650SeriesParallelProblem
from design_research_problems.problems.grammar._battery_problem_base import (
    parse_battery_backend_config,
    parse_battery_requirements,
)
from design_research_problems.problems.optimization._battery_tiers import (
    Battery18650Tier2LayoutOptimizationProblem,
    Battery18650Tier4ThermalOptimizationProblem,
    Battery18650T2PoseSurrogateOptimizationProblem,
    Battery18650T3ATopologySurrogateOptimizationProblem,
    Battery18650T4ThermalHybridOptimizationProblem,
    Battery18650T1RectangularSurrogateOptimizationProblem,
)

_POSE_MOVE_STEP_MM = 10.0
_POSE_ROTATE_STEP_DEG = 15.0
_THERMAL_STEP = 2.5


def _coerce_vector_state(state: tuple[float, ...], expected_dimension: int) -> NDArray[numpy.float64]:
    """Validate and return one vector grammar state as numpy array."""
    candidate = numpy.array(state, dtype=float)
    if candidate.shape != (expected_dimension,):
        raise ValueError(f"Expected a {expected_dimension}-value state tuple, received shape {candidate.shape!r}.")
    return candidate


def _metrics_with_feasibility(
    metrics: BatteryTierMetrics,
    *,
    is_feasible: bool,
    failure_reason: str | None,
) -> BatteryTierMetrics:
    """Return metric payload with updated feasibility metadata."""
    return BatteryTierMetrics(
        cell_count=metrics.cell_count,
        connection_count=metrics.connection_count,
        cost_usd=metrics.cost_usd,
        design_volume_mm3=metrics.design_volume_mm3,
        max_temperature_c=metrics.max_temperature_c,
        voltage_v=metrics.voltage_v,
        capacity_ah=metrics.capacity_ah,
        current_limit_a=metrics.current_limit_a,
        min_clearance_mm=metrics.min_clearance_mm,
        is_feasible=is_feasible,
        failure_reason=failure_reason,
    )


@dataclass(frozen=True)
class _VectorGrammarConfig:
    """Shared vector-grammar transition configuration."""

    move_step_mm: float = _POSE_MOVE_STEP_MM
    rotate_step_deg: float = _POSE_ROTATE_STEP_DEG


class Battery18650Tier1SeriesParallelGrammarProblem(BatteryPack18650SeriesParallelProblem):
    """Tier-1 grammar: constrained rectangular ``SxP`` edits."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier1SeriesParallelGrammarProblem:
        """Build tier-1 grammar from manifest data."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            backend_config=parse_battery_backend_config(manifest),
        )

    def evaluate(self, state: object) -> BatteryTierMetrics:  # type: ignore[override]
        """Evaluate one tier-1 state and return the shared metric contract."""
        evaluation = super().evaluate(state)
        parallel_count = max(1, int(evaluation.parallel_count))
        series_count = max(1, int(evaluation.series_count))
        connection_count = float(max(0, series_count + 1) * max(0, parallel_count - 1))
        per_cell_current = self.requirements.minimum_current_a / float(parallel_count)
        total_heat_w = float(evaluation.cell_count) * (per_cell_current**2) * CELL_SPEC_18650.internal_resistance_ohm
        cooling_conductance = 1.0 + (18.0 * float(evaluation.surface_area) * 1.0e-6)
        max_temperature_c = 25.0 + (total_heat_w / max(cooling_conductance, 1.0e-9))
        return BatteryTierMetrics(
            cell_count=float(evaluation.cell_count),
            connection_count=connection_count,
            cost_usd=float(evaluation.design_cost),
            design_volume_mm3=float(evaluation.design_volume),
            max_temperature_c=max_temperature_c,
            voltage_v=float(evaluation.design_voltage),
            capacity_ah=float(evaluation.design_capacity),
            current_limit_a=float(evaluation.analytic_current_limit),
            min_clearance_mm=float(MIN_SPACING_MM),
            is_feasible=bool(evaluation.is_feasible),
            failure_reason=evaluation.failure_reason,
        )


class Battery18650Tier3TopologyGrammarProblem(BatteryPack18650OpenEndedProblem):
    """Tier-3 grammar: explicit circuit topology edits with variable cell count."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier3TopologyGrammarProblem:
        """Build tier-3 grammar from manifest data."""
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, manifest.parameters.get("max_cell_count", 24))),
            backend_config=parse_battery_backend_config(manifest),
        )

    def evaluate(self, state: object) -> BatteryTierMetrics:  # type: ignore[override]
        """Evaluate one tier-3 state and return the shared metric contract."""
        evaluation = super().evaluate(state)
        delivered_capacity = (
            0.0 if evaluation.delivered_capacity_ah is None else float(evaluation.delivered_capacity_ah)
        )
        nominal_voltage = float(evaluation.pack_nominal_voltage)
        max_cell_current = 0.0 if evaluation.max_cell_current_a is None else float(evaluation.max_cell_current_a)
        parallel_equivalent = max(delivered_capacity / max(CELL_SPEC_18650.nominal_capacity_ah, 1.0e-9), 1.0)
        total_heat_w = (
            float(evaluation.cell_count)
            * ((self.requirements.minimum_current_a / parallel_equivalent) ** 2)
            * CELL_SPEC_18650.internal_resistance_ohm
        )
        cooling_conductance = 1.0 + (18.0 * float(evaluation.surface_area) * 1.0e-6)
        max_temperature_c = 25.0 + (total_heat_w / max(cooling_conductance, 1.0e-9))
        min_clearance = MIN_SPACING_MM if evaluation.is_feasible else -MIN_SPACING_MM
        return BatteryTierMetrics(
            cell_count=float(evaluation.cell_count),
            connection_count=float(evaluation.connection_count),
            cost_usd=float(evaluation.design_cost),
            design_volume_mm3=float(evaluation.design_volume),
            max_temperature_c=max_temperature_c,
            voltage_v=nominal_voltage,
            capacity_ah=delivered_capacity,
            current_limit_a=max(
                max_cell_current, self.requirements.minimum_current_a if evaluation.is_feasible else 0.0
            ),
            min_clearance_mm=float(min_clearance),
            is_feasible=bool(evaluation.is_feasible),
            failure_reason=evaluation.failure_reason,
        )


class Battery18650Tier2LayoutGrammarProblem(GrammarProblem[tuple[float, ...], BatteryTierMetrics]):
    """Tier-2 grammar: discrete pose and ``SxP`` edits over the tier-2 vector schema."""

    def __init__(self, *, optimizer: Battery18650Tier2LayoutOptimizationProblem) -> None:
        """Store the paired tier-2 optimization helper."""
        super().__init__(
            metadata=optimizer.metadata,
            statement_markdown=optimizer.statement_markdown,
            resource_bundle=optimizer.resource_bundle,
        )
        self._optimizer = optimizer
        self._config = _VectorGrammarConfig()

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier2LayoutGrammarProblem:
        """Build tier-2 grammar from manifest data."""
        optimizer = Battery18650Tier2LayoutOptimizationProblem.from_manifest(manifest)
        return cls(optimizer=optimizer)

    def initial_state(self) -> tuple[float, ...]:
        """Return the deterministic tier-2 vector seed state."""
        return tuple(float(value) for value in self._optimizer.generate_initial_solution())

    def enumerate_transitions(self, state: tuple[float, ...]) -> tuple[GrammarTransition[tuple[float, ...]], ...]:
        """Return deterministic local-edit transitions for tier-2 vector states."""
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        transitions: list[GrammarTransition[tuple[float, ...]]] = []
        # Topology edit actions.
        for index, rule_name in ((0, "adjust_series_count"), (1, "adjust_parallel_count")):
            for delta in (-1.0, 1.0):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta", int(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        # Pose actions on the first potential cell.
        pose_start = 2
        for local_index, rule_name in ((0, "move_cell_x"), (1, "move_cell_y"), (2, "move_cell_z")):
            index = pose_start + local_index
            for delta in (-self._config.move_step_mm, self._config.move_step_mm):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta_mm", float(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        for local_index, rule_name in ((3, "rotate_cell_x"), (4, "rotate_cell_y"), (5, "rotate_cell_z")):
            index = pose_start + local_index
            for delta in (-self._config.rotate_step_deg, self._config.rotate_step_deg):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta_deg", float(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        return tuple(transitions)

    def evaluate(self, state: tuple[float, ...]) -> BatteryTierMetrics:
        """Evaluate one tier-2 vector state."""
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        metrics = self._optimizer._metrics_from_variables(vector)
        violation = self._optimizer.max_constraint_violation(vector)
        return _metrics_with_feasibility(
            metrics,
            is_feasible=violation <= 1.0e-9,
            failure_reason=None if violation <= 1.0e-9 else f"Constraint violation {violation:.3g}",
        )


class Battery18650Tier4ThermalGrammarProblem(GrammarProblem[tuple[float, ...], BatteryTierMetrics]):
    """Tier-4 grammar: tier-3 topology/pose edits plus thermal-parameter tuning."""

    def __init__(self, *, optimizer: Battery18650Tier4ThermalOptimizationProblem) -> None:
        """Store the paired tier-4 optimization helper."""
        super().__init__(
            metadata=optimizer.metadata,
            statement_markdown=optimizer.statement_markdown,
            resource_bundle=optimizer.resource_bundle,
        )
        self._optimizer = optimizer
        self._config = _VectorGrammarConfig()

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650Tier4ThermalGrammarProblem:
        """Build tier-4 grammar from manifest data."""
        optimizer = Battery18650Tier4ThermalOptimizationProblem.from_manifest(manifest)
        return cls(optimizer=optimizer)

    def initial_state(self) -> tuple[float, ...]:
        """Return deterministic tier-4 vector seed state."""
        return tuple(float(value) for value in self._optimizer.generate_initial_solution())

    def enumerate_transitions(self, state: tuple[float, ...]) -> tuple[GrammarTransition[tuple[float, ...]], ...]:
        """Return deterministic tier-4 local-edit transitions."""
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        transitions: list[GrammarTransition[tuple[float, ...]]] = []
        # Topology edits.
        for index, rule_name in ((0, "adjust_cell_count"), (1, "adjust_series_count")):
            for delta in (-1.0, 1.0):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta", int(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        # Pose edits on the first potential cell.
        pose_start = 2
        for local_index, rule_name in ((0, "move_cell_x"), (1, "move_cell_y"), (2, "move_cell_z")):
            index = pose_start + local_index
            for delta in (-self._config.move_step_mm, self._config.move_step_mm):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta_mm", float(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        # Thermal tuning edits.
        for index, rule_name in ((-3, "tune_cooling_coefficient"), (-2, "tune_passive_cooling"), (-1, "tune_ambient")):
            for delta in (-_THERMAL_STEP, _THERMAL_STEP):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(
                        candidate[index] + delta,
                        self._optimizer.bounds.lb[index],
                        self._optimizer.bounds.ub[index],
                    )
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta", float(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        return tuple(transitions)

    def evaluate(self, state: tuple[float, ...]) -> BatteryTierMetrics:
        """Evaluate one tier-4 vector state."""
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        metrics = self._optimizer._metrics_from_variables(vector)
        violation = self._optimizer.max_constraint_violation(vector)
        return _metrics_with_feasibility(
            metrics,
            is_feasible=violation <= 1.0e-9,
            failure_reason=None if violation <= 1.0e-9 else f"Constraint violation {violation:.3g}",
        )


class Battery18650T1RectangularSurrogateGrammarProblem(Battery18650Tier1SeriesParallelGrammarProblem):
    """Public tier-1 rectangular grammar benchmark with explicit evaluator metadata."""

    def __init__(
        self,
        *,
        metadata: object,
        statement_markdown: str = "",
        resource_bundle: object | None = None,
        requirements: object | None = None,
        backend_config: BatteryBackendConfig | None = None,
        evaluation_mode: str | BatteryEvaluationMode = BatteryEvaluationMode.ANALYTIC_SURROGATE.value,
    ) -> None:
        super().__init__(
            metadata=cast(object, metadata),
            statement_markdown=statement_markdown,
            resource_bundle=cast(object | None, resource_bundle),
            requirements=cast(object | None, requirements),
            backend_config=backend_config,
        )
        self.evaluation_mode = coerce_battery_evaluation_mode(
            evaluation_mode,
            default=BatteryEvaluationMode.ANALYTIC_SURROGATE,
            supported=(BatteryEvaluationMode.ANALYTIC_SURROGATE,),
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T1RectangularSurrogateGrammarProblem:
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            backend_config=parse_battery_backend_config(manifest),
            evaluation_mode=cast(
                str | BatteryEvaluationMode,
                manifest.parameters.get("evaluation_mode", BatteryEvaluationMode.ANALYTIC_SURROGATE.value),
            ),
        )

    def evaluation_provenance(self, state: object) -> object:
        evaluation = BatteryPack18650SeriesParallelProblem.evaluate(self, state)
        return build_battery_evaluation_provenance(
            representation_mode=BatteryRepresentationMode.RECTANGULAR,
            evaluation_mode=self.evaluation_mode,
            evaluator_implementation=f"{type(self).__module__}:{type(self).__name__}",
            requested_backend_config=self.backend_config,
            honored_backend_fields=tuple(sorted(resolve_battery_backend_config(self.backend_config).as_dict())),
            cell_model_source=evaluation.cell_model_source,
        )


class Battery18650T2PoseSurrogateGrammarProblem(Battery18650Tier2LayoutGrammarProblem):
    """Public tier-2 pose-layout grammar benchmark."""

    def __init__(self, *, optimizer: Battery18650T2PoseSurrogateOptimizationProblem) -> None:
        super().__init__(optimizer=optimizer)

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T2PoseSurrogateGrammarProblem:
        optimizer = Battery18650T2PoseSurrogateOptimizationProblem.from_manifest(manifest)
        return cls(optimizer=optimizer)

    def evaluation_provenance(self, state: tuple[float, ...]) -> object:
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        return self._optimizer.evaluation_provenance(vector)


class Battery18650T3ATopologySurrogateGrammarProblem(GrammarProblem[tuple[float, ...], BatteryTierMetrics]):
    """Public tier-3A topology-allocation grammar benchmark."""

    def __init__(self, *, optimizer: Battery18650T3ATopologySurrogateOptimizationProblem) -> None:
        super().__init__(
            metadata=optimizer.metadata,
            statement_markdown=optimizer.statement_markdown,
            resource_bundle=optimizer.resource_bundle,
        )
        self._optimizer = optimizer
        self._config = _VectorGrammarConfig()

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T3ATopologySurrogateGrammarProblem:
        optimizer = Battery18650T3ATopologySurrogateOptimizationProblem.from_manifest(manifest)
        return cls(optimizer=optimizer)

    def initial_state(self) -> tuple[float, ...]:
        return tuple(float(value) for value in self._optimizer.generate_initial_solution())

    def enumerate_transitions(self, state: tuple[float, ...]) -> tuple[GrammarTransition[tuple[float, ...]], ...]:
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        transitions: list[GrammarTransition[tuple[float, ...]]] = []
        for index, rule_name in ((0, "adjust_cell_count"), (1, "adjust_series_count")):
            for delta in (-1.0, 1.0):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(candidate[index] + delta, self._optimizer.bounds.lb[index], self._optimizer.bounds.ub[index])
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta", int(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        pose_start = 2
        for local_index, rule_name in ((0, "move_cell_x"), (1, "move_cell_y"), (2, "move_cell_z")):
            index = pose_start + local_index
            for delta in (-self._config.move_step_mm, self._config.move_step_mm):
                candidate = vector.copy()
                candidate[index] = float(
                    numpy.clip(candidate[index] + delta, self._optimizer.bounds.lb[index], self._optimizer.bounds.ub[index])
                )
                if candidate[index] == vector[index]:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name=rule_name,
                        parameters=(("delta_mm", float(delta)),),
                        next_state=tuple(float(value) for value in candidate),
                    )
                )
        stage_slot_index = pose_start + 6
        for delta in (-1.0, 1.0):
            candidate = vector.copy()
            candidate[stage_slot_index] = float(
                numpy.clip(
                    candidate[stage_slot_index] + delta,
                    self._optimizer.bounds.lb[stage_slot_index],
                    self._optimizer.bounds.ub[stage_slot_index],
                )
            )
            if candidate[stage_slot_index] == vector[stage_slot_index]:
                continue
            transitions.append(
                GrammarTransition(
                    rule_name="adjust_first_cell_stage_slot",
                    parameters=(("delta", int(delta)),),
                    next_state=tuple(float(value) for value in candidate),
                )
            )
        return tuple(transitions)

    def evaluate(self, state: tuple[float, ...]) -> BatteryTierMetrics:
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        metrics = self._optimizer._metrics_from_variables(vector)
        violation = self._optimizer.max_constraint_violation(vector)
        return _metrics_with_feasibility(
            metrics,
            is_feasible=violation <= 1.0e-9,
            failure_reason=None if violation <= 1.0e-9 else f"Constraint violation {violation:.3g}",
        )

    def evaluation_provenance(self, state: tuple[float, ...]) -> object:
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        return self._optimizer.evaluation_provenance(vector)


class Battery18650T3BNetlistExplicitGrammarProblem(Battery18650Tier3TopologyGrammarProblem):
    """Public tier-3B explicit-netlist grammar benchmark."""

    def __init__(
        self,
        *,
        metadata: object,
        statement_markdown: str = "",
        resource_bundle: object | None = None,
        requirements: object | None = None,
        max_cell_count: int = 24,
        backend_config: BatteryBackendConfig | None = None,
        evaluation_mode: str | BatteryEvaluationMode = BatteryEvaluationMode.EXPLICIT_CIRCUIT.value,
    ) -> None:
        super().__init__(
            metadata=cast(object, metadata),
            statement_markdown=statement_markdown,
            resource_bundle=cast(object | None, resource_bundle),
            requirements=cast(object | None, requirements),
            max_cell_count=max_cell_count,
            backend_config=backend_config,
        )
        self.evaluation_mode = coerce_battery_evaluation_mode(
            evaluation_mode,
            default=BatteryEvaluationMode.EXPLICIT_CIRCUIT,
            supported=(BatteryEvaluationMode.EXPLICIT_CIRCUIT,),
        )

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T3BNetlistExplicitGrammarProblem:
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            requirements=parse_battery_requirements(manifest),
            max_cell_count=int(cast(int, manifest.parameters.get("max_cell_count", 24))),
            backend_config=parse_battery_backend_config(manifest),
            evaluation_mode=cast(
                str | BatteryEvaluationMode,
                manifest.parameters.get("evaluation_mode", BatteryEvaluationMode.EXPLICIT_CIRCUIT.value),
            ),
        )

    def evaluation_provenance(self, state: object) -> object:
        if not isinstance(state, BatteryCircuitState):
            raise TypeError("Expected a BatteryCircuitState.")
        evaluation = BatteryPack18650OpenEndedProblem.evaluate(self, state)
        return build_battery_evaluation_provenance(
            representation_mode=BatteryRepresentationMode.EXPLICIT_NETLIST,
            evaluation_mode=self.evaluation_mode,
            evaluator_implementation=f"{type(self).__module__}:{type(self).__name__}",
            requested_backend_config=self.backend_config,
            honored_backend_fields=tuple(sorted(resolve_battery_backend_config(self.backend_config).as_dict())),
            cell_model_source=evaluation.cell_model_source,
        )


class Battery18650T4ThermalHybridGrammarProblem(Battery18650Tier4ThermalGrammarProblem):
    """Public tier-4 thermal-topology grammar benchmark."""

    def __init__(self, *, optimizer: Battery18650T4ThermalHybridOptimizationProblem) -> None:
        super().__init__(optimizer=optimizer)

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> Battery18650T4ThermalHybridGrammarProblem:
        optimizer = Battery18650T4ThermalHybridOptimizationProblem.from_manifest(manifest)
        return cls(optimizer=optimizer)

    def evaluation_provenance(self, state: tuple[float, ...]) -> object:
        vector = _coerce_vector_state(state, expected_dimension=self._optimizer.bounds.lb.shape[0])
        return self._optimizer.evaluation_provenance(vector)


__all__ = [
    "Battery18650Tier1SeriesParallelGrammarProblem",
    "Battery18650Tier2LayoutGrammarProblem",
    "Battery18650Tier3TopologyGrammarProblem",
    "Battery18650Tier4ThermalGrammarProblem",
    "Battery18650T1RectangularSurrogateGrammarProblem",
    "Battery18650T2PoseSurrogateGrammarProblem",
    "Battery18650T3ATopologySurrogateGrammarProblem",
    "Battery18650T3BNetlistExplicitGrammarProblem",
    "Battery18650T4ThermalHybridGrammarProblem",
]
