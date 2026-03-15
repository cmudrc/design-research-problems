"""Shared backend helpers for compact personnel-allocation problems."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy
from numpy.typing import NDArray


@dataclass(frozen=True)
class CompetingProjectsTask:
    """One project or project phase in the compact personnel-allocation case."""

    name: str
    project_name: str
    required_days: int
    days_elapsed: int
    required_hours_per_day: float
    efficiency_e: float
    max_value_p: float
    startup_a: float
    predecessor_index: int | None = None
    predecessor_completion_threshold: float = 0.0

    @property
    def total_required_hours(self) -> float:
        """Return the experienced-worker hours needed to complete this task."""
        return float(self.required_days * self.required_hours_per_day)

    @property
    def initial_effective_hours(self) -> float:
        """Return the already-invested effective hours at the planning baseline."""
        return min(float(self.days_elapsed) * self.required_hours_per_day, self.total_required_hours)


@dataclass(frozen=True)
class CompetingProjectsWorker:
    """One worker with per-task availability and capability limits."""

    name: str
    total_daily_hours: float
    max_daily_hours_by_task: tuple[float, ...]
    capability_by_task: tuple[float, ...]


@dataclass(frozen=True)
class CompetingProjectsAllocationState:
    """Compact decoded summary for one personnel-allocation plan."""

    tracking_error: float
    total_achieved_value: float
    total_target_value: float
    inactive_hours: float
    total_change_hours: float
    completed_task_count: int
    completion_fractions: tuple[float, ...]
    worker_utilization: tuple[float, ...]


@dataclass(frozen=True)
class CompetingProjectsSimulation:
    """Detailed simulation trace used internally by the packaged benchmark."""

    daily_hours: NDArray[numpy.float64]
    daily_value_by_task: NDArray[numpy.float64]
    target_value_by_task: NDArray[numpy.float64]
    effective_hours_by_task: NDArray[numpy.float64]
    scheduled_hours_by_worker: NDArray[numpy.float64]
    tracking_error: float
    inactive_hours: float
    total_change_hours: float

    def summarize(
        self,
        *,
        tasks: tuple[CompetingProjectsTask, ...],
        workers: tuple[CompetingProjectsWorker, ...],
    ) -> CompetingProjectsAllocationState:
        """Return a stable decoded summary for public APIs and examples."""
        completion_fractions = tuple(
            float(min(max(hours / max(task.total_required_hours, 1e-9), 0.0), 1.0))
            for task, hours in zip(tasks, self.effective_hours_by_task, strict=True)
        )
        worker_utilization = tuple(
            float(
                self.scheduled_hours_by_worker[index]
                / max(workers[index].total_daily_hours * self.daily_hours.shape[0], 1e-9)
            )
            for index in range(len(workers))
        )
        return CompetingProjectsAllocationState(
            tracking_error=float(self.tracking_error),
            total_achieved_value=float(self.daily_value_by_task[-1].sum()),
            total_target_value=float(self.target_value_by_task[-1].sum()),
            inactive_hours=float(self.inactive_hours),
            total_change_hours=float(self.total_change_hours),
            completed_task_count=sum(1 for fraction in completion_fractions if fraction >= 0.999),
            completion_fractions=completion_fractions,
            worker_utilization=worker_utilization,
        )


@dataclass(frozen=True)
class CompetingProjectsAllocationBackend:
    """Reusable backend state for the 2015 competing-projects case study."""

    horizon_days: int
    tasks: tuple[CompetingProjectsTask, ...]
    workers: tuple[CompetingProjectsWorker, ...]
    task_names: tuple[str, ...]
    worker_names: tuple[str, ...]
    variable_shape: tuple[int, int, int]
    variable_count: int
    upper_bounds: NDArray[numpy.float64]
    target_value_by_day: NDArray[numpy.float64]


def _paper_tasks() -> tuple[CompetingProjectsTask, ...]:
    return (
        CompetingProjectsTask(
            name="Project 1 - Phase 1",
            project_name="Project 1",
            required_days=10,
            days_elapsed=0,
            required_hours_per_day=8.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.040,
        ),
        CompetingProjectsTask(
            name="Project 1 - Phase 2",
            project_name="Project 1",
            required_days=10,
            days_elapsed=0,
            required_hours_per_day=8.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.040,
            predecessor_index=0,
            predecessor_completion_threshold=0.80,
        ),
        CompetingProjectsTask(
            name="Project 1 - Phase 3",
            project_name="Project 1",
            required_days=25,
            days_elapsed=0,
            required_hours_per_day=8.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.016,
            predecessor_index=1,
            predecessor_completion_threshold=0.90,
        ),
        CompetingProjectsTask(
            name="Project 1 - Phase 4",
            project_name="Project 1",
            required_days=15,
            days_elapsed=0,
            required_hours_per_day=8.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.026,
            predecessor_index=2,
            predecessor_completion_threshold=0.70,
        ),
        CompetingProjectsTask(
            name="Project 2",
            project_name="Project 2",
            required_days=487,
            days_elapsed=242,
            required_hours_per_day=6.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.0,
        ),
        CompetingProjectsTask(
            name="Project 3",
            project_name="Project 3",
            required_days=189,
            days_elapsed=143,
            required_hours_per_day=4.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.0,
        ),
        CompetingProjectsTask(
            name="Project 4",
            project_name="Project 4",
            required_days=148,
            days_elapsed=0,
            required_hours_per_day=3.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.0,
        ),
        CompetingProjectsTask(
            name="Project 5",
            project_name="Project 5",
            required_days=83,
            days_elapsed=35,
            required_hours_per_day=8.0,
            efficiency_e=1.25,
            max_value_p=0.85,
            startup_a=0.0,
        ),
    )


def _paper_workers() -> tuple[CompetingProjectsWorker, ...]:
    return (
        CompetingProjectsWorker(
            name="Worker A",
            total_daily_hours=5.0,
            max_daily_hours_by_task=(1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
            capability_by_task=(1.0, 1.0, 1.0, 0.8, 0.9, 1.0, 1.0, 0.9),
        ),
        CompetingProjectsWorker(
            name="Worker B",
            total_daily_hours=8.0,
            max_daily_hours_by_task=(4.0, 4.0, 4.0, 4.0, 0.0, 0.0, 4.0, 0.0),
            capability_by_task=(0.8, 0.8, 0.6, 0.6, 0.0, 0.0, 0.7, 0.0),
        ),
        CompetingProjectsWorker(
            name="Worker C",
            total_daily_hours=8.0,
            max_daily_hours_by_task=(4.0, 4.0, 4.0, 4.0, 4.0, 0.0, 0.0, 0.0),
            capability_by_task=(0.9, 1.0, 0.9, 1.0, 0.9, 0.0, 0.0, 0.0),
        ),
        CompetingProjectsWorker(
            name="Worker D",
            total_daily_hours=8.0,
            max_daily_hours_by_task=(1.0, 1.0, 1.0, 1.0, 0.0, 3.0, 0.0, 4.0),
            capability_by_task=(0.9, 0.9, 0.8, 0.7, 0.0, 0.9, 0.0, 0.8),
        ),
        CompetingProjectsWorker(
            name="Worker E",
            total_daily_hours=8.0,
            max_daily_hours_by_task=(0.0, 0.0, 0.0, 0.0, 2.0, 1.0, 0.0, 5.0),
            capability_by_task=(0.0, 0.0, 0.0, 0.0, 0.9, 1.0, 0.0, 0.9),
        ),
    )


def create_competing_projects_backend(*, horizon_days: int = 60) -> CompetingProjectsAllocationBackend:
    """Build the reusable backend bundle for the 2015 personnel-allocation seed."""
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive.")

    tasks = _paper_tasks()
    workers = _paper_workers()
    upper_bounds = numpy.zeros((horizon_days, len(workers), len(tasks)), dtype=float)
    for day_index in range(horizon_days):
        for worker_index, worker in enumerate(workers):
            upper_bounds[day_index, worker_index, :] = worker.max_daily_hours_by_task

    target_value_by_day = build_target_value_trajectory(tasks, horizon_days=horizon_days)
    return CompetingProjectsAllocationBackend(
        horizon_days=horizon_days,
        tasks=tasks,
        workers=workers,
        task_names=tuple(task.name for task in tasks),
        worker_names=tuple(worker.name for worker in workers),
        variable_shape=(horizon_days, len(workers), len(tasks)),
        variable_count=horizon_days * len(workers) * len(tasks),
        upper_bounds=upper_bounds,
        target_value_by_day=target_value_by_day,
    )


def build_target_value_trajectory(
    tasks: tuple[CompetingProjectsTask, ...],
    *,
    horizon_days: int,
) -> NDArray[numpy.float64]:
    """Return the paper-style desired value-growth trajectory over the horizon."""
    effective_hours = numpy.array([task.initial_effective_hours for task in tasks], dtype=float)
    daily_values = numpy.zeros((horizon_days, len(tasks)), dtype=float)
    for day_index in range(horizon_days):
        active = active_task_mask(tasks, effective_hours)
        for task_index, task in enumerate(tasks):
            if active[task_index]:
                effective_hours[task_index] = min(
                    effective_hours[task_index] + task.required_hours_per_day,
                    task.total_required_hours,
                )
        daily_values[day_index, :] = numpy.array(
            [task_value(task, effective_hours[index]) for index, task in enumerate(tasks)],
            dtype=float,
        )
    return daily_values


def active_task_mask(
    tasks: tuple[CompetingProjectsTask, ...],
    effective_hours_by_task: NDArray[numpy.float64],
) -> tuple[bool, ...]:
    """Return whether each task is currently active and allowed to receive work."""
    active: list[bool] = []
    for task_index, task in enumerate(tasks):
        if effective_hours_by_task[task_index] >= task.total_required_hours - 1e-9:
            active.append(False)
            continue
        if task.predecessor_index is None:
            active.append(True)
            continue
        predecessor = tasks[task.predecessor_index]
        predecessor_fraction = effective_hours_by_task[task.predecessor_index] / max(
            predecessor.total_required_hours,
            1e-9,
        )
        active.append(predecessor_fraction + 1e-9 >= task.predecessor_completion_threshold)
    return tuple(active)


def task_value(task: CompetingProjectsTask, effective_hours: float) -> float:
    """Return the cycloidal value estimate used in the paper's case study."""
    if effective_hours <= 0.0:
        return 0.0

    progress_fraction = min(max(effective_hours / max(task.total_required_hours, 1e-9), 0.0), 1.0)
    if progress_fraction >= 1.0 - 1e-12:
        return float(task.max_value_p / (task.startup_a + (1.0 / task.efficiency_e)))

    scaled_time = progress_fraction / task.efficiency_e
    cycloidal_term = progress_fraction**2 - (math.sin(math.pi * progress_fraction) ** 2 / math.pi**2)
    return float((task.max_value_p / (task.startup_a + scaled_time)) * cycloidal_term)


