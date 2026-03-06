"""Tkinter GUI for MATLAB Truss Analysis Program-style design workflows."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from design_research_problems import get_problem


class TrussAPApp:
    """Near-native Tkinter front-end for truss grammar design."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the truss GUI with the packaged grammar backend.

        Args:
            root: Tk root window.
        """
        self.root = root
        self.root.title("Truss Analysis Program Co-Design")
        self.problem = get_problem("truss_analysis_program_design")
        self.state = self.problem.initial_state()

        self.mode_var = tk.StringVar(value="add_joint")
        self.member_size_var = tk.StringVar(value="5")
        self.load_direction_var = tk.StringVar(value="down")
        self.load_magnitude_var = tk.StringVar(value="200000")

        self._joint_index_to_id: list[int] = []
        self._member_index_to_id: list[int] = []
        self._support_vars = [tk.BooleanVar(value=True), tk.BooleanVar(value=True), tk.BooleanVar(value=True)]

        self._build_layout()
        self._refresh()

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        self.canvas = tk.Canvas(left, width=920, height=560, background="#f6f8fb", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self._on_canvas_click)

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

        ttk.Label(right, text="Members").pack(anchor=tk.W, pady=(8, 0))
        self.member_listbox = tk.Listbox(right, height=10, width=36, exportselection=False)
        self.member_listbox.pack(anchor=tk.W, fill=tk.X)

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
        ttk.Button(right, text="Evaluate", command=self._evaluate).pack(anchor=tk.W)
        self.metrics_var = tk.StringVar(value="No evaluation yet.")
        ttk.Label(right, textvariable=self.metrics_var, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        hint = "Select joints/members from the lists; click canvas to add or move joints."
        ttk.Label(right, text=hint, wraplength=280, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

    def _world_to_canvas(self, x_value: float, y_value: float) -> tuple[float, float]:
        x_min, x_max, y_min, y_max = self.state.design_bounds
        width = max(self.canvas.winfo_width(), 200)
        height = max(self.canvas.winfo_height(), 200)
        margin = 20.0
        scale_x = (width - 2.0 * margin) / (x_max - x_min)
        scale_y = (height - 2.0 * margin) / (y_max - y_min)
        canvas_x = margin + (x_value - x_min) * scale_x
        canvas_y = height - margin - (y_value - y_min) * scale_y
        return (canvas_x, canvas_y)

    def _canvas_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        x_min, x_max, y_min, y_max = self.state.design_bounds
        width = max(self.canvas.winfo_width(), 200)
        height = max(self.canvas.winfo_height(), 200)
        margin = 20.0
        scale_x = (width - 2.0 * margin) / (x_max - x_min)
        scale_y = (height - 2.0 * margin) / (y_max - y_min)
        world_x = x_min + (canvas_x - margin) / scale_x
        world_y = y_min + (height - margin - canvas_y) / scale_y
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

    def _draw(self) -> None:
        self.canvas.delete("all")
        x_min, x_max, y_min, y_max = self.state.design_bounds

        # Outer bounds and centerline.
        p0 = self._world_to_canvas(x_min, y_min)
        p1 = self._world_to_canvas(x_max, y_max)
        self.canvas.create_rectangle(p0[0], p1[1], p1[0], p0[1], outline="#9aa6b2")
        axis_start = self._world_to_canvas(x_min, 0.0)
        axis_end = self._world_to_canvas(x_max, 0.0)
        self.canvas.create_line(axis_start[0], axis_start[1], axis_end[0], axis_end[1], fill="#d2dbe3")

        joint_by_id = {joint.joint_id: joint for joint in self.state.joints}

        for member in self.state.members:
            start = joint_by_id.get(member.start_joint_id)
            end = joint_by_id.get(member.end_joint_id)
            if start is None or end is None:
                continue
            x0, y0 = self._world_to_canvas(start.x, start.y)
            x1, y1 = self._world_to_canvas(end.x, end.y)
            self.canvas.create_line(x0, y0, x1, y1, fill="#1f2d3d", width=max(1, int(member.size_index * 0.8)))

        for load in self.state.loads:
            joint = joint_by_id.get(load.joint_id)
            if joint is None:
                continue
            self._draw_load_arrow(joint.x, joint.y, load.direction)

        for joint in self.state.joints:
            x_pos, y_pos = self._world_to_canvas(joint.x, joint.y)
            fill = "#7f8c8d" if joint.is_fixed else "#2563eb"
            self.canvas.create_oval(x_pos - 6, y_pos - 6, x_pos + 6, y_pos + 6, fill=fill, outline="#0f172a")
            self.canvas.create_text(
                x_pos + 12,
                y_pos - 10,
                text=str(joint.joint_id),
                fill="#0f172a",
                font=("Helvetica", 9),
            )

    def _refresh(self) -> None:
        self._draw()
        self._joint_index_to_id = [joint.joint_id for joint in self.state.joints]
        self._member_index_to_id = [member.member_id for member in self.state.members]

        self.joint_listbox.delete(0, tk.END)
        for joint in self.state.joints:
            fixed_text = "fixed" if joint.is_fixed else "editable"
            self.joint_listbox.insert(
                tk.END,
                f"J{joint.joint_id}: ({joint.x:.3f}, {joint.y:.3f}) {fixed_text}",
            )

        self.member_listbox.delete(0, tk.END)
        for member in self.state.members:
            self.member_listbox.insert(
                tk.END,
                f"M{member.member_id}: J{member.start_joint_id}-J{member.end_joint_id} size={member.size_index}",
            )

        for index, value in enumerate(self.state.support_enabled):
            self._support_vars[index].set(value)

    def _selected_joint_ids(self) -> list[int]:
        return [self._joint_index_to_id[index] for index in self.joint_listbox.curselection()]

    def _selected_member_id(self) -> int | None:
        selection = self.member_listbox.curselection()
        if not selection:
            return None
        return self._member_index_to_id[selection[0]]

    def _on_canvas_click(self, event: tk.Event[tk.Misc]) -> None:
        x_value, y_value = self._canvas_to_world(float(event.x), float(event.y))
        mode = self.mode_var.get()

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
            direction = self.load_direction_var.get()
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
            direction = self.load_direction_var.get()
            self.state = self.problem.clear_load(self.state, joint_id=selected[0], direction=direction)
        except Exception as exc:
            messagebox.showerror("Clear load failed", str(exc))
            return
        self._refresh()

    def _evaluate(self) -> None:
        try:
            evaluation = self.problem.evaluate(self.state)
        except Exception as exc:
            messagebox.showerror("Evaluation failed", str(exc))
            return

        self.metrics_var.set(
            "\n".join(
                (
                    f"mass_kg: {evaluation.mass_kg:.3f}",
                    f"min_fos: {evaluation.min_fos:.3f}",
                    f"is_stable: {evaluation.is_stable}",
                    f"is_acceptable: {evaluation.is_acceptable}",
                    f"joints: {evaluation.joint_count}",
                    f"members: {evaluation.member_count}",
                )
            )
        )


def main() -> None:
    """Launch the truss-analysis GUI directly."""
    root = tk.Tk()
    root.geometry("1260x640")
    TrussAPApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
