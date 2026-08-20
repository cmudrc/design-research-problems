#!/usr/bin/env python3
"""Generate per-example Sphinx pages from top-of-file example docstrings."""

from __future__ import annotations

import argparse
import ast
import re
from dataclasses import dataclass
from pathlib import Path

REQUIRED_SECTIONS = (
    "Introduction",
    "Technical Implementation",
    "Expected Results",
)

OPTIONAL_SECTIONS = ("References",)

ALL_SUPPORTED_SECTIONS = REQUIRED_SECTIONS + OPTIONAL_SECTIONS

CATEGORY_ORDER = (
    "catalog",
    "decision",
    "grammar",
    "gui",
    "mcp",
    "optimization",
    "text",
)

CATEGORY_TITLES = {
    "catalog": "Catalog Examples",
    "decision": "Decision Examples",
    "grammar": "Grammar Examples",
    "gui": "GUI Examples",
    "mcp": "MCP Examples",
    "optimization": "Optimization Examples",
    "text": "Text Examples",
    "root": "Core Examples",
}

TITLE_TOKEN_OVERRIDES = {
    "api": "API",
    "cad": "CAD",
    "csv": "CSV",
    "gui": "GUI",
    "iot": "IoT",
    "json": "JSON",
    "mcp": "MCP",
    "mseval": "MSEval",
    "pybamm": "PyBaMM",
    "tk": "Tk",
}


@dataclass(slots=True, frozen=True)
class ExampleDocSpec:
    """One runnable example and parsed docs content."""

    rel_path: str
    category: str
    slug: str
    title: str
    source_start_line: int
    sections: dict[str, str]


def _repo_root() -> Path:
    """Return repository root path."""
    return Path(__file__).resolve().parents[1]


def _discover_runnable_examples(repo_root: Path) -> list[Path]:
    """Discover runnable Python examples under ``examples/``."""
    examples_root = repo_root / "examples"
    discovered: list[Path] = []
    for path in sorted(examples_root.rglob("*.py")):
        rel_parts = path.relative_to(examples_root).parts
        if "__pycache__" in rel_parts:
            continue
        if path.name.startswith("_"):
            continue
        discovered.append(path)
    return discovered


def _parse_python_doc_text(path: Path) -> tuple[str, int]:
    """Parse module docstring text and source start line from one Python example."""
    source = path.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(path))
    docstring = ast.get_docstring(module, clean=False)
    if not isinstance(docstring, str) or not docstring.strip():
        raise ValueError(f"{path}: missing module docstring.")

    source_start_line = 1
    if module.body:
        first = module.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and isinstance(first.end_lineno, int)
        ):
            source_start_line = first.end_lineno + 1

    lines = source.splitlines()
    while source_start_line <= len(lines) and not lines[source_start_line - 1].strip():
        source_start_line += 1

    return docstring, source_start_line


def _extract_title_from_docstring(doc_text: str) -> str | None:
    """Return explicit title from markdown-style ``#`` heading when present."""
    for line in doc_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("# "):
            title = stripped[2:].strip().rstrip(".")
            return title or None
        return None
    return None


def _strip_title_line(doc_text: str) -> str:
    """Drop a leading markdown-style ``#`` title line from one docstring."""
    lines = doc_text.splitlines()
    dropped = False
    kept: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not dropped:
            if not stripped:
                continue
            if stripped.startswith("# "):
                dropped = True
                continue
            dropped = True
        kept.append(line)

    return "\n".join(kept).strip()


def _parse_canonical_sections(*, doc_text: str, source_path: Path) -> dict[str, str]:
    """Parse markdown ``##`` canonical sections from one module docstring."""
    heading_pattern = re.compile(r"^##\s+(.+?)\s*$")
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    saw_supported_heading = False

    for raw_line in _strip_title_line(doc_text).splitlines():
        line = raw_line.rstrip()
        match = heading_pattern.match(line.strip())
        if match is not None:
            heading = match.group(1).strip()
            if heading in ALL_SUPPORTED_SECTIONS:
                saw_supported_heading = True
                current_section = heading
                sections[current_section] = []
            else:
                current_section = None
            continue
        if current_section is not None:
            sections[current_section].append(line)

    if not saw_supported_heading:
        return {}

    missing = [section for section in REQUIRED_SECTIONS if section not in sections]
    if missing:
        raise ValueError(f"{source_path}: missing canonical section(s): {missing}")

    return {name: "\n".join(sections[name]).strip() for name in sections}


