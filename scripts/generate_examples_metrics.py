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
    public_api = {name for name in drp.__all__ if name != "__version__"}
    used = sorted(name for name in public_api if name in combined_source)
    metrics = {
        "example_file_count": len(example_files),
        "public_api_symbol_count": len(public_api),
        "used_public_api_symbols": used,
        "api_coverage_pct": 100.0 if not public_api else 100.0 * len(used) / len(public_api),
    }
    output_dir = ROOT / "artifacts" / "examples"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "examples_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
