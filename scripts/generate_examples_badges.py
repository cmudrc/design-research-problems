"""Generate example-related SVG badges from the example metrics artifact."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "artifacts" / "examples" / "examples_metrics.json"
PASSING_BADGE = ROOT / ".github" / "badges" / "examples-passing.svg"
API_BADGE = ROOT / ".github" / "badges" / "examples-api-coverage.svg"


def _badge(width: int, left_width: int, label: str, value: str, color: str) -> str:
    """Render a generic flat SVG badge.

    Args:
        width: Total badge width in pixels.
        left_width: Width of the label segment in pixels.
        label: Left-hand label text.
        value: Right-hand value text.
        color: Fill color for the value segment.

    Returns:
        SVG markup string.
    """
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="20" role="img" '
        f'aria-label="{label}: {value}">'
        f'<rect width="{left_width}" height="20" fill="#555"/>'
        f'<rect x="{left_width}" width="{width - left_width}" height="20" fill="{color}"/>'
        f'<text x="{left_width / 2:.1f}" y="14" fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        f'font-size="11" text-anchor="middle">{label}</text>'
        f'<text x="{left_width + (width - left_width) / 2:.1f}" y="14" fill="#fff" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11" text-anchor="middle">{value}</text>'
        "</svg>"
    )


def main() -> None:
    """Read example metrics and write the examples badge SVGs."""
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    example_count = int(metrics["example_file_count"])
    api_coverage = float(metrics["api_coverage_pct"])
    PASSING_BADGE.write_text(
        _badge(132, 77, "examples", f"{example_count} files", "#4c1"),
        encoding="utf-8",
    )
    color = "#4c1" if api_coverage >= 75 else "#dfb317"
    API_BADGE.write_text(
        _badge(168, 113, "examples api", f"{api_coverage:.0f}%", color),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
