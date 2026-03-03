"""Shared base helpers for battery grammar problems."""

from __future__ import annotations

from typing import cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.battery_cell_model import load_18650_cell_model
from design_research_problems.problems._domains.battery_circuit import (
    BatteryCircuitEvaluation,
    BatteryCircuitState,
    evaluate_battery_circuit,
)
from design_research_problems.problems._domains.battery_layout import BatteryRequirements, grid_index_limits
from design_research_problems.problems._grammar import GrammarProblem
from design_research_problems.problems._metadata import ProblemMetadata


def _coerce_int(value: object, default: int) -> int:
    """Return an integer manifest value with a fallback default."""
    if value is None:
        return default
    return int(cast(int, value))


def _coerce_float(value: object, default: float) -> float:
    """Return a float manifest value with a fallback default."""
    if value is None:
        return default
    return float(cast(float, value))


def parse_battery_requirements(manifest: ProblemManifest) -> BatteryRequirements:
    """Build the benchmark requirements from one manifest."""
    return BatteryRequirements(
        target_voltage_v=_coerce_float(manifest.parameters.get("target_voltage_v"), 14.8),
        minimum_capacity_ah=_coerce_float(manifest.parameters.get("minimum_capacity_ah"), 10.0),
        minimum_current_a=_coerce_float(manifest.parameters.get("minimum_current_a"), 60.0),
        max_width_mm=_coerce_float(manifest.parameters.get("max_width_mm"), 500.0),
        max_depth_mm=_coerce_float(manifest.parameters.get("max_depth_mm"), 500.0),
        max_height_mm=_coerce_float(manifest.parameters.get("max_height_mm"), 250.0),
        voltage_tolerance_v=_coerce_float(manifest.parameters.get("voltage_tolerance_v"), 0.1),
    )


class BatteryCircuitProblemBase[StateT, EvaluationT](GrammarProblem[StateT, EvaluationT]):
    """Shared base class for battery grammar problems."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        requirements: BatteryRequirements | None = None,
    ) -> None:
        """Store shared packaged battery requirements."""
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

    def evaluate_circuit_state(self, state: BatteryCircuitState) -> BatteryCircuitEvaluation:
        """Evaluate one explicit battery circuit using the shared backend."""
        return evaluate_battery_circuit(
            state=state,
            requirements=self.requirements,
            load_cell_model=load_18650_cell_model,
        )

    def legal_grid_shape(self) -> tuple[int, int, int]:
        """Return the maximum legal grid indices for this packaged benchmark."""
        return grid_index_limits(self.requirements)
