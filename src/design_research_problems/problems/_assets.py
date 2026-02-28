"""Helpers for reading packaged problem assets."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable


@dataclass(frozen=True)
class PackageResourceBundle:
    """Logical package-relative resource directory."""

    package: str
    """Importable package name that owns the resources."""
    resource_dir: str
    """Package-relative directory containing the bundled assets."""

    def _root(self) -> Traversable:
        """Resolve the logical resource directory into a traversable object.

        Returns:
            Traversable package resource directory.
        """
        return files(self.package).joinpath(*self.resource_dir.split("/"))

    def read_text(self, relative_path: str) -> str:
        """Read a UTF-8 text resource.

        Args:
            relative_path: Resource path relative to ``resource_dir``.

        Returns:
            Decoded UTF-8 text content.
        """
        return self._root().joinpath(relative_path).read_text(encoding="utf-8")

    def read_bytes(self, relative_path: str) -> bytes:
        """Read a binary resource.

        Args:
            relative_path: Resource path relative to ``resource_dir``.

        Returns:
            Raw resource bytes.
        """
        return self._root().joinpath(relative_path).read_bytes()
