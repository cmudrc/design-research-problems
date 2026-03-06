"""Tkinter GUI for interactive IoT home cooling-system co-design."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from design_research_problems import get_problem
from design_research_problems.problems._domains.iot_home import IoTHomeProduct, find_iot_room_id


class IoTHomeCoolingApp:
    """Near-native Tkinter front-end for the IoT cooling grammar problem."""

    def __init__(self, root: tk.Tk) -> None:
        """Initialize the IoT GUI with the packaged grammar backend.

        Args:
            root: Tk root window.
        """
        self.root = root
        self.root.title("IoT Home Cooling Co-Design")
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
        self._last_canvas_size: tuple[int, int] = (0, 0)
        self._product_canvas_positions: dict[str, tuple[float, float]] = {}
        self._product_hit_radius_px = 12.0

        self._build_layout()
        self.root.after_idle(self._refresh)

    def _build_layout(self) -> None:
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(main)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = ttk.Frame(main)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=(10, 0))

        self.canvas = tk.Canvas(left, width=920, height=560, background="#f7f7f7", highlightthickness=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
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
        self.product_listbox = tk.Listbox(right, height=12, width=34, selectmode=tk.EXTENDED, exportselection=False)
        self.product_listbox.pack(anchor=tk.W, fill=tk.X)
        self.product_listbox.bind("<<ListboxSelect>>", self._on_product_list_selection)

        ttk.Label(right, text="Links").pack(anchor=tk.W, pady=(8, 0))
        self.link_listbox = tk.Listbox(right, height=8, width=34, exportselection=False)
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
        ttk.Button(right, text="Evaluate", command=self._evaluate).pack(anchor=tk.W)
        self.metrics_var = tk.StringVar(value="No evaluation yet.")
        ttk.Label(right, textvariable=self.metrics_var, justify=tk.LEFT).pack(anchor=tk.W, pady=(6, 0))

        instructions = (
            "Click on the house map to add/move depending on mode.\n"
            "Processors can be placed outside; coolers must be inside."
        )
        ttk.Label(right, text=instructions, wraplength=260, justify=tk.LEFT).pack(anchor=tk.W, pady=(10, 0))

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

    def _world_to_canvas(self, x_value: float, y_value: float) -> tuple[float, float]:
        min_x, max_x, min_y, max_y = self._world_bounds()
        width = max(self.canvas.winfo_width(), 200)
        height = max(self.canvas.winfo_height(), 200)
        margin = 20.0
        scale_x = (width - 2.0 * margin) / (max_x - min_x)
        scale_y = (height - 2.0 * margin) / (max_y - min_y)
        canvas_x = margin + (x_value - min_x) * scale_x
        canvas_y = height - margin - (y_value - min_y) * scale_y
        return (canvas_x, canvas_y)

    def _canvas_to_world(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        min_x, max_x, min_y, max_y = self._world_bounds()
        width = max(self.canvas.winfo_width(), 200)
        height = max(self.canvas.winfo_height(), 200)
        margin = 20.0
        scale_x = (width - 2.0 * margin) / (max_x - min_x)
        scale_y = (height - 2.0 * margin) / (max_y - min_y)
        world_x = min_x + (canvas_x - margin) / scale_x
        world_y = min_y + (height - margin - canvas_y) / scale_y
        return (world_x, world_y)

    def _draw(self) -> None:
        self.canvas.delete("all")
        self._product_canvas_positions = {}

        for room in self.state.house_geometry.rooms:
            points: list[float] = []
            for x_value, y_value in zip(room.x, room.y, strict=True):
                cx, cy = self._world_to_canvas(x_value, y_value)
                points.extend([cx, cy])
            self.canvas.create_polygon(points, fill="#dde8f2", outline="#5b6a7a", width=1)
            center_x = sum(room.x) / len(room.x)
            center_y = sum(room.y) / len(room.y)
            cx, cy = self._world_to_canvas(center_x, center_y)
            self.canvas.create_text(cx, cy, text=room.name, font=("Helvetica", 9), fill="#324150")

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
        if not append:
            self.product_listbox.selection_clear(0, tk.END)
        self.product_listbox.selection_set(target_index)
        self.product_listbox.activate(target_index)
        self.product_listbox.see(target_index)
        product = next((entry for entry in self.state.products if entry.name == product_name), None)
        if isinstance(product, IoTHomeProduct) and product.product_type == "d":
            self.processor_var.set(product.name)
        self._draw()

    def _on_canvas_click(self, event: tk.Event[tk.Misc]) -> None:
        canvas_x = float(event.x)
        canvas_y = float(event.y)
        mode = self.mode_var.get()

        clicked_product_name = self._nearest_product_name(canvas_x, canvas_y)
        if clicked_product_name is not None:
            multi_select = bool(int(getattr(event, "state", 0)) & 0x0001)
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

    def _evaluate(self) -> None:
        try:
            evaluation = self.problem.evaluate(self.state)
        except Exception as exc:
            messagebox.showerror("Evaluation failed", str(exc))
            return

        hottest_room = max(
            (
                find_iot_room_id(self.state.house_geometry, product.x, product.y)
                for product in self.state.products
                if product.product_type in {"s", "e"}
            ),
            default=0,
        )
        self.metrics_var.set(
            "\n".join(
                (
                    f"total_cost: {evaluation.total_cost:.3f}",
                    f"peak_temp_c: {evaluation.peak_temp_c:.3f}",
                    f"capital_cost: {evaluation.capital_cost:.3f}",
                    f"operation_cost: {evaluation.operation_cost:.3f}",
                    f"mapped_sensor_or_cooler_room: {hottest_room}",
                )
            )
        )


def main() -> None:
    """Launch the IoT home cooling GUI directly."""
    root = tk.Tk()
    root.geometry("1250x620")
    IoTHomeCoolingApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
