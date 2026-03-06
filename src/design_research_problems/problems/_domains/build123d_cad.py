"""Shared Build123d-backed helpers for CAD-oriented MCP problems."""

from __future__ import annotations

import importlib.util
import math
from dataclasses import asdict, dataclass
from importlib import import_module
from types import MappingProxyType
from typing import Any

_BASE_HOLE_EDGE_OFFSET_MM = 10.0
_FLANGE_HOLE_EDGE_OFFSET_MM = 10.0
_FLANGE_HOLE_VERTICAL_SPACING_MM = 20.0
_FILLET_FALLBACK_STEP_MM = 0.5

_NOMINAL_ENVELOPE_MM = (80.0, 40.0, 46.0)
_ENVELOPE_TOLERANCE_MM = 0.25
_SCRIPT_SAFE_BUILTINS = MappingProxyType(
    {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "pow": pow,
        "range": range,
        "round": round,
        "set": set,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "Exception": Exception,
        "ValueError": ValueError,
        "RuntimeError": RuntimeError,
        "__import__": __import__,
        "zip": zip,
    }
)


@dataclass(frozen=True)
class MountingBracketSpec:
    """Parametric dimensions for one right-angle mounting bracket."""

    width_mm: float = 80.0
    depth_mm: float = 40.0
    base_thickness_mm: float = 6.0
    flange_height_mm: float = 40.0
    flange_thickness_mm: float = 6.0
    hole_diameter_mm: float = 6.0
    base_hole_count: int = 4
    flange_hole_count: int = 2
    fillet_radius_mm: float = 4.0


def normalize_mounting_bracket_spec(spec: MountingBracketSpec) -> MountingBracketSpec:
    """Validate and normalize one bracket parameter set.

    Args:
        spec: Raw parameter set.

    Returns:
        Validated parameter set.

    Raises:
        ValueError: If any required numeric field is non-positive.
    """
    numeric_fields = {
        "width_mm": spec.width_mm,
        "depth_mm": spec.depth_mm,
        "base_thickness_mm": spec.base_thickness_mm,
        "flange_height_mm": spec.flange_height_mm,
        "flange_thickness_mm": spec.flange_thickness_mm,
        "hole_diameter_mm": spec.hole_diameter_mm,
    }
    for key, value in numeric_fields.items():
        if value <= 0:
            raise ValueError(f"{key} must be > 0.")
    if spec.base_hole_count < 0:
        raise ValueError("base_hole_count must be >= 0.")
    if spec.flange_hole_count < 0:
        raise ValueError("flange_hole_count must be >= 0.")
    if spec.fillet_radius_mm < 0:
        raise ValueError("fillet_radius_mm must be >= 0.")
    return spec


def build123d_available() -> bool:
    """Return whether ``build123d`` is importable in this environment."""
    return importlib.util.find_spec("build123d") is not None


def build123d_version() -> str | None:
    """Return the installed ``build123d`` version string when available."""
    if not build123d_available():
        return None
    try:
        module = import_module("build123d")
    except Exception:
        return None
    version = getattr(module, "__version__", None)
    return str(version) if version is not None else None


def estimate_bracket_volume_mm3(spec: MountingBracketSpec) -> float:
    """Return an analytic net-volume estimate for one bracket.

    Args:
        spec: Validated bracket parameter set.

    Returns:
        Estimated net volume in cubic millimeters.
    """
    base_volume = spec.width_mm * spec.depth_mm * spec.base_thickness_mm
    flange_volume = spec.width_mm * spec.flange_thickness_mm * spec.flange_height_mm
    hole_area = math.pi * (spec.hole_diameter_mm / 2.0) ** 2
    hole_volume = hole_area * (
        (spec.base_hole_count * spec.base_thickness_mm)
        + (spec.flange_hole_count * spec.flange_thickness_mm)
    )
    return max(base_volume + flange_volume - hole_volume, 0.0)


