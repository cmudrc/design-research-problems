from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems.gui import _launcher as launcher


class _FakeRoot:
    def __init__(self) -> None:
        self.geometry_value: str | None = None
        self.mainloop_called = False

    def geometry(self, value: str) -> None:
        self.geometry_value = value

    def mainloop(self) -> None:
        self.mainloop_called = True


class _FakeTk:
    def __init__(self, root: _FakeRoot) -> None:
        self._root = root

    def Tk(self) -> _FakeRoot:
        return self._root


def test_list_gui_apps_and_unknown_id_guard() -> None:
    assert launcher.list_gui_apps() == ("iot", "truss")
    with pytest.raises(ValueError, match="Unknown GUI app id"):
        launcher.launch_gui("unknown")  # type: ignore[arg-type]


def test_import_tk_surfaces_stable_optional_dependency_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def _fake_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "tkinter":
            raise ModuleNotFoundError(name)
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(MissingOptionalDependencyError, match="Tkinter is not available"):
        launcher._import_tk()


def test_launch_gui_constructs_root_and_app(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = _FakeRoot()
    fake_tk = _FakeTk(fake_root)
    called: dict[str, Any] = {}

    class _FakeApp:
        def __init__(self, root: _FakeRoot) -> None:
            called["root"] = root

    monkeypatch.setattr(launcher, "_import_tk", lambda: fake_tk)
    monkeypatch.setattr(launcher, "import_module", lambda _path: SimpleNamespace(IoTHomeCoolingApp=_FakeApp))

    launcher.launch_gui("iot")
    assert fake_root.geometry_value == "1250x760"
    assert fake_root.mainloop_called is True
    assert called["root"] is fake_root


def test_launch_gui_wraps_tk_root_startup_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FailingTk:
        def Tk(self) -> object:
            raise RuntimeError("cannot initialize tk")

    monkeypatch.setattr(launcher, "_import_tk", lambda: _FailingTk())
    monkeypatch.setattr(
        launcher,
        "import_module",
        lambda _path: SimpleNamespace(TrussAPApp=lambda _root: None),
    )
    with pytest.raises(MissingOptionalDependencyError, match="could not initialize a GUI window"):
        launcher.launch_gui("truss")


def test_main_parses_args_and_translates_missing_optional_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, Any] = {}

    def _launch(app: launcher.GUIAppId) -> None:
        called["app"] = app

    monkeypatch.setattr(launcher, "launch_gui", _launch)
    monkeypatch.setattr(sys, "argv", ["prog", "--app", "truss"])
    launcher.main()
    assert called["app"] == "truss"

    def _raise_missing(app: launcher.GUIAppId) -> None:
        raise MissingOptionalDependencyError(f"missing for {app}")

    monkeypatch.setattr(launcher, "launch_gui", _raise_missing)
    monkeypatch.setattr(sys, "argv", ["prog", "--app", "iot"])
    with pytest.raises(SystemExit, match="missing for iot"):
        launcher.main()
