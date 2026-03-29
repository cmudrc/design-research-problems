"""Grammar problem implementations."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from .._grammar import GrammarTransition

_LAZY_EXPORTS = {
    "BatteryCellInstance": "design_research_problems.problems._domains.battery_circuit:BatteryCellInstance",
    "BatteryCellPlacement": "design_research_problems.problems._domains.battery_layout:BatteryCellPlacement",
    "BatteryCircuitEvaluation": "design_research_problems.problems._domains.battery_circuit:BatteryCircuitEvaluation",
    "BatteryCircuitState": "design_research_problems.problems._domains.battery_circuit:BatteryCircuitState",
    "BatteryConnection": "design_research_problems.problems._domains.battery_circuit:BatteryConnection",
    "Battery18650T1RectangularSurrogateGrammarProblem": (
        "design_research_problems.problems.grammar._battery_tiers:Battery18650T1RectangularSurrogateGrammarProblem"
    ),
    "Battery18650T2PoseSurrogateGrammarProblem": (
        "design_research_problems.problems.grammar._battery_tiers:Battery18650T2PoseSurrogateGrammarProblem"
    ),
    "Battery18650T3ATopologySurrogateGrammarProblem": (
        "design_research_problems.problems.grammar._battery_tiers:Battery18650T3ATopologySurrogateGrammarProblem"
    ),
    "Battery18650T3BNetlistExplicitGrammarProblem": (
        "design_research_problems.problems.grammar._battery_tiers:Battery18650T3BNetlistExplicitGrammarProblem"
    ),
    "Battery18650T4ThermalHybridGrammarProblem": (
        "design_research_problems.problems.grammar._battery_tiers:Battery18650T4ThermalHybridGrammarProblem"
    ),
    "BatteryPack18650OpenEndedProblem": (
        "design_research_problems.problems.grammar._battery_pack_open:BatteryPack18650OpenEndedProblem"
    ),
    "BatteryPack18650SeriesParallelProblem": (
        "design_research_problems.problems.grammar._battery_pack_sp:BatteryPack18650SeriesParallelProblem"
    ),
    "IoTHomeCoolingGrammarProblem": "design_research_problems.problems.grammar._iot_home:IoTHomeCoolingGrammarProblem",
    "IoTHomeEvaluation": "design_research_problems.problems.grammar._iot_home:IoTHomeEvaluation",
    "IoTHomeLink": "design_research_problems.problems.grammar._iot_home:IoTHomeLink",
    "IoTHomeProduct": "design_research_problems.problems.grammar._iot_home:IoTHomeProduct",
    "IoTHomeState": "design_research_problems.problems.grammar._iot_home:IoTHomeState",
    "PlanarJoint": "design_research_problems.problems.grammar._planar_truss:PlanarJoint",
    "PlanarLoad": "design_research_problems.problems.grammar._planar_truss:PlanarLoad",
    "PlanarMember": "design_research_problems.problems.grammar._planar_truss:PlanarMember",
    "PlanarTrussEvaluation": ("design_research_problems.problems.grammar._planar_truss:PlanarTrussEvaluation"),
    "PlanarTrussSpanProblem": "design_research_problems.problems.grammar._planar_truss:PlanarTrussSpanProblem",
    "PlanarTrussState": "design_research_problems.problems.grammar._planar_truss:PlanarTrussState",
    "SpaceJoint": "design_research_problems.problems.grammar._space_truss:SpaceJoint",
    "SpaceLoad": "design_research_problems.problems.grammar._space_truss:SpaceLoad",
    "SpaceMember": "design_research_problems.problems.grammar._space_truss:SpaceMember",
    "SpaceTrussEvaluation": "design_research_problems.problems.grammar._space_truss:SpaceTrussEvaluation",
    "SpaceTrussSpanProblem": "design_research_problems.problems.grammar._space_truss:SpaceTrussSpanProblem",
    "SpaceTrussState": "design_research_problems.problems.grammar._space_truss:SpaceTrussState",
    "TrussAPEvaluation": "design_research_problems.problems.grammar._truss_ap:TrussAPEvaluation",
    "TrussAPGrammarProblem": "design_research_problems.problems.grammar._truss_ap:TrussAPGrammarProblem",
    "TrussAPJoint": "design_research_problems.problems.grammar._truss_ap:TrussAPJoint",
    "TrussAPLoad": "design_research_problems.problems.grammar._truss_ap:TrussAPLoad",
    "TrussAPMember": "design_research_problems.problems.grammar._truss_ap:TrussAPMember",
    "TrussAPState": "design_research_problems.problems.grammar._truss_ap:TrussAPState",
    "SeriesParallelBatteryEvaluation": (
        "design_research_problems.problems.grammar._battery_pack_sp:SeriesParallelBatteryEvaluation"
    ),
    "SeriesParallelBatteryState": (
        "design_research_problems.problems.grammar._battery_pack_sp:SeriesParallelBatteryState"
    ),
}

__all__ = ["GrammarTransition", *_LAZY_EXPORTS]


def __getattr__(name: str) -> object:
    """Resolve one lazily exported grammar implementation.

    Args:
        name: Public attribute name requested from this package.

    Returns:
        Exported grammar object referenced by ``name``.

    Raises:
        AttributeError: If ``name`` is not a supported lazy export.
    """
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, _, attr_name = target.partition(":")
    return getattr(import_module(module_path), attr_name)


if TYPE_CHECKING:
    from .._domains.battery_circuit import BatteryCellInstance as BatteryCellInstance
    from .._domains.battery_circuit import BatteryCircuitEvaluation as BatteryCircuitEvaluation
    from .._domains.battery_circuit import BatteryCircuitState as BatteryCircuitState
    from .._domains.battery_circuit import BatteryConnection as BatteryConnection
    from .._domains.battery_layout import BatteryCellPlacement as BatteryCellPlacement
    from ._battery_pack_open import BatteryPack18650OpenEndedProblem as BatteryPack18650OpenEndedProblem
    from ._battery_pack_sp import (
        BatteryPack18650SeriesParallelProblem as BatteryPack18650SeriesParallelProblem,
    )
    from ._battery_pack_sp import SeriesParallelBatteryEvaluation as SeriesParallelBatteryEvaluation
    from ._battery_pack_sp import SeriesParallelBatteryState as SeriesParallelBatteryState
    from ._battery_tiers import (
        Battery18650T1RectangularSurrogateGrammarProblem as Battery18650T1RectangularSurrogateGrammarProblem,
    )
    from ._battery_tiers import Battery18650T2PoseSurrogateGrammarProblem as Battery18650T2PoseSurrogateGrammarProblem
    from ._battery_tiers import (
        Battery18650T3ATopologySurrogateGrammarProblem as Battery18650T3ATopologySurrogateGrammarProblem,
    )
    from ._battery_tiers import (
        Battery18650T3BNetlistExplicitGrammarProblem as Battery18650T3BNetlistExplicitGrammarProblem,
    )
    from ._battery_tiers import Battery18650T4ThermalHybridGrammarProblem as Battery18650T4ThermalHybridGrammarProblem
    from ._iot_home import IoTHomeCoolingGrammarProblem as IoTHomeCoolingGrammarProblem
    from ._iot_home import IoTHomeEvaluation as IoTHomeEvaluation
    from ._iot_home import IoTHomeLink as IoTHomeLink
    from ._iot_home import IoTHomeProduct as IoTHomeProduct
    from ._iot_home import IoTHomeState as IoTHomeState
    from ._planar_truss import PlanarJoint as PlanarJoint
    from ._planar_truss import PlanarLoad as PlanarLoad
    from ._planar_truss import PlanarMember as PlanarMember
    from ._planar_truss import PlanarTrussEvaluation as PlanarTrussEvaluation
    from ._planar_truss import PlanarTrussSpanProblem as PlanarTrussSpanProblem
    from ._planar_truss import PlanarTrussState as PlanarTrussState
    from ._space_truss import SpaceJoint as SpaceJoint
    from ._space_truss import SpaceLoad as SpaceLoad
    from ._space_truss import SpaceMember as SpaceMember
    from ._space_truss import SpaceTrussEvaluation as SpaceTrussEvaluation
    from ._space_truss import SpaceTrussSpanProblem as SpaceTrussSpanProblem
    from ._space_truss import SpaceTrussState as SpaceTrussState
    from ._truss_ap import TrussAPEvaluation as TrussAPEvaluation
    from ._truss_ap import TrussAPGrammarProblem as TrussAPGrammarProblem
    from ._truss_ap import TrussAPJoint as TrussAPJoint
    from ._truss_ap import TrussAPLoad as TrussAPLoad
    from ._truss_ap import TrussAPMember as TrussAPMember
    from ._truss_ap import TrussAPState as TrussAPState
