"""Validate that a coverage report meets a minimum threshold."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    """Load coverage JSON, compute coverage, and enforce a minimum threshold.

    Raises:
        SystemExit: If the measured coverage is below the configured minimum.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--coverage-json", required=True)
    parser.add_argument("--minimum", type=float, default=0.0)
    args = parser.parse_args()

    payload = json.loads(Path(args.coverage_json).read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    covered = float(totals.get("covered_lines", 0))
    total = float(totals.get("num_statements", 0))
    percent = 100.0 if total == 0 else 100.0 * covered / total
    if percent < args.minimum:
        raise SystemExit(f"Coverage {percent:.2f}% is below the minimum {args.minimum:.2f}%.")


if __name__ == "__main__":
    main()