def coerce_daily_hours(
    flat_variables: NDArray[numpy.float64],
    *,
    backend: CompetingProjectsAllocationBackend,
) -> NDArray[numpy.float64]:
    """Clip one flat plan into the static day-worker-task bounds used by the package."""
    clipped = numpy.clip(
        numpy.array(flat_variables, dtype=float, copy=True).reshape(backend.variable_shape),
        0.0,
        backend.upper_bounds,
    )
    for day_index in range(backend.horizon_days):
        for worker_index, worker in enumerate(backend.workers):
            row = clipped[day_index, worker_index, :]
            total = float(row.sum())
            if total <= worker.total_daily_hours + 1e-12:
                continue
            scale = worker.total_daily_hours / total
            clipped[day_index, worker_index, :] = row * scale
    return clipped


def simulate_competing_projects_plan(
    flat_variables: NDArray[numpy.float64],
    *,
    backend: CompetingProjectsAllocationBackend,
) -> CompetingProjectsSimulation:
    """Simulate one daily personnel-allocation plan against the target trajectory."""
    daily_hours = coerce_daily_hours(flat_variables, backend=backend)
    tasks = backend.tasks
    effective_hours = numpy.array([task.initial_effective_hours for task in tasks], dtype=float)
    daily_value_by_task = numpy.zeros((backend.horizon_days, len(tasks)), dtype=float)
    scheduled_hours_by_worker = numpy.zeros(len(backend.workers), dtype=float)
    inactive_hours = 0.0

    for day_index in range(backend.horizon_days):
        active = active_task_mask(tasks, effective_hours)
        for worker_index, worker in enumerate(backend.workers):
            for task_index, task in enumerate(tasks):
                scheduled_hours = float(daily_hours[day_index, worker_index, task_index])
                if scheduled_hours <= 0.0:
                    continue
                scheduled_hours_by_worker[worker_index] += scheduled_hours
                if not active[task_index]:
                    inactive_hours += scheduled_hours
                    continue
                capability = worker.capability_by_task[task_index]
                if capability <= 0.0:
                    inactive_hours += scheduled_hours
                    continue
                remaining_effective_hours = max(task.total_required_hours - effective_hours[task_index], 0.0)
                effective_contribution = scheduled_hours * capability
                if effective_contribution <= remaining_effective_hours + 1e-12:
                    effective_hours[task_index] += effective_contribution
                    continue
                usable_fraction = remaining_effective_hours / max(effective_contribution, 1e-12)
                effective_hours[task_index] = task.total_required_hours
                inactive_hours += scheduled_hours * (1.0 - usable_fraction)

        daily_value_by_task[day_index, :] = numpy.array(
            [task_value(task, effective_hours[index]) for index, task in enumerate(tasks)],
            dtype=float,
        )

    total_change_hours = float(numpy.abs(numpy.diff(daily_hours, axis=0)).sum())
    tracking_error = float(numpy.square(backend.target_value_by_day - daily_value_by_task).sum())
    return CompetingProjectsSimulation(
        daily_hours=daily_hours,
        daily_value_by_task=daily_value_by_task,
        target_value_by_task=backend.target_value_by_day,
        effective_hours_by_task=effective_hours,
        scheduled_hours_by_worker=scheduled_hours_by_worker,
        tracking_error=tracking_error,
        inactive_hours=inactive_hours,
        total_change_hours=total_change_hours,
    )


