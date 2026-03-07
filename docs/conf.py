"""Sphinx configuration for the project documentation."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from sphinx.application import Sphinx

autoclass_content = "both"

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

project = "design-research-problems"
copyright = "2026, design-research-problems contributors"
author = "design-research-problems contributors"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinxcontrib.mermaid",
]
if os.environ.get("DRP_DOCS_ENABLE_INTERSPHINX") == "1":
    extensions.append("sphinx.ext.intersphinx")

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_param = True
napoleon_use_rtype = False
autodoc_typehints = "none"
autosummary_generate = True
autosummary_imported_members = True
nitpicky = True
intersphinx_mapping = (
    {
        "python": ("https://docs.python.org/3", None),
    }
    if "sphinx.ext.intersphinx" in extensions
    else {}
)
nitpick_ignore_regex = [("py:class", r"numpy\..+"), ("py:class", r"collections\.abc\..+")]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

if os.environ.get("READTHEDOCS") == "True":
    html_theme = "sphinx_rtd_theme"
else:
    try:
        import sphinx_rtd_theme  # noqa: F401

        html_theme = "sphinx_rtd_theme"
    except ImportError:
        html_theme = "alabaster"

html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_logo = "drc.png"
html_favicon = "_static/favicon.ico"
html_title = project
html_theme_options = {"logo_only": False}

linkcheck_retries = 2
linkcheck_timeout = 10
linkcheck_workers = 10
linkcheck_anchors = False

_VIEWPORT_META_RE = re.compile(r'<meta name="viewport"[^>]*>', re.IGNORECASE)


def _dedupe_viewport_meta(
    app: object,
    pagename: str,
    templatename: str,
    context: dict[str, object],
    doctree: object,
) -> None:
    del app, pagename, templatename, doctree
    metatags = context.get("metatags")
    if isinstance(metatags, str):
        context["metatags"] = _VIEWPORT_META_RE.sub("", metatags)


def setup(app: Sphinx) -> None:
    """Register build-time hooks."""
    app.connect("html-page-context", _dedupe_viewport_meta)