def _derive_sections_from_docstring(doc_text: str) -> dict[str, str]:
    """Build fallback sections when canonical ``##`` sections are absent."""
    introduction = _strip_title_line(doc_text).strip()
    if not introduction:
        introduction = "This example page is generated directly from the module docstring."

    technical = (
        "This page is generated from the top-of-file module docstring and the example source code. "
        "The full script is included below for direct inspection."
    )
    expected = (
        "Run the command shown above from repository root. Output should summarize the problem setup, "
        "a baseline solution, or diagnostic values relevant to this example."
    )

    return {
        "Introduction": introduction,
        "Technical Implementation": technical,
        "Expected Results": expected,
    }


def _slug_for_example(*, rel_parts: tuple[str, ...]) -> str:
    """Build deterministic docs slug for one example path."""
    if len(rel_parts) <= 1:
        subpath_without_ext = Path(rel_parts[-1]).with_suffix("").as_posix()
    else:
        subpath_without_ext = Path(*rel_parts[1:]).with_suffix("").as_posix()
    slug = subpath_without_ext.replace("/", "_").replace("-", "_")
    if not slug:
        slug = Path(rel_parts[-1]).stem
    return slug


def _title_for_example(*, rel_parts: tuple[str, ...], explicit_title: str | None) -> str:
    """Build human-readable page title for one example path."""
    if explicit_title:
        return explicit_title

    if len(rel_parts) <= 1:
        subpath_without_ext = Path(rel_parts[-1]).with_suffix("").as_posix()
    else:
        subpath_without_ext = Path(*rel_parts[1:]).with_suffix("").as_posix()

    label = subpath_without_ext.replace("/", " / ").replace("_", " ").replace("-", " ")
    title_parts: list[str] = []
    for token in label.split(" "):
        if token == "/":
            title_parts.append(token)
            continue
        normalized = token.strip().lower()
        if not normalized:
            continue
        title_parts.append(TITLE_TOKEN_OVERRIDES.get(normalized, normalized.capitalize()))
    return " ".join(title_parts)


def _extract_mermaid(technical_section: str) -> str | None:
    """Extract Mermaid diagram text from one technical section when present."""
    lines = technical_section.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "```mermaid":
            start = index + 1
            break

    if start is None:
        return None

    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].strip() == "```":
            end = index
            break

    mermaid_text = "\n".join(lines[start:end]).strip()
    return mermaid_text or None


def _strip_mermaid_block(technical_section: str) -> str:
    """Return technical section text without Mermaid fenced block."""
    lines = technical_section.splitlines()
    start = None
    end = None
    for index, line in enumerate(lines):
        if line.strip().lower() == "```mermaid":
            start = index
            break
    if start is None:
        return technical_section.strip()

    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "```":
            end = index
            break
    if end is None:
        end = len(lines) - 1

    stripped_lines = lines[:start] + lines[end + 1 :]
    return "\n".join(stripped_lines).strip()


def _strip_expected_results_run_preface(expected_results: str) -> str:
    """Remove legacy run-command preface from Expected Results text."""
    lines = expected_results.splitlines()
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index >= len(lines) or lines[index].strip().lower() != "run:":
        return expected_results.strip()

    index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    if index < len(lines):
        stripped = lines[index].strip()
        if stripped.startswith("- ") or stripped.startswith("* "):
            index += 1
    while index < len(lines) and not lines[index].strip():
        index += 1
    return "\n".join(lines[index:]).strip()


def _normalize_code_block_indentation(body: str) -> str:
    """Ensure code-block bodies remain indented when embedded text spans lines."""
    lines = body.splitlines()
    normalized: list[str] = []
    in_code_block = False
    saw_content_line = False

    for line in lines:
        stripped = line.strip()
        if not in_code_block and stripped.startswith(".. code-block::"):
            in_code_block = True
            saw_content_line = False
            normalized.append(line)
            continue

        if in_code_block:
            if not saw_content_line:
                normalized.append(line)
                if stripped:
                    saw_content_line = True
                continue
            if line.startswith("   ") or not stripped:
                normalized.append(line)
            else:
                normalized.append(f"   {line}")
            continue

        normalized.append(line)

    return "\n".join(normalized).strip()


def _render_optional_section(*, heading: str, body: str | None, prelude: list[str] | None = None) -> list[str]:
    """Render one optional RST section block."""
    normalized = (body or "").strip()
    if not normalized and not prelude:
        return []

    lines = [
        heading,
        "-" * len(heading),
        "",
    ]
    if prelude:
        lines.extend(prelude)
    if normalized:
        lines.extend(
            [
                normalized,
                "",
            ]
        )
    elif lines[-1] != "":
        lines.append("")

    return lines