def build_manager_baseline_plan(backend: CompetingProjectsAllocationBackend) -> NDArray[numpy.float64]:
    """Build a feasible naive schedule that allocates hours in fixed task order."""
    plan = numpy.zeros(backend.variable_shape, dtype=float)
    effective_hours = numpy.array([task.initial_effective_hours for task in backend.tasks], dtype=float)
    for day_index in range(backend.horizon_days):
        active = active_task_mask(backend.tasks, effective_hours)
        for worker_index, worker in enumerate(backend.workers):
            remaining_hours = worker.total_daily_hours
            for task_index, task in enumerate(backend.tasks):
                if remaining_hours <= 1e-9:
                    break
                if not active[task_index] or worker.capability_by_task[task_index] <= 0.0:
                    continue
                remaining_effective_hours = max(task.total_required_hours - effective_hours[task_index], 0.0)
                if remaining_effective_hours <= 1e-9:
                    continue
                daily_need = min(task.required_hours_per_day, remaining_effective_hours)
                assignable = min(
                    worker.max_daily_hours_by_task[task_index],
                    remaining_hours,
                    daily_need,
                )
                if assignable <= 1e-9:
                    continue
                plan[day_index, worker_index, task_index] = assignable
                remaining_hours -= assignable
                effective_hours[task_index] = min(
                    effective_hours[task_index] + assignable * worker.capability_by_task[task_index],
                    task.total_required_hours,
                )
    return plan.reshape(-1)


