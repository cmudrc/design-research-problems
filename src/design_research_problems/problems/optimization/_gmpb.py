"""Dynamic optimization wrapper around the external GMPB benchmark."""

from __future__ import annotations

from typing import cast

import numpy
from gmpb import GMPB, GMPBConfig
from gmpb.state import EnvironmentState
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import Bounds, OptimizationProblem, OptimizationResult


class GMPBOptimizationProblem(OptimizationProblem):
    """Stateful minimization wrapper over the GMPB dynamic maximization benchmark."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        config: GMPBConfig | None = None,
        seed: int | None = None,
    ) -> None:
        """Initialize the GMPB wrapper with one benchmark configuration.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            config: Optional benchmark configuration override.
            seed: Optional benchmark seed used for reproducible environments.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.config = config or GMPBConfig(d=5, m=10)
        self._seed = seed
        self._benchmark = GMPB(self.config, seed=seed)
        lower_bounds, upper_bounds = self._benchmark.global_bounds()
        self.bounds = Bounds(lb=lower_bounds, ub=upper_bounds)
        self.constraints = []

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> GMPBOptimizationProblem:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized GMPB optimization wrapper.

        Raises:
            ProblemEvaluationError: If the manifest contains invalid GMPB parameters.
        """
        try:
            parameters = manifest.parameters
            config = GMPBConfig(
                d=int(cast(int, parameters.get("dimension", 5))),
                m=int(cast(int, parameters.get("component_count", 10))),
                T=int(cast(int, parameters.get("environment_count", 100))),
                change_frequency=int(cast(int, parameters.get("change_frequency", 1000))),
                lb=float(cast(float, parameters.get("lower_bound", -100.0))),
                ub=float(cast(float, parameters.get("upper_bound", 100.0))),
            )
            seed = cast(int | None, parameters.get("seed"))
            if seed is not None:
                seed = int(seed)
        except (TypeError, ValueError) as exc:
            raise ProblemEvaluationError(
                f"Invalid GMPB manifest parameters for {manifest.metadata.problem_id!r}: {exc}"
            ) from exc

        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            config=config,
            seed=seed,
        )

    def reset(self, seed: int | None = None) -> None:
        """Reset the underlying benchmark state.

        Args:
            seed: Optional replacement seed for future resets.
        """
        if seed is not None:
            self._seed = seed
        self._benchmark.reset(seed=self._seed)

    def step_environment(self) -> None:
        """Advance the underlying benchmark by one environment."""
        self._benchmark.step_environment()

    def current_environment_index(self) -> int:
        """Return the active GMPB environment index.

        Returns:
            Zero-based environment index.
        """
        return int(self._benchmark.current_environment_index())

    def evaluations_in_environment(self) -> int:
        """Return the consumed evaluations in the current environment.

        Returns:
            Number of evaluations already consumed in the current environment.
        """
        return int(self._benchmark.evaluations_in_environment())

    def native_evaluate(self, variables: NDArray[numpy.float64]) -> float:
        """Return the native GMPB maximization score and consume one evaluation.

        Args:
            variables: Candidate design vector.

        Returns:
            Native GMPB maximization score.
        """
        candidate = numpy.array(variables, dtype=float, copy=True)
        return float(self._benchmark.evaluate(candidate))

    def current_state(self, copy: bool = True) -> EnvironmentState:
        """Return the current benchmark environment state.

        Args:
            copy: Whether to deep-copy state arrays before returning them.

        Returns:
            Current GMPB environment snapshot.
        """
        return self._benchmark.get_state(copy=copy)

    def native_bounds(self) -> tuple[NDArray[numpy.float64], NDArray[numpy.float64]]:
        """Return the benchmark's native lower and upper bound vectors.

        Returns:
            Lower and upper bound vectors in native GMPB form.
        """
        lower_bounds, upper_bounds = self._benchmark.global_bounds()
        return (
            numpy.array(lower_bounds, dtype=float, copy=True),
            numpy.array(upper_bounds, dtype=float, copy=True),
        )

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Sample one uniformly random initial solution within bounds.

        Args:
            seed: Optional seed for the sampling RNG.

        Returns:
            One in-bounds candidate vector.
        """
        rng = numpy.random.default_rng(seed)
        return rng.uniform(self.bounds.lb, self.bounds.ub).astype(float, copy=False)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the minimization objective derived from the native GMPB score.

        Args:
            variables: Candidate design vector.

        Returns:
            Negated GMPB objective value suitable for minimization.
        """
        return -self.native_evaluate(variables)

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> OptimizationResult:
        """Run a simple random-search baseline over the dynamic benchmark.

        Args:
            initial_solution: Optional caller-supplied starting design.
            seed: Optional seed for candidate sampling.
            maxiter: Maximum evaluation budget for the random search.

        Returns:
            Best candidate found within the allotted evaluation budget.

        Raises:
            ValueError: If ``initial_solution`` has the wrong shape.
        """
        budget = max(1, int(maxiter))
        rng = numpy.random.default_rng(seed)

        if initial_solution is None:
            best_candidate = self.generate_initial_solution(seed=seed)
        else:
            best_candidate = numpy.array(initial_solution, dtype=float, copy=True)
            if best_candidate.shape != self.bounds.lb.shape:
                raise ValueError(
                    "Expected a "
                    f"{self.bounds.lb.shape[0]}-variable design vector, received shape {best_candidate.shape!r}."
                )
            best_candidate = numpy.clip(best_candidate, self.bounds.lb, self.bounds.ub)

        best_value = self.objective(best_candidate)
        evaluations = 1

        for _ in range(budget - 1):
            candidate = rng.uniform(self.bounds.lb, self.bounds.ub).astype(float, copy=False)
            value = self.objective(candidate)
            evaluations += 1
            if value < best_value:
                best_candidate = numpy.array(candidate, dtype=float, copy=True)
                best_value = value

        return OptimizationResult(
            x=numpy.array(best_candidate, dtype=float, copy=True),
            fun=float(best_value),
            success=True,
            message=("Completed GMPB dynamic random-search baseline over the changing benchmark environment."),
            nit=budget,
            nfev=evaluations,
        )
