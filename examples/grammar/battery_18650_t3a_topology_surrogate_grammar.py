"""Inspect the T3A topology surrogate battery grammar benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    problem = derp.get_problem("battery_18650_t3a_topology_surrogate_grammar")
    state = problem.initial_state()
    evaluation = problem.evaluate(state)
    provenance = problem.evaluation_provenance(state)
    print(problem.metadata.problem_id)
    print("default-evaluation-mode", provenance.evaluation_mode)
    print("representation-mode", provenance.representation_mode)
    print("feasible", evaluation.is_feasible)
    print("metric-keys", ",".join(sorted(evaluation.as_dict())))


if __name__ == "__main__":
    main()
