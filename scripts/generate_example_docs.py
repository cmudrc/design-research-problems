"""Generate the docs page that lists the checked-in runnable examples."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "examples" / "index.rst"


def _render() -> str:
    """Render the examples index page from the example scripts on disk.

    Returns:
        Full reStructuredText content for ``docs/examples/index.rst``.
    """
    lines = [
        "Examples",
        "========",
        "",
        "The example inventory is generated from the checked-in scripts.",
        "",
    ]
    for path in sorted(ROOT.glob("examples/**/*.py")):
        lines.append(f"- ``{path.relative_to(ROOT).as_posix()}``")
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
