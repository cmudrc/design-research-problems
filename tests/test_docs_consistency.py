"""Tests for source-backed documentation consistency checks."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_checker() -> ModuleType:
    """Load the checker directly from its script path."""
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_consistency.py"
    spec = importlib.util.spec_from_file_location("check_docs_consistency", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_reference_guard_scans_nested_pages_and_all_autodoc_kinds(monkeypatch, tmp_path: Path) -> None:
    """Nested private class/function paths must not leak into public reference docs."""
    checker = _load_checker()
    reference_path = tmp_path / "docs" / "reference" / "nested" / "private.rst"
    reference_path.parent.mkdir(parents=True)
    reference_path.write_text(
        """\
.. autoclass:: design_research_problems.problems._metadata.ProblemKind
.. autofunction:: design_research_problems._catalog._registry.get_problem
.. autodecorator:: design_research_problems._internal.register
.. autoproperty:: design_research_problems.PublicType._private_value
.. automodule:: design_research_problems.problems
""",
        encoding="utf-8",
    )
    monkeypatch.setattr(checker, "ROOT", tmp_path)

    errors = checker._check_private_reference_boundaries()

    assert len(errors) == 4
    assert "problems._metadata.ProblemKind" in errors[0]
    assert "_catalog._registry.get_problem" in errors[1]
    assert "_internal.register" in errors[2]
    assert "PublicType._private_value" in errors[3]
    assert all("use a public alias" in error for error in errors)
