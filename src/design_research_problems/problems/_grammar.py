"""Base class for grammar-driven discrete problems."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._computable import ComputableProblem
from design_research_problems.problems._mcp import (
    create_fastmcp_server,
    register_design_brief_resource,
    to_json_value,
)
from design_research_problems.problems._metadata import ProblemMetadata

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


@dataclass(frozen=True)
class GrammarTransition[StateT]:
    """One deterministic grammar transition produced by a concrete rule method."""

    rule_name: str
    """Concrete public method name used to produce the transition."""
    parameters: tuple[tuple[str, object], ...]
    """Ordered keyword arguments that fully specify the rule call."""
    next_state: StateT
    """State returned by applying the rule."""


class GrammarProblem[StateT, EvaluationT](ComputableProblem[StateT, EvaluationT], ABC):
    """Abstract base for grammar-defined discrete design problems."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Store shared metadata for one grammar problem.

        Args:
            metadata: Shared packaged metadata for the problem.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )

    @abstractmethod
    def initial_state(self) -> StateT:
        """Return the canonical starting state.

        Returns:
            Library-defined initial design state.
        """

    @abstractmethod
    def enumerate_transitions(self, state: StateT) -> tuple[GrammarTransition[StateT], ...]:
        """Return deterministic legal transitions for the given state.

        Args:
            state: Current grammar state.

        Returns:
            Fully specified legal transitions in deterministic order.
        """

    def enumerate_next_states(self, state: StateT) -> tuple[StateT, ...]:
        """Return the legal successor states for the given state.

        This convenience method supports generic grammar-family tooling that
        only needs the next design states, not the richer transition metadata.

        Args:
            state: Current grammar state.

        Returns:
            Deterministic next states in the same order as
            :meth:`enumerate_transitions`.
        """
        return tuple(transition.next_state for transition in self.enumerate_transitions(state))

    def to_mcp_server(
        self,
        *,
        server_name: str | None = None,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
        include_grammar_helpers: bool = True,
    ) -> FastMCP:
        """Expose this grammar problem through a stateful FastMCP server.

        The server maintains one mutable ``current_state`` per server instance.
        It is intended for one-agent/single-client usage by contract.

        Args:
            server_name: Optional explicit server name.
            include_citation: Whether the design brief includes citations.
            citation_mode: Citation rendering mode for the design brief.
            include_grammar_helpers: Whether to include helper tools
                ``reset_design``, ``get_design``, ``list_transitions``,
                and ``evaluate``.

        Returns:
            Configured FastMCP server.
        """
        server = create_fastmcp_server(self, server_name=server_name)
        register_design_brief_resource(
            server,
            brief_text=self.render_brief(include_citation=include_citation, citation_mode=citation_mode),
        )

        current_state = self.initial_state()

        def get_design() -> dict[str, object]:
            """Return the current grammar design state.

            Returns:
                MCP-ready payload describing the current design state.
            """
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "design": to_json_value(current_state),
            }

        def reset_design() -> dict[str, object]:
            """Reset and return the canonical initial grammar state.

            Returns:
                MCP-ready payload describing the reset design state.
            """
            nonlocal current_state
            current_state = self.initial_state()
            return get_design()

        def list_transitions() -> dict[str, object]:
            """List deterministic legal transitions for the current state.

            Returns:
                MCP-ready payload listing the available transitions.
            """
            transitions = self.enumerate_transitions(current_state)
            serialized = [
                {
                    "rule_name": transition.rule_name,
                    "parameters": {key: to_json_value(value) for key, value in transition.parameters},
                }
                for transition in transitions
            ]
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "transition_count": len(serialized),
                "transitions": serialized,
            }

        def evaluate_tool() -> dict[str, object]:
            """Evaluate and return metrics for the current state.

            Returns:
                MCP-ready evaluation payload for the current design.
            """
            evaluation = self.evaluate(current_state)
            objective_value, higher_is_better, is_feasible = _evaluation_summary_fields(evaluation)
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "design": to_json_value(current_state),
                "evaluation": to_json_value(evaluation),
                "objective_value": objective_value,
                "higher_is_better": higher_is_better,
                "is_feasible": is_feasible,
                **self._mcp_evaluation_extras(current_state),
            }

        def submit_final(justification: str | None = None) -> dict[str, object]:
            """Submit the current state as the final grammar design.

            Returns:
                MCP-ready submission payload for the current design.
            """
            evaluation = self.evaluate(current_state)
            objective_value, higher_is_better, is_feasible = _evaluation_summary_fields(evaluation)
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "design": to_json_value(current_state),
                "evaluation": to_json_value(evaluation),
                "objective_value": objective_value,
                "higher_is_better": higher_is_better,
                "is_feasible": is_feasible,
                "justification": None if justification is None else justification.strip() or None,
                **self._mcp_evaluation_extras(current_state),
            }

        def _set_current_state(state: StateT) -> None:
            """Update the mutable current-state closure.

            Args:
                state: New grammar state to store.
            """
            nonlocal current_state
            current_state = state

        def _get_current_state() -> StateT:
            """Return the mutable current-state closure.

            Returns:
                Current grammar state.
            """
            return current_state

        if include_grammar_helpers:
            server.add_tool(
                reset_design,
                name="reset_design",
                title="Reset Design",
                description="Reset the internal grammar state to the canonical initial design.",
            )
            server.add_tool(
                get_design,
                name="get_design",
                title="Get Design",
                description="Return the current internal grammar design state.",
            )
            server.add_tool(
                list_transitions,
                name="list_transitions",
                title="List Transitions",
                description="List legal transitions from the current grammar state.",
            )
            server.add_tool(
                evaluate_tool,
                name="evaluate",
                title="Evaluate Design",
                description="Evaluate the current internal grammar design state.",
            )

        for rule_name, rule_method in self._mcp_rule_methods():
            rule_tool = self._mcp_rule_tool(
                rule_name=rule_name,
                rule_method=rule_method,
                get_state=_get_current_state,
                set_state=_set_current_state,
            )
            rule_doc = inspect.getdoc(rule_method)
            rule_summary = rule_doc.splitlines()[0].strip() if rule_doc else f"Apply grammar rule '{rule_name}'."
            server.add_tool(
                rule_tool,
                name=rule_name,
                title=rule_name.replace("_", " ").title(),
                description=rule_summary,
            )

        server.add_tool(
            submit_final,
            name="submit_final",
            title="Submit Final Answer",
            description="Submit the current grammar design state as the final answer.",
        )
        return server

    def _mcp_evaluation_extras(self, state: StateT) -> dict[str, object]:
        """Return optional MCP-facing evaluation extras for one grammar state."""
        report: dict[str, object] = {}
        evaluation_provenance = getattr(self, "evaluation_provenance", None)
        if callable(evaluation_provenance):
            report["evaluation_provenance"] = to_json_value(evaluation_provenance(state))
        return report

    @abstractmethod
    def evaluate(self, state: StateT) -> EvaluationT:
        """Evaluate one design state.

        Args:
            state: Grammar state to evaluate.

        Returns:
            Problem-specific evaluation result.
        """

    def _mcp_rule_methods(self) -> tuple[tuple[str, Callable[..., StateT]], ...]:
        """Return public grammar-rule callables suitable for MCP exposure.

        Returns:
            Sorted ``(rule_name, bound_method)`` pairs.
        """
        methods: list[tuple[str, Callable[..., StateT]]] = []
        for name, _method in inspect.getmembers(type(self), predicate=inspect.isfunction):
            if name.startswith("_"):
                continue
            if name in {
                "from_manifest",
                "initial_state",
                "enumerate_transitions",
                "enumerate_next_states",
                "evaluate",
                "to_mcp_server",
            }:
                continue
            bound_method = getattr(self, name)
            signature = inspect.signature(bound_method)
            parameters = list(signature.parameters.values())
            if not parameters or parameters[0].name != "state":
                continue
            if not _annotation_tokens_match(parameters[0].annotation, signature.return_annotation):
                continue
            methods.append((name, bound_method))
        methods.sort(key=lambda item: item[0])
        return tuple(methods)

    def _mcp_rule_tool(
        self,
        *,
        rule_name: str,
        rule_method: Callable[..., StateT],
        get_state: Callable[[], StateT],
        set_state: Callable[[StateT], None],
    ) -> Callable[..., dict[str, object]]:
        """Build one MCP tool wrapper around a grammar-rule method.

        Args:
            rule_name: Exposed MCP tool name.
            rule_method: Bound grammar-rule callable.
            get_state: Callable returning the current mutable grammar state.
            set_state: Callable updating the current mutable grammar state.

        Returns:
            Tool function with an MCP-friendly argument signature.
        """
        original_signature = inspect.signature(rule_method)
        original_parameters = list(original_signature.parameters.values())[1:]
        tool_parameters = []
        for parameter in original_parameters:
            kind = parameter.kind
            if kind in {inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD}:
                kind = inspect.Parameter.KEYWORD_ONLY
            tool_parameters.append(parameter.replace(kind=kind))
        tool_signature = inspect.Signature(parameters=tool_parameters, return_annotation=dict[str, object])

        def rule_tool(**kwargs: object) -> dict[str, object]:
            """Apply the wrapped grammar rule and update the current state.

            Args:
                **kwargs: Keyword arguments forwarded to the grammar rule.

            Returns:
                MCP-ready payload describing the updated design.
            """
            next_state = rule_method(get_state(), **kwargs)
            set_state(next_state)
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "rule_name": rule_name,
                "design": to_json_value(next_state),
            }

        rule_tool.__name__ = rule_name
        rule_tool.__signature__ = tool_signature  # type: ignore[attr-defined]
        return rule_tool


