"""Compact worker-hours allocation benchmark for competing design projects."""

from __future__ import annotations

from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.personnel_allocation import (
    CompetingProjectsAllocationState,
    build_manager_baseline_plan,
    build_value_tracking_plan,
    create_competing_projects_backend,
    simulate_competing_projects_plan,
)
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)


class CompetingProjectsWorkerHoursProblem(OptimizationProblem):
    """Daily worker-hours allocation benchmark derived from Freiheit (2015)."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        horizon_days: int = 60,
        change_penalty_weight: float = 0.015,
        inactive_hours_penalty: float = 0.25,
    ) -> None:
        """Initialize the compact personnel-allocation benchmark."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        if horizon_days <= 0:
            raise ValueError("horizon_days must be positive.")
        if change_penalty_weight < 0.0:
            raise ValueError("change_penalty_weight must be nonnegative.")
        if inactive_hours_penalty < 0.0:
            raise ValueError("inactive_hours_penalty must be nonnegative.")

        self.horizon_days = horizon_days
        self.change_penalty_weight = change_penalty_weight
        self.inactive_hours_penalty = inactive_hours_penalty
        self.backend = create_competing_projects_backend(horizon_days=horizon_days)
        self.task_names = self.backend.task_names
        self.worker_names = self.backend.worker_names
        self.variable_shape = self.backend.variable_shape

        self.bounds = Bounds(
            lb=numpy.zeros(self.backend.variable_count, dtype=float),
            ub=self.backend.upper_bounds.reshape(-1),
        )
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._daily_worker_margin_factory(day_index, worker_index))
            for day_index in range(self.horizon_days)
            for worker_index in range(len(self.backend.workers))
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> CompetingProjectsWorkerHoursProblem:
        """Construct the compact benchmark from packaged manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            horizon_days=int(cast(int, parameters.get("horizon_days", 60))),
            change_penalty_weight=float(cast(float, parameters.get("change_penalty_weight", 0.015))),
            inactive_hours_penalty=float(cast(float, parameters.get("inactive_hours_penalty", 0.25))),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return a deterministic zero-allocation seed over the planning horizon."""
        del seed
        return numpy.zeros(self.backend.variable_count, dtype=float)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the scalar tracking-error objective with lightweight penalties."""
        simulation = self._simulate(variables)
        return float(
            simulation.tracking_error
            + (self.change_penalty_weight * simulation.total_change_hours)
            + (self.inactive_hours_penalty * simulation.inactive_hours)
        )

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the main reported metrics for one daily allocation plan."""
        simulation = self._simulate(variables)
        summary = simulation.summarize(tasks=self.backend.tasks, workers=self.backend.workers)
        return {
            "tracking_error": summary.tracking_error,
            "inactive_hours": summary.inactive_hours,
            "total_change_hours": summary.total_change_hours,
            "total_achieved_value": summary.total_achieved_value,
            "total_target_value": summary.total_target_value,
            "completed_task_count": float(summary.completed_task_count),
        }

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Run deterministic baseline schedules and return the best allocation found."""
        del seed, maxiter
        candidates = [self.generate_initial_solution(), build_manager_baseline_plan(self.backend)]
        if initial_solution is not None:
            candidates.append(numpy.array(initial_solution, dtype=float, copy=True))
        candidates.append(build_value_tracking_plan(self.backend))

        best = min(
            candidates,
            key=lambda candidate: (
                self.max_constraint_violation(candidate),
                self.objective(candidate),
            ),
        )
        evaluation = self.evaluate(best)
        message = (
            "Ran the compact worker-hours baseline schedule set and kept the best plan."
            if evaluation.is_feasible
            else "Ran the compact worker-hours baseline and returned the least-violating plan."
        )
        return OptimizationResult(
            x=numpy.array(best, dtype=float, copy=True),
            fun=float(evaluation.objective_value),
            success=evaluation.is_feasible,
            message=message,
            nit=len(candidates),
            nfev=len(candidates),
        )

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> CompetingProjectsAllocationState:
        """Decode one flat daily allocation vector into a compact benchmark summary."""
        simulation = self._simulate(variables)
        return simulation.summarize(tasks=self.backend.tasks, workers=self.backend.workers)

    def _simulate(self, variables: NDArray[numpy.float64]):
        return simulate_competing_projects_plan(self._normalize_vector(variables), backend=self.backend)

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        candidate = numpy.array(variables, dtype=float, copy=True)
        if candidate.shape != (self.backend.variable_count,):
            raise ValueError(
                f"variables must match the compact worker-hours benchmark shape ({self.backend.variable_count},)."
            )
        return candidate

    def _daily_worker_margin_factory(self, day_index: int, worker_index: int):
        worker = self.backend.workers[worker_index]

        def evaluate(variables: NDArray[numpy.float64]) -> float:
            daily_hours = self._normalize_vector(variables).reshape(self.backend.variable_shape)
            return float(worker.total_daily_hours - daily_hours[day_index, worker_index, :].sum())

        return evaluate
