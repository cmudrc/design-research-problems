from __future__ import annotations

import importlib
import runpy
import sys
from types import ModuleType, SimpleNamespace

import pytest

from design_research_problems._catalog import _registry as registry_module
from design_research_problems._catalog._registry import ProblemRegistry, _resolve_object
from design_research_problems._lazy_exports import module_dir, resolve_lazy_export
from design_research_problems.problems import ProblemKind, ProblemMetadata, ProblemTaxonomy


def _taxonomy(
    *,
    tags: tuple[str, ...] = ("alpha",),
    deliverable_type: str | None = None,
    timebox_hint_minutes: int | None = None,
    participants: str | None = None,
) -> ProblemTaxonomy:
    return ProblemTaxonomy(
        formulation="textual",
        convexity=None,
        design_variable_type=None,
        is_dynamic=False,
        orientation="engineering_practical",
        feasibility_ratio_hint=None,
        objective_mode="qualitative",
        constraint_nature="informal",
        bounds_summary=None,
        tags=tags,
        deliverable_type=deliverable_type,
        timebox_hint_minutes=timebox_hint_minutes,
        participants=participants,
    )


def _metadata(
    problem_id: str,
    *,
    kind: ProblemKind = ProblemKind.TEXT,
    implementation: str | None = None,
    capabilities: tuple[str, ...] = ("statement-markdown",),
    study_suitability: tuple[str, ...] = ("ideation-friendly",),
    tags: tuple[str, ...] = ("alpha",),
) -> ProblemMetadata:
    return ProblemMetadata(
        problem_id=problem_id,
        title=f"Title for {problem_id}",
        summary=f"Summary for {problem_id}",
        kind=kind,
        taxonomy=_taxonomy(tags=tags),
        citations=(),
        assets=(),
        capabilities=capabilities,
        study_suitability=study_suitability,
        implementation=implementation,
    )


def _manifest(metadata: ProblemMetadata) -> SimpleNamespace:
    return SimpleNamespace(
        metadata=metadata,
        parameters={},
        statement_markdown=f"# {metadata.title}",
    )


def test_public_package_dir_and_lazy_helpers_cover_edge_cases() -> None:
    package = importlib.import_module("design_research_problems")

    assert "Problem" in dir(package)

    resolved = resolve_lazy_export(
        module_name="demo.module",
        exports={"sqrt": "math:sqrt"},
        export_name="sqrt",
        namespace={},
    )
    assert resolved(9) == 3

    with pytest.raises(AttributeError, match="has no attribute"):
        resolve_lazy_export(
            module_name="demo.module",
            exports={"sqrt": "math:sqrt"},
            export_name="missing",
            namespace={},
        )

    with pytest.raises(AttributeError, match="Invalid lazy export target"):
        resolve_lazy_export(
            module_name="demo.module",
            exports={"broken": "not-a-target"},
            export_name="broken",
            namespace={},
        )

    listing = module_dir({"local_name": object()}, ["exported_name"])
    assert listing == ["exported_name", "local_name"]


def test_gui_main_module_delegates_to_launcher(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    launcher = ModuleType("design_research_problems.gui._launcher")
    launcher.main = lambda: called.append("main")  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "design_research_problems.gui._launcher", launcher)

    runpy.run_module("design_research_problems.gui.__main__", run_name="__main__")

    assert called == ["main"]


def test_resolve_object_and_registry_filter_helpers_raise_usefully() -> None:
    with pytest.raises(Exception, match="Invalid implementation path"):
        _resolve_object("not-a-valid-path")

    registry = ProblemRegistry()
    registry._manifests = {
        "alpha": _manifest(_metadata("alpha")),
    }

    with pytest.raises(KeyError, match="Unknown problem id"):
        registry.feature_flags("missing")
    with pytest.raises(KeyError, match="Unknown problem id"):
        registry.capabilities("missing")
    with pytest.raises(KeyError, match="Unknown problem id"):
        registry.study_suitability("missing")
    with pytest.raises(KeyError, match="Unknown problem id"):
        registry.get("missing")

    assert registry.search(kind=ProblemKind.OPTIMIZATION) == ()
    assert registry.search(tags=("missing",)) == ()
    assert registry.search(feature_flags=("human subjects ready",)) == ()
    assert registry.search(capabilities=("prompt packet",)) == ()
    assert registry.search(study_suitability=("requirements study ready",)) == ()
    assert registry.search(text="not-present") == ()


def test_registry_get_dispatches_factories_and_type_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ProblemRegistry()

    implementation_manifests = {
        "factory": _manifest(_metadata("factory", implementation="pkg:factory")),
        "callable": _manifest(_metadata("callable", implementation="pkg:callable")),
        "broken": _manifest(_metadata("broken", implementation="pkg:value")),
    }
    registry._manifests = implementation_manifests

    target_factory = SimpleNamespace(from_manifest=lambda manifest: ("factory", manifest.metadata.problem_id))

    def direct_factory(manifest):
        return ("callable", manifest.metadata.problem_id)

    non_callable = object()

    def fake_resolve(path: str) -> object:
        return {
            "pkg:factory": target_factory,
            "pkg:callable": direct_factory,
            "pkg:value": non_callable,
        }[path]

    monkeypatch.setattr(registry_module, "_resolve_object", fake_resolve)

    assert registry.get("factory") == ("factory", "factory")
    assert registry.get("callable") == ("callable", "callable")
    with pytest.raises(Exception, match="not callable"):
        registry.get("broken")

    decision_manifest = _manifest(_metadata("decision", kind=ProblemKind.DECISION))
    mcp_manifest = _manifest(_metadata("mcp", kind=ProblemKind.MCP))
    missing_impl_manifest = _manifest(_metadata("optimization", kind=ProblemKind.OPTIMIZATION))
    registry._manifests = {
        "decision": decision_manifest,
        "mcp": mcp_manifest,
        "optimization": missing_impl_manifest,
    }

    monkeypatch.setattr(
        registry_module,
        "load_decision_problem",
        lambda manifest: ("decision", manifest.metadata.problem_id),
    )
    monkeypatch.setattr(
        registry_module,
        "MCPProblem",
        SimpleNamespace(
            from_manifest=lambda manifest: ("mcp", manifest.metadata.problem_id),
        ),
    )

    assert registry.get("decision") == ("decision", "decision")
    assert registry.get("mcp") == ("mcp", "mcp")
    with pytest.raises(Exception, match="missing an implementation path"):
        registry.get("optimization")

    registry.get = lambda problem_id: 42  # type: ignore[method-assign]
    with pytest.raises(TypeError, match="expected str"):
        registry.get_as("alpha", str)
