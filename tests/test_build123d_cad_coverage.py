from __future__ import annotations

from types import SimpleNamespace

import pytest

from design_research_problems.problems._domains import build123d_cad as cad


class _DummyBBoxSize:
    X = 80.0
    Y = 40.0
    Z = 46.0


class _DummyBBox:
    size = _DummyBBoxSize()


class _DummyShape:
    volume = 123.4
    area = 456.7

    def bounding_box(self) -> _DummyBBox:
        return _DummyBBox()

    def is_valid(self) -> bool:
        return True


class _NullContext:
    """Context manager used by the in-memory Build123d protocol double."""

    def __init__(self, *_args: object) -> None:
        pass

    def __enter__(self) -> _NullContext:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _BracketEdge:
    """Edge double positioned at the bracket's internal corner."""

    def center(self) -> SimpleNamespace:
        return SimpleNamespace(Y=-14.0, Z=6.0)


class _BracketPart(_NullContext):
    """BuildPart double exposing the subset consumed by the adapter."""

    def __init__(self) -> None:
        self.part = SimpleNamespace(volume=41_000.0)

    def edges(self) -> list[_BracketEdge]:
        return [_BracketEdge()]


def test_normalize_mounting_bracket_spec_validates_inputs() -> None:
    spec = cad.MountingBracketSpec()
    assert cad.normalize_mounting_bracket_spec(spec) is spec

    with pytest.raises(ValueError, match="width_mm must be > 0"):
        cad.normalize_mounting_bracket_spec(cad.MountingBracketSpec(width_mm=0))
    with pytest.raises(ValueError, match="base_hole_count must be >= 0"):
        cad.normalize_mounting_bracket_spec(cad.MountingBracketSpec(base_hole_count=-1))
    with pytest.raises(ValueError, match="flange_hole_count must be >= 0"):
        cad.normalize_mounting_bracket_spec(cad.MountingBracketSpec(flange_hole_count=-1))
    with pytest.raises(ValueError, match="fillet_radius_mm must be >= 0"):
        cad.normalize_mounting_bracket_spec(cad.MountingBracketSpec(fillet_radius_mm=-0.1))


def test_geometry_helpers_return_deterministic_layouts() -> None:
    spec = cad.MountingBracketSpec(base_hole_count=4, flange_hole_count=2)
    assert cad._max_offset(half_span=1.0, hole_radius=1.0, preferred=10.0) == 0.0
    assert cad._symmetric_offsets(0, half_span=20.0, edge_offset=5.0) == []
    assert cad._symmetric_offsets(1, half_span=20.0, edge_offset=5.0) == [0.0]
    assert len(cad._base_hole_centers_xy(spec)) == 4
    assert cad._base_hole_centers_xy(cad.MountingBracketSpec(base_hole_count=0)) == []
    assert len(cad._flange_hole_centers_z(spec)) == 2
    assert cad._flange_hole_centers_z(cad.MountingBracketSpec(flange_hole_count=0)) == []
    assert cad._fillet_candidates_mm(0.0) == []
    assert cad._fillet_candidates_mm(1.0) == [1.0, 0.5]
    assert cad._base_hole_centers_xy(cad.MountingBracketSpec(base_hole_count=1)) == [(0.0, 0.0)]
    assert len(cad._base_hole_centers_xy(cad.MountingBracketSpec(base_hole_count=2))) == 2
    assert len(cad._flange_hole_centers_z(cad.MountingBracketSpec(flange_hole_count=1))) == 1
    assert len(cad._flange_hole_centers_z(cad.MountingBracketSpec(flange_hole_count=3))) == 3
    assert cad._fillet_candidates_mm(0.75) == [0.75, 0.5]


def test_render_build123d_script_embeds_parameter_values() -> None:
    script = cad.render_build123d_script(cad.MountingBracketSpec(width_mm=90.0, base_hole_count=3))
    assert "WIDTH = 90.0" in script
    assert "BASE_HOLE_COUNT = 3" in script
    assert "result = part.part" in script


