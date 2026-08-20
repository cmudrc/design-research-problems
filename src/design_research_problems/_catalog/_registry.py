"""Problem registry facade."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import TYPE_CHECKING, Literal, TypeVar, cast, overload

from design_research_problems._catalog._loader import load_problem_manifests
from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems import MCPProblem, Problem, ProblemKind, TextProblem
from design_research_problems.problems._decision import load_decision_problem
from design_research_problems.problems._metadata import ProblemCatalogSummary, ProblemMetadata

if TYPE_CHECKING:
    from design_research_problems.problems import (
        DecisionProblem,
        MCPProblem,
        OptimizationProblem,
    )
    from design_research_problems.problems.grammar import (
        Battery18650T1RectangularSurrogateGrammarProblem,
        Battery18650T2PoseSurrogateGrammarProblem,
        Battery18650T3ATopologySurrogateGrammarProblem,
        Battery18650T3BNetlistExplicitGrammarProblem,
        Battery18650T4ThermalHybridGrammarProblem,
        BatteryPack18650OpenEndedProblem,
        BatteryPack18650SeriesParallelProblem,
        IoTHomeCoolingGrammarProblem,
        PlanarTrussSpanProblem,
        SpaceTrussSpanProblem,
        TrussAPGrammarProblem,
    )
    from design_research_problems.problems.optimization import (
        Battery18650T1RectangularSurrogateOptimizationProblem,
        Battery18650T2PoseSurrogateOptimizationProblem,
        Battery18650T3ATopologySurrogateOptimizationProblem,
        Battery18650T3BNetlistExplicitOptimizationProblem,
        Battery18650T4ThermalHybridOptimizationProblem,
        BatteryFastChargeDFNAnchorOptimizationProblem,
        BatteryGridSizingProblem,
        BatteryOpenEndedCapacityMaxProblem,
        CompetingProjectsWorkerHoursProblem,
        GMPBOptimizationProblem,
        PlanarTrussEngineeringOptimizationProblem,
        SpaceTrussEngineeringOptimizationProblem,
        UnrestrictedWindFarmLayoutOptimizationProblem,
        WindFarmLayoutOptimizationProblem,
    )

type _PlanarTrussProblemId = Literal[
    "planar_truss_span",
    "planar_roof_truss_three_point_symmetric",
    "planar_roof_truss_three_point_symmetric_depth_sixth",
    "planar_roof_truss_three_point_symmetric_depth_sixth_discrete_sizing",
    "planar_roof_truss_three_point_symmetric_depth_eighth",
    "planar_roof_truss_seven_point_symmetric",
    "planar_roof_truss_seven_point_asymmetric",
]

type _SpaceTrussProblemId = Literal["space_truss_span"]
type _IoTGrammarProblemId = Literal["iot_home_cooling_system_design"]
type _TrussAPProblemId = Literal["truss_analysis_program_design"]
type _BatteryGrammarProblemId = Literal[
    "battery_18650_t1_rectangular_surrogate_grammar",
    "battery_18650_t2_pose_surrogate_grammar",
    "battery_18650_t3a_topology_surrogate_grammar",
    "battery_18650_t3b_netlist_explicit_2rc_grammar",
    "battery_18650_t3b_netlist_explicit_grammar",
    "battery_18650_t4_thermal_hybrid_grammar",
]
type _BatteryOptimizationProblemId = Literal[
    "battery_18650_t1_rectangular_surrogate_opt",
    "battery_18650_t2_pose_surrogate_opt",
    "battery_18650_t3a_topology_explicit_2rc_opt",
    "battery_18650_t3a_topology_surrogate_opt",
    "battery_18650_t3b_netlist_explicit_opt",
    "battery_18650_t4_thermal_hybrid_2rc_opt",
    "battery_18650_t4_thermal_hybrid_opt",
    "battery_fast_charge_dfn_anchor_opt",
]

type _MSEvalProblemId = Literal[
    "decision_mseval_kitchen_utensil_grip_corrosion_resistant",
    "decision_mseval_kitchen_utensil_grip_high_strength",
    "decision_mseval_kitchen_utensil_grip_lightweight",
    "decision_mseval_kitchen_utensil_grip_resistant_to_heat",
    "decision_mseval_safety_helmet_corrosion_resistant",
    "decision_mseval_safety_helmet_high_strength",
    "decision_mseval_safety_helmet_lightweight",
    "decision_mseval_safety_helmet_resistant_to_heat",
    "decision_mseval_spacecraft_component_corrosion_resistant",
    "decision_mseval_spacecraft_component_high_strength",
    "decision_mseval_spacecraft_component_lightweight",
    "decision_mseval_spacecraft_component_resistant_to_heat",
    "decision_mseval_underwater_component_corrosion_resistant",
    "decision_mseval_underwater_component_high_strength",
    "decision_mseval_underwater_component_lightweight",
    "decision_mseval_underwater_component_resistant_to_heat",
]

type _DecisionProblemId = Literal["decision_laptop_design_profit_maximization"] | _MSEvalProblemId

type _OptimizationProblemId = (
    _BatteryOptimizationProblemId
    | Literal[
        "battery_pack_18650_series_parallel_cost_min",
        "battery_pack_18650_open_ended_capacity_max",
        "gmpb_default_dynamic_min",
        "pill_capsule_min_area",
        "moneymaker_hip_pump_cost_min",
        "planar_truss_span_mass_min",
        "planar_truss_span_deflection_min",
        "planar_truss_span_fos_max",
        "space_truss_span_mass_min",
        "treadle_pump_ide_material_min",
        "wind_farm_grid_qkp_power_max",
        "wind_farm_unrestricted_deficit_min",
        "worker_hours_competing_projects_value_tracking_min",
    ]
)

_ProblemSubT = TypeVar("_ProblemSubT", bound=Problem)


def _resolve_object(import_path: str) -> object:
    """Import one ``module:attribute`` object reference.

    Args:
        import_path: Import target in ``module:attribute`` form.

    Returns:
        Imported Python object.

    Raises:
        design_research_problems.ProblemEvaluationError: If the import path is malformed.
    """
    module_path, _, attr_name = import_path.partition(":")
    if not module_path or not attr_name:
        raise ProblemEvaluationError(f"Invalid implementation path: {import_path!r}")
    return getattr(import_module(module_path), attr_name)


class ProblemRegistry:
    """Lazy-loading registry for the packaged problem catalog."""

    def __init__(self) -> None:
        """Initialize an empty lazy registry cache."""
        self._manifests: dict[str, ProblemManifest] | None = None

    def _catalog(self) -> dict[str, ProblemManifest]:
        """Return the cached manifest catalog.

        Returns:
            Mapping of problem IDs to parsed manifests.
        """
        if self._manifests is None:
            self._manifests = load_problem_manifests()
        return self._manifests

    def list(self) -> tuple[ProblemMetadata, ...]:
        """Return all problem metadata in ID-sorted order.

        Returns:
            Metadata entries sorted by problem ID.
        """
        return tuple(self._catalog()[problem_id].metadata for problem_id in sorted(self._catalog()))

    def by_kind(self, kind: ProblemKind) -> tuple[ProblemMetadata, ...]:
        """Return metadata entries with the requested kind.

        Args:
            kind: Problem kind to filter for.

        Returns:
            Matching metadata entries.
        """
        return tuple(metadata for metadata in self.list() if metadata.kind is kind)

    def feature_flags(self, problem_id: str) -> tuple[str, ...]:
        """Return the feature flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Feature flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.feature_flags

    def capabilities(self, problem_id: str) -> tuple[str, ...]:
        """Return the normalized capability flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Capability flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.capabilities

    def study_suitability(self, problem_id: str) -> tuple[str, ...]:
        """Return the normalized study-suitability flags for one problem ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Study-suitability flags in deterministic sorted order.

        Raises:
            KeyError: If the ID is unknown.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")
        return manifest.metadata.study_suitability

    def kind_feature_flags(self) -> dict[ProblemKind, tuple[str, ...]]:
        """Return aggregated feature flags for each problem kind.

        Returns:
            Mapping of problem kinds to the union of feature flags across that family.
        """
        grouped: dict[ProblemKind, set[str]] = {kind: set() for kind in ProblemKind}
        for metadata in self.list():
            grouped[metadata.kind].update(metadata.feature_flags)
        return {kind: tuple(sorted(grouped[kind])) for kind in ProblemKind}

    def search(
        self,
        tags: tuple[str, ...] = (),
        text: str = "",
        feature_flags: tuple[str, ...] = (),
        kind: ProblemKind | None = None,
        capabilities: tuple[str, ...] = (),
        study_suitability: tuple[str, ...] = (),
    ) -> tuple[ProblemMetadata, ...]:
        """Search metadata by tags and free text.

        Args:
            tags: Tags that must all be present on a matching entry.
            text: Case-insensitive free-text search term.
            feature_flags: Feature flags that must all be present on a matching entry.
            kind: Optional problem-kind filter.
            capabilities: Capability flags that must all be present.
            study_suitability: Study-suitability flags that must all be present.

        Returns:
            Matching metadata entries.
        """
        tag_set = {tag.lower() for tag in tags}
        feature_flag_set = {flag.strip().lower().replace(" ", "-") for flag in feature_flags}
        capability_set = {flag.strip().lower().replace(" ", "-") for flag in capabilities}
        suitability_set = {flag.strip().lower().replace(" ", "-") for flag in study_suitability}
        text_query = text.strip().lower()
        matches: list[ProblemMetadata] = []
        for metadata in self.list():
            if kind is not None and metadata.kind is not kind:
                continue
            if tag_set and not tag_set.issubset({tag.lower() for tag in metadata.taxonomy.tags}):
                continue
            if feature_flag_set and not feature_flag_set.issubset(set(metadata.feature_flags)):
                continue
            if capability_set and not capability_set.issubset(set(metadata.capabilities)):
                continue
            if suitability_set and not suitability_set.issubset(set(metadata.study_suitability)):
                continue
            haystack = " ".join(
                (metadata.problem_id, metadata.title, metadata.summary, *metadata.taxonomy.tags)
            ).lower()
            if text_query and text_query not in haystack:
                continue
            matches.append(metadata)
        return tuple(matches)

    def summaries(
        self,
        tags: tuple[str, ...] = (),
        text: str = "",
        feature_flags: tuple[str, ...] = (),
        kind: ProblemKind | None = None,
        capabilities: tuple[str, ...] = (),
        study_suitability: tuple[str, ...] = (),
    ) -> tuple[ProblemCatalogSummary, ...]:
        """Return compact search results for agent-facing problem selection.

        Args:
            tags: Tags that must all be present on a matching entry.
            text: Case-insensitive free-text search term.
            feature_flags: Feature flags that must all be present on a matching entry.
            kind: Optional problem-kind filter.
            capabilities: Capability flags that must all be present.
            study_suitability: Study-suitability flags that must all be present.

        Returns:
            Compact summaries for matching entries in deterministic order.
        """
        return tuple(
            ProblemCatalogSummary.from_metadata(metadata)
            for metadata in self.search(
                tags=tags,
                text=text,
                feature_flags=feature_flags,
                kind=kind,
                capabilities=capabilities,
                study_suitability=study_suitability,
            )
        )

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t1_rectangular_surrogate_grammar"]
    ) -> Battery18650T1RectangularSurrogateGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t2_pose_surrogate_grammar"]
    ) -> Battery18650T2PoseSurrogateGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3a_topology_surrogate_grammar"]
    ) -> Battery18650T3ATopologySurrogateGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3b_netlist_explicit_grammar"]
    ) -> Battery18650T3BNetlistExplicitGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3b_netlist_explicit_2rc_grammar"]
    ) -> Battery18650T3BNetlistExplicitGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t4_thermal_hybrid_grammar"]
    ) -> Battery18650T4ThermalHybridGrammarProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_pack_18650_series_parallel"]
    ) -> BatteryPack18650SeriesParallelProblem: ...

    @overload
    def get(self, problem_id: Literal["battery_pack_18650_open_ended"]) -> BatteryPack18650OpenEndedProblem: ...

    @overload
    def get(self, problem_id: _PlanarTrussProblemId) -> PlanarTrussSpanProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t1_rectangular_surrogate_opt"]
    ) -> Battery18650T1RectangularSurrogateOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t2_pose_surrogate_opt"]
    ) -> Battery18650T2PoseSurrogateOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3a_topology_surrogate_opt"]
    ) -> Battery18650T3ATopologySurrogateOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3a_topology_explicit_2rc_opt"]
    ) -> Battery18650T3ATopologySurrogateOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t3b_netlist_explicit_opt"]
    ) -> Battery18650T3BNetlistExplicitOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t4_thermal_hybrid_2rc_opt"]
    ) -> Battery18650T4ThermalHybridOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_18650_t4_thermal_hybrid_opt"]
    ) -> Battery18650T4ThermalHybridOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_fast_charge_dfn_anchor_opt"]
    ) -> BatteryFastChargeDFNAnchorOptimizationProblem: ...

    @overload
    def get(self, problem_id: Literal["battery_pack_18650_series_parallel_cost_min"]) -> BatteryGridSizingProblem: ...

    @overload
    def get(
        self, problem_id: Literal["battery_pack_18650_open_ended_capacity_max"]
    ) -> BatteryOpenEndedCapacityMaxProblem: ...

    @overload
    def get(self, problem_id: Literal["gmpb_default_dynamic_min"]) -> GMPBOptimizationProblem: ...

    @overload
    def get(self, problem_id: _SpaceTrussProblemId) -> SpaceTrussSpanProblem: ...

    @overload
    def get(self, problem_id: _IoTGrammarProblemId) -> IoTHomeCoolingGrammarProblem: ...

    @overload
    def get(self, problem_id: _TrussAPProblemId) -> TrussAPGrammarProblem: ...

    @overload
    def get(
        self,
        problem_id: Literal[
            "planar_truss_span_mass_min",
            "planar_truss_span_deflection_min",
            "planar_truss_span_fos_max",
        ],
    ) -> PlanarTrussEngineeringOptimizationProblem: ...

    @overload
    def get(self, problem_id: Literal["space_truss_span_mass_min"]) -> SpaceTrussEngineeringOptimizationProblem: ...

    @overload
    def get(self, problem_id: Literal["wind_farm_grid_qkp_power_max"]) -> WindFarmLayoutOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["wind_farm_unrestricted_deficit_min"]
    ) -> UnrestrictedWindFarmLayoutOptimizationProblem: ...

    @overload
    def get(
        self, problem_id: Literal["worker_hours_competing_projects_value_tracking_min"]
    ) -> CompetingProjectsWorkerHoursProblem: ...

    @overload
    def get(self, problem_id: _OptimizationProblemId) -> OptimizationProblem: ...

    @overload
    def get(
        self,
        problem_id: _DecisionProblemId,
    ) -> DecisionProblem: ...

    @overload
    def get(self, problem_id: str) -> Problem: ...

    def get(self, problem_id: str) -> Problem:
        """Instantiate one problem by ID.

        Args:
            problem_id: Stable catalog identifier.

        Returns:
            Loaded problem instance.

        Raises:
            KeyError: If the ID is unknown.
            design_research_problems.ProblemEvaluationError: If the packaged implementation metadata is invalid.
        """
        manifest = self._catalog().get(problem_id)
        if manifest is None:
            raise KeyError(f"Unknown problem id: {problem_id}")

        implementation = manifest.metadata.implementation
        if implementation is not None:
            target = _resolve_object(implementation)
            factory = getattr(target, "from_manifest", None)
            if callable(factory):
                manifest_factory = cast(Callable[[ProblemManifest], Problem], factory)
                return manifest_factory(manifest)

            if callable(target):
                direct_factory = cast(Callable[[ProblemManifest], Problem], target)
                return direct_factory(manifest)

            raise ProblemEvaluationError(f"Problem implementation for {problem_id!r} is not callable.")

        if manifest.metadata.kind is ProblemKind.TEXT:
            return TextProblem.from_manifest(manifest)
        if manifest.metadata.kind is ProblemKind.DECISION:
            return load_decision_problem(manifest)
        if manifest.metadata.kind is ProblemKind.MCP:
            return MCPProblem.from_manifest(manifest)
        raise ProblemEvaluationError(f"Problem {problem_id!r} is missing an implementation path.")

    def get_as(self, problem_id: str, expected_type: type[_ProblemSubT]) -> _ProblemSubT:
        """Instantiate one problem by ID and assert the runtime type.

        Args:
            problem_id: Stable catalog identifier.
            expected_type: Required runtime problem class.

        Returns:
            Loaded problem instance narrowed to ``expected_type``.

        Raises:
            TypeError: If the loaded problem is not an instance of ``expected_type``.
        """
        problem = self.get(problem_id)
        if not isinstance(problem, expected_type):
            raise TypeError(
                f"Problem {problem_id!r} resolved to {type(problem).__name__}, expected {expected_type.__name__}."
            )
        return problem


