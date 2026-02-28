"""Generate an SVG coverage badge from the pytest coverage JSON artifact."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BADGE_PATH = ROOT / ".github" / "badges" / "coverage.svg"
INPUT_PATH = ROOT / "artifacts" / "coverage" / "coverage.json"


def _pick_color(percent: int) -> str:
    """Map one percentage to the shared badge color scale.

    Args:
        percent: Coverage percentage from 0 to 100.

    Returns:
        Hex color string for the badge.
    """
    if percent >= 90:
        return "#4c1"
    if percent >= 80:
        return "#97ca00"
    if percent >= 70:
        return "#a4a61d"
    if percent >= 60:
        return "#dfb317"
    if percent >= 50:
        return "#fe7d37"
    return "#e05d44"


def _text_width(text: str) -> int:
    """Approximate badge text width in pixels.

    Args:
        text: Badge text segment.

    Returns:
        Approximate pixel width.
    """
    return 10 + (len(text) * 6)


def _render_badge(label: str, message: str, color: str) -> str:
    """Render a glossy badge matching the shared repo style.

    Args:
        label: Left-hand badge label.
        message: Right-hand badge message.
        color: Fill color for the message segment.

    Returns:
        SVG markup string.
    """
    label_width = _text_width(label)
    message_width = _text_width(message)
    total_width = label_width + message_width
    label_x = label_width / 2
    message_x = label_width + (message_width / 2)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_width}" 
    height="20" role="img" aria-label="{label}: {message}">
  <linearGradient id="g" x2="0" y2="100%">
    <stop offset="0" stop-color="#fff" stop-opacity=".7"/>
    <stop offset=".1" stop-color="#aaa" stop-opacity=".1"/>
    <stop offset=".9" stop-opacity=".3"/>
    <stop offset="1" stop-opacity=".5"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_width}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{label_width}" height="20" fill="#555"/>
    <rect x="{label_width}" width="{message_width}" height="20" fill="{color}"/>
    <rect width="{total_width}" height="20" fill="url(#g)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" 
  font-size="11">
    <text x="{label_x:.1f}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
    <text x="{label_x:.1f}" y="14">{label}</text>
    <text x="{message_x:.1f}" y="15" fill="#010101" fill-opacity=".3">{message}</text>
    <text x="{message_x:.1f}" y="14">{message}</text>
  </g>
</svg>
"""


def _read_percent_display(path: Path) -> int:
    """Read the coverage percentage from the pytest coverage JSON.

    Args:
        path: Coverage JSON artifact path.

    Returns:
        Rounded integer percentage for display.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    raw_display = totals.get("percent_covered_display")
    if raw_display is not None:
        normalized = str(raw_display).strip().rstrip("%")
        return int(float(normalized))

    covered = float(totals.get("covered_lines", 0))
    total = float(totals.get("num_statements", 0))
    percent = 100.0 if total == 0 else 100.0 * covered / total
    return round(percent)


def main() -> None:
    """Read the coverage artifact and write the coverage badge SVG."""
    percent = _read_percent_display(INPUT_PATH)
    BADGE_PATH.write_text(
        _render_badge("Test Coverage", f"{percent}%", _pick_color(percent)),
        encoding="utf-8",
    )
    print(f"Wrote {BADGE_PATH} ({percent}%)")


if __name__ == "__main__":
    main()
