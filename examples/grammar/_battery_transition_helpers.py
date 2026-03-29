"""Helpers for hand-stepping vector-style battery grammar examples."""

from __future__ import annotations

from typing import Any


def apply_first_transition(problem: Any, state: tuple[float, ...], rule_name: str) -> tuple[float, ...]:
    """Return the next state for the first transition matching ``rule_name``."""

    for transition in problem.enumerate_transitions(state):
        if transition.rule_name == rule_name:
            return transition.next_state
    raise RuntimeError(f"No transition named {rule_name!r} was available from the current state.")