def _render_example_page(spec: ExampleDocSpec) -> str:
    """Render one example page as RST."""
    run_command = f"PYTHONPATH=src python {spec.rel_path}"
    include_path = f"../../../{spec.rel_path}"

    introduction = spec.sections["Introduction"]
    technical_implementation = spec.sections["Technical Implementation"]
    expected_results = _normalize_code_block_indentation(
        _strip_expected_results_run_preface(spec.sections["Expected Results"])
    )
    references = spec.sections.get("References")

    mermaid = _extract_mermaid(technical_implementation)
    technical_text = _strip_mermaid_block(technical_implementation)

    lines = [
        spec.title,
        "=" * len(spec.title),
        "",
        f"Source: ``{spec.rel_path}``",
        "",
        "Introduction",
        "------------",
        "",
        introduction,
        "",
        "Technical Implementation",
        "------------------------",
        "",
    ]

    if technical_text:
        lines.extend(
            [
                technical_text,
                "",
            ]
        )

    if mermaid:
        lines.extend(
            [
                ".. mermaid::",
                "",
                *[f"   {line}" for line in mermaid.splitlines()],
                "",
            ]
        )

    lines.extend(
        [
            f".. literalinclude:: {include_path}",
            "   :language: python",
            f"   :lines: {spec.source_start_line}-",
            "   :linenos:",
            "",
        ]
    )

    expected_prelude = [
        ".. rubric:: Run Command",
        "",
        ".. code-block:: bash",
        "",
        f"   {run_command}",
        "",
    ]
    lines.extend(
        _render_optional_section(
            heading="Expected Results",
            body=expected_results,
            prelude=expected_prelude,
        )
    )
    lines.extend(_render_optional_section(heading="References", body=references))
    return "\n".join(lines)


def _category_title(category: str) -> str:
    """Return one display title for a category key."""
    if category in CATEGORY_TITLES:
        return CATEGORY_TITLES[category]
    return category.replace("_", " ").title() + " Examples"


def _ordered_categories(specs: list[ExampleDocSpec]) -> list[str]:
    """Return deterministic category ordering for generated indexes."""
    used = {spec.category for spec in specs}
    ordered = [category for category in CATEGORY_ORDER if category in used]
    extras = sorted(category for category in used if category not in CATEGORY_ORDER)
    return ordered + extras


def _render_category_index(*, category: str, entries: list[ExampleDocSpec]) -> str:
    """Render one category index page as RST."""
    title = _category_title(category)
    lines: list[str] = [
        title,
        "=" * len(title),
        "",
        f"Generated from top-of-file example docstrings in ``examples/{category}``.",
        "",
        ".. toctree::",
        "   :maxdepth: 1",
        "",
    ]
    for entry in entries:
        lines.append(f"   {entry.slug}")
    lines.append("")
    return "\n".join(lines)


def _render_examples_index(categories: list[str]) -> str:
    """Render top-level examples index page as RST."""
    title = "Examples"
    lines = [
        title,
        "=" * len(title),
        "",
        "The examples in this repository are runnable research-oriented scripts. They are",
        "designed to show not only API usage, but how the library fits into realistic",
        "experimental workflows. The featured examples below list dependencies,",
        "expected scope, and the primary concept they demonstrate.",
        "",
        "Featured Examples",
        "-----------------",
        "",
        "Peanut Sheller Packet",
        "~~~~~~~~~~~~~~~~~~~~~",
        "",
        "Load and render a citation-linked ideation prompt packet.",
        "",
        "**Requires:** base install",
        "**Runtime:** short",
        "**Teaches:** text-problem loading, prompt rendering, metadata inspection",
        "",
        "Laptop Design Decision",
        "~~~~~~~~~~~~~~~~~~~~~~",
        "",
        "Evaluate a structured decision task with explicit criteria.",
        "",
        "**Requires:** base install",
        "**Runtime:** short",
        "**Teaches:** decision problem contracts, evaluator output interpretation",
        "",
        "Pill Problem Optimization",
        "~~~~~~~~~~~~~~~~~~~~~~~~~",
        "",
        "Solve a constrained optimization benchmark from the packaged catalog.",
        "",
        "**Requires:** base install",
        "**Runtime:** short",
        "**Teaches:** optimization interfaces, feasibility checks, objective interpretation",
        "",
        "Planar Truss Span Grammar",
        "~~~~~~~~~~~~~~~~~~~~~~~~~",
        "",
        "Step through a constructive grammar-based truss design task.",
        "",
        "**Requires:** ``grammar``",
        "**Runtime:** short to medium",
        "**Teaches:** state transitions, action enumeration, grammar workflow structure",
        "",
        "Build123d Parametric Mounting Bracket",
        "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~",
        "",
        "Run an MCP-backed CAD-style task with external execution.",
        "",
        "**Requires:** ``mcp,cad``",
        "**Runtime:** medium",
        "**Teaches:** MCP task wrapping, external backend interaction, CAD workflow integration",
        "",
        "Full Catalog",
        "------------",
        "",
        ".. toctree::",
        "   :maxdepth: 2",
        "",
    ]
    lines.extend(f"   {category}/index" for category in categories)
    lines.append("")
    return "\n".join(lines)


