"""Shared base helpers for battery grammar problems."""

from __future__ import annotations

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._battery_problem_config import (
    resolve_battery_requirements,
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
from design_research_problems.problems._domains.battery_layout import BatteryRequirements, grid_index_limits
from design_research_problems.problems._grammar import GrammarProblem
from design_research_problems.problems._metadata import ProblemMetadata


class BatteryCircuitProblemBase[StateT, EvaluationT](GrammarProblem[StateT, EvaluationT]):
    """Shared base class for battery grammar problems."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
        backend_config: BatteryBackendConfig | None = None,
    ) -> None:
        """Store shared packaged battery requirements.

        Args:
            metadata: Value for ``metadata``.
            statement_markdown: Value for ``statement_markdown``.
            resource_bundle: Value for ``resource_bundle``.
            requirements: Value for ``requirements``.
            backend_config: Value for ``backend_config``.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.requirements = resolve_battery_requirements(requirements)
        self.backend_config = backend_config

    def evaluate_circuit_state(self, state: BatteryCircuitState) -> BatteryCircuitEvaluation:
        """Evaluate one explicit battery circuit using the shared backend.

        Args:
            state: Value for ``state``.

        Returns:
            Computed result for this callable.
        """
        return evaluate_battery_circuit(
            state=state,
            requirements=self.requirements,
            load_cell_model=load_18650_cell_model,
            backend_config=self.backend_config,
        )

    def legal_grid_shape(self) -> tuple[int, int, int]:
        """Return the maximum legal grid indices for this packaged benchmark.

        Returns:
            Computed result for this callable.
        """
        return grid_index_limits(self.requirements)