def _annotation_tokens_match(left: object, right: object) -> bool:
    """Return whether two annotation values describe the same nominal type.

    Args:
        left: First annotation token.
        right: Second annotation token.

    Returns:
        ``True`` when both annotations normalize to the same token.
    """
    left_token = _annotation_token(left)
    right_token = _annotation_token(right)
    if not left_token or not right_token:
        return False
    return left_token == right_token


def _annotation_token(annotation: object) -> str:
    """Normalize one annotation value to a lightweight comparable token.

    Args:
        annotation: Annotation value from ``inspect``.

    Returns:
        Normalized token string.
    """
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        return annotation.strip().replace(" ", "")
    name = getattr(annotation, "__name__", "")
    if name:
        return name.strip().replace(" ", "")
    return str(annotation).strip().replace(" ", "")


def _evaluation_summary_fields(evaluation: object) -> tuple[float, bool, bool]:
    """Extract canonical objective and feasibility fields from one evaluation object.

    Args:
        evaluation: Family-specific evaluation payload.

    Returns:
        ``(objective_value, higher_is_better, is_feasible)`` tuple.
    """
    is_feasible = bool(getattr(evaluation, "is_feasible", True))

    objective_value = getattr(evaluation, "objective_value", None)
    if isinstance(objective_value, int | float):
        higher_is_better = bool(getattr(evaluation, "higher_is_better", False))
        return (float(objective_value), higher_is_better, is_feasible)

    for key, higher in (
        ("total_cost", False),
        ("mass", False),
        ("deflection", False),
        ("peak_temp_c", False),
        ("design_cost", False),
        ("delivered_capacity_ah", True),
        ("fos", True),
        ("min_fos", True),
    ):
        value = getattr(evaluation, key, None)
        if isinstance(value, int | float):
            return (float(value), higher, is_feasible)

    return (0.0, False, is_feasible)


__all__ = ["GrammarProblem", "GrammarTransition"]
