"""Load packaged problem manifests and resources."""

from __future__ import annotations

import tomllib
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._metadata import (
    KNOWN_PROBLEM_CAPABILITIES,
    KNOWN_STUDY_SUITABILITY,
    Citation,
    ProblemAsset,
    ProblemKind,
    ProblemMetadata,
    ProblemTaxonomy,
)

_PACKAGE = "design_research_problems"
_CATALOG_DIR = "_assets/catalog"


def _catalog_root() -> Traversable:
    """Return the traversable root directory for packaged catalog resources.

    Returns:
        Package resource directory containing all problem entries.
    """
    return files(_PACKAGE).joinpath("_assets", "catalog")


def _resource_root(resource_dir: str) -> Traversable:
    """Return the traversable root directory for one packaged resource path.

    Args:
        resource_dir: Package-relative resource directory.

    Returns:
        Traversable directory for the requested resource path.
    """
    return files(_PACKAGE).joinpath(*resource_dir.split("/"))


def _parse_problem_kind(raw_kind: str) -> ProblemKind:
    """Parse one manifest problem-kind string into the enum.

    Args:
        raw_kind: Raw string from the manifest file.

    Returns:
        Parsed problem kind.

    Raises:
        ValueError: If the manifest contains an unsupported problem kind.
    """
    normalized = raw_kind.strip().lower()
    if normalized == "text":
        return ProblemKind.TEXT
    if normalized == "decision":
        return ProblemKind.DECISION
    if normalized == "optimization":
        return ProblemKind.OPTIMIZATION
    if normalized == "grammar":
        return ProblemKind.GRAMMAR
    if normalized == "mcp":
        return ProblemKind.MCP
    raise ValueError(f"Unsupported problem kind: {raw_kind!r}")


def _parse_citations(raw_data: dict[str, Any], resource_dir: str) -> tuple[Citation, ...]:
    """Build citation objects from one manifest payload.

    Args:
        raw_data: Parsed TOML manifest mapping.
        resource_dir: Package-relative resource directory for the entry.

    Returns:
        Parsed citations in manifest order.
    """
    citations: list[Citation] = []
    for entry in cast(list[dict[str, Any]], raw_data.get("citations", [])):
        raw_text = str(entry.get("raw_text", "")).strip()
        raw_text_file = cast(str | None, entry.get("raw_text_file"))
        if raw_text_file:
            raw_text = _resource_root(resource_dir).joinpath(raw_text_file).read_text(encoding="utf-8")
        authors = tuple(
            str(author).strip() for author in cast(list[object], entry.get("authors", [])) if str(author).strip()
        )
        citations.append(
            Citation(
                key=str(entry["key"]),
                kind=str(entry.get("kind", "inline")),
                authors=authors,
                title=str(entry.get("title", "")),
                year=int(entry["year"]) if "year" in entry else None,
                venue=cast(str | None, entry.get("venue")),
                doi=cast(str | None, entry.get("doi")),
                formatted_text=cast(str | None, entry.get("formatted_text")),
                raw_text=raw_text,
                url=cast(str | None, entry.get("url")),
                provisional=bool(entry.get("provisional", False)),
            )
        )

    return tuple(citations)


def _parse_assets(raw_assets: list[dict[str, Any]]) -> tuple[ProblemAsset, ...]:
    """Build asset metadata objects from raw manifest entries.

    Args:
        raw_assets: Raw asset dictionaries from the manifest.

    Returns:
        Parsed asset metadata tuple.
    """
    return tuple(
        ProblemAsset(
            name=str(entry["name"]),
            media_type=str(entry["media_type"]),
            description=str(entry.get("description", "")),
            resource_path=str(entry["path"]),
        )
        for entry in raw_assets
    )


def _normalize_vocab_values(raw_values: list[object], known_values: frozenset[str]) -> tuple[str, ...]:
    """Build a normalized, deterministic vocabulary tuple.

    Args:
        raw_values: Raw manifest values.
        known_values: Allowed normalized values.

    Returns:
        Sorted unique normalized values.

    Raises:
        ValueError: If an unsupported value is encountered.
    """
    normalized: set[str] = set()
    for raw_value in raw_values:
        value = str(raw_value).strip().lower().replace(" ", "-")
        if not value:
            continue
        if value not in known_values:
            raise ValueError(f"Unsupported catalog value: {value!r}")
        normalized.add(value)
    return tuple(sorted(normalized))


