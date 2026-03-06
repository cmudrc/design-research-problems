"""Run lightweight consistency checks for generated docs files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    """Verify that docs references and generated docs files are present.

    Raises:
        SystemExit: If required docs references or generated files are missing.
    """
    docs_index = (ROOT / "docs" / "index.rst").read_text(encoding="utf-8")
    generated_examples = ROOT / "docs" / "examples" / "index.rst"
    generated_problem_catalog = ROOT / "docs" / "problem_catalog" / "index.rst"
    generated_problem_family_pages = (
        ROOT / "docs" / "problem_catalog" / "text.rst",
        ROOT / "docs" / "problem_catalog" / "decision.rst",
        ROOT / "docs" / "problem_catalog" / "optimization.rst",
        ROOT / "docs" / "problem_catalog" / "grammar.rst",
        ROOT / "docs" / "problem_catalog" / "mcp.rst",
    )
    if ":doc:`examples/index`" not in docs_index:
        raise SystemExit("docs/index.rst must reference examples/index.")
    if ":doc:`problem_catalog/index`" not in docs_index:
        raise SystemExit("docs/index.rst must reference problem_catalog/index.")
    if not generated_examples.exists():
        raise SystemExit("docs/examples/index.rst is missing.")
    if not generated_problem_catalog.exists():
        raise SystemExit("docs/problem_catalog/index.rst is missing.")
    if any(not path.exists() for path in generated_problem_family_pages):
        raise SystemExit("docs/problem_catalog family index files are missing.")


if __name__ == "__main__":
    main()
