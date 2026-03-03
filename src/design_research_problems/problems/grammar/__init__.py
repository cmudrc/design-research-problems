"""Grammar problem implementations."""

from __future__ import annotations

from importlib import import_module

from .._grammar import GrammarTransition

_LAZY_EXPORTS = {
    "BatteryCellInstance": "design_research_problems.problems.grammar._battery_circuit:BatteryCellInstance",
    "BatteryCellPlacement": "design_research_problems.problems.grammar._battery_core:BatteryCellPlacement",
    "BatteryCircuitEvaluation": "design_research_problems.problems.grammar._battery_circuit:BatteryCircuitEvaluation",
    "BatteryCircuitState": "design_research_problems.problems.grammar._battery_circuit:BatteryCircuitState",
    "BatteryConnection": "design_research_problems.problems.grammar._battery_circuit:BatteryConnection",
    "BatteryPack18650OpenEndedProblem": (
        "design_research_problems.problems.grammar._battery_pack_open:"
        "BatteryPack18650OpenEndedProblem"
    ),
    "BatteryPack18650SeriesParallelProblem": (
        "design_research_problems.problems.grammar._battery_pack_sp:"
        "BatteryPack18650SeriesParallelProblem"
    ),
    "PlanarJoint": "design_research_problems.problems.grammar._planar_truss:PlanarJoint",
    "PlanarLoad": "design_research_problems.problems.grammar._planar_truss:PlanarLoad",
    "PlanarMember": "design_research_problems.problems.grammar._planar_truss:PlanarMember",
    "PlanarTrussEvaluation": (
        "design_research_problems.problems.grammar._planar_truss:"
        "PlanarTrussEvaluation"
    ),
    "PlanarTrussSpanProblem": "design_research_problems.problems.grammar._planar_truss:PlanarTrussSpanProblem",
    "PlanarTrussState": "design_research_problems.problems.grammar._planar_truss:PlanarTrussState",
    "SeriesParallelBatteryEvaluation": (
        "design_research_problems.problems.grammar._battery_pack_sp:"
        "SeriesParallelBatteryEvaluation"
    ),
    "SeriesParallelBatteryState": (
        "design_research_problems.problems.grammar._battery_pack_sp:"
        "SeriesParallelBatteryState"
    ),
}

__all__ = ["GrammarTransition", *_LAZY_EXPORTS]


def __getattr__(name: str) -> object:
    """Resolve one lazily exported grammar implementation."""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_path, _, attr_name = target.partition(":")
    return getattr(import_module(module_path), attr_name)
