"""Inspect tier-2 battery grammar benchmark."""

from __future__ import annotations

import design_research_problems as derp


def main() -> None:
    problem = derp.get_problem("battery_18650_t2_layout_grammar")
    state = problem.initial_state()
    transitions = problem.enumerate_transitions(state)
    next_state = transitions[0].next_state if transitions else state
    evaluation = problem.evaluate(next_state)
    print(problem.metadata.problem_id)
    print("transitions", len(transitions))
    print("feasible", evaluation.is_feasible)
    print("metric-keys", ",".join(sorted(evaluation.as_dict())))


if __name__ == "__main__":
    main()
