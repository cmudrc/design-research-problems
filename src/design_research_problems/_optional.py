"""Shared helpers for optional dependency imports and install hints."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

from design_research_problems._exceptions import MissingOptionalDependencyError

_PACKAGE_NAME = "design-research-problems"


def optional_install_hint(*extras: str) -> str:
    """Return a pip-install hint for one or more extras.

    Args:
        *extras: Optional extra names in ``pyproject.toml``.

    Returns:
        Human-readable ``pip install`` command.
    """
    joined = ",".join(extra.strip() for extra in extras if extra.strip())
    if not joined:
        return f"pip install {_PACKAGE_NAME}"
    return f"pip install {_PACKAGE_NAME}[{joined}]"


def import_optional_module(
    module_name: str,
    *,
    required_for: str,
    extras: tuple[str, ...],
    dependency_label: str | None = None,
    make_target: str | None = None,
) -> ModuleType:
    """Import one optional module with a standardized error message.

    Args:
        module_name: Import path to resolve.
        required_for: Short context describing what feature needs the module.
        extras: Package extras that satisfy this dependency.
        dependency_label: Optional user-facing dependency label override.
        make_target: Optional Make target for editable local checkouts.

    Returns:
        Imported module.

    Raises:
        MissingOptionalDependencyError: If the module import fails.
    """
    try:
        return import_module(module_name)
    except ImportError as exc:
        label = dependency_label or module_name.split(".")[0]
        message = f"{label} is required for {required_for}. Install it with: {optional_install_hint(*extras)}"
        if make_target:
            message += f" or run: make {make_target}"
        raise MissingOptionalDependencyError(message) from exc


__all__ = ["import_optional_module", "optional_install_hint"]
