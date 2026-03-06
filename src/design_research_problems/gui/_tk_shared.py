"""Shared Tkinter infrastructure helpers used by packaged GUI apps."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True)
class CanvasSidebarLayout:
    """Main GUI shell with drawing canvas and scrollable sidebar."""

    main: ttk.Frame
    left: ttk.Frame
    right: ttk.Frame
    canvas: tk.Canvas
    sidebar_canvas: tk.Canvas
    sidebar_window_id: int


@dataclass
class CanvasResizeGuard:
    """Track canvas size changes and call one redraw callback when needed."""

    last_size: tuple[int, int] = (0, 0)

    def handle_configure(self, event: tk.Event[tk.Misc], on_resize: Callable[[], None]) -> None:
        """Run one redraw callback only when canvas dimensions actually change."""
        width = int(getattr(event, "width", 0))
        height = int(getattr(event, "height", 0))
        next_size = (width, height)
        if next_size == self.last_size:
            return
        self.last_size = next_size
        if width > 1 and height > 1:
            on_resize()


@dataclass(frozen=True)
class ViewportTransform:
    """World/canvas transform terms for one aspect-preserving viewport."""

    scale: float
    offset_x: float
    offset_y: float
    min_x: float
    max_y: float

    def world_to_canvas(self, x_value: float, y_value: float) -> tuple[float, float]:
        """Convert one world-space coordinate to canvas-space pixels."""
        canvas_x = self.offset_x + (x_value - self.min_x) * self.scale
        canvas_y = self.offset_y + (self.max_y - y_value) * self.scale
        return (canvas_x, canvas_y)

    def canvas_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        """Convert one canvas-space coordinate back to world coordinates."""
        world_x = self.min_x + (canvas_x - self.offset_x) / self.scale
        world_y = self.max_y - (canvas_y - self.offset_y) / self.scale
        return (world_x, world_y)


def build_canvas_sidebar_layout(
    root: tk.Misc,
    *,
    sidebar_width: int,
    canvas_width: int = 920,
    canvas_height: int = 560,
    canvas_background: str = "#f7f7f7",
    root_padding: int = 8,
    sidebar_pad_x: tuple[int, int] = (10, 0),
    canvas_highlightthickness: int = 1,
) -> CanvasSidebarLayout:
    """Create one shared frame/canvas/sidebar shell used by GUI apps."""
    main = ttk.Frame(root, padding=root_padding)
    main.pack(fill=tk.BOTH, expand=True)

    left = ttk.Frame(main)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    sidebar_outer = ttk.Frame(main)
    sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=sidebar_pad_x)
    sidebar_canvas = tk.Canvas(sidebar_outer, width=sidebar_width, highlightthickness=0, borderwidth=0)
    sidebar_scrollbar = ttk.Scrollbar(sidebar_outer, orient=tk.VERTICAL, command=sidebar_canvas.yview)
    sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
    sidebar_canvas.pack(side=tk.LEFT, fill=tk.Y)
    sidebar_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

    right = ttk.Frame(sidebar_canvas)
    sidebar_window_id = sidebar_canvas.create_window((0, 0), window=right, anchor=tk.NW)

    canvas = tk.Canvas(
        left,
        width=canvas_width,
        height=canvas_height,
        background=canvas_background,
        highlightthickness=canvas_highlightthickness,
    )
    canvas.pack(fill=tk.BOTH, expand=True)

    return CanvasSidebarLayout(
        main=main,
        left=left,
        right=right,
        canvas=canvas,
        sidebar_canvas=sidebar_canvas,
        sidebar_window_id=sidebar_window_id,
    )


def update_sidebar_scrollregion(sidebar_canvas: tk.Canvas) -> None:
    """Refresh the sidebar scrollregion for all current content."""
    bbox = sidebar_canvas.bbox("all")
    if bbox is None:
        sidebar_canvas.configure(scrollregion=(0, 0, 0, 0))
        return
    sidebar_canvas.configure(scrollregion=bbox)


def keep_sidebar_content_width(sidebar_canvas: tk.Canvas, sidebar_window_id: int, width: int) -> None:
    """Pin sidebar content width to the visible sidebar canvas width."""
    if width > 0:
        sidebar_canvas.itemconfigure(sidebar_window_id, width=width)


def compute_viewport_transform(
    bounds: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
    margin: float = 24.0,
) -> ViewportTransform:
    """Compute one aspect-preserving viewport transform from bounds/canvas size."""
    min_x, max_x, min_y, max_y = bounds
    safe_width = max(width, 200)
    safe_height = max(height, 200)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    usable_width = max(safe_width - 2.0 * margin, 1.0)
    usable_height = max(safe_height - 2.0 * margin, 1.0)
    scale = min(usable_width / span_x, usable_height / span_y)
    draw_width = span_x * scale
    draw_height = span_y * scale
    offset_x = (safe_width - draw_width) / 2.0
    offset_y = (safe_height - draw_height) / 2.0
    return ViewportTransform(
        scale=scale,
        offset_x=offset_x,
        offset_y=offset_y,
        min_x=min_x,
        max_y=max_y,
    )


def viewport_from_canvas(
    bounds: tuple[float, float, float, float],
    canvas: tk.Canvas,
    *,
    margin: float = 24.0,
) -> ViewportTransform:
    """Compute one viewport transform directly from one Tk canvas widget."""
    return compute_viewport_transform(
        bounds,
        width=canvas.winfo_width(),
        height=canvas.winfo_height(),
        margin=margin,
    )


def is_additive_multiselect_event(event: tk.Event[tk.Misc]) -> bool:
    """Return whether one event has a common additive multi-selection modifier."""
    state_bits = int(getattr(event, "state", 0))
    return bool(state_bits & 0x0001 or state_bits & 0x0004 or state_bits & 0x0008)


def run_evaluation_cycle[EvaluationT](
    *,
    evaluate: Callable[[], EvaluationT],
    on_success: Callable[[EvaluationT], tuple[EvaluationT | None, str]],
    set_latest: Callable[[EvaluationT | None], None],
    metrics_var: tk.StringVar,
) -> None:
    """Run one evaluation pass and update shared latest/metrics GUI state."""
    try:
        evaluation = evaluate()
    except Exception as exc:
        set_latest(None)
        metrics_var.set(f"evaluation_error: {exc}")
        return

    latest, metrics_text = on_success(evaluation)
    set_latest(latest)
    metrics_var.set(metrics_text)


def fit_window_to_content(
    root: tk.Tk,
    *,
    preferred_width: int,
    preferred_height: int,
    min_width: int = 980,
    min_height: int = 620,
    screen_margin_x: int = 40,
    screen_margin_y: int = 80,
) -> None:
    """Resize one root window to fit content while staying within screen bounds."""
    root.update_idletasks()
    required_width = root.winfo_reqwidth()
    required_height = root.winfo_reqheight()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    max_width = max(300, screen_width - screen_margin_x)
    max_height = max(300, screen_height - screen_margin_y)
    target_width = max(required_width, preferred_width)
    target_height = max(required_height, preferred_height)
    target_width = min(target_width, max_width)
    target_height = min(target_height, max_height)

    safe_min_width = min(min_width, max_width)
    safe_min_height = min(min_height, max_height)
    root.minsize(safe_min_width, safe_min_height)
    root.geometry(f"{int(target_width)}x{int(target_height)}")


__all__ = [
    "CanvasResizeGuard",
    "CanvasSidebarLayout",
    "ViewportTransform",
    "build_canvas_sidebar_layout",
    "compute_viewport_transform",
    "fit_window_to_content",
    "is_additive_multiselect_event",
    "keep_sidebar_content_width",
    "run_evaluation_cycle",
    "update_sidebar_scrollregion",
    "viewport_from_canvas",
]
