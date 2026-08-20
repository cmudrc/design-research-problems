"""Check public documentation against source-owned compatibility contracts."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROBLEM_KINDS = ("text", "decision", "optimization", "grammar", "mcp")
API_EXPORT_PATTERN = re.compile(r"^- ``([A-Za-z_][A-Za-z0-9_]*)``\s*$", re.MULTILINE)
EXAMPLE_INVENTORY_PATTERN = re.compile(r"^- `([^`]+\.py)`:", re.MULTILINE)
PROHIBITED_TAXONOMY_PATTERNS = (
    re.compile(r"\bbenchmark families for ideation\b", re.IGNORECASE),
    re.compile(r"\btasks spanning ideation, decision", re.IGNORECASE),
    re.compile(r"\bproblem families?:\s*ideation(?:,|\b)", re.IGNORECASE),
    re.compile(r"\bideation problem family\b", re.IGNORECASE),
)
CURATED_TAXONOMY_DOCS = (
    "README.md",
    "docs/index.rst",
    "docs/guides.rst",
    "docs/concepts.rst",
    "docs/catalog_guide.rst",
    "docs/problems/index.rst",
    "docs/problems/ideation.rst",
    "docs/downstream_metadata_contract.rst",
)


def _assigned_value(module: ast.Module, name: str) -> ast.expr:
    """Return one named top-level assignment value.

    Args:
        module: Parsed Python module.
        name: Assignment target name.

    Returns:
        Assigned expression.

    Raises:
        SystemExit: If the assignment is missing.
    """
    for node in module.body:
        is_named_assignment = isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        )
        if is_named_assignment:
            return node.value
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            return node.value
    raise SystemExit(f"Could not find top-level assignment {name!r}.")


def _public_exports() -> set[str]:
    """Parse the source-owned top-level export manifest.

    Returns:
        Public export names.
    """
    source_path = ROOT / "src" / "design_research_problems" / "__init__.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    export_value = _assigned_value(module, "_EXPORTS")
    if not isinstance(export_value, ast.Dict):
        raise SystemExit("design_research_problems._EXPORTS must remain a dictionary literal.")

    names = {key.value for key in export_value.keys if isinstance(key, ast.Constant) and isinstance(key.value, str)}
    return {"__version__", "integration", *names}


def _problem_kind_values() -> tuple[str, ...]:
    """Parse canonical values from the ``ProblemKind`` enum.

    Returns:
        Enum values in source order.
    """
    source_path = ROOT / "src" / "design_research_problems" / "problems" / "_metadata.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in module.body:
        if not isinstance(node, ast.ClassDef) or node.name != "ProblemKind":
            continue
        values: list[str] = []
        for statement in node.body:
            if not isinstance(statement, ast.Assign) or not isinstance(statement.value, ast.Constant):
                continue
            if isinstance(statement.value.value, str):
                values.append(statement.value.value)
        return tuple(values)
    raise SystemExit("Could not find the ProblemKind enum.")


def _check_generated_docs() -> list[str]:
    """Check required generated indexes and homepage links.

    Returns:
        Consistency errors.
    """
    errors: list[str] = []
    docs_index = (ROOT / "docs" / "index.rst").read_text(encoding="utf-8")
    for marker in (":doc:`guides`", ":doc:`examples/index`", ":doc:`problem_catalog/index`"):
        if marker not in docs_index:
            errors.append(f"docs/index.rst must reference {marker}.")

    required_paths = (
        ROOT / "docs" / "examples" / "index.rst",
        ROOT / "docs" / "problem_catalog" / "index.rst",
        *(ROOT / "docs" / "problem_catalog" / f"{kind}.rst" for kind in EXPECTED_PROBLEM_KINDS),
    )
    errors.extend(
        f"Required generated docs file is missing: {path.relative_to(ROOT)}"
        for path in required_paths
        if not path.exists()
    )
    return errors


def _check_public_api_docs() -> list[str]:
    """Compare ``docs/api.rst`` with the top-level export manifest.

    Returns:
        Consistency errors.
    """
    documented = set(API_EXPORT_PATTERN.findall((ROOT / "docs" / "api.rst").read_text(encoding="utf-8")))
    expected = _public_exports()
    errors: list[str] = []
    if missing := sorted(expected - documented):
        errors.append(f"docs/api.rst is missing top-level exports: {missing}")
    if extra := sorted(documented - expected):
        errors.append(f"docs/api.rst lists non-top-level exports: {extra}")
    return errors


def _check_problem_kinds_and_taxonomy() -> list[str]:
    """Check the five-kind contract and reject known taxonomy drift.

    Returns:
        Consistency errors.
    """
    errors: list[str] = []
    actual_kinds = _problem_kind_values()
    if actual_kinds != EXPECTED_PROBLEM_KINDS:
        errors.append(f"ProblemKind values must be {EXPECTED_PROBLEM_KINDS}; found {actual_kinds}.")

    concepts = (ROOT / "docs" / "concepts.rst").read_text(encoding="utf-8")
    required_markers = (
        "The ideation catalog is a curated subset of the ``text`` kind.",
        "``ProblemMetadata.kind`` → ``ProblemBinding.family`` →",
        '``ProblemBinding.metadata["problem_kind"]`` is a parallel metadata alias',
        "exported ``problem_family``",
    )
    for marker in required_markers:
        if marker not in concepts:
            errors.append(f"docs/concepts.rst is missing compatibility marker: {marker}")

    for relative_path in CURATED_TAXONOMY_DOCS:
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for pattern in PROHIBITED_TAXONOMY_PATTERNS:
            if pattern.search(text):
                errors.append(f"{relative_path} contains prohibited taxonomy wording matching {pattern.pattern!r}.")
    return errors


def _check_example_inventory() -> list[str]:
    """Compare runnable example files with ``examples/README.md``.

    Returns:
        Consistency errors.
    """
    examples_root = ROOT / "examples"
    expected = {
        path.relative_to(examples_root).as_posix()
        for path in examples_root.rglob("*.py")
        if not path.name.startswith("_") and "__pycache__" not in path.parts
    }
    readme = (examples_root / "README.md").read_text(encoding="utf-8")
    documented = set(EXAMPLE_INVENTORY_PATTERN.findall(readme))
    errors: list[str] = []
    if missing := sorted(expected - documented):
        errors.append(f"examples/README.md is missing runnable examples: {missing}")
    if stale := sorted(documented - expected):
        errors.append(f"examples/README.md lists missing runnable examples: {stale}")
    return errors


def _check_private_reference_boundaries() -> list[str]:
    """Reject public autodoc directives aimed at private paths.

    Returns:
        Consistency errors.
    """
    errors: list[str] = []
    autodoc_directive = re.compile(
        r"^\.\. auto[A-Za-z]+::\s+"
        r"(?P<target>design_research_problems(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*$",
        re.MULTILINE,
    )
    for path in sorted((ROOT / "docs" / "reference").rglob("*.rst")):
        text = path.read_text(encoding="utf-8")
        for match in autodoc_directive.finditer(text):
            target = match.group("target")
            if not any(segment.startswith("_") for segment in target.split(".")[1:]):
                continue
            errors.append(f"{path.relative_to(ROOT)} autodocuments private target {target!r}; use a public alias.")
    return errors


def main() -> None:
    """Run all documentation consistency checks.

    Raises:
        SystemExit: If any documentation contract is inconsistent.
    """
    errors = [
        *_check_generated_docs(),
        *_check_public_api_docs(),
        *_check_problem_kinds_and_taxonomy(),
        *_check_example_inventory(),
        *_check_private_reference_boundaries(),
    ]
    if errors:
        raise SystemExit("Documentation consistency check failed:\n- " + "\n- ".join(errors))


if __name__ == "__main__":
    main()