def test_build123d_version_handles_absent_and_import_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cad, "build123d_available", lambda: False)
    assert cad.build123d_version() is None

    monkeypatch.setattr(cad, "build123d_available", lambda: True)
    monkeypatch.setattr(cad, "import_module", lambda _name: SimpleNamespace(__version__="9.9.9"))
    assert cad.build123d_version() == "9.9.9"

    def _raise_import(_name: str) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(cad, "import_module", _raise_import)
    assert cad.build123d_version() is None


def test_script_namespace_includes_safe_import_and_exported_symbols(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_module = SimpleNamespace(__all__=["Foo"], Foo=object())
    monkeypatch.setattr(cad, "import_module", lambda _name: fake_module)

    namespace = cad._script_build123d_namespace()
    assert namespace["build123d"] is fake_module
    assert namespace["Foo"] is fake_module.Foo
    assert callable(namespace["__builtins__"]["__import__"])


def test_coerce_script_result_shape_supports_part_wrapper_and_rejects_invalid() -> None:
    wrapper = SimpleNamespace(part=_DummyShape())
    assert cad._coerce_script_result_shape(wrapper, result_name="result") is wrapper.part
    assert cad._coerce_script_result_shape(_DummyShape(), result_name="result") is not None
    with pytest.raises(ValueError, match="must resolve to a Build123d part-like object"):
        cad._coerce_script_result_shape(object(), result_name="result")


def test_evaluate_scripted_part_reports_metrics_without_real_build123d(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cad, "build123d_available", lambda: True)
    monkeypatch.setattr(cad, "build123d_version", lambda: "0.test")
    monkeypatch.setattr(
        cad,
        "_script_build123d_namespace",
        lambda: {"__builtins__": {"abs": abs, "ValueError": ValueError}, "dummy_shape": _DummyShape()},
    )

    payload = cad.evaluate_scripted_part("result = dummy_shape")
    assert payload["backend"] == "build123d"
    assert payload["build123d_available"] is True
    assert payload["build123d_version"] == "0.test"
    assert payload["is_valid"] is True
    assert payload["volume_mm3"] == pytest.approx(123.4)
    assert payload["surface_area_mm2"] == pytest.approx(456.7)
    assert payload["constraint_checks"]["matches_nominal_envelope"] is True


def test_evaluate_scripted_part_validates_preconditions_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cad, "build123d_available", lambda: False)
    with pytest.raises(RuntimeError, match="build123d is not installed"):
        cad.evaluate_scripted_part("result = 1")

    monkeypatch.setattr(cad, "build123d_available", lambda: True)
    monkeypatch.setattr(cad, "_script_build123d_namespace", lambda: {"__builtins__": {"ValueError": ValueError}})

    with pytest.raises(ValueError, match="script must be a non-empty Python source string"):
        cad.evaluate_scripted_part("   ")
    with pytest.raises(ValueError, match="result_name must be a valid Python identifier"):
        cad.evaluate_scripted_part("result = 1", result_name="123bad")
    with pytest.raises(ValueError, match="must assign the final model"):
        cad.evaluate_scripted_part("x = 1")
    with pytest.raises(ValueError, match="must resolve to a Build123d part-like object"):
        cad.evaluate_scripted_part("result = 123")
    with pytest.raises(ValueError, match="Script execution failed"):
        cad.evaluate_scripted_part("raise ValueError('boom')")


@pytest.mark.parametrize(
    "script",
    [
        "import os",
        "from . import Box",
        "from os import path",
        "from build123d import *",
        "open('file.txt')",
        "object.__subclasses__()",
        "value = object.__class__",
        "value = __builtins__",
        "global value",
    ],
)
def test_script_validator_rejects_unsafe_python_features(script: str) -> None:
    with pytest.raises(ValueError):
        cad._validate_build123d_script(script)


def test_script_validator_and_import_hook_report_syntax_and_import_errors() -> None:
    with pytest.raises(ValueError, match="invalid Python syntax"):
        cad._validate_build123d_script("if:")
    with pytest.raises(ImportError, match="Relative imports"):
        cad._safe_script_import("build123d", level=1)
    with pytest.raises(ImportError, match="is not allowed"):
        cad._safe_script_import("os")
    assert cad._safe_script_import("math") is not None
    assert "line 1" in str(cad._script_restriction_error("restricted", cad.ast.parse("x = 1").body[0]))
    assert str(cad._script_restriction_error("restricted")) == "restricted"