_DEFAULT_REGISTRY = ProblemRegistry()


def _coerce_problem_kind(kind: ProblemKind | str | None) -> ProblemKind | None:
    """Normalize an optional problem-kind filter.

    Args:
        kind: ProblemKind value, string value, or ``None``.

    Returns:
        Normalized kind or ``None``.
    """
    if kind is None or isinstance(kind, ProblemKind):
        return kind
    return ProblemKind(kind.strip().lower())


def list_problems() -> tuple[str, ...]:
    """Return all packaged problem IDs.

    Returns:
        Stable problem IDs in sorted order.
    """
    return tuple(metadata.problem_id for metadata in _DEFAULT_REGISTRY.list())


def search_problem_summaries(
    *,
    tags: tuple[str, ...] = (),
    text: str = "",
    feature_flags: tuple[str, ...] = (),
    kind: ProblemKind | str | None = None,
    capabilities: tuple[str, ...] = (),
    study_suitability: tuple[str, ...] = (),
) -> tuple[ProblemCatalogSummary, ...]:
    """Search the packaged catalog and return compact problem summaries.

    This is the agent-facing counterpart to loading full briefs with
    ``get_problem(...).render_brief()``. It keeps context windows small while
    still exposing problem IDs, titles, kinds, taxonomy, tags, and capability
    flags needed for routing.

    Args:
        tags: Tags that must all be present on a matching entry.
        text: Case-insensitive free-text search term.
        feature_flags: Feature flags that must all be present on a matching entry.
        kind: Optional problem-kind filter as a ``ProblemKind`` or string value.
        capabilities: Capability flags that must all be present.
        study_suitability: Study-suitability flags that must all be present.

    Returns:
        Compact summaries for matching entries in deterministic order.

    Raises:
        ValueError: If ``kind`` is a string that is not a known problem kind.
    """
    return _DEFAULT_REGISTRY.summaries(
        tags=tags,
        text=text,
        feature_flags=feature_flags,
        kind=_coerce_problem_kind(kind),
        capabilities=capabilities,
        study_suitability=study_suitability,
    )


