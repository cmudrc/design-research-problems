"""Tkinter GUI for MATLAB Truss Analysis Program-style design workflows."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, ttk
from typing import cast

from design_research_problems import get_problem
from design_research_problems.problems._domains.truss_ap import TrussAPEvaluation, TrussLoadDirection
from design_research_problems.problems.grammar._truss_ap import TrussAPGrammarProblem


class TrussAPApp:
    """Near-native Tkinter front-end for truss grammar design."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the truss GUI with the packaged grammar backend.

        Args:
            root: Tk root window.
        """
        self.root = root
        self.root.title("Truss Analysis Program Co-Design")
        self.root.minsize(980, 620)
        problem = get_problem("truss_analysis_program_design")
        if not isinstance(problem, TrussAPGrammarProblem):
            raise TypeError("Truss GUI requires the TrussAPGrammarProblem direct-stiffness backend.")
        self.problem = problem
        self.state = self.problem.initial_state()

        self.mode_var = tk.StringVar(value="add_joint")
        self.member_size_var = tk.StringVar(value="5")
        self.load_direction_var = tk.StringVar(value="down")
        self.load_magnitude_var = tk.StringVar(value="200000")

        self._joint_index_to_id: list[int] = []
        self._member_index_to_id: list[int] = []
        self._support_vars = [tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)]
        self._joint_canvas_positions: dict[int, tuple[float, float]] = {}
        self._member_canvas_segments: dict[int, tuple[float, float, float, float]] = {}
        self._joint_hit_radius_px = 12.0
        self._member_hit_radius_px = 10.0
        self._last_canvas_size: tuple[int, int] = (0, 0)
        self._latest_evaluation: TrussAPEvaluation | None = None

        self._build_layout()
        self.root.after_idle(self._refresh)

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        sidebar_outer = ttk.Frame(main)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))
        self.sidebar_canvas = tk.Canvas(sidebar_outer, width=350, highlightthickness=0, borderwidth=0)
        sidebar_scrollbar = ttk.Scrollbar(sidebar_outer, orient=tk.VERTICAL, command=self.sidebar_canvas.yview)
        self.sidebar_canvas.configure(yscrollcommand=sidebar_scrollbar.set)
        self.sidebar_canvas.pack(side=tk.LEFT, fill=tk.Y)
        sidebar_scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        right = ttk.Frame(self.sidebar_canvas)
        self._sidebar_window_id = self.sidebar_canvas.create_window((0, 0), window=right, anchor=tk.NW)
        right.bind("<Configure>", self._on_sidebar_content_configure)
        self.sidebar_canvas.bind("<Configure>", self._on_sidebar_canvas_configure)

        self.canvas = tk.Canvas(left, width=920, height=560, background="#f6f8fb", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        ttk.Label(right, text="Canvas Click Mode").pack(anchor=tk.W)
        ttk.Combobox(
            right,
            textvariable=self.mode_var,
            values=("add_joint", "move_selected_joint"),
            state="readonly",
            width=26,
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right, text="Joints").pack(anchor=tk.W)
        self.joint_listbox = tk.Listbox(right, height=10, width=36, selectmode=tk.EXTENDED, exportselection=False)
        self.joint_listbox.pack(anchor=tk.W, fill=tk.X)
        self.joint_listbox.bind("<<ListboxSelect>>", self._on_joint_list_selection)

        ttk.Label(right, text="Members").pack(anchor=tk.W, pady=(8, 0))
        self.member_listbox = tk.Listbox(right, height=10, width=36, exportselection=False)
        self.member_listbox.pack(anchor=tk.W, fill=tk.X)
        self.member_listbox.bind("<<ListboxSelect>>", self._on_member_list_selection)

        ttk.Label(right, text="Member Size").pack(anchor=tk.W, pady=(8, 0))
        ttk.Combobox(
            right,
            textvariable=self.member_size_var,
            values=tuple(str(index) for index in range(1, 11)),
            state="readonly",
            width=10,
        ).pack(anchor=tk.W)

        ttk.Button(right, text="Add Member (2 joints)", command=self._add_member).pack(anchor=tk.W, pady=(8, 0))
        ttk.Button(right, text="Resize Selected Member", command=self._resize_member).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(right, text="Delete Selected Member", command=self._delete_member).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(right, text="Delete Selected Joint", command=self._delete_joint).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(right).pack(fill=tk.X, pady=10)

        ttk.Label(right, text="Supports").pack(anchor=tk.W)
        for support_id in (1, 2, 3):
            ttk.Checkbutton(
                right,
                text=f"Support {support_id}",
                variable=self._support_vars[support_id - 1],
                command=self._apply_support_toggles,
            ).pack(anchor=tk.W)

        ttk.Label(right, text="Load Direction").pack(anchor=tk.W, pady=(8, 0))
        ttk.Combobox(
            right,
            textvariable=self.load_direction_var,
            values=("left", "down", "right", "up"),
            state="readonly",
            width=10,
        ).pack(anchor=tk.W)

        ttk.Label(right, text="Load Magnitude (N)").pack(anchor=tk.W)
        ttk.Combobox(
            right,
            textvariable=self.load_magnitude_var,
            values=tuple(str(int(value)) for value in self.state.load_magnitude_options_n),
            state="readonly",
            width=10,
        ).pack(anchor=tk.W)

        ttk.Button(right, text="Set Load (1 joint)", command=self._set_load).pack(anchor=tk.W, pady=(8, 0))
        ttk.Button(right, text="Clear Load (1 joint)", command=self._clear_load).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(right).pack(fill=tk.X, pady=10)
        ttk.Button(right, text="Re-evaluate now", command=self._evaluate).pack(anchor=tk.W)
        self.metrics_var = tk.StringVar(value="No evaluation yet.")
        ttk.Label(right, textvariable=self.metrics_var, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        hint = (
            "Select joints/members from the lists or canvas. Under-determined trusses (m + r < 2j) are not "
            "evaluated. Member colors and FOS labels appear after a successful structural solve."
        )
        ttk.Label(right, text=hint, wraplength=280, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

    def _on_sidebar_content_configure(self, _event: tk.Event[tk.Misc]) -> None:
        """Update sidebar scroll range when content height changes."""
        self.sidebar_canvas.configure(scrollregion=self.sidebar_canvas.bbox("all"))

    def _on_sidebar_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """Keep sidebar content width equal to the visible canvas width."""
        width = int(getattr(event, "width", 0))
        if width > 0:
            self.sidebar_canvas.itemconfigure(self._sidebar_window_id, width=width)

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """Redraw when canvas dimensions change to keep initial scaling stable."""
        width = int(getattr(event, "width", 0))
        height = int(getattr(event, "height", 0))
        next_size = (width, height)
        if next_size == self._last_canvas_size:
            return
        self._last_canvas_size = next_size
        if width > 1 and height > 1:
            self._draw()

    def _on_joint_list_selection(self, _event: tk.Event[tk.Misc]) -> None:
        """Refresh visual highlight when listbox selection changes."""
        self._draw()

    def _on_member_list_selection(self, _event: tk.Event[tk.Misc]) -> None:
        """Refresh visual highlight when member selection changes."""
        self._draw()

    def _viewport_transform(
        self,
        bounds: tuple[float, float, float, float],
    ) -> tuple[float, float, float, float, float]:
        """Return scale/offset terms for an aspect-preserving world-to-canvas map."""
        x_min, x_max, y_min, y_max = bounds
        width = max(self.canvas.winfo_width(), 200)
        height = max(self.canvas.winfo_height(), 200)
        margin = 24.0
        span_x = max(x_max - x_min, 1e-9)
        span_y = max(y_max - y_min, 1e-9)
        usable_width = max(width - 2.0 * margin, 1.0)
        usable_height = max(height - 2.0 * margin, 1.0)
        scale = min(usable_width / span_x, usable_height / span_y)
        draw_width = span_x * scale
        draw_height = span_y * scale
        offset_x = (width - draw_width) / 2.0
        offset_y = (height - draw_height) / 2.0
        return (scale, offset_x, offset_y, x_min, y_max)

    def _world_to_canvas(self, x_value: float, y_value: float) -> tuple[float, float]:
        scale, offset_x, offset_y, x_min, y_max = self._viewport_transform(self.state.design_bounds)
        canvas_x = offset_x + (x_value - x_min) * scale
        canvas_y = offset_y + (y_max - y_value) * scale
        return (canvas_x, canvas_y)

    def _canvas_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        scale, offset_x, offset_y, x_min, y_max = self._viewport_transform(self.state.design_bounds)
        world_x = x_min + (canvas_x - offset_x) / scale
        world_y = y_max - (canvas_y - offset_y) / scale
        return (world_x, world_y)

    def _draw_load_arrow(self, x_value: float, y_value: float, direction: str, color: str = "#8b1a1a") -> None:
        dx = 0.0
        dy = 0.0
        span = 0.7
        if direction == "left":
            dx = -span
        elif direction == "right":
            dx = span
        elif direction == "up":
            dy = span
        elif direction == "down":
            dy = -span

        x0, y0 = self._world_to_canvas(x_value, y_value)
        x1, y1 = self._world_to_canvas(x_value + dx, y_value + dy)
        self.canvas.create_line(x0, y0, x1, y1, fill=color, width=2, arrow=tk.LAST)

    def _format_fos(self, value: float) -> str:
        if math.isinf(value):
            return "inf"
        return f"{value:.2f}"

    def _member_color_for_fos(self, value: float | None) -> str:
        if value is None or not math.isfinite(value):
            return "#334155"
        if value < 1.0:
            return "#b91c1c"
        if value < self.state.fos_target:
            return "#b45309"
        return "#166534"

    def _reaction_unknown_count(self) -> int:
        """Return planar support-reaction unknown count from support toggles."""
        count = 0
        if self.state.support_enabled[0]:
            count += 2
        if self.state.support_enabled[1]:
            count += 1
        if self.state.support_enabled[2]:
            count += 2
        return count

    def _determinacy_values(self) -> tuple[int, int, int, int]:
        """Return ``(m, r, lhs, rhs)`` for planar determinacy ``m + r >= 2j``."""
        member_count = len(self.state.members)
        reaction_count = self._reaction_unknown_count()
        joint_count = len(self.state.joints)
        lhs = member_count + reaction_count
        rhs = 2 * joint_count
        return (member_count, reaction_count, lhs, rhs)

    def _evaluation_waiting_message(self) -> str:
        """Build the status message shown while under-determined."""
        member_count, reaction_count, lhs, rhs = self._determinacy_values()
        lines = [
            "Evaluation disabled while the truss is under-determined.",
            f"determinacy: m + r = {lhs} (m={member_count}, r={reaction_count}); 2j = {rhs}",
        ]
        return "\n".join(lines)

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._joint_canvas_positions = {}
        self._member_canvas_segments = {}
        x_min, x_max, y_min, y_max = self.state.design_bounds

        # Outer bounds and centerline.
        p0 = self._world_to_canvas(x_min, y_min)
        p1 = self._world_to_canvas(x_max, y_max)
        self.canvas.create_rectangle(p0[0], p1[1], p1[0], p0[1], outline="#9aa6b2")
        axis_start = self._world_to_canvas(x_min, 0.0)
        axis_end = self._world_to_canvas(x_max, 0.0)
        self.canvas.create_line(axis_start[0], axis_start[1], axis_end[0], axis_end[1], fill="#d2dbe3")

        joint_by_id = {joint.joint_id: joint for joint in self.state.joints}
        selected_member_id = self._selected_member_id()
        fos_by_member_id: dict[int, float] = {}
        if self._latest_evaluation is not None and (
            len(self._latest_evaluation.fos_by_member) == len(self.state.members)
        ):
            for member, fos_value in zip(self.state.members, self._latest_evaluation.fos_by_member, strict=True):
                fos_by_member_id[member.member_id] = float(fos_value)

        for member in self.state.members:
            start = joint_by_id.get(member.start_joint_id)
            end = joint_by_id.get(member.end_joint_id)
            if start is None or end is None:
                continue
            x0, y0 = self._world_to_canvas(start.x, start.y)
            x1, y1 = self._world_to_canvas(end.x, end.y)
            self._member_canvas_segments[member.member_id] = (x0, y0, x1, y1)
            member_fos_value = fos_by_member_id.get(member.member_id)
            color = self._member_color_for_fos(member_fos_value)
            is_selected = member.member_id == selected_member_id
            width = max(2, int(member.size_index * 0.8))
            if is_selected:
                width += 2
                color = "#f59e0b"
            self.canvas.create_line(x0, y0, x1, y1, fill=color, width=width)
            if member_fos_value is not None:
                label_x = (x0 + x1) / 2.0
                label_y = (y0 + y1) / 2.0 - 10.0
                self.canvas.create_text(
                    label_x,
                    label_y,
                    text=f"FOS {self._format_fos(member_fos_value)}",
                    fill=color,
                    font=("Helvetica", 8),
                )

        for load in self.state.loads:
            joint = joint_by_id.get(load.joint_id)
            if joint is None:
                continue
            self._draw_load_arrow(joint.x, joint.y, load.direction)

        selected_joint_ids = set(self._selected_joint_ids())
        for joint in self.state.joints:
            x_pos, y_pos = self._world_to_canvas(joint.x, joint.y)
            self._joint_canvas_positions[joint.joint_id] = (x_pos, y_pos)
            fill = "#7f8c8d" if joint.is_fixed else "#2563eb"
            is_selected = joint.joint_id in selected_joint_ids
            outline = "#f59e0b" if is_selected else "#0f172a"
            radius = 7 if is_selected else 6
            line_width = 2 if is_selected else 1
            self.canvas.create_oval(
                x_pos - radius,
                y_pos - radius,
                x_pos + radius,
                y_pos + radius,
                fill=fill,
                outline=outline,
                width=line_width,
            )
            self.canvas.create_text(
                x_pos + 12,
                y_pos - 10,
                text=str(joint.joint_id),
                fill="#0f172a",
                font=("Helvetica", 9),
            )

    def _refresh(self) -> None:
        selected_joint_ids = set(self._selected_joint_ids())
        selected_member_id = self._selected_member_id()

        self._joint_index_to_id = [joint.joint_id for joint in self.state.joints]
        self._member_index_to_id = [member.member_id for member in self.state.members]

        self.joint_listbox.delete(0, tk.END)
        for joint in self.state.joints:
            fixed_text = "fixed" if joint.is_fixed else "editable"
            self.joint_listbox.insert(
                tk.END,
                f"J{joint.joint_id}: ({joint.x:.3f}, {joint.y:.3f}) {fixed_text}",
            )
        self.joint_listbox.selection_clear(0, tk.END)
        for index, joint_id in enumerate(self._joint_index_to_id):
            if joint_id in selected_joint_ids:
                self.joint_listbox.selection_set(index)

        self.member_listbox.delete(0, tk.END)
        for member in self.state.members:
            self.member_listbox.insert(
                tk.END,
                f"M{member.member_id}: J{member.start_joint_id}-J{member.end_joint_id} size={member.size_index}",
            )
        self.member_listbox.selection_clear(0, tk.END)
        if selected_member_id is not None:
            for index, member_id in enumerate(self._member_index_to_id):
                if member_id == selected_member_id:
                    self.member_listbox.selection_set(index)
                    break

        for index, value in enumerate(self.state.support_enabled):
            self._support_vars[index].set(value)
        self._reevaluate_state()
        self._draw()

    def _selected_joint_ids(self) -> list[int]:
        selected_indices = (int(index) for index in self.joint_listbox.curselection())
        return [
            self._joint_index_to_id[index] for index in selected_indices if 0 <= index < len(self._joint_index_to_id)
        ]

    def _selected_member_id(self) -> int | None:
        selection = self.member_listbox.curselection()
        if not selection:
            return None
        selected_index = int(selection[0])
        if not (0 <= selected_index < len(self._member_index_to_id)):
            return None
        return self._member_index_to_id[selected_index]

    def _nearest_joint_id(self, canvas_x: float, canvas_y: float) -> int | None:
        """Return nearest joint under one canvas click, using a hit area."""
        best_joint_id: int | None = None
        best_distance_sq = self._joint_hit_radius_px**2
        for joint_id, (joint_x, joint_y) in self._joint_canvas_positions.items():
            distance_sq = (joint_x - canvas_x) ** 2 + (joint_y - canvas_y) ** 2
            if distance_sq <= best_distance_sq:
                best_distance_sq = distance_sq
                best_joint_id = joint_id
        return best_joint_id

    def _distance_sq_to_segment(
        self,
        px: float,
        py: float,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> float:
        """Return squared distance from one point to one line segment."""
        dx = x1 - x0
        dy = y1 - y0
        segment_len_sq = dx * dx + dy * dy
        if segment_len_sq <= 1e-12:
            return (px - x0) ** 2 + (py - y0) ** 2
        projection = ((px - x0) * dx + (py - y0) * dy) / segment_len_sq
        projection = min(1.0, max(0.0, projection))
        nearest_x = x0 + projection * dx
        nearest_y = y0 + projection * dy
        return (px - nearest_x) ** 2 + (py - nearest_y) ** 2

    def _nearest_member_id(self, canvas_x: float, canvas_y: float) -> int | None:
        """Return nearest member under one canvas click, using a hit area."""
        best_member_id: int | None = None
        best_distance_sq = self._member_hit_radius_px**2
        for member_id, (x0, y0, x1, y1) in self._member_canvas_segments.items():
            distance_sq = self._distance_sq_to_segment(canvas_x, canvas_y, x0, y0, x1, y1)
            if distance_sq <= best_distance_sq:
                best_distance_sq = distance_sq
                best_member_id = member_id
        return best_member_id

    def _select_joint_by_id(self, joint_id: int, *, append: bool = False) -> None:
        """Select one joint in the listbox by identifier.

        Args:
            joint_id: Joint identifier to select.
            append: Whether to keep existing selection and toggle this joint.
        """
        target_index = next((index for index, item in enumerate(self._joint_index_to_id) if item == joint_id), None)
        if target_index is None:
            return
        if append:
            if self.joint_listbox.selection_includes(target_index):
                self.joint_listbox.selection_clear(target_index)
            else:
                self.joint_listbox.selection_set(target_index)
        else:
            self.joint_listbox.selection_clear(0, tk.END)
            self.joint_listbox.selection_set(target_index)
        self.joint_listbox.activate(target_index)
        self.joint_listbox.see(target_index)
        self._draw()

    def _select_member_by_id(self, member_id: int) -> None:
        """Select one member in the listbox by identifier."""
        target_index = next((index for index, item in enumerate(self._member_index_to_id) if item == member_id), None)
        if target_index is None:
            return
        self.member_listbox.selection_clear(0, tk.END)
        self.member_listbox.selection_set(target_index)
        self.member_listbox.activate(target_index)
        self.member_listbox.see(target_index)
        self._draw()

    def _is_multiselect_event(self, event: tk.Event[tk.Misc]) -> bool:
        """Return whether one click event requests additive multi-selection.

        Args:
            event: Tk click event.

        Returns:
            ``True`` when the event has a common modifier for additive selection.
        """
        state_bits = int(getattr(event, "state", 0))
        return bool(state_bits & 0x0001 or state_bits & 0x0004 or state_bits & 0x0008)

    def _on_canvas_click(self, event: tk.Event[tk.Misc]) -> None:
        canvas_x = float(event.x)
        canvas_y = float(event.y)
        mode = self.mode_var.get()

        clicked_joint_id = self._nearest_joint_id(canvas_x, canvas_y)
        if clicked_joint_id is not None:
            self._select_joint_by_id(clicked_joint_id, append=self._is_multiselect_event(event))
            if mode == "move_selected_joint":
                # In move mode: clicking a joint selects it; clicking empty space moves it.
                return
            # In add mode: clicking a joint only selects; click empty space to add.
            if mode == "add_joint":
                return

        clicked_member_id = self._nearest_member_id(canvas_x, canvas_y)
        if clicked_member_id is not None:
            self._select_member_by_id(clicked_member_id)
            return

        x_value, y_value = self._canvas_to_world(canvas_x, canvas_y)

        try:
            if mode == "add_joint":
                self.state = self.problem.add_joint(self.state, x=x_value, y=y_value)
            elif mode == "move_selected_joint":
                selected = self._selected_joint_ids()
                if len(selected) != 1:
                    raise ValueError("Select exactly one joint to move.")
                self.state = self.problem.move_joint(self.state, joint_id=selected[0], x=x_value, y=y_value)
            else:
                raise ValueError(f"Unsupported mode: {mode}")
        except Exception as exc:
            messagebox.showerror("Action failed", str(exc))
            return

        self._refresh()

    def _add_member(self) -> None:
        selected = self._selected_joint_ids()
        if len(selected) != 2:
            messagebox.showerror("Invalid selection", "Select exactly two joints to create one member.")
            return
        try:
            size_index = int(self.member_size_var.get())
            self.state = self.problem.add_member(
                self.state,
                start_joint_id=selected[0],
                end_joint_id=selected[1],
                size_index=size_index,
            )
        except Exception as exc:
            messagebox.showerror("Add member failed", str(exc))
            return
        self._refresh()

    def _resize_member(self) -> None:
        member_id = self._selected_member_id()
        if member_id is None:
            messagebox.showerror("Invalid selection", "Select one member to resize.")
            return
        try:
            size_index = int(self.member_size_var.get())
            self.state = self.problem.set_member_size(self.state, member_id=member_id, size_index=size_index)
        except Exception as exc:
            messagebox.showerror("Resize failed", str(exc))
            return
        self._refresh()

    def _delete_member(self) -> None:
        member_id = self._selected_member_id()
        if member_id is None:
            messagebox.showerror("Invalid selection", "Select one member to delete.")
            return
        try:
            self.state = self.problem.delete_member(self.state, member_id=member_id)
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self._refresh()

    def _delete_joint(self) -> None:
        selected = self._selected_joint_ids()
        if len(selected) != 1:
            messagebox.showerror("Invalid selection", "Select exactly one joint to delete.")
            return
        try:
            self.state = self.problem.delete_joint(self.state, joint_id=selected[0])
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self._refresh()

    def _apply_support_toggles(self) -> None:
        try:
            updated = self.state
            for support_id in range(1, len(self._support_vars) + 1):
                updated = self.problem.set_support_enabled(
                    updated,
                    support_id=support_id,
                    enabled=self._support_vars[support_id - 1].get(),
                )
            self.state = updated
        except Exception as exc:
            messagebox.showerror("Support update failed", str(exc))
            return
        self._refresh()

    def _set_load(self) -> None:
        selected = self._selected_joint_ids()
        if len(selected) != 1:
            messagebox.showerror("Invalid selection", "Select exactly one joint to set a load.")
            return

        try:
            direction_raw = self.load_direction_var.get()
            if direction_raw not in {"left", "down", "right", "up"}:
                raise ValueError("Load direction must be one of left, down, right, or up.")
            direction = cast(TrussLoadDirection, direction_raw)
            magnitude = float(self.load_magnitude_var.get())
            self.state = self.problem.set_load(
                self.state,
                joint_id=selected[0],
                direction=direction,
                magnitude_n=magnitude,
            )
        except Exception as exc:
            messagebox.showerror("Set load failed", str(exc))
            return
        self._refresh()

    def _clear_load(self) -> None:
        selected = self._selected_joint_ids()
        if len(selected) != 1:
            messagebox.showerror("Invalid selection", "Select exactly one joint to clear a load.")
            return

        try:
            direction_raw = self.load_direction_var.get()
            if direction_raw not in {"left", "down", "right", "up"}:
                raise ValueError("Load direction must be one of left, down, right, or up.")
            direction = cast(TrussLoadDirection, direction_raw)
            self.state = self.problem.clear_load(self.state, joint_id=selected[0], direction=direction)
        except Exception as exc:
            messagebox.showerror("Clear load failed", str(exc))
            return
        self._refresh()

    def _reevaluate_state(self) -> None:
        """Run one evaluation pass and update cached metrics/overlay data."""
        _member_count, _reaction_count, lhs, rhs = self._determinacy_values()
        if lhs < rhs:
            self._latest_evaluation = None
            self.metrics_var.set(self._evaluation_waiting_message())
            return

        try:
            evaluation = self.problem.evaluate(self.state)
        except Exception as exc:
            self._latest_evaluation = None
            self.metrics_var.set(f"evaluation_error: {exc}")
            return

        if (
            evaluation.is_stable
            and evaluation.failure_reason is None
            and len(evaluation.fos_by_member) == len(self.state.members)
        ):
            self._latest_evaluation = evaluation
        else:
            self._latest_evaluation = None
        lines = [
            f"mass_kg: {evaluation.mass_kg:.3f}",
            f"min_fos: {evaluation.min_fos:.3f}",
            f"is_stable: {evaluation.is_stable}",
            f"is_acceptable: {evaluation.is_acceptable}",
            f"joints: {evaluation.joint_count}",
            f"members: {evaluation.member_count}",
        ]
        if evaluation.failure_reason:
            lines.append(f"reason: {evaluation.failure_reason}")
        self.metrics_var.set("\n".join(lines))

    def _evaluate(self) -> None:
        """Re-run evaluation on demand (auto-runs after every edit too)."""
        self._reevaluate_state()
        self._draw()


def main() -> None:
    """Launch the truss-analysis GUI directly."""
    root = tk.Tk()
    root.geometry("1260x640")
    TrussAPApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
