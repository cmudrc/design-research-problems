"""Optimization problem implementations."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_EXPORTS = {
    "BatteryGridSizingProblem": (
        "design_research_problems.problems.optimization._battery_grid:BatteryGridSizingProblem"
    ),
    "BatteryOpenEndedCapacityMaxProblem": (
        "design_research_problems.problems.optimization._battery_open_ended:BatteryOpenEndedCapacityMaxProblem"
    ),
    "IDETreadlePumpMaterialMin": (
        "design_research_problems.problems.optimization._ide_treadle:IDETreadlePumpMaterialMin"
    ),
    "MoneyMakerHipPumpProblem": ("design_research_problems.problems.optimization._moneymaker:MoneyMakerHipPumpProblem"),
    "PillCapsuleMinArea": "design_research_problems.problems.optimization._pill:PillCapsuleMinArea",
    "PlanarTrussEngineeringOptimizationProblem": (
        "design_research_problems.problems.optimization._truss_topology:PlanarTrussEngineeringOptimizationProblem"
    ),
    "SpaceTrussEngineeringOptimizationProblem": (
        "design_research_problems.problems.optimization._truss_topology:SpaceTrussEngineeringOptimizationProblem"
    ),
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> object:
    """Resolve one lazily exported optimization implementation.

    Args:
        name: Public attribute name requested from this package.

    Returns:
        Exported optimization object referenced by ``name``.

    Raises:
        AttributeError: If ``name`` is not a supported lazy export.
    """
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, _, attr_name = target.partition(":")
    return getattr(import_module(module_path), attr_name)


if TYPE_CHECKING:
    from ._battery_grid import BatteryGridSizingProblem as BatteryGridSizingProblem
    from ._battery_open_ended import BatteryOpenEndedCapacityMaxProblem as BatteryOpenEndedCapacityMaxProblem
    from ._ide_treadle import IDETreadlePumpMaterialMin as IDETreadlePumpMaterialMin
    from ._moneymaker import MoneyMakerHipPumpProblem as MoneyMakerHipPumpProblem
    from ._pill import PillCapsuleMinArea as PillCapsuleMinArea
    from ._truss_topology import (
        PlanarTrussEngineeringOptimizationProblem as PlanarTrussEngineeringOptimizationProblem,
    )
    from ._truss_topology import (
        SpaceTrussEngineeringOptimizationProblem as SpaceTrussEngineeringOptimizationProblem,
    )
