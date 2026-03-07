"""Generate the docs page that lists the checked-in runnable examples."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "examples" / "index.rst"


def _category_title(category: str) -> str:
    """Render a display title for an example category key.

    Args:
        category: Top-level examples category from the relative path.

    Returns:
        Human-readable category heading.
    """
    return "Core" if category == "root" else category.replace("_", " ").title()


def _render() -> str:
    """Render the examples index page from the example scripts on disk.

    Returns:
        Full reStructuredText content for ``docs/examples/index.rst``.
    """
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(ROOT.glob("examples/**/*.py")):
        relative = path.relative_to(ROOT)
        category = relative.parts[1] if len(relative.parts) >= 3 else "root"
        grouped[category].append(relative)

    lines = [
        "Examples",
        "========",
        "",
        "The example inventory is generated from checked-in scripts.",
        "",
        "Run any example from repository root:",
        "",
        ".. code-block:: bash",
        "",
        "   PYTHONPATH=src python examples/<category>/<example_name>.py",
        "",
    ]
    for category in sorted(grouped):
        title = _category_title(category)
        lines.append(title)
        lines.append("-" * len(title))
        lines.append("")
        for relative in grouped[category]:
            lines.append(f"- ``{relative.as_posix()}``")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Write or validate the generated examples index page.

    Raises:
        SystemExit: If ``--check`` is used and the generated file is stale.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    rendered = _render()
    if args.check:
        if not OUTPUT.exists():
            raise SystemExit("docs/examples/index.rst is missing.")
        current = OUTPUT.read_text(encoding="utf-8")
        if current != rendered:
            raise SystemExit("docs/examples/index.rst is out of date.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
