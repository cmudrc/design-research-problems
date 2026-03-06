from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from design_research_problems.gui import _tk_shared as shared


class _FakeCanvas:
    def __init__(self, *, width: int = 640, height: int = 480, bbox_value: object = None) -> None:
        self._width = width
        self._height = height
        self._bbox_value = bbox_value
        self.last_configure: dict[str, object] = {}
        self.last_itemconfigure: tuple[int, dict[str, object]] | None = None

    def bbox(self, _tag: str) -> object:
        return self._bbox_value

    def configure(self, **kwargs: object) -> None:
        self.last_configure = kwargs

    def itemconfigure(self, item_id: int, **kwargs: object) -> None:
        self.last_itemconfigure = (item_id, kwargs)

    def winfo_width(self) -> int:
        return self._width

    def winfo_height(self) -> int:
        return self._height


class _FakeRoot:
    def __init__(self) -> None:
        self._minsize: tuple[int, int] | None = None
        self._geometry: str | None = None

    def update_idletasks(self) -> None:
        return None

    def winfo_reqwidth(self) -> int:
        return 1400

    def winfo_reqheight(self) -> int:
        return 900

    def winfo_screenwidth(self) -> int:
        return 1200

    def winfo_screenheight(self) -> int:
        return 800

    def minsize(self, width: int, height: int) -> None:
        self._minsize = (width, height)

    def geometry(self, value: str) -> None:
        self._geometry = value


def test_canvas_resize_guard_runs_callback_only_on_size_change() -> None:
    guard = shared.CanvasResizeGuard()
    calls: list[str] = []
    event = SimpleNamespace(width=100, height=80)

    guard.handle_configure(event, lambda: calls.append("called"))
    guard.handle_configure(event, lambda: calls.append("called"))
    guard.handle_configure(SimpleNamespace(width=1, height=1), lambda: calls.append("called"))

    assert calls == ["called"]


def test_viewport_transform_roundtrip_and_canvas_convenience() -> None:
    transform = shared.compute_viewport_transform((0.0, 10.0, 0.0, 5.0), width=800, height=600)
    canvas_point = transform.world_to_canvas(2.5, 1.5)
    world_point = transform.canvas_to_world(*canvas_point)
    assert world_point[0] == pytest.approx(2.5)
    assert world_point[1] == pytest.approx(1.5)

    canvas = _FakeCanvas(width=500, height=300)
    from_canvas = shared.viewport_from_canvas((0.0, 10.0, 0.0, 10.0), canvas)
    assert from_canvas.scale > 0.0


def test_sidebar_helpers_update_scroll_and_width() -> None:
    empty_canvas = _FakeCanvas(bbox_value=None)
    shared.update_sidebar_scrollregion(empty_canvas)
    assert empty_canvas.last_configure["scrollregion"] == (0, 0, 0, 0)

    filled_canvas = _FakeCanvas(bbox_value=(1, 2, 3, 4))
    shared.update_sidebar_scrollregion(filled_canvas)
    assert filled_canvas.last_configure["scrollregion"] == (1, 2, 3, 4)

    shared.keep_sidebar_content_width(filled_canvas, sidebar_window_id=7, width=240)
    assert filled_canvas.last_itemconfigure == (7, {"width": 240})
    shared.keep_sidebar_content_width(filled_canvas, sidebar_window_id=7, width=0)
    assert filled_canvas.last_itemconfigure == (7, {"width": 240})


def test_event_modifier_and_evaluation_cycle_helpers() -> None:
    assert shared.is_additive_multiselect_event(SimpleNamespace(state=0x0001)) is True
    assert shared.is_additive_multiselect_event(SimpleNamespace(state=0)) is False

    latest: list[object | None] = []
    metrics: dict[str, str] = {}
    metrics_var = SimpleNamespace(set=lambda value: metrics.__setitem__("text", value))

    shared.run_evaluation_cycle(
        evaluate=lambda: 10,
        on_success=lambda value: (value, f"value={value}"),
        set_latest=latest.append,
        metrics_var=cast(Any, metrics_var),
    )
    assert latest[-1] == 10
    assert metrics["text"] == "value=10"

    shared.run_evaluation_cycle(
        evaluate=lambda: (_ for _ in ()).throw(RuntimeError("bad-eval")),
        on_success=lambda value: (value, "unused"),
        set_latest=latest.append,
        metrics_var=cast(Any, metrics_var),
    )
    assert latest[-1] is None
    assert "evaluation_error: bad-eval" in metrics["text"]


def test_fit_window_to_content_applies_screen_clamped_geometry() -> None:
    root = _FakeRoot()
    shared.fit_window_to_content(root, preferred_width=1000, preferred_height=700)
    assert root._minsize == (980, 620)
    assert root._geometry == "1160x720"
