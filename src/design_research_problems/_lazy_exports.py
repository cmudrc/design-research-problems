"""Helpers for lazily resolved public exports."""

from __future__ import annotations

from importlib import import_module
from typing import Final


def resolve_lazy_export(
    module_name: str,
    exports: dict[str, str],
    export_name: str,
    namespace: dict[str, object],
) -> object:
    """Resolve and cache one lazy export.

    Args:
        module_name: Importable module name owning the lazy exports.
        exports: Mapping of public symbol names to ``module:attribute`` targets.
        export_name: Public symbol name being requested.
        namespace: Mutable module globals dictionary used for caching.

    Returns:
        Resolved export object.

    Raises:
        AttributeError: If the symbol is unknown or maps to an invalid target.
    """
    if export_name not in exports:
        raise AttributeError(f"module {module_name!r} has no attribute {export_name!r}")

    target = exports[export_name]
    module_path, _, attr_name = target.partition(":")
    if not module_path or not attr_name:
        raise AttributeError(f"Invalid lazy export target for {export_name!r}: {target!r}")

    value = getattr(import_module(module_path), attr_name)
    namespace[export_name] = value
    return value


def module_dir(namespace: dict[str, object], exports: list[str]) -> list[str]:
    """Return a sorted combined directory listing.

    Args:
        namespace: Module globals dictionary.
        exports: Public export names that should appear in interactive discovery.

    Returns:
        Sorted attribute names.
    """
    names: Final[set[str]] = set(namespace).union(exports)
    return sorted(names)
