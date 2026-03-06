from __future__ import annotations

import pytest

from design_research_problems.problems._domains import build123d_cad


def test_validate_build123d_script_rejects_non_whitelisted_import() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        build123d_cad._validate_build123d_script("import os\nresult = None")


def test_validate_build123d_script_rejects_dunder_attribute_access() -> None:
    with pytest.raises(ValueError, match="Dunder attribute access"):
        build123d_cad._validate_build123d_script("x = (1).__class__\nresult = x")


def test_validate_build123d_script_rejects_exec_family_calls() -> None:
    with pytest.raises(ValueError, match=r"Call to 'exec' is not allowed"):
        build123d_cad._validate_build123d_script("exec('print(1)')\nresult = None")


def test_validate_build123d_script_allows_build123d_and_math_imports() -> None:
    build123d_cad._validate_build123d_script("from build123d import Box\nimport math\n_ = math.sqrt(4)\nresult = Box")


def test_safe_script_import_rejects_relative_or_disallowed_modules() -> None:
    with pytest.raises(ImportError, match="Relative imports are not allowed"):
        build123d_cad._safe_script_import("build123d", level=1)
    with pytest.raises(ImportError, match="Allowed imports"):
        build123d_cad._safe_script_import("os")
