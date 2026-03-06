"""Grammar problem for IoT home cooling-system co-design."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations
from typing import SupportsFloat, cast

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._domains.iot_home import (
    IoTHomeEvaluation,
    IoTHomeLink,
    IoTHomeProduct,
    IoTHomeState,
    build_default_iot_home_state,
    evaluate_iot_home_state,
    find_iot_room_id,
    iot_link_exists,
    iot_link_pair_is_legal,
    resolve_product_room,
)
from design_research_problems.problems._grammar import GrammarProblem, GrammarTransition
from design_research_problems.problems._metadata import ProblemMetadata


def _coerce_float(value: object) -> float:
    """Convert one manifest value into ``float``.

    Args:
        value: Raw manifest value.

    Returns:
        Float-converted value.
    """
    return float(cast(SupportsFloat, value))


def _coerce_int(value: object) -> int:
    """Convert one manifest value into ``int``.

    Args:
        value: Raw manifest value.

    Returns:
        Int-converted value.
    """
    return int(cast(int, value))


def _coerce_float_tuple(raw_values: object) -> tuple[float, ...]:
    """Convert a manifest value into a tuple of floats.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Tuple of float-converted values.

    Raises:
        TypeError: If the value is not a list/tuple.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of floats.")
    return tuple(_coerce_float(value) for value in raw_values)


def _coerce_points(raw_values: object) -> tuple[tuple[float, float], ...]:
    """Convert a manifest value into fixed placement coordinates.

    Args:
        raw_values: Raw manifest value.

    Returns:
        Tuple of ``(x, y)`` coordinate pairs.

    Raises:
        TypeError: If any point is not a two-value sequence.
    """
    if not isinstance(raw_values, list | tuple):
        raise TypeError("Expected a list or tuple of 2-item coordinate pairs.")
    points: list[tuple[float, float]] = []
    for raw_value in raw_values:
        if not isinstance(raw_value, list | tuple) or len(raw_value) != 2:
            raise TypeError("Each candidate point must contain exactly two values.")
        x_value, y_value = raw_value
        points.append((_coerce_float(x_value), _coerce_float(y_value)))
    return tuple(points)


def _coerce_state(state: object) -> IoTHomeState:
    """Validate that an incoming state is an ``IoTHomeState``.

    Args:
        state: Arbitrary object supplied by a caller.

    Returns:
        Validated IoT home-cooling state.

    Raises:
        TypeError: If ``state`` is not an ``IoTHomeState``.
    """
    if not isinstance(state, IoTHomeState):
        raise TypeError("state must be an IoTHomeState")
    return state


def _with_products(state: IoTHomeState, products: tuple[IoTHomeProduct, ...]) -> IoTHomeState:
    """Return a copy of a state with updated product records.

    Args:
        state: Input state.
        products: Replacement product tuple.

    Returns:
        Updated state.
    """
    return replace(state, products=products)


def _with_links(state: IoTHomeState, links: tuple[IoTHomeLink, ...]) -> IoTHomeState:
    """Return a copy of a state with updated link records.

    Args:
        state: Input state.
        links: Replacement link tuple.

    Returns:
        Updated state.
    """
    return replace(state, links=links)


def _occupancy_key(x: float, y: float) -> tuple[float, float]:
    """Return the canonical occupancy key for one coordinate.

    Args:
        x: x coordinate.
        y: y coordinate.

    Returns:
        Coordinate key tuple.
    """
    return (x, y)


def _next_name(existing_names: set[str], prefix: str) -> str:
    """Return the next deterministic generated name with one prefix.

    Args:
        existing_names: Names already in use.
        prefix: Prefix for the generated identifier.

    Returns:
        Unique generated name.
    """
    max_index = -1
    for name in existing_names:
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix) :]
        if suffix.isdigit():
            max_index = max(max_index, int(suffix))
    candidate = f"{prefix}{max_index + 1}"
    while candidate in existing_names:
        max_index += 1
        candidate = f"{prefix}{max_index + 1}"
    return candidate


