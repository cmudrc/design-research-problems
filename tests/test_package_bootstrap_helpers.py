from __future__ import annotations

import importlib.metadata
import runpy
from pathlib import Path

import design_research_problems
import pytest

from design_research_problems._lazy_exports import module_dir, resolve_lazy_export


def test_package_helpers_cover_lazy_exports_and_dir_listing() -> None:
    namespace: dict[str, object] = {}

    resolved = resolve_lazy_export(
        module_name="design_research_problems",
        exports={"Counter": "collections:Counter"},
        export_name="Counter",
        namespace=namespace,
    )

    assert resolved.__name__ == "Counter"
    assert namespace["Counter"] is resolved
    assert "Problem" in design_research_problems.__dir__()
    assert module_dir({"alpha": 1}, ["beta"]) == ["alpha", "beta"]

    with pytest.raises(AttributeError, match="Invalid lazy export target"):
        resolve_lazy_export(
            module_name="design_research_problems",
            exports={"broken": "collections"},
            export_name="broken",
            namespace={},
        )


def test_package_version_falls_back_when_distribution_metadata_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = Path(design_research_problems.__file__).resolve()

    def _missing_version(_: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(importlib.metadata, "version", _missing_version)

    namespace = runpy.run_path(str(module_path))

    assert namespace["__version__"] == "0+unknown"


def test_gui_main_module_invokes_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        "design_research_problems.gui._launcher.main",
        lambda: called.append("launched"),
    )

    runpy.run_module("design_research_problems.gui.__main__", run_name="__main__")

    assert called == ["launched"]
