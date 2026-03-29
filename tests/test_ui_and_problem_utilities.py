from __future__ import annotations

import runpy
import sys
import warnings
from dataclasses import dataclass
from types import MappingProxyType, ModuleType, SimpleNamespace

import numpy
import pytest

import design_research_problems.gui as gui_module
from design_research_problems import gui
from design_research_problems._catalog import _loader as loader_module
from design_research_problems._optional import import_optional_module, optional_install_hint
from design_research_problems.gui import _tk_shared as tk_shared_module
from design_research_problems.problems import _assets as assets_module
from design_research_problems.problems import _mcp as mcp_module
from design_research_problems.problems import _problem as problem_module
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import (
    Citation,
    ProblemAsset,
    ProblemKind,
    ProblemMetadata,
    ProblemTaxonomy,
)
from design_research_problems.problems._problem import Problem


@dataclass
class _FakeTraversable:
    name: str
    children: dict[str, _FakeTraversable] | None = None
    text: str | None = None
    data: bytes | None = None
    directory: bool = True

    def joinpath(self, *parts: str) -> _FakeTraversable:
        node: _FakeTraversable = self
        for part in parts:
            if node.children is None:
                return _FakeTraversable(part)
            node = node.children.get(part, _FakeTraversable(part))
        return node

    def read_text(self, encoding: str = "utf-8") -> str:
        del encoding
        assert self.text is not None
        return self.text

    def read_bytes(self) -> bytes:
        assert self.data is not None
        return self.data

    def is_dir(self) -> bool:
        return self.directory

    def is_file(self) -> bool:
        return not self.directory

    def iterdir(self) -> tuple[_FakeTraversable, ...]:
        return tuple(self.children.values() if self.children else ())


def _metadata(*, assets: tuple[ProblemAsset, ...] = ()) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id="utility_problem",
        title="Utility Problem",
        summary="Problem utility helper coverage.",
        kind=ProblemKind.TEXT,
        taxonomy=ProblemTaxonomy(
            formulation="textual",
            convexity=None,
            design_variable_type=None,
            is_dynamic=False,
            orientation="engineering_practical",
            feasibility_ratio_hint=None,
            objective_mode="qualitative",
            constraint_nature="informal",
            bounds_summary=None,
            tags=("utility",),
        ),
        citations=(
            Citation(
                key="demo",
                kind="bibtex",
                authors=("Author",),
                title="Utility Citation",
                year=2024,
                raw_text="@article{demo,...}",
                doi="10.1234/demo",
                url="https://example.com/demo",
            ),
        ),
        assets=assets,
        capabilities=("statement-markdown",),
        study_suitability=(),
    )


def test_loader_helpers_cover_resource_and_duplicate_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_root = _FakeTraversable(
        "design_research_problems",
        children={
            "_assets": _FakeTraversable(
                "_assets",
                children={
                    "catalog": _FakeTraversable(
                        "catalog",
                        children={
                            "nested": _FakeTraversable(
                                "nested",
                                children={
                                    "problem_a": _FakeTraversable(
                                        "problem_a",
                                        children={
                                            "problem.toml": _FakeTraversable(
                                                "problem.toml",
                                                directory=False,
                                                text="",
                                            ),
                                        },
                                    ),
                                },
                            ),
                            "notes.txt": _FakeTraversable("notes.txt", directory=False, text="skip"),
                        },
                    ),
                    "citations": _FakeTraversable(
                        "citations",
                        children={
                            "raw.txt": _FakeTraversable("raw.txt", directory=False, text="Loaded from resource file"),
                        },
                    ),
                },
            )
        },
    )
    monkeypatch.setattr(loader_module, "files", lambda package: fake_root)

    assert loader_module._resource_root("_assets/citations").name == "citations"
    with pytest.raises(ValueError, match="Unsupported problem kind"):
        loader_module._parse_problem_kind("mystery")

    citations = loader_module._parse_citations(
        {
            "citations": [
                {
                    "key": "demo",
                    "kind": "inline",
                    "title": "Demo",
                    "raw_text_file": "raw.txt",
                }
            ]
        },
        "_assets/citations",
    )
    assert citations[0].raw_text == "Loaded from resource file"

    with pytest.raises(ValueError, match="Unsupported catalog value"):
        loader_module._normalize_vocab_values(["", "unknown"], frozenset({"known"}))

    directories = loader_module._iter_manifest_directories(loader_module._catalog_root())
    assert directories == (
        (fake_root.joinpath("_assets", "catalog", "nested", "problem_a"), "_assets/catalog/nested/problem_a"),
    )

    monkeypatch.setattr(
        loader_module,
        "_iter_manifest_directories",
        lambda root: ((object(), "one"), (object(), "two")),
    )
    monkeypatch.setattr(
        loader_module,
        "_load_single_manifest",
        lambda entry, resource_dir: SimpleNamespace(
            metadata=SimpleNamespace(problem_id="duplicate"),
            resource_dir=resource_dir,
        ),
    )
    with pytest.raises(ValueError, match="Duplicate problem_id detected"):
        loader_module.load_problem_manifests()