class IoTHomeCoolingGrammarProblem(GrammarProblem[IoTHomeState, IoTHomeEvaluation]):
    """Bounded grammar for IoT home cooling-system co-design."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        candidate_points: tuple[tuple[float, float], ...] = (),
        cooler_btus_options: tuple[float, ...] = (5_000.0, 10_000.0, 15_000.0, 20_000.0),
        cooler_cfm_options: tuple[float, ...] = (100.0, 200.0, 300.0, 400.0),
        default_cooler_btus: float = 10_000.0,
        default_cooler_cfm: float = 200.0,
        max_products: int = 32,
    ) -> None:
        """Initialize the IoT home-cooling grammar problem.

        Args:
            metadata: Shared packaged metadata.
            statement_markdown: Human-readable problem statement.
            resource_bundle: Optional package-resource loader.
            candidate_points: Finite placement points for product edits.
            cooler_btus_options: Allowed BTU/h choices for cooler tuning.
            cooler_cfm_options: Allowed CFM choices for cooler tuning.
            default_cooler_btus: Default BTU/h when adding new coolers.
            default_cooler_cfm: Default CFM when adding new coolers.
            max_products: Hard cap for product count during enumeration.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.candidate_points = candidate_points
        self.cooler_btus_options = cooler_btus_options
        self.cooler_cfm_options = cooler_cfm_options
        self.default_cooler_btus = default_cooler_btus
        self.default_cooler_cfm = default_cooler_cfm
        self.max_products = max_products

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> IoTHomeCoolingGrammarProblem:
        """Construct the IoT grammar problem from packaged parameters.

        Args:
            manifest: Parsed packaged manifest.

        Returns:
            Initialized IoT grammar problem.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            candidate_points=_coerce_points(manifest.parameters.get("candidate_points", ())),
            cooler_btus_options=_coerce_float_tuple(
                manifest.parameters.get("cooler_btus_options", (5_000.0, 10_000.0, 15_000.0, 20_000.0))
            ),
            cooler_cfm_options=_coerce_float_tuple(
                manifest.parameters.get("cooler_cfm_options", (100.0, 200.0, 300.0, 400.0))
            ),
            default_cooler_btus=_coerce_float(manifest.parameters.get("default_cooler_btus", 10_000.0)),
            default_cooler_cfm=_coerce_float(manifest.parameters.get("default_cooler_cfm", 200.0)),
            max_products=_coerce_int(manifest.parameters.get("max_products", 32)),
        )

    def initial_state(self) -> IoTHomeState:
        """Return the canonical empty IoT network state.

        Returns:
            Empty IoT home-cooling state.
        """
        return build_default_iot_home_state()

    def evaluate(self, state: IoTHomeState) -> IoTHomeEvaluation:
        """Evaluate one IoT home-cooling design state.

        Args:
            state: Current design state.

        Returns:
            Lifecycle-cost and thermal metrics.
        """
        typed_state = _coerce_state(state)
        return evaluate_iot_home_state(typed_state)

    def enumerate_transitions(self, state: IoTHomeState) -> tuple[GrammarTransition[IoTHomeState], ...]:
        """Return deterministic legal transitions for one IoT design state.

        Args:
            state: Current design state.

        Returns:
            Deterministic legal transitions.
        """
        typed_state = _coerce_state(state)
        transitions: list[GrammarTransition[IoTHomeState]] = []

        occupied_points = {_occupancy_key(product.x, product.y) for product in typed_state.products}
        processors = tuple(product for product in typed_state.products if product.product_type == "d")

        if len(typed_state.products) < self.max_products:
            for x_value, y_value in self.candidate_points:
                if _occupancy_key(x_value, y_value) in occupied_points:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="add_processor",
                        parameters=(("x", x_value), ("y", y_value)),
                        next_state=self.add_processor(typed_state, x=x_value, y=y_value),
                    )
                )

            for processor in processors:
                for x_value, y_value in self.candidate_points:
                    if _occupancy_key(x_value, y_value) in occupied_points:
                        continue
                    transitions.append(
                        GrammarTransition(
                            rule_name="add_sensor",
                            parameters=(("dm_name", processor.name), ("x", x_value), ("y", y_value)),
                            next_state=self.add_sensor(typed_state, dm_name=processor.name, x=x_value, y=y_value),
                        )
                    )
                    room_id = find_iot_room_id(typed_state.house_geometry, x_value, y_value)
                    if room_id == 0:
                        continue
                    transitions.append(
                        GrammarTransition(
                            rule_name="add_cooler",
                            parameters=(
                                ("dm_name", processor.name),
                                ("x", x_value),
                                ("y", y_value),
                                ("btus", self.default_cooler_btus),
                                ("cfm", self.default_cooler_cfm),
                            ),
                            next_state=self.add_cooler(
                                typed_state,
                                dm_name=processor.name,
                                x=x_value,
                                y=y_value,
                                btus=self.default_cooler_btus,
                                cfm=self.default_cooler_cfm,
                            ),
                        )
                    )

        for product in typed_state.products:
            for x_value, y_value in self.candidate_points:
                if _occupancy_key(x_value, y_value) == _occupancy_key(product.x, product.y):
                    continue
                if _occupancy_key(x_value, y_value) in occupied_points:
                    continue
                if product.product_type == "e" and find_iot_room_id(typed_state.house_geometry, x_value, y_value) == 0:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="move_product",
                        parameters=(("product_name", product.name), ("x", x_value), ("y", y_value)),
                        next_state=self.move_product(typed_state, product_name=product.name, x=x_value, y=y_value),
                    )
                )

        for product in typed_state.products:
            transitions.append(
                GrammarTransition(
                    rule_name="delete_product",
                    parameters=(("product_name", product.name),),
                    next_state=self.delete_product(typed_state, product_name=product.name),
                )
            )

        product_by_name = {product.name: product for product in typed_state.products}
        ordered_names = sorted(product_by_name)
        for init_name, term_name in combinations(ordered_names, 2):
            if iot_link_exists(typed_state.links, init_name, term_name):
                continue
            init_type = product_by_name[init_name].product_type
            term_type = product_by_name[term_name].product_type
            if not iot_link_pair_is_legal(init_type, term_type):
                continue
            transitions.append(
                GrammarTransition(
                    rule_name="add_link",
                    parameters=(("init_name", init_name), ("term_name", term_name)),
                    next_state=self.add_link(typed_state, init_name=init_name, term_name=term_name),
                )
            )

        for link in typed_state.links:
            transitions.append(
                GrammarTransition(
                    rule_name="delete_link",
                    parameters=(("link_name", link.name),),
                    next_state=self.delete_link(typed_state, link_name=link.name),
                )
            )

        for product in typed_state.products:
            if product.product_type != "e":
                continue
            for btus_value in self.cooler_btus_options:
                if btus_value == product.btus:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="tune_cooler",
                        parameters=(("cooler_name", product.name), ("btus", btus_value)),
                        next_state=self.tune_cooler(typed_state, cooler_name=product.name, btus=btus_value),
                    )
                )
            for cfm_value in self.cooler_cfm_options:
                if cfm_value == product.cfm:
                    continue
                transitions.append(
                    GrammarTransition(
                        rule_name="tune_cooler",
                        parameters=(("cooler_name", product.name), ("cfm", cfm_value)),
                        next_state=self.tune_cooler(typed_state, cooler_name=product.name, cfm=cfm_value),
                    )
                )

        return tuple(transitions)

    def add_processor(
        self,
        state: IoTHomeState,
        *,
        x: float,
        y: float,
        name: str | None = None,
    ) -> IoTHomeState:
        """Add one processor at a candidate point.

        Args:
            state: Current state.
            x: Processor x coordinate.
            y: Processor y coordinate.
            name: Optional explicit processor name.

        Returns:
            Updated state with one additional processor.

        Raises:
            ValueError: If the name or position is invalid.
        """
        typed_state = _coerce_state(state)
        if any(_occupancy_key(product.x, product.y) == _occupancy_key(x, y) for product in typed_state.products):
            raise ValueError("A product already occupies that location.")

        existing_names = {product.name for product in typed_state.products}
        next_name = _next_name(existing_names, "d") if name is None else name
        if next_name in existing_names:
            raise ValueError("Product name already exists.")

        added = IoTHomeProduct(name=next_name, product_type="d", x=x, y=y)
        return _with_products(typed_state, (*typed_state.products, added))

    def add_sensor(
        self,
        state: IoTHomeState,
        *,
        dm_name: str,
        x: float,
        y: float,
        name: str | None = None,
        link_name: str | None = None,
    ) -> IoTHomeState:
        """Add one sensor and link it to a processor.

        Args:
            state: Current state.
            dm_name: Processor name for the new sensor link.
            x: Sensor x coordinate.
            y: Sensor y coordinate.
            name: Optional explicit sensor name.
            link_name: Optional explicit link name.

        Returns:
            Updated state with one additional sensor and link.

        Raises:
            ValueError: If inputs are invalid.
        """
        typed_state = _coerce_state(state)
        product_by_name = {product.name: product for product in typed_state.products}
        dm = product_by_name.get(dm_name)
        if dm is None or dm.product_type != "d":
            raise ValueError("Sensors must connect to an existing processor.")
        if any(_occupancy_key(product.x, product.y) == _occupancy_key(x, y) for product in typed_state.products):
            raise ValueError("A product already occupies that location.")

        existing_names = {product.name for product in typed_state.products}
        next_name = _next_name(existing_names, "s") if name is None else name
        if next_name in existing_names:
            raise ValueError("Product name already exists.")

        sensor = IoTHomeProduct(name=next_name, product_type="s", x=x, y=y)
        next_state = _with_products(typed_state, (*typed_state.products, resolve_product_room(typed_state, sensor)))
        return self.add_link(next_state, init_name=dm_name, term_name=next_name, link_name=link_name)

    def add_cooler(
        self,
        state: IoTHomeState,
        *,
        dm_name: str,
        x: float,
        y: float,
        btus: float,
        cfm: float,
        name: str | None = None,
        link_name: str | None = None,
    ) -> IoTHomeState:
        """Add one cooler and link it to a processor.

        Args:
            state: Current state.
            dm_name: Processor name for the new cooler link.
            x: Cooler x coordinate.
            y: Cooler y coordinate.
            btus: Cooler BTU/h setting.
            cfm: Cooler CFM setting.
            name: Optional explicit cooler name.
            link_name: Optional explicit link name.

        Returns:
            Updated state with one additional cooler and link.

        Raises:
            ValueError: If inputs are invalid.
        """
        typed_state = _coerce_state(state)
        product_by_name = {product.name: product for product in typed_state.products}
        dm = product_by_name.get(dm_name)
        if dm is None or dm.product_type != "d":
            raise ValueError("Coolers must connect to an existing processor.")
        if any(_occupancy_key(product.x, product.y) == _occupancy_key(x, y) for product in typed_state.products):
            raise ValueError("A product already occupies that location.")

        room_id = find_iot_room_id(typed_state.house_geometry, x, y)
        if room_id == 0:
            raise ValueError("Coolers cannot be placed outside the home.")

        existing_names = {product.name for product in typed_state.products}
        next_name = _next_name(existing_names, "e") if name is None else name
        if next_name in existing_names:
            raise ValueError("Product name already exists.")

        cooler = IoTHomeProduct(
            name=next_name,
            product_type="e",
            x=x,
            y=y,
            room_id=room_id,
            btus=btus,
            cfm=cfm,
        )
        next_state = _with_products(typed_state, (*typed_state.products, cooler))
        return self.add_link(next_state, init_name=dm_name, term_name=next_name, link_name=link_name)

    def move_product(self, state: IoTHomeState, *, product_name: str, x: float, y: float) -> IoTHomeState:
        """Move one product to a new location.

        Args:
            state: Current state.
            product_name: Product to move.
            x: New x coordinate.
            y: New y coordinate.

        Returns:
            Updated state with one moved product.

        Raises:
            ValueError: If the move is invalid.
        """
        typed_state = _coerce_state(state)
        product_index = next(
            (index for index, product in enumerate(typed_state.products) if product.name == product_name),
            None,
        )
        if product_index is None:
            raise ValueError("Unknown product name.")

        for index, product in enumerate(typed_state.products):
            if index == product_index:
                continue
            if _occupancy_key(product.x, product.y) == _occupancy_key(x, y):
                raise ValueError("A product already occupies that location.")

        product = typed_state.products[product_index]
        if product.product_type == "e" and find_iot_room_id(typed_state.house_geometry, x, y) == 0:
            raise ValueError("Coolers cannot be moved outside the home.")

        moved = replace(product, x=x, y=y)
        moved = resolve_product_room(typed_state, moved)
        products = list(typed_state.products)
        products[product_index] = moved
        return _with_products(typed_state, tuple(products))

    def delete_product(self, state: IoTHomeState, *, product_name: str) -> IoTHomeState:
        """Delete one product and clean up connected links.

        Args:
            state: Current state.
            product_name: Product to remove.

        Returns:
            Updated state without the removed product.

        Raises:
            ValueError: If the product is unknown.
        """
        typed_state = _coerce_state(state)
        product_by_name = {product.name: product for product in typed_state.products}
        removed = product_by_name.get(product_name)
        if removed is None:
            raise ValueError("Unknown product name.")

        products = tuple(product for product in typed_state.products if product.name != product_name)
        remaining_product_names = {product.name for product in products}

        kept_links: list[IoTHomeLink] = []
        dm_names: list[str] = []
        other_names: list[str] = []
        for link in typed_state.links:
            if link.init_name == product_name or link.term_name == product_name:
                other_name = link.term_name if link.init_name == product_name else link.init_name
                other_product = product_by_name.get(other_name)
                if other_product is None:
                    continue
                if other_product.product_type == "d":
                    dm_names.append(other_name)
                else:
                    other_names.append(other_name)
                continue
            kept_links.append(link)

        if removed.product_type == "j":
            existing_link_names = {link.name for link in kept_links}
            for dm_name in sorted(set(dm_names)):
                if dm_name not in remaining_product_names:
                    continue
                for other_name in sorted(set(other_names)):
                    if other_name not in remaining_product_names:
                        continue
                    dm_product = next(product for product in products if product.name == dm_name)
                    other_product = next(product for product in products if product.name == other_name)
                    if not iot_link_pair_is_legal(dm_product.product_type, other_product.product_type):
                        continue
                    if iot_link_exists(tuple(kept_links), dm_name, other_name):
                        continue
                    generated_name = f"{dm_name}.{other_name}"
                    if generated_name in existing_link_names:
                        generated_name = _next_name(existing_link_names, "l")
                    kept_links.append(IoTHomeLink(name=generated_name, init_name=dm_name, term_name=other_name))
                    existing_link_names.add(generated_name)

        cleaned_links = tuple(link for link in kept_links if link.init_name in remaining_product_names)
        cleaned_links = tuple(link for link in cleaned_links if link.term_name in remaining_product_names)
        return replace(typed_state, products=products, links=cleaned_links)

    def add_link(
        self,
        state: IoTHomeState,
        *,
        init_name: str,
        term_name: str,
        link_name: str | None = None,
    ) -> IoTHomeState:
        """Add one legal direct link between two products.

        Args:
            state: Current state.
            init_name: First endpoint product name.
            term_name: Second endpoint product name.
            link_name: Optional explicit link name.

        Returns:
            Updated state with one additional link.

        Raises:
            ValueError: If the link is invalid.
        """
        typed_state = _coerce_state(state)
        if init_name == term_name:
            raise ValueError("A link cannot connect a product to itself.")

        product_by_name = {product.name: product for product in typed_state.products}
        init_product = product_by_name.get(init_name)
        term_product = product_by_name.get(term_name)
        if init_product is None or term_product is None:
            raise ValueError("Links must reference existing products.")
        if iot_link_exists(typed_state.links, init_name, term_name):
            raise ValueError("This link already exists.")
        if not iot_link_pair_is_legal(init_product.product_type, term_product.product_type):
            raise ValueError("This direct link type pairing is not allowed.")

        existing_link_names = {link.name for link in typed_state.links}
        next_link_name = _next_name(existing_link_names, "l") if link_name is None else link_name
        if next_link_name in existing_link_names:
            raise ValueError("Link name already exists.")

        added = IoTHomeLink(name=next_link_name, init_name=init_name, term_name=term_name)
        return _with_links(typed_state, (*typed_state.links, added))

    def delete_link(self, state: IoTHomeState, *, link_name: str) -> IoTHomeState:
        """Delete one link by name.

        Args:
            state: Current state.
            link_name: Link to remove.

        Returns:
            Updated state without the removed link.

        Raises:
            ValueError: If the link name is unknown.
        """
        typed_state = _coerce_state(state)
        if not any(link.name == link_name for link in typed_state.links):
            raise ValueError("Unknown link name.")
        links = tuple(link for link in typed_state.links if link.name != link_name)
        return _with_links(typed_state, links)

    def tune_cooler(
        self,
        state: IoTHomeState,
        *,
        cooler_name: str,
        btus: float | None = None,
        cfm: float | None = None,
    ) -> IoTHomeState:
        """Tune one cooler's BTU/h or CFM setting.

        Args:
            state: Current state.
            cooler_name: Cooler to tune.
            btus: Optional replacement BTU/h setting.
            cfm: Optional replacement CFM setting.

        Returns:
            Updated state with the tuned cooler.

        Raises:
            ValueError: If the target cooler or settings are invalid.
        """
        typed_state = _coerce_state(state)
        if btus is None and cfm is None:
            raise ValueError("At least one cooler setting must be provided.")
        if btus is not None and btus not in self.cooler_btus_options:
            raise ValueError("Unsupported BTU/h setting.")
        if cfm is not None and cfm not in self.cooler_cfm_options:
            raise ValueError("Unsupported CFM setting.")

        products = list(typed_state.products)
        target_index = next((index for index, product in enumerate(products) if product.name == cooler_name), None)
        if target_index is None:
            raise ValueError("Unknown cooler name.")
        if products[target_index].product_type != "e":
            raise ValueError("Only coolers can be tuned.")

        replacement = products[target_index]
        if btus is not None:
            replacement = replace(replacement, btus=btus)
        if cfm is not None:
            replacement = replace(replacement, cfm=cfm)
        products[target_index] = replacement
        return _with_products(typed_state, tuple(products))


__all__ = [
    "IoTHomeCoolingGrammarProblem",
    "IoTHomeEvaluation",
    "IoTHomeLink",
    "IoTHomeProduct",
    "IoTHomeState",
]