def test_build123d_bracket_volume_raises_when_dependency_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_import(_name: str) -> object:
        raise ImportError("missing")

    monkeypatch.setattr(cad, "import_module", _raise_import)
    with pytest.raises(RuntimeError, match="build123d is not installed"):
        cad._build123d_bracket_volume_mm3(cad.MountingBracketSpec())


def test_build123d_bracket_volume_uses_backend_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bracket construction should use the documented Build123d primitive protocol."""
    primitive_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    fillet_radii: list[float] = []

    def _record_primitive(name: str):
        def _primitive(*args: object, **kwargs: object) -> None:
            primitive_calls.append((name, args, kwargs))

        return _primitive

    def _fillet(_edges: object, radius: float) -> None:
        fillet_radii.append(radius)
        if len(fillet_radii) == 1:
            raise ValueError("requested radius is infeasible")

    fake_module = SimpleNamespace(
        BuildPart=_BracketPart,
        Box=_record_primitive("box"),
        Cylinder=_record_primitive("cylinder"),
        Locations=_NullContext,
        Location=lambda *args: args,
        fillet=_fillet,
        Align=SimpleNamespace(CENTER="center", MIN="min"),
        Mode=SimpleNamespace(SUBTRACT="subtract"),
    )
    monkeypatch.setattr(cad, "import_module", lambda _name: fake_module)

    volume, applied_fillet, warning = cad._build123d_bracket_volume_mm3(cad.MountingBracketSpec())

    assert volume == pytest.approx(41_000.0)
    assert applied_fillet == pytest.approx(3.5)
    assert warning == "Requested 4 mm fillet; applied feasible 3.5 mm."
    assert [call[0] for call in primitive_calls].count("box") == 2
    assert [call[0] for call in primitive_calls].count("cylinder") == 6
    assert fillet_radii == [4.0, 3.5]


def test_build123d_bracket_volume_with_optional_backend() -> None:
    pytest.importorskip("build123d")

    volume, applied_fillet, warning = cad._build123d_bracket_volume_mm3(cad.MountingBracketSpec())

    assert volume > 0.0
    assert applied_fillet is not None
    assert applied_fillet > 0.0
    assert warning is None or "applied feasible" in warning


def test_scripted_part_wraps_shape_metric_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    shape = SimpleNamespace(
        volume=1.0,
        area=1.0,
        bounding_box=lambda: (_ for _ in ()).throw(RuntimeError("no bounding box")),
        is_valid=lambda: True,
    )
    monkeypatch.setattr(cad, "build123d_available", lambda: True)
    monkeypatch.setattr(
        cad,
        "_script_build123d_namespace",
        lambda: {"__builtins__": {}, "shape": shape},
    )

    with pytest.raises(ValueError, match="Could not compute shape metrics"):
        cad.evaluate_scripted_part("result = shape")


def test_bracket_report_handles_backend_available_and_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = cad.MountingBracketSpec()

    monkeypatch.setattr(cad, "build123d_available", lambda: False)
    monkeypatch.setattr(cad, "build123d_version", lambda: None)
    payload = cad.bracket_report(spec)
    assert payload["build123d_available"] is False
    assert payload["build123d_volume_mm3"] is None
    assert payload["analytic_volume_mm3"] > 0.0

    monkeypatch.setattr(cad, "build123d_available", lambda: True)
    monkeypatch.setattr(cad, "build123d_version", lambda: "1.2.3")
    monkeypatch.setattr(cad, "_build123d_bracket_volume_mm3", lambda _spec: (10.0, 2.0, None))
    payload_ok = cad.bracket_report(spec)
    assert payload_ok["build123d_volume_mm3"] == pytest.approx(10.0)
    assert payload_ok["build123d_applied_fillet_radius_mm"] == pytest.approx(2.0)
    assert payload_ok["warning"] is None

    def _raise_runtime(_spec: cad.MountingBracketSpec) -> tuple[float, float | None, str | None]:
        raise RuntimeError("backend mismatch")

    monkeypatch.setattr(cad, "_build123d_bracket_volume_mm3", _raise_runtime)
    payload_warn = cad.bracket_report(spec)
    assert payload_warn["warning"] == "backend mismatch"
