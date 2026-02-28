"""Load packaged problem manifests and resources."""

from __future__ import annotations

import tomllib
from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Any, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._metadata import (
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
    if normalized == "optimization":
        return ProblemKind.OPTIMIZATION
    if normalized == "grammar":
        return ProblemKind.GRAMMAR
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
    citation_file = raw_data.get("citation_file")
    if isinstance(citation_file, str):
        resource = _resource_root(resource_dir).joinpath(citation_file)
        raw_text = resource.read_text(encoding="utf-8")
        citations.append(
            Citation(
                key=str(raw_data.get("citation_key", "")),
                kind=str(raw_data.get("citation_kind", "bibtex")),
                raw_text=raw_text,
                url=cast(str | None, raw_data.get("citation_url")),
            )
        )

    for entry in cast(list[dict[str, Any]], raw_data.get("citations", [])):
        citations.append(
            Citation(
                key=str(entry["key"]),
                kind=str(entry.get("kind", "inline")),
                raw_text=str(entry["raw_text"]),
                url=cast(str | None, entry.get("url")),
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


def _parse_taxonomy(raw_taxonomy: dict[str, Any]) -> ProblemTaxonomy:
    """Build the shared taxonomy object from raw manifest data.

    Args:
        raw_taxonomy: Raw taxonomy mapping from the manifest.

    Returns:
        Parsed taxonomy object.
    """
    return ProblemTaxonomy(
        formulation=str(raw_taxonomy.get("formulation", "unspecified")),
        convexity=str(raw_taxonomy.get("convexity", "unknown")),
        design_variable_type=str(raw_taxonomy.get("design_variable_type", "unknown")),
        is_dynamic=bool(raw_taxonomy.get("is_dynamic", False)),
        orientation=str(raw_taxonomy.get("orientation", "unknown")),
        feasibility_ratio_hint=raw_taxonomy.get("feasibility_ratio_hint"),
        objective_mode=str(raw_taxonomy.get("objective_mode", "single")),
        constraint_nature=str(raw_taxonomy.get("constraint_nature", "unspecified")),
        bounds_summary=str(raw_taxonomy.get("bounds_summary", "unspecified")),
        tags=tuple(str(tag) for tag in raw_taxonomy.get("tags", [])),
    )


def _load_single_manifest(entry: Any) -> ProblemManifest:
    """Load one problem manifest directory.

    Args:
        entry: Traversable directory representing one problem entry.

    Returns:
        Parsed problem manifest object.
    """
    raw_text = entry.joinpath("problem.toml").read_text(encoding="utf-8")
    raw_data = tomllib.loads(raw_text)
    resource_dir = f"{_CATALOG_DIR}/{entry.name}"
    metadata = ProblemMetadata(
        problem_id=str(raw_data["problem_id"]),
        title=str(raw_data["title"]),
        summary=str(raw_data["summary"]),
        kind=_parse_problem_kind(str(raw_data["kind"])),
        taxonomy=_parse_taxonomy(cast(dict[str, Any], raw_data.get("taxonomy", {}))),
        citations=_parse_citations(raw_data, resource_dir),
        assets=_parse_assets(cast(list[dict[str, Any]], raw_data.get("assets", []))),
        implementation=cast(str | None, raw_data.get("implementation")),
    )
    statement_resource = str(raw_data.get("statement_file", "statement.md"))
    parameters = cast(dict[str, object], raw_data.get("parameters", {}))
    return ProblemManifest(
        metadata=metadata,
        resource_dir=resource_dir,
        statement_resource=statement_resource,
        parameters=parameters,
    )


def load_problem_manifests() -> dict[str, ProblemManifest]:
    """Load all packaged problem manifests.

    Returns:
        Mapping of problem IDs to parsed manifests.
    """
    manifests: dict[str, ProblemManifest] = {}
    for entry in sorted(_catalog_root().iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        manifest = _load_single_manifest(entry)
        manifests[manifest.metadata.problem_id] = manifest
    return manifests


def load_statement_text(manifest: ProblemManifest) -> str:
    """Load the statement markdown for one problem manifest.

    Args:
        manifest: Parsed manifest describing the packaged resource path.

    Returns:
        UTF-8 Markdown statement text.
    """
    return _resource_root(manifest.resource_dir).joinpath(manifest.statement_resource).read_text(encoding="utf-8")
