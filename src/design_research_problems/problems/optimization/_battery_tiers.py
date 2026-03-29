"""Compatibility exports for tiered 18650 battery optimization problems."""

from design_research_problems.problems._battery_tier_problems import (
    Battery18650T1RectangularSurrogateOptimizationProblem,
    Battery18650T2PoseSurrogateOptimizationProblem,
    Battery18650T3ATopologySurrogateOptimizationProblem,
    Battery18650T4ThermalHybridOptimizationProblem,
)

__all__ = [
    "Battery18650T1RectangularSurrogateOptimizationProblem",
    "Battery18650T2PoseSurrogateOptimizationProblem",
    "Battery18650T3ATopologySurrogateOptimizationProblem",
    "Battery18650T4ThermalHybridOptimizationProblem",
]