def _max_offset(half_span: float, hole_radius: float, preferred: float) -> float:
    """Return one edge offset that remains inside a half-span."""
    feasible = half_span - hole_radius - 0.5
    if feasible <= 0:
        return 0.0
    return min(preferred, feasible)


def _symmetric_offsets(count: int, half_span: float, edge_offset: float) -> list[float]:
    """Return evenly spaced offsets around zero."""
    if count <= 0:
        return []
    if count == 1:
        return [0.0]
    usable_half_span = max(half_span - edge_offset, 0.0)
    start = -usable_half_span
    step = (2.0 * usable_half_span) / (count - 1)
    return [start + (step * index) for index in range(count)]


def _base_hole_centers_xy(spec: MountingBracketSpec) -> list[tuple[float, float]]:
    """Return base-hole centers in the XY plane."""
    if spec.base_hole_count <= 0:
        return []
    hole_radius = spec.hole_diameter_mm / 2.0
    x_edge_offset = _max_offset(spec.width_mm / 2.0, hole_radius, _BASE_HOLE_EDGE_OFFSET_MM)
    y_edge_offset = _max_offset(spec.depth_mm / 2.0, hole_radius, _BASE_HOLE_EDGE_OFFSET_MM)
    if spec.base_hole_count == 1:
        return [(0.0, 0.0)]
    if spec.base_hole_count == 2:
        x_values = _symmetric_offsets(2, spec.width_mm / 2.0, x_edge_offset)
        return [(x_values[0], 0.0), (x_values[1], 0.0)]

    row_count = 2
    col_count = math.ceil(spec.base_hole_count / row_count)
    x_values = _symmetric_offsets(col_count, spec.width_mm / 2.0, x_edge_offset)
    y_values = _symmetric_offsets(row_count, spec.depth_mm / 2.0, y_edge_offset)

    centers: list[tuple[float, float]] = []
    for y_mm in y_values:
        for x_mm in x_values:
            centers.append((x_mm, y_mm))
            if len(centers) == spec.base_hole_count:
                return centers
    return centers


def _flange_hole_centers_z(spec: MountingBracketSpec) -> list[float]:
    """Return flange-hole center Z coordinates."""
    if spec.flange_hole_count <= 0:
        return []
    hole_radius = spec.hole_diameter_mm / 2.0
    z_edge_offset = _max_offset(spec.flange_height_mm / 2.0, hole_radius, _FLANGE_HOLE_EDGE_OFFSET_MM)
    z_center = spec.base_thickness_mm + (spec.flange_height_mm / 2.0)

    if spec.flange_hole_count == 1:
        return [z_center]
    if spec.flange_hole_count == 2:
        max_half_spacing = max((spec.flange_height_mm / 2.0) - z_edge_offset, 0.0)
        preferred_half_spacing = _FLANGE_HOLE_VERTICAL_SPACING_MM / 2.0
        half_spacing = min(preferred_half_spacing, max_half_spacing)
        return [z_center - half_spacing, z_center + half_spacing]

    offsets = _symmetric_offsets(spec.flange_hole_count, spec.flange_height_mm / 2.0, z_edge_offset)
    return [z_center + offset for offset in offsets]


def _fillet_candidates_mm(requested_radius_mm: float) -> list[float]:
    """Return descending fillet radii used for feasibility fallback."""
    if requested_radius_mm <= 0:
        return []
    candidates: list[float] = []
    radius = requested_radius_mm
    while radius >= _FILLET_FALLBACK_STEP_MM:
        rounded = round(radius, 4)
        if not candidates or not math.isclose(candidates[-1], rounded):
            candidates.append(rounded)
        radius -= _FILLET_FALLBACK_STEP_MM
    if candidates and not math.isclose(candidates[-1], _FILLET_FALLBACK_STEP_MM):
        candidates.append(_FILLET_FALLBACK_STEP_MM)
    return candidates