def _build_specs(repo_root: Path) -> list[ExampleDocSpec]:
    """Build parsed docs specs for runnable examples."""
    specs: list[ExampleDocSpec] = []

    for path in _discover_runnable_examples(repo_root):
        rel_path = path.relative_to(repo_root).as_posix()
        rel_parts = path.relative_to(repo_root / "examples").parts
        category = rel_parts[0] if len(rel_parts) > 1 else "root"

        doc_text, source_start_line = _parse_python_doc_text(path)
        explicit_title = _extract_title_from_docstring(doc_text)

        canonical_sections = _parse_canonical_sections(doc_text=doc_text, source_path=path)
        sections = canonical_sections or _derive_sections_from_docstring(doc_text)

        specs.append(
            ExampleDocSpec(
                rel_path=rel_path,
                category=category,
                slug=_slug_for_example(rel_parts=rel_parts),
                title=_title_for_example(rel_parts=rel_parts, explicit_title=explicit_title),
                source_start_line=source_start_line,
                sections=sections,
            )
        )

    categories = _ordered_categories(specs)
    return sorted(specs, key=lambda item: (categories.index(item.category), item.rel_path))


def _sync_file(*, path: Path, content: str, check: bool, stale: list[str]) -> None:
    """Write one generated file or record drift in check mode."""
    desired = content.rstrip() + "\n"
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == desired:
            return

    if check:
        stale.append(path.as_posix())
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(desired, encoding="utf-8")


def _sync_stale_pages(*, generated_pages: set[Path], docs_examples_root: Path, check: bool, stale: list[str]) -> None:
    """Remove stale generated pages or report drift in check mode."""
    if not docs_examples_root.exists():
        return

    for category_dir in sorted(path for path in docs_examples_root.iterdir() if path.is_dir()):
        for existing in sorted(category_dir.glob("*.rst")):
            if existing in generated_pages:
                continue
            if check:
                stale.append(existing.as_posix())
            else:
                existing.unlink()
        if not check and not any(category_dir.iterdir()):
            category_dir.rmdir()


def generate(*, repo_root: Path, check: bool) -> int:
    """Generate docs pages or validate generated pages are up to date."""
    specs = _build_specs(repo_root)
    categories = _ordered_categories(specs)
    docs_examples_root = repo_root / "docs" / "examples"

    stale: list[str] = []
    generated_pages: set[Path] = set()

    _sync_file(
        path=docs_examples_root / "index.rst",
        content=_render_examples_index(categories),
        check=check,
        stale=stale,
    )

    for category in categories:
        entries = [item for item in specs if item.category == category]
        if not entries:
            continue

        category_index_path = docs_examples_root / category / "index.rst"
        generated_pages.add(category_index_path)
        _sync_file(
            path=category_index_path,
            content=_render_category_index(category=category, entries=entries),
            check=check,
            stale=stale,
        )

        for entry in entries:
            page_path = docs_examples_root / category / f"{entry.slug}.rst"
            generated_pages.add(page_path)
            _sync_file(
                path=page_path,
                content=_render_example_page(entry),
                check=check,
                stale=stale,
            )

    _sync_stale_pages(generated_pages=generated_pages, docs_examples_root=docs_examples_root, check=check, stale=stale)

    if stale:
        print("Example docs are out of date:")
        for path in sorted(stale):
            print(f"- {path}")
        return 1

    if check:
        print("Example docs are up to date.")
    else:
        print("Generated example docs.")
    return 0


def main() -> int:
    """CLI entrypoint for example docs generation/check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate generated docs are up to date.")
    args = parser.parse_args()
    return generate(repo_root=_repo_root(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
