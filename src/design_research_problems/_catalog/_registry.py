"""Problem registry facade."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import cast

from design_research_problems._catalog._loader import load_problem_manifests, load_statement_text
from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems import (
    DecisionProblem,
    GrammarProblem,
    OptimizationProblem,
    ProblemKind,
    TextProblem,
)
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemMetadata


def _resolve_object(import_path: str) -> object:
    """Import one ``module:attribute`` object reference.

    Args:
        import_path: Import target in ``module:attribute`` form.

    Returns:
        Imported Python object.

    Raises:
        design_research_problems.ProblemEvaluationError: If the import path is malformed.
    """
    module_path, _, attr_name = import_path.partition(":")
    if not module_path or not attr_name:
        raise ProblemEvaluationError(f"Invalid implementation path: {import_path!r}")
    return getattr(import_module(module_path), attr_name)


ProblemInstance = TextProblem | DecisionProblem | OptimizationProblem | GrammarProblem


class ProblemRegistry:
    """Lazy-loading registry for the packaged problem catalog."""

    def __init__(self) -> None:
        """Initialize an empty lazy registry cache."""
        self._manifests: dict[str, ProblemManifest] | None = None

    def _catalog(self) -> dict[str, ProblemManifest]:
        """Return the cached manifest catalog.

        Returns:
            Mapping of problem IDs to parsed manifests.
        """
        if self._manifests is None:
            self._manifests = load_problem_manifests()
        return self._manifests

    def list(self) -> tuple[ProblemMetadata, ...]:
        """Return all problem metadata in ID-sorted order.

        Returns:
            Metadata entries sorted by problem ID.
        """
        return tuple(self._catalog()[problem_id].metadata for problem_id in sorted(self._catalog()))

    def by_kind(self, kind: ProblemKind) -> tuple[ProblemMetadata, ...]:
        """Return metadata entries with the requested kind.

        Args:
            kind: Problem family to filter for.

        Returns:
            Matching metadata entries.
        """
        return tuple(metadata for metadata in self.list() if metadata.kind is kind)

    def feature_flags(self, problem_id: str) -> tuple[str, ...]:
        """Return the feature flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Feature flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.feature_flags

    def capabilities(self, problem_id: str) -> tuple[str, ...]:
        """Return the normalized capability flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Capability flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.capabilities

    def study_suitability(self, problem_id: str) -> tuple[str, ...]:
        """Return the normalized study-suitability flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Study-suitability flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.study_suitability

    def kind_feature_flags(self) -> dict[ProblemKind, tuple[str, ...]]:
        """Return aggregated feature flags for each problem family.

        Returns:
            Mapping of problem kinds to the union of feature flags across that family.
        """
        grouped: dict[ProblemKind, set[str]] = {kind: set() for kind in ProblemKind}
        for metadata in self.list():
            grouped[metadata.kind].update(metadata.feature_flags)
        return {kind: tuple(sorted(grouped[kind])) for kind in ProblemKind}

    def search(
        self,
        tags: tuple[str, ...] = (),
        text: str = "",
        feature_flags: tuple[str, ...] = (),
        kind: ProblemKind | None = None,
        capabilities: tuple[str, ...] = (),
        study_suitability: tuple[str, ...] = (),
    ) -> tuple[ProblemMetadata, ...]:
        """Search metadata by tags and free text.

        Args:
            tags: Tags that must all be present on a matching entry.
            text: Case-insensitive free-text search term.
            feature_flags: Feature flags that must all be present on a matching entry.
            kind: Optional problem-family filter.
            capabilities: Capability flags that must all be present.
            study_suitability: Study-suitability flags that must all be present.

        Returns:
            Matching metadata entries.
        """
        tag_set = {tag.lower() for tag in tags}
        feature_flag_set = {flag.strip().lower().replace(" ", "-") for flag in feature_flags}
        capability_set = {flag.strip().lower().replace(" ", "-") for flag in capabilities}
        suitability_set = {flag.strip().lower().replace(" ", "-") for flag in study_suitability}
        text_query = text.strip().lower()
        matches: list[ProblemMetadata] = []
        for metadata in self.list():
            if kind is not None and metadata.kind is not kind:
                continue
            if tag_set and not tag_set.issubset({tag.lower() for tag in metadata.taxonomy.tags}):
                continue
            if feature_flag_set and not feature_flag_set.issubset(set(metadata.feature_flags)):
                continue
            if capability_set and not capability_set.issubset(set(metadata.capabilities)):
                continue
            if suitability_set and not suitability_set.issubset(set(metadata.study_suitability)):
                continue
            haystack = " ".join(
                (metadata.problem_id, metadata.title, metadata.summary, *metadata.taxonomy.tags)
            ).lower()
            if text_query and text_query not in haystack:
                continue
            matches.append(metadata)
        return tuple(matches)

    def get(self, problem_id: str) -> ProblemInstance:
        """Instantiate one problem by ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Loaded problem instance.

        Raises:
            KeyError: If the ID is unknown.
            design_research_problems.ProblemEvaluationError: If the packaged implementation metadata is invalid.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")

        statement_markdown = load_statement_text(manifest)
        implementation = manifest.metadata.implementation
        if implementation is not None:
            target = _resolve_object(implementation)
            factory = getattr(target, "from_manifest", None)
            if callable(factory):
                manifest_factory = cast(Callable[[ProblemManifest, str], ProblemInstance], factory)
                return manifest_factory(manifest, statement_markdown)

            if callable(target):
                direct_factory = cast(Callable[[object, str], ProblemInstance], target)
                return direct_factory(manifest.metadata, statement_markdown)

            raise ProblemEvaluationError(f"Problem implementation for {problem_id!r} is not callable.")

        if manifest.metadata.kind is ProblemKind.TEXT:
            return TextProblem(
                metadata=manifest.metadata,
                statement_markdown=statement_markdown,
                assets=manifest.metadata.assets,
                resource_bundle=PackageResourceBundle("design_research_problems", manifest.resource_dir),
            )
        if manifest.metadata.kind is ProblemKind.DECISION:
            return DecisionProblem(
                metadata=manifest.metadata,
                statement_markdown=statement_markdown,
                assets=manifest.metadata.assets,
                resource_bundle=PackageResourceBundle("design_research_problems", manifest.resource_dir),
                parameters=manifest.parameters,
            )
        raise ProblemEvaluationError(f"Problem {problem_id!r} is missing an implementation path.")


_DEFAULT_REGISTRY = ProblemRegistry()


def list_problems() -> tuple[str, ...]:
    """Return all packaged problem IDs.

    Returns:
        Stable problem IDs in sorted order.
    """
    return tuple(metadata.problem_id for metadata in _DEFAULT_REGISTRY.list())


def get_problem(problem_id: str) -> TextProblem | DecisionProblem | OptimizationProblem | GrammarProblem:
    """Return one problem instance by ID.

    Args:
        problem_id: Stable catalog identifier.

    Returns:
        Loaded problem instance.
    """
    return _DEFAULT_REGISTRY.get(problem_id)