@overload
def get_problem(
    problem_id: Literal["battery_18650_t1_rectangular_surrogate_grammar"],
) -> Battery18650T1RectangularSurrogateGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t2_pose_surrogate_grammar"],
) -> Battery18650T2PoseSurrogateGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3a_topology_surrogate_grammar"],
) -> Battery18650T3ATopologySurrogateGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3b_netlist_explicit_grammar"],
) -> Battery18650T3BNetlistExplicitGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3b_netlist_explicit_2rc_grammar"],
) -> Battery18650T3BNetlistExplicitGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t4_thermal_hybrid_grammar"],
) -> Battery18650T4ThermalHybridGrammarProblem: ...


@overload
def get_problem(problem_id: Literal["battery_pack_18650_series_parallel"]) -> BatteryPack18650SeriesParallelProblem: ...


@overload
def get_problem(problem_id: Literal["battery_pack_18650_open_ended"]) -> BatteryPack18650OpenEndedProblem: ...


@overload
def get_problem(problem_id: _PlanarTrussProblemId) -> PlanarTrussSpanProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t1_rectangular_surrogate_opt"],
) -> Battery18650T1RectangularSurrogateOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t2_pose_surrogate_opt"],
) -> Battery18650T2PoseSurrogateOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3a_topology_surrogate_opt"],
) -> Battery18650T3ATopologySurrogateOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3a_topology_explicit_2rc_opt"],
) -> Battery18650T3ATopologySurrogateOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t3b_netlist_explicit_opt"],
) -> Battery18650T3BNetlistExplicitOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t4_thermal_hybrid_2rc_opt"],
) -> Battery18650T4ThermalHybridOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_18650_t4_thermal_hybrid_opt"],
) -> Battery18650T4ThermalHybridOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_fast_charge_dfn_anchor_opt"],
) -> BatteryFastChargeDFNAnchorOptimizationProblem: ...