def _parse_taxonomy(raw_taxonomy: dict[str, Any]) -> ProblemTaxonomy:
    """Build the shared taxonomy object from raw manifest data.

    Args:
        raw_taxonomy: Raw taxonomy mapping from the manifest.

    Returns:
        Parsed taxonomy object.
    """
    return ProblemTaxonomy(
        formulation=cast(str | None, raw_taxonomy.get("formulation")),
        convexity=cast(str | None, raw_taxonomy.get("convexity")),
        design_variable_type=cast(str | None, raw_taxonomy.get("design_variable_type")),
        is_dynamic=bool(raw_taxonomy.get("is_dynamic", False)),
        orientation=cast(str | None, raw_taxonomy.get("orientation")),
        feasibility_ratio_hint=raw_taxonomy.get("feasibility_ratio_hint"),
        objective_mode=cast(str | None, raw_taxonomy.get("objective_mode")),
        constraint_nature=cast(str | None, raw_taxonomy.get("constraint_nature")),
        bounds_summary=cast(str | None, raw_taxonomy.get("bounds_summary")),
        tags=tuple(str(tag) for tag in raw_taxonomy.get("tags", [])),
        deliverable_type=cast(str | None, raw_taxonomy.get("deliverable_type")),
        timebox_hint_minutes=cast(int | None, raw_taxonomy.get("timebox_hint_minutes")),
        participants=cast(str | None, raw_taxonomy.get("participants")),
        evaluation_mode=cast(str | None, raw_taxonomy.get("evaluation_mode")),
    )


def _load_single_manifest(entry: Traversable, resource_dir: str) -> ProblemManifest:
    """Load one problem manifest directory.

    Args:
        entry: Traversable directory representing one problem entry.
        resource_dir: Package-relative resource directory for the entry.

    Returns:
        Parsed problem manifest object.
    """
    raw_text = entry.joinpath("problem.toml").read_text(encoding="utf-8")
    raw_data = tomllib.loads(raw_text)
    statement_markdown = str(raw_data["statement"])
    metadata = ProblemMetadata(
        problem_id=str(raw_data["problem_id"]),
        title=str(raw_data["title"]),
        summary=str(raw_data["summary"]),
        kind=_parse_problem_kind(str(raw_data["kind"])),
        taxonomy=_parse_taxonomy(cast(dict[str, Any], raw_data.get("taxonomy", {}))),
        citations=_parse_citations(raw_data, resource_dir),
        assets=_parse_assets(cast(list[dict[str, Any]], raw_data.get("assets", []))),
        capabilities=_normalize_vocab_values(
            cast(list[object], raw_data.get("capabilities", [])),
            KNOWN_PROBLEM_CAPABILITIES,
        ),
        study_suitability=_normalize_vocab_values(
            cast(list[object], raw_data.get("study_suitability", [])),
            KNOWN_STUDY_SUITABILITY,
        ),
        implementation=cast(str | None, raw_data.get("implementation")),
    )
    parameters = cast(dict[str, object], raw_data.get("parameters", {}))
    return ProblemManifest(
        metadata=metadata,
        resource_dir=resource_dir,
        statement_markdown=statement_markdown,
        parameters=parameters,
    )


def _iter_manifest_directories(
    root: Traversable,
    resource_dir: str = _CATALOG_DIR,
) -> tuple[tuple[Traversable, str], ...]:
    """Return all catalog problem directories, including nested ones.

    Args:
        root: Traversable directory to scan recursively.
        resource_dir: Package-relative resource path for ``root``.

    Returns:
        Tuples of manifest directories and their package-relative resource paths.
    """
    entries: list[tuple[Traversable, str]] = []
    for entry in sorted(root.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        entry_resource_dir = f"{resource_dir}/{entry.name}"
        if entry.joinpath("problem.toml").is_file():
            entries.append((entry, entry_resource_dir))
            continue
        entries.extend(_iter_manifest_directories(entry, entry_resource_dir))
    return tuple(entries)


def load_problem_manifests() -> dict[str, ProblemManifest]:
    """Load all packaged problem manifests.

    Returns:
        Mapping of problem IDs to parsed manifests.
    """
    manifests: dict[str, ProblemManifest] = {}
    for entry, resource_dir in _iter_manifest_directories(_catalog_root()):
        manifest = _load_single_manifest(entry, resource_dir)
        existing = manifests.get(manifest.metadata.problem_id)
        if existing is not None:
            raise ValueError(
                "Duplicate problem_id detected in packaged catalog: "
                f"{manifest.metadata.problem_id!r} appears in both "
                f"{existing.resource_dir!r} and {manifest.resource_dir!r}."
            )
        manifests[manifest.metadata.problem_id] = manifest
    return manifests


def load_statement_text(manifest: ProblemManifest) -> str:
    """Load the statement markdown for one problem manifest.

    Args:
        manifest: Parsed manifest describing the packaged resource path.

    Returns:
        UTF-8 Markdown statement text.
    """
    return manifest.statement_markdown