def _build123d_bracket_volume_mm3(
    spec: MountingBracketSpec,
) -> tuple[float, float | None, str | None]:
    """Build the full bracket in Build123d and return physical model metrics.

    Args:
        spec: Validated bracket parameter set.

    Returns:
        Tuple of modeled volume, applied fillet radius, and optional warning.

    Raises:
        RuntimeError: If Build123d primitives cannot be evaluated.
    """
    try:
        module = import_module("build123d")
    except Exception as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("build123d is not installed.") from exc

    build_part = getattr(module, "BuildPart", None)
    box = getattr(module, "Box", None)
    cylinder = getattr(module, "Cylinder", None)
    locations = getattr(module, "Locations", None)
    location = getattr(module, "Location", None)
    fillet = getattr(module, "fillet", None)
    align = getattr(module, "Align", None)
    mode = getattr(module, "Mode", None)
    if (
        not callable(build_part)
        or not callable(box)
        or not callable(cylinder)
        or not callable(locations)
        or not callable(location)
        or not callable(fillet)
        or align is None
        or mode is None
    ):  # pragma: no cover - defensive API compatibility path
        raise RuntimeError("Required build123d CAD APIs are unavailable in this installation.")

    try:
        align_center = align.CENTER
        align_min = align.MIN
        mode_subtract = mode.SUBTRACT
        flange_center_y = (-spec.depth_mm / 2.0) + (spec.flange_thickness_mm / 2.0)

        with build_part() as part:
            box(
                spec.width_mm,
                spec.depth_mm,
                spec.base_thickness_mm,
                align=(align_center, align_center, align_min),
            )
            with locations((0.0, flange_center_y, spec.base_thickness_mm)):
                box(
                    spec.width_mm,
                    spec.flange_thickness_mm,
                    spec.flange_height_mm,
                    align=(align_center, align_center, align_min),
                )

            for x_mm, y_mm in _base_hole_centers_xy(spec):
                with locations((x_mm, y_mm, 0.0)):
                    cylinder(
                        radius=(spec.hole_diameter_mm / 2.0),
                        height=spec.base_thickness_mm,
                        align=(align_center, align_center, align_min),
                        mode=mode_subtract,
                    )

            for z_mm in _flange_hole_centers_z(spec):
                with locations(location((0.0, flange_center_y, z_mm), (90.0, 0.0, 0.0))):
                    cylinder(
                        radius=(spec.hole_diameter_mm / 2.0),
                        height=spec.flange_thickness_mm,
                        align=(align_center, align_center, align_center),
                        mode=mode_subtract,
                    )

            warning: str | None = None
            applied_fillet_radius: float | None = None
            if spec.fillet_radius_mm > 0:
                target_y = (-spec.depth_mm / 2.0) + spec.flange_thickness_mm
                target_z = spec.base_thickness_mm
                corner_edges = [
                    edge
                    for edge in part.edges()
                    if abs(float(edge.center().Y) - target_y) <= 1e-6
                    and abs(float(edge.center().Z) - target_z) <= 1e-6
                ]
                if corner_edges:
                    for candidate_radius in _fillet_candidates_mm(spec.fillet_radius_mm):
                        try:
                            fillet(corner_edges, candidate_radius)
                        except ValueError:
                            continue
                        applied_fillet_radius = candidate_radius
                        break
                    if applied_fillet_radius is None:
                        warning = (
                            "Internal-corner fillet could not be applied for the current geometry."
                        )
                    elif applied_fillet_radius < spec.fillet_radius_mm:
                        warning = (
                            f"Requested {spec.fillet_radius_mm:.3g} mm fillet; "
                            f"applied feasible {applied_fillet_radius:.3g} mm."
                        )
                else:
                    warning = "No internal-corner edge was available for filleting."
            volume_mm3 = float(part.part.volume)
            return volume_mm3, applied_fillet_radius, warning
    except Exception as exc:  # pragma: no cover - defensive API compatibility path
        raise RuntimeError(f"build123d model evaluation failed: {exc}") from exc