@overload
def get_problem(problem_id: Literal["battery_pack_18650_series_parallel_cost_min"]) -> BatteryGridSizingProblem: ...


@overload
def get_problem(
    problem_id: Literal["battery_pack_18650_open_ended_capacity_max"],
) -> BatteryOpenEndedCapacityMaxProblem: ...


@overload
def get_problem(problem_id: Literal["gmpb_default_dynamic_min"]) -> GMPBOptimizationProblem: ...


@overload
def get_problem(problem_id: _SpaceTrussProblemId) -> SpaceTrussSpanProblem: ...


@overload
def get_problem(problem_id: _IoTGrammarProblemId) -> IoTHomeCoolingGrammarProblem: ...


@overload
def get_problem(problem_id: _TrussAPProblemId) -> TrussAPGrammarProblem: ...


@overload
def get_problem(
    problem_id: Literal[
        "planar_truss_span_mass_min",
        "planar_truss_span_deflection_min",
        "planar_truss_span_fos_max",
    ],
) -> PlanarTrussEngineeringOptimizationProblem: ...


@overload
def get_problem(problem_id: Literal["space_truss_span_mass_min"]) -> SpaceTrussEngineeringOptimizationProblem: ...


@overload
def get_problem(problem_id: Literal["wind_farm_grid_qkp_power_max"]) -> WindFarmLayoutOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["wind_farm_unrestricted_deficit_min"],
) -> UnrestrictedWindFarmLayoutOptimizationProblem: ...


@overload
def get_problem(
    problem_id: Literal["worker_hours_competing_projects_value_tracking_min"],
) -> CompetingProjectsWorkerHoursProblem: ...


@overload
def get_problem(problem_id: _OptimizationProblemId) -> OptimizationProblem: ...


@overload
def get_problem(problem_id: _DecisionProblemId) -> DecisionProblem: ...


@overload
def get_problem(problem_id: str) -> Problem: ...


def get_problem(problem_id: str) -> Problem:
    """Return one problem instance by ID.

    Args:
        problem_id: Stable catalog identifier.

    Returns:
        Loaded problem instance.
    """
    return _DEFAULT_REGISTRY.get(problem_id)


def get_problem_as[ProblemSubT: Problem](problem_id: str, expected_type: type[ProblemSubT]) -> ProblemSubT:
    """Return one problem instance by ID with an asserted runtime type.

    Args:
        problem_id: Stable catalog identifier.
        expected_type: Required runtime problem class.

    Returns:
        Loaded problem instance narrowed to ``expected_type``.
    """
    return _DEFAULT_REGISTRY.get_as(problem_id, expected_type)
