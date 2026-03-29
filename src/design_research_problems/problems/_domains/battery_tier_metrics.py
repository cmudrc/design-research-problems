"""Shared metric contract for tiered 18650 battery problems."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BatteryTierMetrics:
    """Canonical metric payload used across tiered battery problems."""

    cell_count: float
    """Evaluated physical cell count."""
    connection_count: float
    """Evaluated explicit or inferred electrical connection count."""
    cost_usd: float
    """Estimated battery-pack cost."""
    design_volume_mm3: float
    """Computed pack bounding volume."""
    max_temperature_c: float
    """Estimated peak battery temperature under load."""
    voltage_v: float
    """Pack voltage metric used for feasibility checks."""
    capacity_ah: float
    """Pack capacity metric used for feasibility checks."""
    current_limit_a: float
    """Continuous current capability metric."""
    min_clearance_mm: float
    """Minimum pairwise cell clearance."""
    is_feasible: bool
    """Whether the candidate is feasible under problem constraints."""
    failure_reason: str | None = None
    """Optional failure reason for infeasible candidates."""

    def as_dict(self) -> dict[str, float]:
        """Return the canonical optimization ``objective_components`` mapping.

        Returns:
            Canonical metric-key payload shared by tiered battery optimizers.
        """
        return {
            "cell_count": float(self.cell_count),
            "connection_count": float(self.connection_count),
            "cost_usd": float(self.cost_usd),
            "design_volume_mm3": float(self.design_volume_mm3),
            "max_temperature_c": float(self.max_temperature_c),
            "voltage_v": float(self.voltage_v),
            "capacity_ah": float(self.capacity_ah),
            "current_limit_a": float(self.current_limit_a),
            "min_clearance_mm": float(self.min_clearance_mm),
        }


@dataclass(frozen=True)
class BatteryObjectiveWeights:
    """Scalarization weights for tiered battery optimization objectives."""

    volume: float
    """Weight applied to normalized design volume."""
    cost: float
    """Weight applied to normalized design cost."""
    temperature: float
    """Weight applied to normalized peak temperature."""

    @classmethod
    def from_mapping(
        cls,
        value: object,
        *,
        default_volume: float,
        default_cost: float,
        default_temperature: float,
    ) -> BatteryObjectiveWeights:
        """Build one weights object from manifest-compatible payloads.

        Args:
            value: Raw mapping-like value from manifest parameters.
            default_volume: Fallback volume weight.
            default_cost: Fallback cost weight.
            default_temperature: Fallback temperature weight.

        Returns:
            Parsed objective weights.
        """
        if not isinstance(value, dict):
            return cls(
                volume=float(default_volume),
                cost=float(default_cost),
                temperature=float(default_temperature),
            )
        return cls(
            volume=float(value.get("volume", default_volume)),
            cost=float(value.get("cost", default_cost)),
            temperature=float(value.get("temperature", default_temperature)),
        )


__all__ = ["BatteryObjectiveWeights", "BatteryTierMetrics"]
