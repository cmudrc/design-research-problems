"""Seed constrained optimization problem: minimum-area pill capsule."""

from __future__ import annotations

import math
from typing import cast

import numpy
from numpy.typing import NDArray

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import Bounds, ConstraintDefinition, OptimizationProblem


def _pill_volume(radius: float, length: float) -> float:
    """Calculate the capsule volume.

    Args:
        radius: Capsule end-cap radius.
        length: Cylindrical section length.

    Returns:
        Capsule volume.
    """
    return 4.0 / 3.0 * math.pi * radius**3 + length * math.pi * radius**2


def _pill_area(radius: float, length: float) -> float:
    """Calculate the capsule surface area.

    Args:
        radius: Capsule end-cap radius.
        length: Cylindrical section length.

    Returns:
        Capsule surface area.
    """
    return 2.0 * math.pi * radius * length + 4.0 * math.pi * radius**2


class PillCapsuleMinArea(OptimizationProblem):
    """Two-variable constrained optimization problem."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        required_volume: float = 1e-6,
    ) -> None:
        """Initialize the seed pill optimization problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            required_volume: Fixed target volume.
        """
        super().__init__(metadata=metadata, statement_markdown=statement_markdown)
        self.required_volume = required_volume
        self.bounds = Bounds(
            lb=numpy.array([0.0, 0.0], dtype=float),
            ub=numpy.array([1.0, 1.0], dtype=float),
        )
        self.constraints = [
            ConstraintDefinition(
                kind="eq",
                evaluate=lambda values: _pill_volume(float(values[0]), float(values[1])),
                target=self.required_volume,
            )
        ]

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest, statement_markdown: str) -> PillCapsuleMinArea:
        """Construct an instance from packaged manifest data.

        Args:
            manifest: Parsed packaged manifest.
            statement_markdown: Human-readable problem statement.

        Returns:
            Initialized problem instance.
        """
        required_volume = float(cast(float, manifest.parameters.get("required_volume", 1e-6)))
        return cls(metadata=manifest.metadata, statement_markdown=statement_markdown, required_volume=required_volume)

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return a seeded starting point.

        Args:
            seed: Optional random seed.

        Returns:
            Two-variable initial solution vector.
        """
        rng = numpy.random.default_rng(seed)
        return rng.random(2)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return the pill area.

        Args:
            variables: Two-element vector of ``radius`` and ``length``.

        Returns:
            Surface area objective value.
        """
        return _pill_area(float(variables[0]), float(variables[1]))

    def load_data(self) -> object:
        """Report that no curated dataset exists for this seed problem.

        Returns:
            This method never returns a dataset.

        Raises:
            NotImplementedError: Always, because no curated dataset exists yet.
        """
        raise NotImplementedError("There is no dataset available for this problem.")
