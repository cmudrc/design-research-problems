"""Generate example-related SVG badges from the example metrics artifact."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "artifacts" / "examples" / "examples_metrics.json"
PASSING_BADGE = ROOT / ".github" / "badges" / "examples-passing.svg"
API_BADGE = ROOT / ".github" / "badges" / "examples-api-coverage.svg"


def _pick_color(percent: int) -> str:
    """Map one percentage to the shared badge color scale.

    Args:
        percent: Percentage from 0 to 100.

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


def _read_metrics() -> tuple[int, int, float, int, int]:
    """Read example and public-API metrics from the generated JSON artifact.

    Returns:
        Tuple of example pass counts, example percentage, and API coverage counts.
    """
    metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    examples = metrics.get("examples")
    public_api = metrics.get("public_api")
    if isinstance(examples, dict) and isinstance(public_api, dict):
        passed = int(examples.get("passed", 0))
        total = int(examples.get("total", 0))
        pass_percent = float(examples.get("pass_percent", 0.0))
        covered_exports = int(public_api.get("covered_exports", 0))
        total_exports = int(public_api.get("total_exports", 0))
        return passed, total, pass_percent, covered_exports, total_exports

    example_count = int(metrics.get("example_file_count", 0))
    api_coverage_pct = float(metrics.get("api_coverage_pct", 0.0))
    public_api_symbol_count = int(metrics.get("public_api_symbol_count", 0))
    covered_exports = round((api_coverage_pct / 100.0) * public_api_symbol_count)
    return example_count, example_count, 100.0, covered_exports, public_api_symbol_count


def main() -> None:
    """Read example metrics and write the examples badge SVGs."""
    passed, total, pass_percent, covered_exports, total_exports = _read_metrics()
    PASSING_BADGE.write_text(
        _render_badge("Examples Passing", f"{passed}/{total}", _pick_color(round(pass_percent))),
        encoding="utf-8",
    )
    api_coverage_percent = round((covered_exports / total_exports) * 100.0) if total_exports else 100
    API_BADGE.write_text(
        _render_badge(
            "API in Examples",
            f"{covered_exports}/{total_exports}",
            _pick_color(api_coverage_percent),
        ),
        encoding="utf-8",
    )
    print(f"Wrote {PASSING_BADGE} and {API_BADGE} (examples: {passed}/{total}, api: {covered_exports}/{total_exports})")


if __name__ == "__main__":
    main()
