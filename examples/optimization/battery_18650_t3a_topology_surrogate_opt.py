"""Inspect the T3A topology surrogate battery optimization benchmark."""

from __future__ import annotations

import design_research_problems as derp

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
    problem = derp.get_problem("battery_18650_t3a_topology_surrogate_opt")
    initial = problem.generate_initial_solution(seed=3)
    surrogate_components = problem.objective_components(initial)
    surrogate_provenance = problem.evaluation_provenance(initial)
    explicit_problem = type(problem)(
        metadata=problem.metadata,
        statement_markdown=problem.statement_markdown,
        resource_bundle=problem.resource_bundle,
        requirements=problem.requirements,
        max_cell_count=problem.max_cell_count,
        minimum_spacing_mm=problem.minimum_spacing_mm,
        objective_weights=problem.objective_weights,
        cooling_coefficient_w_per_m2k=problem.cooling_coefficient_w_per_m2k,
        passive_cooling_w_per_k=problem.passive_cooling_w_per_k,
        ambient_temperature_c=problem.ambient_temperature_c,
        maximum_temperature_c=problem.maximum_temperature_c,
        load_current_a=problem.load_current_a,
        backend_config=problem.backend_config,
        evaluation_mode="explicit_circuit",
        imbalance_model=problem.imbalance_model.value,
    )
    explicit_components = explicit_problem.objective_components(initial)
    explicit_provenance = explicit_problem.evaluation_provenance(initial)
    print(problem.metadata.problem_id)
    print("surrogate-mode", surrogate_provenance.evaluation_mode)
    print("explicit-mode", explicit_provenance.evaluation_mode)
    print("surrogate", " ".join(f"{key}={surrogate_components[key]:.3f}" for key in COMMON_KEYS))
    print("explicit", " ".join(f"{key}={explicit_components[key]:.3f}" for key in COMMON_KEYS))


if __name__ == "__main__":
    main()
