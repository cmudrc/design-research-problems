"""Tkinter GUI for interactive IoT home cooling-system."""

from __future__ import annotations

import math
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from design_research_problems import get_problem
from design_research_problems.gui._tk_shared import (
    CanvasResizeGuard,
    ViewportTransform,
    build_canvas_sidebar_layout,
    fit_window_to_content,
    is_additive_multiselect_event,
    keep_sidebar_content_width,
    run_evaluation_cycle,
    update_sidebar_scrollregion,
    viewport_from_canvas,
)
from design_research_problems.problems._domains.iot_home import IoTHomeEvaluation, IoTHomeProduct


class IoTHomeCoolingApp:
    """Near-native Tkinter front-end for the IoT cooling grammar problem."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the IoT GUI with the packaged grammar backend.

        Args:
            root: Tk root window.
        """
        self.root = root
        self.root.title("IoT Home Cooling")
        self.root.minsize(980, 620)
        self._compact_sidebar = self.root.winfo_screenheight() <= 1000
        self.problem = get_problem("iot_home_cooling_system_design")
        self.state = self.problem.initial_state()
        self._btus_options = tuple(int(value) for value in self.problem.cooler_btus_options)
        self._cfm_options = tuple(int(value) for value in self.problem.cooler_cfm_options)

        self.mode_var = tk.StringVar(value="add_processor")
        self.processor_var = tk.StringVar(value="")
        self.btus_var = tk.StringVar(value=str(int(self.problem.default_cooler_btus)))
        self.cfm_var = tk.StringVar(value=str(int(self.problem.default_cooler_cfm)))

        self._product_index_to_name: list[str] = []
        self._link_index_to_name: list[str] = []
        self._resize_guard = CanvasResizeGuard()
        self._product_canvas_positions: dict[str, tuple[float, float]] = {}
        self._product_hit_radius_px = 12.0
        self._latest_evaluation: IoTHomeEvaluation | None = None

        self._build_layout()
        self.root.after_idle(self._initialize_view)

    def _initialize_view(self) -> None:
        """Run first refresh, then size window to fit rendered sidebar content."""
        self._refresh()
        self.root.update_idletasks()
        sidebar_height = self._sidebar_content.winfo_reqheight() + 24
        fit_window_to_content(
            self.root,
            preferred_width=1250,
            preferred_height=max(760, sidebar_height),
            min_width=980,
            min_height=620,
            screen_margin_y=40,
        )

    def _build_layout(self) -> None:
        layout = build_canvas_sidebar_layout(
            self.root,
            sidebar_width=330,
            canvas_width=920,
            canvas_height=560,
            canvas_background="#f7f7f7",
        )
        self.canvas = layout.canvas
        self.sidebar_canvas = layout.sidebar_canvas
        self._sidebar_window_id = layout.sidebar_window_id
        right = layout.right
        self._sidebar_content = right

        right.bind("<Configure>", self._on_sidebar_content_configure)
        self.sidebar_canvas.bind("<Configure>", self._on_sidebar_canvas_configure)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        ttk.Label(right, text="Mode").pack(anchor=tk.W)
        mode_combo = ttk.Combobox(
            right,
            textvariable=self.mode_var,
            state="readonly",
            values=("add_processor", "add_sensor", "add_cooler", "move_selected"),
            width=22,
        )
        mode_combo.pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right, text="Processor (for sensor/cooler)").pack(anchor=tk.W)
        self.processor_combo = ttk.Combobox(right, textvariable=self.processor_var, state="readonly", width=22)
        self.processor_combo.pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right, text="Cooler BTU/h").pack(anchor=tk.W)
        ttk.Combobox(
            right,
            textvariable=self.btus_var,
            state="readonly",
            width=10,
            values=tuple(str(value) for value in self._btus_options),
        ).pack(anchor=tk.W)

        ttk.Label(right, text="Cooler CFM").pack(anchor=tk.W)
        ttk.Combobox(
            right,
            textvariable=self.cfm_var,
            state="readonly",
            width=10,
            values=tuple(str(value) for value in self._cfm_options),
        ).pack(anchor=tk.W, pady=(0, 8))

        ttk.Label(right, text="Products").pack(anchor=tk.W)
        product_list_height = 9 if self._compact_sidebar else 12
        self.product_listbox = tk.Listbox(
            right,
            height=product_list_height,
            width=34,
            selectmode=tk.EXTENDED,
            exportselection=False,
        )
        self.product_listbox.pack(anchor=tk.W, fill=tk.X)
        self.product_listbox.bind("<<ListboxSelect>>", self._on_product_list_selection)

        ttk.Label(right, text="Links").pack(anchor=tk.W, pady=(8, 0))
        link_list_height = 6 if self._compact_sidebar else 8
        self.link_listbox = tk.Listbox(right, height=link_list_height, width=34, exportselection=False)
        self.link_listbox.pack(anchor=tk.W, fill=tk.X)

        ttk.Button(right, text="Add Link (2 selected products)", command=self._add_link_from_selection).pack(
            anchor=tk.W, pady=(8, 0)
        )
        ttk.Button(
            right,
            text="Delete Selected Product",
            command=self._delete_selected_product,
        ).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(
            right,
            text="Delete Selected Link",
            command=self._delete_selected_link,
        ).pack(anchor=tk.W, pady=(6, 0))
        ttk.Button(
            right,
            text="Tune Selected Cooler",
            command=self._tune_selected_cooler,
        ).pack(anchor=tk.W, pady=(6, 0))

        ttk.Separator(right).pack(fill=tk.X, pady=10)
        ttk.Button(right, text="Re-evaluate now", command=self._evaluate).pack(anchor=tk.W)
        self.metrics_var = tk.StringVar(value="No evaluation yet.")
        ttk.Label(right, textvariable=self.metrics_var, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        instructions = (
            "Click on the house map to add/move depending on mode.\n"
            "Processors can be placed outside; coolers must be inside.\n"
            "Room colors and labels reflect evaluated temperature."
        )
        ttk.Label(right, text=instructions, wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

    def _on_sidebar_content_configure(self, _event: tk.Event[tk.Misc]) -> None:
        """Update sidebar scroll range when content height changes."""
        update_sidebar_scrollregion(self.sidebar_canvas)

    def _on_sidebar_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """Keep sidebar content width equal to the visible canvas width."""
        width = int(getattr(event, "width", 0))
        keep_sidebar_content_width(self.sidebar_canvas, self._sidebar_window_id, width)

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """Redraw when canvas dimensions change to keep initial scaling stable."""
        self._resize_guard.handle_configure(event, self._draw)

    def _on_product_list_selection(self, _event: tk.Event[tk.Misc]) -> None:
        """Refresh visual highlight when product selection changes."""
        selected = self._selected_product_names()
        if len(selected) == 1:
            product = next((entry for entry in self.state.products if entry.name == selected[0]), None)
            if isinstance(product, IoTHomeProduct) and product.product_type == "d":
                self.processor_var.set(product.name)
        self._draw()

    def _world_bounds(self) -> tuple[float, float, float, float]:
        room_x = [x for room in self.state.house_geometry.rooms for x in room.x]
        room_y = [y for room in self.state.house_geometry.rooms for y in room.y]
        product_x = [product.x for product in self.state.products]
        product_y = [product.y for product in self.state.products]
        xs = room_x + product_x + [-16.0, 81.0]
        ys = room_y + product_y + [-2.0, 50.0]
        return (min(xs), max(xs), min(ys), max(ys))

    def _viewport_transform(self) -> ViewportTransform:
        """Return scale/offset terms for an aspect-preserving world-to-canvas map."""
        return viewport_from_canvas(self._world_bounds(), self.canvas)

    def _world_to_canvas(self, x_value: float, y_value: float) -> tuple[float, float]:
        return self._viewport_transform().world_to_canvas(x_value, y_value)

    def _canvas_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        return self._viewport_transform().canvas_to_world(canvas_x, canvas_y)

    def _temperature_to_color(self, temperature_c: float | None) -> str:
        """Map one room temperature to a blue-to-red fill color."""
        if temperature_c is None or not math.isfinite(temperature_c):
            return "#dde8f2"
        min_temp = 16.0
        max_temp = 34.0
        clamped = min(max(temperature_c, min_temp), max_temp)
        ratio = (clamped - min_temp) / (max_temp - min_temp)
        cold_rgb = (59, 130, 246)
        hot_rgb = (239, 68, 68)
        red = round(cold_rgb[0] + ratio * (hot_rgb[0] - cold_rgb[0]))
        green = round(cold_rgb[1] + ratio * (hot_rgb[1] - cold_rgb[1]))
        blue = round(cold_rgb[2] + ratio * (hot_rgb[2] - cold_rgb[2]))
        return f"#{red:02x}{green:02x}{blue:02x}"

    def _room_temperatures_by_id(self) -> dict[int, float]:
        """Return evaluated room temperatures keyed by room id."""
        if self._latest_evaluation is None:
            return {}
        values = self._latest_evaluation.room_temperatures_c
        if len(values) != len(self.state.house_geometry.rooms):
            return {}
        return {room.room_id: float(values[room.room_id - 1]) for room in self.state.house_geometry.rooms}

    def _draw_temperature_legend(self) -> None:
        """Draw a continuous room-temperature colorbar in canvas coordinates."""
        x0 = 12
        y0 = 12
        self.canvas.create_text(
            x0,
            y0,
            text="Room temp (C)",
            anchor=tk.NW,
            fill="#111827",
            font=("Helvetica", 9, "bold"),
        )
        min_temp_c = 16.0
        max_temp_c = 34.0
        bar_top = y0 + 20
        bar_height = 138
        bar_width = 16
        steps = 69
        step_height = bar_height / steps

        for step in range(steps):
            y_start = bar_top + step * step_height
            y_end = bar_top + (step + 1) * step_height
            fraction_from_top = (step + 0.5) / steps
            temperature_c = max_temp_c - fraction_from_top * (max_temp_c - min_temp_c)
            color = self._temperature_to_color(temperature_c)
            self.canvas.create_rectangle(x0, y_start, x0 + bar_width, y_end, fill=color, outline=color)

        self.canvas.create_rectangle(
            x0,
            bar_top,
            x0 + bar_width,
            bar_top + bar_height,
            outline="#374151",
            width=1,
        )

        ticks_c = (34.0, 30.0, 26.0, 22.0, 18.0, 16.0)
        for tick_c in ticks_c:
            ratio = (max_temp_c - tick_c) / (max_temp_c - min_temp_c)
            tick_y = bar_top + ratio * bar_height
            self.canvas.create_line(x0 + bar_width, tick_y, x0 + bar_width + 4, tick_y, fill="#374151", width=1)
            self.canvas.create_text(
                x0 + bar_width + 8,
                tick_y,
                text=f"{tick_c:.0f}",
                anchor=tk.W,
                fill="#111827",
                font=("Helvetica", 8),
            )

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._product_canvas_positions = {}
        room_temperatures = self._room_temperatures_by_id()

        for room in self.state.house_geometry.rooms:
            points: list[float] = []
            for x_value, y_value in zip(room.x, room.y, strict=True):
                cx, cy = self._world_to_canvas(x_value, y_value)
                points.extend([cx, cy])
            room_temp = room_temperatures.get(room.room_id)
            self.canvas.create_polygon(
                points,
                fill=self._temperature_to_color(room_temp),
                outline="#5b6a7a",
                width=1,
            )
            center_x = sum(room.x) / len(room.x)
            center_y = sum(room.y) / len(room.y)
            cx, cy = self._world_to_canvas(center_x, center_y)
            room_label = room.name if room_temp is None else f"{room.name}\n{room_temp:.1f} C"
            self.canvas.create_text(cx, cy, text=room_label, font=("Helvetica", 8), fill="#1f2937")

        product_by_name = {product.name: product for product in self.state.products}
        for link in self.state.links:
            init_product = product_by_name.get(link.init_name)
            term_product = product_by_name.get(link.term_name)
            if init_product is None or term_product is None:
                continue
            x0, y0 = self._world_to_canvas(init_product.x, init_product.y)
            x1, y1 = self._world_to_canvas(term_product.x, term_product.y)
            self.canvas.create_line(x0, y0, x1, y1, fill="#444", width=1)

        colors = {"d": "#1951a5", "s": "#1f8a5b", "e": "#cf5d1b", "j": "#7d3c98"}
        labels = {"d": "P", "s": "S", "e": "C", "j": "J"}
        selected_names = set(self._selected_product_names())
        for product in self.state.products:
            cx, cy = self._world_to_canvas(product.x, product.y)
            self._product_canvas_positions[product.name] = (cx, cy)
            color = colors.get(product.product_type, "#333")
            is_selected = product.name in selected_names
            outline = "#f59e0b" if is_selected else "#111"
            radius = 7 if is_selected else 6
            line_width = 2 if is_selected else 1
            self.canvas.create_oval(
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill=color,
                outline=outline,
                width=line_width,
            )
            self.canvas.create_text(cx, cy - 12, text=product.name, font=("Helvetica", 8), fill="#111")
            self.canvas.create_text(
                cx,
                cy + 12,
                text=labels.get(product.product_type, "?"),
                font=("Helvetica", 8),
                fill="#111",
            )
        if room_temperatures:
            self._draw_temperature_legend()

    def _refresh(self) -> None:
        selected_product_names = set(self._selected_product_names())
        selected_link_name = self._selected_link_name()

        self._product_index_to_name = [product.name for product in self.state.products]
        self._link_index_to_name = [link.name for link in self.state.links]

        self.product_listbox.delete(0, tk.END)
        for product in self.state.products:
            room_text = "outside" if (product.room_id or 0) == 0 else f"room {product.room_id}"
            self.product_listbox.insert(
                tk.END,
                f"{product.name} ({product.product_type}) @ ({product.x:.2f}, {product.y:.2f}) {room_text}",
            )
        self.product_listbox.selection_clear(0, tk.END)
        for index, product_name in enumerate(self._product_index_to_name):
            if product_name in selected_product_names:
                self.product_listbox.selection_set(index)

        self.link_listbox.delete(0, tk.END)
        for link in self.state.links:
            self.link_listbox.insert(tk.END, f"{link.name}: {link.init_name} <-> {link.term_name}")
        self.link_listbox.selection_clear(0, tk.END)
        if selected_link_name is not None:
            for index, link_name in enumerate(self._link_index_to_name):
                if link_name == selected_link_name:
                    self.link_listbox.selection_set(index)
                    break

        processors = [product.name for product in self.state.products if product.product_type == "d"]
        self.processor_combo["values"] = processors
        if processors and self.processor_var.get() not in processors:
            self.processor_var.set(processors[0])
        if not processors:
            self.processor_var.set("")
        self._reevaluate_state()
        self._draw()

    def _selected_product_names(self) -> list[str]:
        selected_indices = (int(index) for index in self.product_listbox.curselection())
        return [
            self._product_index_to_name[index]
            for index in selected_indices
            if 0 <= index < len(self._product_index_to_name)
        ]

    def _selected_link_name(self) -> str | None:
        selection = self.link_listbox.curselection()
        if not selection:
            return None
        selected_index = int(selection[0])
        if not (0 <= selected_index < len(self._link_index_to_name)):
            return None
        return self._link_index_to_name[selected_index]

    def _nearest_product_name(self, canvas_x: float, canvas_y: float) -> str | None:
        """Return nearest product under one canvas click, using a hit area."""
        best_name: str | None = None
        best_distance_sq = self._product_hit_radius_px**2
        for product_name, (product_x, product_y) in self._product_canvas_positions.items():
            distance_sq = (product_x - canvas_x) ** 2 + (product_y - canvas_y) ** 2
            if distance_sq <= best_distance_sq:
                best_distance_sq = distance_sq
                best_name = product_name
        return best_name

    def _select_product_by_name(self, product_name: str, *, append: bool = False) -> None:
        """Select one product in the listbox by identifier."""
        target_index = next(
            (index for index, item in enumerate(self._product_index_to_name) if item == product_name),
            None,
        )
        if target_index is None:
            return
        if append:
            if self.product_listbox.selection_includes(target_index):
                self.product_listbox.selection_clear(target_index)
            else:
                self.product_listbox.selection_set(target_index)
        else:
            self.product_listbox.selection_clear(0, tk.END)
            self.product_listbox.selection_set(target_index)
        self.product_listbox.activate(target_index)
        self.product_listbox.see(target_index)
        product = next((entry for entry in self.state.products if entry.name == product_name), None)
        if isinstance(product, IoTHomeProduct) and product.product_type == "d":
            self.processor_var.set(product.name)
        self._draw()

    def _is_multiselect_event(self, event: tk.Event[tk.Misc]) -> bool:
        """Return whether one click event requests additive multi-selection."""
        return is_additive_multiselect_event(event)

    def _on_canvas_click(self, event: tk.Event[tk.Misc]) -> None:
        canvas_x = float(event.x)
        canvas_y = float(event.y)
        mode = self.mode_var.get()

        clicked_product_name = self._nearest_product_name(canvas_x, canvas_y)
        if clicked_product_name is not None:
            multi_select = self._is_multiselect_event(event)
            self._select_product_by_name(clicked_product_name, append=multi_select)
            if mode == "move_selected":
                # In move mode: clicking a product selects it; clicking empty space moves it.
                return
            # In add modes: clicking a product only selects; click empty space to add.
            if mode in {"add_processor", "add_sensor", "add_cooler"}:
                return

        world_x, world_y = self._canvas_to_world(canvas_x, canvas_y)

        try:
            if mode == "add_processor":
                self.state = self.problem.add_processor(self.state, x=world_x, y=world_y)
            elif mode == "add_sensor":
                dm_name = self.processor_var.get()
                if not dm_name:
                    raise ValueError("Select a processor before adding a sensor.")
                self.state = self.problem.add_sensor(self.state, dm_name=dm_name, x=world_x, y=world_y)
            elif mode == "add_cooler":
                dm_name = self.processor_var.get()
                if not dm_name:
                    raise ValueError("Select a processor before adding a cooler.")
                self.state = self.problem.add_cooler(
                    self.state,
                    dm_name=dm_name,
                    x=world_x,
                    y=world_y,
                    btus=float(self.btus_var.get()),
                    cfm=float(self.cfm_var.get()),
                )
            elif mode == "move_selected":
                selected = self._selected_product_names()
                if len(selected) != 1:
                    raise ValueError("Select exactly one product to move.")
                self.state = self.problem.move_product(self.state, product_name=selected[0], x=world_x, y=world_y)
            else:
                raise ValueError(f"Unsupported mode: {mode}")
        except Exception as exc:
            messagebox.showerror("Action failed", str(exc))
            return

        self._refresh()

    def _add_link_from_selection(self) -> None:
        selected = self._selected_product_names()
        if len(selected) != 2:
            messagebox.showerror("Invalid selection", "Select exactly two products to link.")
            return
        try:
            self.state = self.problem.add_link(self.state, init_name=selected[0], term_name=selected[1])
        except Exception as exc:
            messagebox.showerror("Add link failed", str(exc))
            return
        self._refresh()

    def _delete_selected_product(self) -> None:
        selected = self._selected_product_names()
        if len(selected) != 1:
            messagebox.showerror("Invalid selection", "Select exactly one product to delete.")
            return
        try:
            self.state = self.problem.delete_product(self.state, product_name=selected[0])
        except Exception as exc:
            messagebox.showerror("Delete failed", str(exc))
            return
        self._refresh()

    def _delete_selected_link(self) -> None:
        link_name = self._selected_link_name()
        if link_name is None:
            messagebox.showerror("Invalid selection", "Select one link to delete.")
            return
        try:
            self.state = self.problem.delete_link(self.state, link_name=link_name)
        except Exception as exc:
            messagebox.showerror("Delete link failed", str(exc))
            return
        self._refresh()

    def _tune_selected_cooler(self) -> None:
        selected = self._selected_product_names()
        if len(selected) != 1:
            messagebox.showerror("Invalid selection", "Select exactly one cooler to tune.")
            return

        product_name = selected[0]
        product = next((entry for entry in self.state.products if entry.name == product_name), None)
        if not isinstance(product, IoTHomeProduct) or product.product_type != "e":
            messagebox.showerror("Invalid selection", "Selected product is not a cooler.")
            return

        btus_value = simpledialog.askinteger(
            "Cooler BTU/h",
            f"BTU/h (allowed: {', '.join(str(value) for value in self._btus_options)}):",
            initialvalue=int(product.btus),
        )
        if btus_value is None:
            return
        cfm_value = simpledialog.askinteger(
            "Cooler CFM",
            f"CFM (allowed: {', '.join(str(value) for value in self._cfm_options)}):",
            initialvalue=int(product.cfm),
        )
        if cfm_value is None:
            return
        if btus_value not in self._btus_options:
            messagebox.showerror("Tune failed", "Selected BTU/h is not one of the supported discrete options.")
            return
        if cfm_value not in self._cfm_options:
            messagebox.showerror("Tune failed", "Selected CFM is not one of the supported discrete options.")
            return

        try:
            self.state = self.problem.tune_cooler(
                self.state,
                cooler_name=product.name,
                btus=float(btus_value),
                cfm=float(cfm_value),
            )
        except Exception as exc:
            messagebox.showerror("Tune failed", str(exc))
            return
        self._refresh()

    def _set_latest_evaluation(self, evaluation: IoTHomeEvaluation | None) -> None:
        """Store one latest evaluation object for overlay drawing and metrics."""
        self._latest_evaluation = evaluation

    def _summarize_evaluation(self, evaluation: IoTHomeEvaluation) -> tuple[IoTHomeEvaluation | None, str]:
        """Return ``(latest_evaluation, metrics_text)`` for one successful evaluate() call."""
        room_temperatures = evaluation.room_temperatures_c
        hottest_room_id = 0
        if room_temperatures:
            hottest_room_id = max(
                range(1, len(room_temperatures) + 1),
                key=lambda room_id: room_temperatures[room_id - 1],
            )

        lines = [
            f"total_cost: {evaluation.total_cost:.3f}",
            f"peak_temp_c: {evaluation.peak_temp_c:.3f}",
            f"capital_cost: {evaluation.capital_cost:.3f}",
            f"operation_cost: {evaluation.operation_cost:.3f}",
            f"discomfort: {evaluation.discomfort:.3f}",
            f"hottest_room_id: {hottest_room_id}",
        ]
        if evaluation.failure_reason:
            lines.append(f"reason: {evaluation.failure_reason}")
        return (evaluation, "\n".join(lines))

    def _reevaluate_state(self) -> None:
        """Run one evaluation pass and update cached metrics/overlay data."""
        run_evaluation_cycle(
            evaluate=lambda: self.problem.evaluate(self.state),
            on_success=self._summarize_evaluation,
            set_latest=self._set_latest_evaluation,
            metrics_var=self.metrics_var,
        )

    def _evaluate(self) -> None:
        """Re-run evaluation on demand (auto-runs after every edit too)."""
        self._reevaluate_state()
        self._draw()


def main() -> None:
    """Launch the IoT home cooling GUI directly."""
    root = tk.Tk()
    root.geometry("1250x620")
    IoTHomeCoolingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
