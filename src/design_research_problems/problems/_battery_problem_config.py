"""Shared battery-problem defaults and manifest parsing helpers."""

from __future__ import annotations

from typing import cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._domains.battery_cell_model import (
    BatteryBackendConfig,
    battery_backend_config_from_mapping,
)
from design_research_problems.problems._domains.battery_layout import BatteryRequirements


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


def default_battery_requirements() -> BatteryRequirements:
    """Return the library default 18650 battery requirements."""
    return BatteryRequirements(
        target_voltage_v=14.8,
        minimum_capacity_ah=10.0,
        minimum_current_a=60.0,
        max_width_mm=500.0,
        max_depth_mm=500.0,
        max_height_mm=250.0,
        voltage_tolerance_v=0.1,
    )


def resolve_battery_requirements(requirements: BatteryRequirements | None) -> BatteryRequirements:
    """Return provided requirements or the shared defaults."""
    return default_battery_requirements() if requirements is None else requirements


def parse_battery_requirements(manifest: ProblemManifest) -> BatteryRequirements:
    """Build battery requirements from one manifest."""
    return BatteryRequirements(
        target_voltage_v=_coerce_float(manifest.parameters.get("target_voltage_v"), 14.8),
        minimum_capacity_ah=_coerce_float(manifest.parameters.get("minimum_capacity_ah"), 10.0),
        minimum_current_a=_coerce_float(manifest.parameters.get("minimum_current_a"), 60.0),
        max_width_mm=_coerce_float(manifest.parameters.get("max_width_mm"), 500.0),
        max_depth_mm=_coerce_float(manifest.parameters.get("max_depth_mm"), 500.0),
        max_height_mm=_coerce_float(manifest.parameters.get("max_height_mm"), 250.0),
        voltage_tolerance_v=_coerce_float(manifest.parameters.get("voltage_tolerance_v"), 0.1),
    )


def parse_battery_backend_config(manifest: ProblemManifest) -> BatteryBackendConfig | None:
    """Parse optional battery backend config from one manifest."""
    raw_backend = manifest.parameters.get("battery_backend")
    if raw_backend is None:
        return None
    return battery_backend_config_from_mapping(raw_backend)


__all__ = [
    "_coerce_float",
    "_coerce_int",
    "default_battery_requirements",
    "parse_battery_backend_config",
    "parse_battery_requirements",
    "resolve_battery_requirements",
]