def render_build123d_script(spec: MountingBracketSpec) -> str:
    """Return a reproducible Build123d script for one bracket configuration."""
    return (
        "from build123d import Align, BuildPart, Box, Cylinder, Location, Locations, Mode, fillet\n\n"
        f"WIDTH = {spec.width_mm}\n"
        f"DEPTH = {spec.depth_mm}\n"
        f"BASE_THICKNESS = {spec.base_thickness_mm}\n"
        f"FLANGE_HEIGHT = {spec.flange_height_mm}\n"
        f"FLANGE_THICKNESS = {spec.flange_thickness_mm}\n\n"
        f"HOLE_DIAMETER = {spec.hole_diameter_mm}\n"
        f"BASE_HOLE_COUNT = {spec.base_hole_count}\n"
        f"FLANGE_HOLE_COUNT = {spec.flange_hole_count}\n"
        f"FILLET_RADIUS = {spec.fillet_radius_mm}\n\n"
        "BASE_EDGE_OFFSET = 10.0\n"
        "FLANGE_EDGE_OFFSET = 10.0\n"
        "FLANGE_VERTICAL_SPACING = 20.0\n\n"
        "def symmetric_offsets(count: int, half_span: float, edge_offset: float) -> list[float]:\n"
        "    if count <= 0:\n"
        "        return []\n"
        "    if count == 1:\n"
        "        return [0.0]\n"
        "    usable_half_span = max(half_span - edge_offset, 0.0)\n"
        "    start = -usable_half_span\n"
        "    step = (2.0 * usable_half_span) / (count - 1)\n"
        "    return [start + (step * index) for index in range(count)]\n\n"
        "def max_offset(half_span: float, hole_radius: float, preferred: float) -> float:\n"
        "    feasible = half_span - hole_radius - 0.5\n"
        "    if feasible <= 0:\n"
        "        return 0.0\n"
        "    return min(preferred, feasible)\n\n"
        "hole_radius = HOLE_DIAMETER / 2.0\n"
        "x_edge = max_offset(WIDTH / 2.0, hole_radius, BASE_EDGE_OFFSET)\n"
        "y_edge = max_offset(DEPTH / 2.0, hole_radius, BASE_EDGE_OFFSET)\n"
        "flange_z_edge = max_offset(FLANGE_HEIGHT / 2.0, hole_radius, FLANGE_EDGE_OFFSET)\n\n"
        "with BuildPart() as part:\n"
        "    Box(WIDTH, DEPTH, BASE_THICKNESS, align=(Align.CENTER, Align.CENTER, Align.MIN))\n"
        "    flange_center_y = -DEPTH / 2.0 + FLANGE_THICKNESS / 2.0\n"
        "    with Locations((0.0, flange_center_y, BASE_THICKNESS)):\n"
        "        Box(WIDTH, FLANGE_THICKNESS, FLANGE_HEIGHT, align=(Align.CENTER, Align.CENTER, Align.MIN))\n\n"
        "    if BASE_HOLE_COUNT == 1:\n"
        "        base_holes = [(0.0, 0.0)]\n"
        "    elif BASE_HOLE_COUNT == 2:\n"
        "        x_vals = symmetric_offsets(2, WIDTH / 2.0, x_edge)\n"
        "        base_holes = [(x_vals[0], 0.0), (x_vals[1], 0.0)]\n"
        "    else:\n"
        "        rows = 2\n"
        "        cols = (BASE_HOLE_COUNT + 1) // rows\n"
        "        x_vals = symmetric_offsets(cols, WIDTH / 2.0, x_edge)\n"
        "        y_vals = symmetric_offsets(rows, DEPTH / 2.0, y_edge)\n"
        "        base_holes = []\n"
        "        for y_mm in y_vals:\n"
        "            for x_mm in x_vals:\n"
        "                base_holes.append((x_mm, y_mm))\n"
        "                if len(base_holes) == BASE_HOLE_COUNT:\n"
        "                    break\n"
        "            if len(base_holes) == BASE_HOLE_COUNT:\n"
        "                break\n\n"
        "    for x_mm, y_mm in base_holes:\n"
        "        with Locations((x_mm, y_mm, 0.0)):\n"
        "            Cylinder(\n"
        "                radius=hole_radius,\n"
        "                height=BASE_THICKNESS,\n"
        "                align=(Align.CENTER, Align.CENTER, Align.MIN),\n"
        "                mode=Mode.SUBTRACT,\n"
        "            )\n\n"
        "    z_center = BASE_THICKNESS + FLANGE_HEIGHT / 2.0\n"
        "    if FLANGE_HOLE_COUNT == 1:\n"
        "        flange_holes_z = [z_center]\n"
        "    elif FLANGE_HOLE_COUNT == 2:\n"
        "        max_half_spacing = max(FLANGE_HEIGHT / 2.0 - flange_z_edge, 0.0)\n"
        "        half_spacing = min(FLANGE_VERTICAL_SPACING / 2.0, max_half_spacing)\n"
        "        flange_holes_z = [z_center - half_spacing, z_center + half_spacing]\n"
        "    else:\n"
        "        z_offsets = symmetric_offsets(FLANGE_HOLE_COUNT, FLANGE_HEIGHT / 2.0, flange_z_edge)\n"
        "        flange_holes_z = [z_center + offset for offset in z_offsets]\n\n"
        "    for z_mm in flange_holes_z:\n"
        "        with Locations(Location((0.0, flange_center_y, z_mm), (90.0, 0.0, 0.0))):\n"
        "            Cylinder(\n"
        "                radius=hole_radius,\n"
        "                height=FLANGE_THICKNESS,\n"
        "                align=(Align.CENTER, Align.CENTER, Align.CENTER),\n"
        "                mode=Mode.SUBTRACT,\n"
        "            )\n\n"
        "    target_y = -DEPTH / 2.0 + FLANGE_THICKNESS\n"
        "    inner_edges = [\n"
        "        edge\n"
        "        for edge in part.edges()\n"
        "        if abs(edge.center().Y - target_y) <= 1e-6 and abs(edge.center().Z - BASE_THICKNESS) <= 1e-6\n"
        "    ]\n"
        "    radius = FILLET_RADIUS\n"
        "    while inner_edges and radius >= 0.5:\n"
        "        try:\n"
        "            fillet(inner_edges, radius)\n"
        "            break\n"
        "        except ValueError:\n"
        "            radius -= 0.5\n\n"
        "result = part.part\n"
    )


