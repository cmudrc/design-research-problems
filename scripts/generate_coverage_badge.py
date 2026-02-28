"""Generate an SVG coverage badge from the pytest coverage JSON artifact."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BADGE_PATH = ROOT / ".github" / "badges" / "coverage.svg"
INPUT_PATH = ROOT / "artifacts" / "coverage" / "coverage.json"


def _color(percent: float) -> str:
    """Map one coverage percentage to a badge color.

    Args:
        percent: Coverage percentage from 0 to 100.

    Returns:
        Hex color string for the badge.
    """
    if percent >= 90:
        return "#4c1"
    if percent >= 75:
        return "#97CA00"
    if percent >= 60:
        return "#dfb317"
    return "#e05d44"


def _badge(label: str, value: str, color: str) -> str:
    """Render a small flat SVG badge.

    Args:
        label: Left-hand badge label.
        value: Right-hand badge value.
        color: Fill color for the value segment.

    Returns:
        SVG markup string.
    """
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="110" height="20" role="img" '
        f'aria-label="{label}: {value}">'
        '<rect width="63" height="20" fill="#555"/>'
        f'<rect x="63" width="47" height="20" fill="{color}"/>'
        '<text x="31.5" y="14" fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f"{label}</text>"
        '<text x="86.5" y="14" fill="#fff" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" '
        'font-size="11" text-anchor="middle">'
        f"{value}</text>"
        "</svg>"
    )


def main() -> None:
    """Read the coverage artifact and write the coverage badge SVG."""
    payload = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    covered = float(totals.get("covered_lines", 0))
    total = float(totals.get("num_statements", 0))
    percent = 100.0 if total == 0 else 100.0 * covered / total
    BADGE_PATH.write_text(_badge("coverage", f"{percent:.0f}%", _color(percent)), encoding="utf-8")


if __name__ == "__main__":
    main()
