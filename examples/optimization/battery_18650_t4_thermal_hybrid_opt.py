"""Inspect the T4 thermal hybrid battery optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp
from design_research_problems import MissingOptionalDependencyError

COMMON_KEYS = (
    "cell_count",
    "connection_count",
    "cost_usd",
    "design_volume_mm3",
    "max_temperature_c",
    "voltage_v",
    "capacity_ah",
    "current_limit_a",
    "min_clearance_mm",
)


def main() -> None:
    try:
        problem = derp.get_problem("battery_18650_t4_thermal_hybrid_opt")
        initial = problem.generate_initial_solution(seed=4)
        hybrid_components = problem.objective_components(initial)
        hybrid_provenance = problem.evaluation_provenance(initial)
        explicit_problem = type(problem)(
            metadata=problem.metadata,
            statement_markdown=problem.statement_markdown,
            resource_bundle=problem.resource_bundle,
            requirements=problem.requirements,
            max_cell_count=problem.max_cell_count,
            minimum_spacing_mm=problem.minimum_spacing_mm,
            objective_weights=problem.objective_weights,
            cooling_coefficient_bounds=problem.cooling_coefficient_bounds,
            passive_cooling_bounds=problem.passive_cooling_bounds,
            ambient_temperature_bounds=problem.ambient_temperature_bounds,
            thermal_model=problem.thermal_model,
            thermal_neighbor_clearance_mm=problem.thermal_neighbor_clearance_mm,
            thermal_contact_decay_mm=problem.thermal_contact_decay_mm,
            thermal_contact_resistance_k_per_w=problem.thermal_contact_resistance_k_per_w,
            thermal_flow_shadowing_factor=problem.thermal_flow_shadowing_factor,
            thermal_airflow_axis=problem.thermal_airflow_axis,
            thermal_reference_soc=problem.thermal_reference_soc,
            maximum_temperature_c=problem.maximum_temperature_c,
            load_current_a=problem.load_current_a,
            backend_config=problem.backend_config,
            evaluation_mode="explicit_circuit",
            imbalance_model=problem.imbalance_model.value,
        )
        explicit_components = explicit_problem.objective_components(initial)
        print(problem.metadata.problem_id)
        print("hybrid-mode", hybrid_provenance.evaluation_mode)
        print("hybrid", " ".join(f"{key}={hybrid_components[key]:.3f}" for key in COMMON_KEYS))
        print("explicit", " ".join(f"{key}={explicit_components[key]:.3f}" for key in COMMON_KEYS))
    except MissingOptionalDependencyError as exc:
        print(exc)


if __name__ == "__main__":
    main()