def _script_build123d_namespace() -> dict[str, object]:
    """Return globals exposed to script execution."""
    module = import_module("build123d")
    exported_raw = getattr(module, "__all__", None)
    exported_names: list[str]
    if isinstance(exported_raw, list | tuple):
        exported_names = [name for name in exported_raw if isinstance(name, str)]
    else:
        exported_names = [name for name in dir(module) if not name.startswith("_")]

    namespace: dict[str, object] = {
        "__builtins__": dict(_SCRIPT_SAFE_BUILTINS),
        "math": math,
        "build123d": module,
    }
    for name in exported_names:
        namespace[name] = getattr(module, name)
    return namespace


def _coerce_script_result_shape(result_obj: object, *, result_name: str) -> object:
    """Extract one shape-like object with volume and bounding-box APIs."""
    part_candidate = getattr(result_obj, "part", None)
    shape = part_candidate if part_candidate is not None else result_obj
    if not hasattr(shape, "volume") or not hasattr(shape, "bounding_box"):
        raise ValueError(
            f"Script variable {result_name!r} must resolve to a Build123d part-like object "
            "with volume and bounding_box APIs."
        )
    return shape


def evaluate_scripted_part(script: str, *, result_name: str = "result") -> dict[str, Any]:
    """Execute one Build123d script and return CAD metrics.

    Args:
        script: Agent-authored Python script that builds a part.
        result_name: Variable name containing the final model object.

    Returns:
        JSON-ready evaluation payload.

    Raises:
        RuntimeError: If Build123d is unavailable.
        ValueError: If script input or output is invalid.
    """
    if not build123d_available():
        raise RuntimeError("build123d is not installed.")

    normalized_script = script.strip()
    if not normalized_script:
        raise ValueError("script must be a non-empty Python source string.")
    if not result_name.isidentifier():
        raise ValueError("result_name must be a valid Python identifier.")

    namespace = _script_build123d_namespace()
    try:
        compiled = compile(normalized_script, "<build123d-agent-script>", "exec")
        exec(compiled, namespace, namespace)
    except Exception as exc:
        raise ValueError(f"Script execution failed: {exc}") from exc

    if result_name not in namespace:
        raise ValueError(
            f"Script must assign the final model to variable {result_name!r}."
        )

    shape = _coerce_script_result_shape(namespace[result_name], result_name=result_name)

    try:
        bbox = shape.bounding_box()
        bbox_size = bbox.size
        bbox_x = float(bbox_size.X)
        bbox_y = float(bbox_size.Y)
        bbox_z = float(bbox_size.Z)
        observed_sorted = sorted((bbox_x, bbox_y, bbox_z), reverse=True)
        expected_sorted = sorted(_NOMINAL_ENVELOPE_MM, reverse=True)
        envelope_within_tolerance = all(
            abs(observed - expected) <= _ENVELOPE_TOLERANCE_MM
            for observed, expected in zip(observed_sorted, expected_sorted, strict=True)
        )
    except Exception as exc:
        raise ValueError(f"Could not compute shape metrics: {exc}") from exc

    is_valid_raw = getattr(shape, "is_valid", None)
    is_valid = bool(is_valid_raw() if callable(is_valid_raw) else is_valid_raw)

    return {
        "backend": "build123d",
        "build123d_available": True,
        "build123d_version": build123d_version(),
        "result_name": result_name,
        "is_valid": is_valid,
        "volume_mm3": float(shape.volume),
        "surface_area_mm2": float(shape.area) if hasattr(shape, "area") else None,
        "bounding_box_mm": {"x": bbox_x, "y": bbox_y, "z": bbox_z},
        "constraint_checks": {
            "nominal_envelope_mm": {
                "x": _NOMINAL_ENVELOPE_MM[0],
                "y": _NOMINAL_ENVELOPE_MM[1],
                "z": _NOMINAL_ENVELOPE_MM[2],
            },
            "tolerance_mm": _ENVELOPE_TOLERANCE_MM,
            "observed_sorted_mm": observed_sorted,
            "matches_nominal_envelope": envelope_within_tolerance,
        },
        "script": normalized_script,
    }


