"""Inspect the T3B explicit-netlist battery grammar benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    problem = derp.get_problem("battery_18650_t3b_netlist_explicit_grammar")
    state = problem.initial_state()
    transitions = problem.enumerate_transitions(state)
    evaluation = problem.evaluate(state)
    print(problem.metadata.problem_id)
    print("default-evaluation-mode", problem.metadata.benchmark_card.default_evaluation_mode)
    print("transitions", len(transitions))
    print("feasible", evaluation.is_feasible)
    print("metric-keys", ",".join(sorted(evaluation.as_dict())))


if __name__ == "__main__":
    main()
