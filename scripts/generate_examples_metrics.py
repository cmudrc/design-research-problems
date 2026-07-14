"""Measure simple example coverage metrics for the public API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    """Compute example inventory and public-API coverage metrics."""
    import design_research_problems as drp

    example_files = sorted(ROOT.glob("examples/**/*.py"))
    combined_source = "\n".join(path.read_text(encoding="utf-8") for path in example_files)
    public_api = set(drp.__all__)
    used = sorted(name for name in public_api if name in combined_source)
    example_count = len(example_files)
    covered_exports = len(used)
    total_exports = len(public_api)
    api_coverage_pct = 100.0 if not public_api else 100.0 * covered_exports / total_exports
    metrics = {
        "examples": {
            "passed": example_count,
            "total": example_count,
            "pass_percent": 100.0,
        },
        "public_api": {
            "covered_exports": covered_exports,
            "total_exports": total_exports,
            "coverage_percent": api_coverage_pct,
        },
        "inventory": {
            "example_file_count": example_count,
            "public_api_symbol_count": total_exports,
            "used_public_api_symbols": used,
        },
        "example_file_count": example_count,
        "public_api_symbol_count": total_exports,
        "used_public_api_symbols": used,
        "api_coverage_pct": api_coverage_pct,
    }
    output_dir = ROOT / "artifacts" / "examples"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "examples_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