def bracket_report(spec: MountingBracketSpec) -> dict[str, Any]:
    """Build a normalized report for one bracket configuration.

    Args:
        spec: Validated bracket parameter set.

    Returns:
        JSON-ready report that includes analytic and Build123d-backed values.
    """
    analytic_volume = estimate_bracket_volume_mm3(spec)
    payload: dict[str, Any] = {
        "backend": "build123d",
        "parameters": asdict(spec),
        "build123d_available": build123d_available(),
        "build123d_version": build123d_version(),
        "analytic_volume_mm3": analytic_volume,
        "build123d_volume_mm3": None,
        "build123d_applied_fillet_radius_mm": None,
        "warning": None,
        "build123d_script": render_build123d_script(spec),
    }
    if payload["build123d_available"]:
        try:
            volume_mm3, applied_fillet_radius_mm, warning = _build123d_bracket_volume_mm3(spec)
            payload["build123d_volume_mm3"] = max(volume_mm3, 0.0)
            payload["build123d_applied_fillet_radius_mm"] = applied_fillet_radius_mm
            payload["warning"] = warning
        except RuntimeError as exc:  # pragma: no cover - optional backend mismatch path
            payload["warning"] = str(exc)
    return payload


__all__ = [
    "MountingBracketSpec",
    "bracket_report",
    "build123d_available",
    "build123d_version",
    "estimate_bracket_volume_mm3",
    "evaluate_scripted_part",
    "normalize_mounting_bracket_spec",
    "render_build123d_script",
]
