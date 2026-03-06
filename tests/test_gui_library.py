from __future__ import annotations

import subprocess
import sys

from design_research_problems.gui import list_gui_apps


def test_gui_app_registry_lists_supported_launchers() -> None:
    assert list_gui_apps() == ("iot", "truss")


def test_gui_module_entrypoint_help_is_available_without_tk() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "design_research_problems.gui", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--app {iot,truss}" in completed.stdout
