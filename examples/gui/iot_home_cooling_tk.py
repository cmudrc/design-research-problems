"""Compatibility launcher for the packaged IoT home cooling GUI."""

from __future__ import annotations

import design_research_problems as derp
from design_research_problems.gui import launch_gui


def main() -> None:
    """Launch the IoT home cooling GUI from the core library."""
    try:
        launch_gui("iot")
    except derp.MissingOptionalDependencyError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