def test_problem_helpers_mcp_json_optional_and_assets_cover_edge_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_server = SimpleNamespace(tools=[])
    fake_server.add_tool = lambda func, **kwargs: fake_server.tools.append((func, kwargs))
    monkeypatch.setattr(problem_module, "create_fastmcp_server", lambda *args, **kwargs: fake_server)
    monkeypatch.setattr(problem_module, "register_design_brief_resource", lambda *args, **kwargs: None)

    problem = Problem(metadata=_metadata(), statement_markdown="# Different Title")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert problem._starts_with_h1("# Different Title") is True
    assert any("does not match metadata title" in str(warning.message) for warning in caught)

    server = problem.to_mcp_server()
    submit_func = next(func for func, kwargs in server.tools if kwargs["name"] == "submit_final")
    with pytest.raises(ValueError, match="non-empty string"):
        submit_func("   ")

    with pytest.raises(RuntimeError, match="no resource bundle attached"):
        problem.read_asset("diagram")

    asset_metadata = _metadata(
        assets=(
            ProblemAsset(
                name="diagram",
                media_type="image/png",
                description="Demo asset",
                resource_path="diagram.png",
            ),
        )
    )
    bundle = SimpleNamespace(
        read_bytes=lambda resource_path: b"diagram-bytes" if resource_path == "diagram.png" else b""
    )
    asset_problem = Problem(metadata=asset_metadata, resource_bundle=bundle)
    assert asset_problem.read_asset("diagram") == b"diagram-bytes"
    with pytest.raises(KeyError, match="Unknown asset name"):
        asset_problem.read_asset("missing")

    fake_asset_root = _FakeTraversable(
        "design_research_problems",
        children={
            "_assets": _FakeTraversable(
                "_assets",
                children={
                    "demo": _FakeTraversable(
                        "demo",
                        children={
                            "binary.bin": _FakeTraversable("binary.bin", directory=False, data=b"binary-data"),
                        },
                    ),
                },
            )
        },
    )
    monkeypatch.setattr(assets_module, "files", lambda package: fake_asset_root)
    bundle = PackageResourceBundle("design_research_problems", "_assets/demo")
    assert bundle.read_bytes("binary.bin") == b"binary-data"

    assert mcp_module.to_json_value(numpy.int64(7)) == 7
    assert mcp_module.to_json_value(MappingProxyType({"count": numpy.int64(3)})) == {"count": 3}
    assert mcp_module.to_json_value(b"hello") == "hello"
    assert mcp_module.normalized_optional_text(None) is None

    assert optional_install_hint() == "pip install design-research-problems"
    monkeypatch.setattr(
        "design_research_problems._optional.import_module",
        lambda name: (_ for _ in ()).throw(ImportError("missing")),
    )
    with pytest.raises(Exception, match="make gui"):
        import_optional_module(
            "missing.module",
            required_for="GUI support",
            extras=("gui",),
            make_target="gui",
        )


def test_gui_helpers_cover_lazy_exports_launcher_and_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "launch_gui" in dir(gui)
    assert "launch_gui" in dir(gui_module)

    launcher_events: list[tuple[str, object]] = []

    class FakeRoot:
        def geometry(self, value: str) -> None:
            launcher_events.append(("geometry", value))

        def mainloop(self) -> None:
            launcher_events.append(("mainloop", None))

    fake_tk = ModuleType("tkinter")
    fake_tk.Tk = lambda: FakeRoot()  # type: ignore[attr-defined]
    app_module = ModuleType("design_research_problems.gui.iot_home_cooling_tk")

    class IoTHomeCoolingApp:
        def __init__(self, root: object) -> None:
            launcher_events.append(("app", root))

    app_module.IoTHomeCoolingApp = IoTHomeCoolingApp  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "tkinter", fake_tk)
    monkeypatch.setitem(sys.modules, "design_research_problems.gui.iot_home_cooling_tk", app_module)
    monkeypatch.setattr(sys, "argv", ["launcher", "--app", "iot"])

    runpy.run_module("design_research_problems.gui._launcher", run_name="__main__")

    assert ("geometry", "1250x760") in launcher_events
    assert any(event[0] == "mainloop" for event in launcher_events)

    widget_events: list[tuple[str, object]] = []

    class FakeFrame:
        def __init__(self, parent: object, **kwargs: object) -> None:
            self.parent = parent
            self.kwargs = kwargs

        def pack(self, **kwargs: object) -> None:
            widget_events.append(("frame.pack", kwargs))

    class FakeCanvas:
        def __init__(self, parent: object, **kwargs: object) -> None:
            self.parent = parent
            self.kwargs = kwargs

        def configure(self, **kwargs: object) -> None:
            widget_events.append(("canvas.configure", kwargs))

        def pack(self, **kwargs: object) -> None:
            widget_events.append(("canvas.pack", kwargs))

        def yview(self, *args: object) -> None:
            widget_events.append(("canvas.yview", args))

        def create_window(self, coords: tuple[int, int], *, window: object, anchor: str) -> int:
            widget_events.append(("canvas.create_window", (coords, window, anchor)))
            return 7

    class FakeScrollbar:
        def __init__(self, parent: object, **kwargs: object) -> None:
            self.parent = parent
            self.kwargs = kwargs

        def pack(self, **kwargs: object) -> None:
            widget_events.append(("scrollbar.pack", kwargs))

        def set(self, *args: object) -> None:
            widget_events.append(("scrollbar.set", args))

    fake_tk_namespace = SimpleNamespace(
        BOTH="both",
        LEFT="left",
        Y="y",
        NW="nw",
        VERTICAL="vertical",
        Canvas=FakeCanvas,
        Misc=object,
        Event=object,
        StringVar=object,
        Tk=object,
    )
    fake_ttk_namespace = SimpleNamespace(Frame=FakeFrame, Scrollbar=FakeScrollbar)
    monkeypatch.setattr(tk_shared_module, "tk", fake_tk_namespace)
    monkeypatch.setattr(tk_shared_module, "ttk", fake_ttk_namespace)

    layout = tk_shared_module.build_canvas_sidebar_layout(object(), sidebar_width=280)
    assert layout.sidebar_window_id == 7
    assert any(event[0] == "canvas.pack" for event in widget_events)
