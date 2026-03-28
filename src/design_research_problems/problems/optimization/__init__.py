"""Optimization problem implementations."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_LAZY_EXPORTS = {
    "BatteryFastChargeDFNAnchorOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_fast_charge:BatteryFastChargeDFNAnchorOptimizationProblem"
    ),
    "Battery18650T1RectangularSurrogateOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_tiers:"
        "Battery18650T1RectangularSurrogateOptimizationProblem"
    ),
    "Battery18650T2PoseSurrogateOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_tiers:Battery18650T2PoseSurrogateOptimizationProblem"
    ),
    "Battery18650T3ATopologySurrogateOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_tiers:"
        "Battery18650T3ATopologySurrogateOptimizationProblem"
    ),
    "Battery18650T3BNetlistExplicitOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_open_ended:"
        "Battery18650T3BNetlistExplicitOptimizationProblem"
    ),
    "Battery18650T4ThermalHybridOptimizationProblem": (
        "design_research_problems.problems.optimization._battery_tiers:Battery18650T4ThermalHybridOptimizationProblem"
    ),
    "BatteryGridSizingProblem": (
        "design_research_problems.problems.optimization._battery_grid:BatteryGridSizingProblem"
    ),
    "BatteryOrientedLayoutProblem": (
        "design_research_problems.problems.optimization._battery_oriented_layout:BatteryOrientedLayoutProblem"
    ),
    "BatteryOpenEndedCapacityMaxProblem": (
        "design_research_problems.problems.optimization._battery_open_ended:BatteryOpenEndedCapacityMaxProblem"
    ),
    "GMPBOptimizationProblem": "design_research_problems.problems.optimization._gmpb:GMPBOptimizationProblem",
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
    "CompetingProjectsWorkerHoursProblem": (
        "design_research_problems.problems.optimization._worker_hours_allocation:CompetingProjectsWorkerHoursProblem"
    ),
    "WindFarmLayoutOptimizationProblem": (
        "design_research_problems.problems.optimization._wind_farm_layout:WindFarmLayoutOptimizationProblem"
    ),
    "UnrestrictedWindFarmLayoutOptimizationProblem": (
        "design_research_problems.problems.optimization._wind_farm_unrestricted:UnrestrictedWindFarmLayoutOptimizationProblem"
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
    from ._battery_fast_charge import (
        BatteryFastChargeDFNAnchorOptimizationProblem as BatteryFastChargeDFNAnchorOptimizationProblem,
    )
    from ._battery_grid import BatteryGridSizingProblem as BatteryGridSizingProblem
    from ._battery_open_ended import (
        Battery18650T3BNetlistExplicitOptimizationProblem as Battery18650T3BNetlistExplicitOptimizationProblem,
    )
    from ._battery_open_ended import BatteryOpenEndedCapacityMaxProblem as BatteryOpenEndedCapacityMaxProblem
    from ._battery_oriented_layout import BatteryOrientedLayoutProblem as BatteryOrientedLayoutProblem
    from ._battery_tiers import (
        Battery18650T1RectangularSurrogateOptimizationProblem as Battery18650T1RectangularSurrogateOptimizationProblem,
    )
    from ._battery_tiers import (
        Battery18650T2PoseSurrogateOptimizationProblem as Battery18650T2PoseSurrogateOptimizationProblem,
    )
    from ._battery_tiers import (
        Battery18650T3ATopologySurrogateOptimizationProblem as Battery18650T3ATopologySurrogateOptimizationProblem,
    )
    from ._battery_tiers import (
        Battery18650T4ThermalHybridOptimizationProblem as Battery18650T4ThermalHybridOptimizationProblem,
    )
    from ._gmpb import GMPBOptimizationProblem as GMPBOptimizationProblem
    from ._ide_treadle import IDETreadlePumpMaterialMin as IDETreadlePumpMaterialMin
    from ._moneymaker import MoneyMakerHipPumpProblem as MoneyMakerHipPumpProblem
    from ._pill import PillCapsuleMinArea as PillCapsuleMinArea
    from ._truss_topology import (
        PlanarTrussEngineeringOptimizationProblem as PlanarTrussEngineeringOptimizationProblem,
    )
    from ._truss_topology import (
        SpaceTrussEngineeringOptimizationProblem as SpaceTrussEngineeringOptimizationProblem,
    )
    from ._wind_farm_layout import WindFarmLayoutOptimizationProblem as WindFarmLayoutOptimizationProblem
    from ._wind_farm_unrestricted import (
        UnrestrictedWindFarmLayoutOptimizationProblem as UnrestrictedWindFarmLayoutOptimizationProblem,
    )
    from ._worker_hours_allocation import CompetingProjectsWorkerHoursProblem as CompetingProjectsWorkerHoursProblem
