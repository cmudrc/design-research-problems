"""Core launcher for Tkinter GUI integrations."""

from __future__ import annotations

import argparse
from importlib import import_module
from typing import Any, Final, Literal, Protocol, cast

from design_research_problems._exceptions import MissingOptionalDependencyError

type GUIAppId = Literal["iot", "truss"]


class _TkModule(Protocol):
    """Minimal Tk module protocol required by this launcher."""

    def Tk(self) -> Any:
        """Construct and return the root Tk window."""
        ...


_GUI_APP_SPECS: Final[dict[GUIAppId, tuple[str, str, str]]] = {
    "iot": (
        "design_research_problems.gui.iot_home_cooling_tk",
        "IoTHomeCoolingApp",
        "1250x620",
    ),
    "truss": (
        "design_research_problems.gui.truss_analysis_program_tk",
        "TrussAPApp",
        "1260x640",
    ),
}


def list_gui_apps() -> tuple[GUIAppId, ...]:
    """Return supported GUI application identifiers."""
    return tuple(_GUI_APP_SPECS)


def _import_tk() -> _TkModule:
    """Import tkinter or raise a stable optional-dependency error."""
    try:
        import tkinter as tk
    except ModuleNotFoundError as exc:
        raise MissingOptionalDependencyError(
            "Tkinter is not available in this Python environment. "
            "Install/use a Python build with Tk support to run GUI examples."
        ) from exc
    return cast(_TkModule, tk)


def launch_gui(app: GUIAppId = "iot") -> None:
    """Launch one packaged Tkinter GUI app by identifier.

    Args:
        app: GUI identifier (`"iot"` or `"truss"`).

    Raises:
        ValueError: If ``app`` is unknown.
        MissingOptionalDependencyError: If Tkinter is unavailable.
    """
    if app not in _GUI_APP_SPECS:
        valid = ", ".join(sorted(_GUI_APP_SPECS))
        raise ValueError(f"Unknown GUI app id: {app!r}. Valid ids: {valid}")

    tk = _import_tk()
    module_path, class_name, geometry = _GUI_APP_SPECS[app]
    module = import_module(module_path)
    app_class = getattr(module, class_name)

    try:
        root = tk.Tk()
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "Tkinter is installed but could not initialize a GUI window. "
            "Ensure Tcl/Tk runtime files are available in this environment."
        ) from exc
    root.geometry(geometry)
    app_class(root)
    root.mainloop()


def main() -> None:
    """Parse CLI arguments and launch one GUI app."""
    parser = argparse.ArgumentParser(description="Launch a packaged design-research-problems GUI.")
    parser.add_argument(
        "--app",
        choices=list_gui_apps(),
        default="iot",
        help="GUI to launch: 'iot' or 'truss'.",
    )
    args = parser.parse_args()

    try:
        launch_gui(app=args.app)
    except MissingOptionalDependencyError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