def build_value_tracking_plan(
    backend: CompetingProjectsAllocationBackend,
    *,
    hour_quantum: float = 1.0,
) -> NDArray[numpy.float64]:
    """Build a feasible greedy schedule that chases the daily value-growth targets."""
    if hour_quantum <= 0.0:
        raise ValueError("hour_quantum must be positive.")

    plan = numpy.zeros(backend.variable_shape, dtype=float)
    effective_hours = numpy.array([task.initial_effective_hours for task in backend.tasks], dtype=float)
    for day_index in range(backend.horizon_days):
        active = active_task_mask(backend.tasks, effective_hours)
        target_today = backend.target_value_by_day[day_index, :]
        for worker_index, worker in enumerate(backend.workers):
            remaining_hours = worker.total_daily_hours
            task_hours = numpy.zeros(len(backend.tasks), dtype=float)
            while remaining_hours + 1e-9 >= hour_quantum:
                current_values = numpy.array(
                    [task_value(task, effective_hours[index]) for index, task in enumerate(backend.tasks)],
                    dtype=float,
                )
                scores: list[tuple[float, int]] = []
                for task_index, task in enumerate(backend.tasks):
                    if not active[task_index]:
                        continue
                    capability = worker.capability_by_task[task_index]
                    if capability <= 0.0:
                        continue
                    if task_hours[task_index] + hour_quantum > worker.max_daily_hours_by_task[task_index] + 1e-9:
                        continue
                    remaining_effective_hours = max(task.total_required_hours - effective_hours[task_index], 0.0)
                    if remaining_effective_hours <= 1e-9:
                        continue
                    current_gap = float(max(target_today[task_index] - current_values[task_index], 0.0))
                    final_gap = float(
                        max(backend.target_value_by_day[-1, task_index] - current_values[task_index], 0.0)
                    )
                    score = capability * ((2.0 * current_gap) + final_gap)
                    if task.predecessor_index is not None:
                        predecessor = backend.tasks[task.predecessor_index]
                        predecessor_fraction = effective_hours[task.predecessor_index] / max(
                            predecessor.total_required_hours,
                            1e-9,
                        )
                        unlock_gap = max(task.predecessor_completion_threshold - predecessor_fraction, 0.0)
                        score += 0.15 * capability * max(1.0 - unlock_gap, 0.0)
                    scores.append((score, task_index))
                if not scores:
                    break
                best_score, best_task_index = max(scores)
                if best_score <= 1e-12:
                    break
                task = backend.tasks[best_task_index]
                plan[day_index, worker_index, best_task_index] += hour_quantum
                task_hours[best_task_index] += hour_quantum
                remaining_hours -= hour_quantum
                effective_hours[best_task_index] = min(
                    effective_hours[best_task_index] + hour_quantum * worker.capability_by_task[best_task_index],
                    task.total_required_hours,
                )
                active = active_task_mask(backend.tasks, effective_hours)
        if day_index + 1 < backend.horizon_days:
            continue
    return plan.reshape(-1)
