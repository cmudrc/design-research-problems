"""Run lightweight consistency checks for the checked-in docs files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Verify that the docs index references generated example docs.

    Raises:
        SystemExit: If required docs references or generated files are missing.
    """
    docs_index = (ROOT / "docs" / "index.rst").read_text(encoding="utf-8")
    generated_examples = ROOT / "docs" / "examples" / "index.rst"
    if ":doc:`examples/index`" not in docs_index:
        raise SystemExit("docs/index.rst must reference examples/index.")
    if not generated_examples.exists():
        raise SystemExit("docs/examples/index.rst is missing.")


if __name__ == "__main__":
    main()
