"""Optimization problem implementations."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_EXPORTS = {
    "BatteryGridSizingProblem": (
        "design_research_problems.problems.optimization._battery_grid:BatteryGridSizingProblem"
    ),
    "IDETreadlePumpMaterialMin": (
        "design_research_problems.problems.optimization._ide_treadle:IDETreadlePumpMaterialMin"
    ),
    "MoneyMakerHipPumpProblem": ("design_research_problems.problems.optimization._moneymaker:MoneyMakerHipPumpProblem"),
    "PillCapsuleMinArea": "design_research_problems.problems.optimization._pill:PillCapsuleMinArea",
}

__all__ = list(_LAZY_EXPORTS)


def __getattr__(name: str) -> object:
    """Resolve one lazily exported optimization implementation."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, _, attr_name = target.partition(":")
    return getattr(import_module(module_path), attr_name)


if TYPE_CHECKING:
    from ._battery_grid import BatteryGridSizingProblem as BatteryGridSizingProblem
    from ._ide_treadle import IDETreadlePumpMaterialMin as IDETreadlePumpMaterialMin
    from ._moneymaker import MoneyMakerHipPumpProblem as MoneyMakerHipPumpProblem
    from ._pill import PillCapsuleMinArea as PillCapsuleMinArea
