"""Decision problem container."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import product
from math import exp, prod
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

from design_research_problems._exceptions import ProblemEvaluationError
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._computable import ComputableProblem
from design_research_problems.problems._mcp import (
    create_fastmcp_server,
    normalized_optional_text,
    register_design_brief_resource,
    to_json_value,
)
from design_research_problems.problems._metadata import ProblemMetadata

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

    from design_research_problems._catalog._manifest import ProblemManifest

_DISCRETE_MARKET_SIZE = 1_600_000.0
_CHOICE_METRIC_TOP_CHOICE_SHARE = "top-choice-share"
_CHOICE_METRIC_MEAN_RATING = "mean-rating"
_CHOICE_METRIC_MEDIAN_RATING = "median-rating"
ChoiceMetric = Literal["top-choice-share", "mean-rating", "median-rating"]
_SUPPORTED_CHOICE_METRICS = frozenset(
    {
        _CHOICE_METRIC_TOP_CHOICE_SHARE,
        _CHOICE_METRIC_MEAN_RATING,
        _CHOICE_METRIC_MEDIAN_RATING,
    }
)
type DecisionCandidateKind = Literal["discrete-option", "empirical-choice"]


@dataclass(frozen=True)
class DecisionVariableSpec:
    """One bounded engineering-side design variable."""

    symbol: str
    """Stable symbol used in equations and references."""
    label: str
    """Human-readable variable label."""
    unit: str | None
    """Display unit when the source provides one."""
    lower_bound: float
    """Inclusive lower bound for the variable."""
    upper_bound: float
    """Inclusive upper bound for the variable."""

    def __post_init__(self) -> None:
        """Normalize the bounds and enforce a valid interval.

        Raises:
            ValueError: If required fields are empty or the bounds are invalid.
        """
        symbol = self.symbol.strip()
        if not symbol:
            raise ValueError("DecisionVariableSpec requires a non-empty symbol.")
        label = self.label.strip()
        if not label:
            raise ValueError(f"DecisionVariableSpec {symbol!r} requires a non-empty label.")
        unit = None if self.unit is None else self.unit.strip() or None
        lower_bound = float(self.lower_bound)
        upper_bound = float(self.upper_bound)
        if lower_bound > upper_bound:
            raise ValueError(f"DecisionVariableSpec {symbol!r} has lower_bound > upper_bound.")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "lower_bound", lower_bound)
        object.__setattr__(self, "upper_bound", upper_bound)


@dataclass(frozen=True)
class DecisionFactor:
    """One discrete factor in an explicit option space."""

    key: str
    """Stable factor key used in discrete option mappings."""
    label: str
    """Human-readable factor label."""
    unit: str | None
    """Display unit when the source provides one."""
    levels: tuple[float, ...]
    """Ordered discrete levels in source order."""
    part_worths: tuple[float, ...]
    """Utility coefficients aligned with ``levels``."""

    def __post_init__(self) -> None:
        """Normalize and validate the factor definition.

        Raises:
            ValueError: If required fields are empty or the factor payload is malformed.
        """
        key = self.key.strip()
        if not key:
            raise ValueError("DecisionFactor requires a non-empty key.")
        label = self.label.strip()
        if not label:
            raise ValueError(f"DecisionFactor {key!r} requires a non-empty label.")
        unit = None if self.unit is None else self.unit.strip() or None
        levels = tuple(float(level) for level in self.levels)
        if not levels:
            raise ValueError(f"DecisionFactor {key!r} must define at least one level.")
        if any(left >= right for left, right in pairwise(levels)):
            raise ValueError(f"DecisionFactor {key!r} levels must be strictly increasing.")
        part_worths = tuple(float(value) for value in self.part_worths)
        if part_worths and len(part_worths) != len(levels):
            raise ValueError(f"DecisionFactor {key!r} part_worths length must match levels length.")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "levels", levels)
        object.__setattr__(self, "part_worths", part_worths)


@dataclass(frozen=True)
class DecisionOption:
    """One explicit discrete option candidate."""

    values: Mapping[str, float]
    """Exact factor-key to level-value mapping."""

    def __post_init__(self) -> None:
        """Freeze the numeric value mapping."""
        object.__setattr__(self, "values", _freeze_numeric_mapping(self.values))


@dataclass(frozen=True)
class DecisionProfile:
    """One observed alternative profile, such as a competitor."""

    name: str
    """Display name for the observed profile."""
    values: Mapping[str, float]
    """Observed factor-key to value mapping."""

    def __post_init__(self) -> None:
        """Freeze the profile payload.

        Raises:
            ValueError: If the profile name is empty or the values mapping is malformed.
        """
        name = self.name.strip()
        if not name:
            raise ValueError("DecisionProfile requires a non-empty name.")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "values", _freeze_numeric_mapping(self.values))


@dataclass(frozen=True)
class DecisionObjectiveSpec:
    """Structured description of a decision objective."""

    key: str
    """Stable identifier for the objective."""
    label: str
    """Human-readable objective label."""
    sense: str
    """Optimization sense such as ``maximize``."""
    domain: str
    """Model domain such as ``discrete-option``."""
    expression: str
    """Symbolic formula text for the objective."""
    variables: tuple[str, ...]
    """Referenced variable or factor names."""
    executable: bool
    """Whether the package can evaluate this objective directly."""

    def __post_init__(self) -> None:
        """Normalize textual fields and variable references.

        Raises:
            ValueError: If required fields are empty.
        """
        key = self.key.strip()
        if not key:
            raise ValueError("DecisionObjectiveSpec requires a non-empty key.")
        label = self.label.strip()
        if not label:
            raise ValueError(f"DecisionObjectiveSpec {key!r} requires a non-empty label.")
        sense = self.sense.strip().lower()
        if not sense:
            raise ValueError(f"DecisionObjectiveSpec {key!r} requires a non-empty sense.")
        domain = self.domain.strip().lower()
        if not domain:
            raise ValueError(f"DecisionObjectiveSpec {key!r} requires a non-empty domain.")
        expression = self.expression.strip()
        if not expression:
            raise ValueError(f"DecisionObjectiveSpec {key!r} requires a non-empty expression.")
        variables = _normalize_string_tuple(self.variables, context=f"DecisionObjectiveSpec {key!r} variables")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "sense", sense)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "expression", expression)
        object.__setattr__(self, "variables", variables)


@dataclass(frozen=True)
class DecisionConstraintSpec:
    """Structured description of a decision constraint."""

    key: str
    """Stable identifier for the constraint."""
    label: str
    """Human-readable constraint label."""
    relation: str
    """Constraint relation such as ``<=``."""
    domain: str
    """Model domain such as ``continuous-design``."""
    expression: str
    """Symbolic formula text for the constraint."""
    variables: tuple[str, ...]
    """Referenced variable names."""
    executable: bool
    """Whether the package can evaluate this constraint directly."""

    def __post_init__(self) -> None:
        """Normalize textual fields and variable references.

        Raises:
            ValueError: If required fields are empty.
        """
        key = self.key.strip()
        if not key:
            raise ValueError("DecisionConstraintSpec requires a non-empty key.")
        label = self.label.strip()
        if not label:
            raise ValueError(f"DecisionConstraintSpec {key!r} requires a non-empty label.")
        relation = self.relation.strip()
        if not relation:
            raise ValueError(f"DecisionConstraintSpec {key!r} requires a non-empty relation.")
        domain = self.domain.strip().lower()
        if not domain:
            raise ValueError(f"DecisionConstraintSpec {key!r} requires a non-empty domain.")
        expression = self.expression.strip()
        if not expression:
            raise ValueError(f"DecisionConstraintSpec {key!r} requires a non-empty expression.")
        variables = _normalize_string_tuple(self.variables, context=f"DecisionConstraintSpec {key!r} variables")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "relation", relation)
        object.__setattr__(self, "domain", domain)
        object.__setattr__(self, "expression", expression)
        object.__setattr__(self, "variables", variables)


@dataclass(frozen=True)
class DecisionChoiceBenchmark:
    """One empirical categorical choice benchmark entry."""

    key: str
    """Stable option key used for evaluation."""
    label: str
    """Human-readable option label."""
    top_choice_share: float
    """Tie-adjusted fraction of experts whose top score includes this choice."""
    mean_rating: float
    """Mean 0-10 source rating for this choice."""
    median_rating: float
    """Median 0-10 source rating for this choice."""
    std_rating: float
    """Sample standard deviation of the source ratings."""

    def __post_init__(self) -> None:
        """Normalize and validate the benchmark entry.

        Raises:
            ValueError: If any required field is empty or any numeric field is invalid.
        """
        key = self.key.strip().lower()
        if not key:
            raise ValueError("DecisionChoiceBenchmark requires a non-empty key.")
        label = self.label.strip()
        if not label:
            raise ValueError(f"DecisionChoiceBenchmark {key!r} requires a non-empty label.")
        top_choice_share = float(self.top_choice_share)
        if not 0.0 <= top_choice_share <= 1.0:
            raise ValueError(f"DecisionChoiceBenchmark {key!r} top_choice_share must be in [0, 1].")
        std_rating = float(self.std_rating)
        if std_rating < 0.0:
            raise ValueError(f"DecisionChoiceBenchmark {key!r} std_rating must be non-negative.")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "label", label)
        object.__setattr__(self, "top_choice_share", top_choice_share)
        object.__setattr__(self, "mean_rating", float(self.mean_rating))
        object.__setattr__(self, "median_rating", float(self.median_rating))
        object.__setattr__(self, "std_rating", std_rating)


type DecisionCandidate = DecisionOption | Mapping[str, float] | str


@dataclass(frozen=True)
class DecisionEvaluation:
    """Unified evaluation result for one decision candidate."""

    candidate_kind: DecisionCandidateKind
    """Whether the result came from a discrete or empirical decision problem."""
    candidate: DecisionOption | str
    """Canonical candidate representation used for evaluation."""
    candidate_label: str
    """Human-readable candidate label."""
    objective_value: float
    """Objective scalar used for ranking."""
    objective_metric: str
    """Metric or objective identifier used to populate ``objective_value``."""
    option: DecisionOption | None = None
    """Normalized option that was evaluated when in discrete mode."""
    utility: float | None = None
    """Discrete part-worth utility of the option."""
    predicted_share: float | None = None
    """Predicted logit market share against the competitor set."""
    expected_demand_units: float | None = None
    """Expected demand under the fixed market-size assumption."""
    choice_key: str | None = None
    """Canonical empirical choice key when in empirical mode."""
    choice_label: str | None = None
    """Human-readable empirical choice label when in empirical mode."""
    top_choice_share: float | None = None
    """Tie-adjusted fraction of expert top matches."""
    mean_rating: float | None = None
    """Mean 0-10 source rating for the choice."""
    median_rating: float | None = None
    """Median 0-10 source rating for the choice."""
    std_rating: float | None = None
    """Sample standard deviation of the source ratings."""
    response_count: int | None = None
    """Number of valid respondents included in the aggregate."""

    def __post_init__(self) -> None:
        """Normalize textual and numeric outputs.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        candidate_label = self.candidate_label.strip()
        if not candidate_label:
            raise ValueError("DecisionEvaluation requires a non-empty candidate_label.")
        objective_metric = self.objective_metric.strip().lower()
        if not objective_metric:
            raise ValueError("DecisionEvaluation requires a non-empty objective_metric.")
        if self.candidate_kind not in {"discrete-option", "empirical-choice"}:
            raise ValueError(f"Unsupported decision candidate kind: {self.candidate_kind!r}")
        object.__setattr__(self, "candidate_label", candidate_label)
        object.__setattr__(self, "objective_value", float(self.objective_value))
        object.__setattr__(self, "objective_metric", objective_metric)
        if self.utility is not None:
            object.__setattr__(self, "utility", float(self.utility))
        if self.predicted_share is not None:
            object.__setattr__(self, "predicted_share", float(self.predicted_share))
        if self.expected_demand_units is not None:
            object.__setattr__(self, "expected_demand_units", float(self.expected_demand_units))
        if self.choice_key is not None:
            choice_key = self.choice_key.strip().lower()
            if not choice_key:
                raise ValueError("DecisionEvaluation choice_key must be non-empty when provided.")
            object.__setattr__(self, "choice_key", choice_key)
        if self.choice_label is not None:
            choice_label = self.choice_label.strip()
            if not choice_label:
                raise ValueError("DecisionEvaluation choice_label must be non-empty when provided.")
            object.__setattr__(self, "choice_label", choice_label)
        if self.top_choice_share is not None:
            object.__setattr__(self, "top_choice_share", float(self.top_choice_share))
        if self.mean_rating is not None:
            object.__setattr__(self, "mean_rating", float(self.mean_rating))
        if self.median_rating is not None:
            object.__setattr__(self, "median_rating", float(self.median_rating))
        if self.std_rating is not None:
            object.__setattr__(self, "std_rating", float(self.std_rating))
        if self.response_count is not None:
            response_count = int(self.response_count)
            if response_count < 0:
                raise ValueError("DecisionEvaluation response_count must be non-negative.")
            object.__setattr__(self, "response_count", response_count)


@dataclass(frozen=True)
class _ParsedDecisionPayload:
    """Internal parsed representation of structured decision fields."""

    decision_variable_specs: tuple[DecisionVariableSpec, ...]
    """Parsed engineering variable specs."""
    option_factors: tuple[DecisionFactor, ...]
    """Parsed discrete conjoint factors."""
    choice_benchmarks: tuple[DecisionChoiceBenchmark, ...]
    """Parsed empirical categorical choice benchmarks."""
    competitor_profiles: tuple[DecisionProfile, ...]
    """Parsed observed competitor profiles."""
    objective_specs: tuple[DecisionObjectiveSpec, ...]
    """Parsed objective descriptors."""
    constraint_specs: tuple[DecisionConstraintSpec, ...]
    """Parsed constraint descriptors."""
    default_choice_metric: ChoiceMetric
    """Default metric for empirical choice ranking."""
    response_count: int
    """Number of valid respondents represented by the aggregates."""


@dataclass(frozen=True)
class _NaturalCubicSpline:
    """Natural cubic spline with linear endpoint extrapolation."""

    x_values: tuple[float, ...]
    """Ordered spline knot positions."""
    y_values: tuple[float, ...]
    """Spline knot values aligned with ``x_values``."""
    second_derivatives: tuple[float, ...]
    """Precomputed second derivatives at each knot."""

    @classmethod
    def from_points(cls, x_values: Sequence[float], y_values: Sequence[float]) -> _NaturalCubicSpline:
        """Build one spline from ordered knot values.

        Args:
            x_values: Ordered knot positions.
            y_values: Knot values aligned with ``x_values``.

        Returns:
            Spline instance ready for evaluation.

        Raises:
            ValueError: If the point sequences are empty, mismatched, or not strictly increasing.
        """
        x = tuple(float(value) for value in x_values)
        y = tuple(float(value) for value in y_values)
        if len(x) != len(y):
            raise ValueError("Natural cubic spline requires x and y sequences of the same length.")
        if not x:
            raise ValueError("Natural cubic spline requires at least one point.")
        if any(left >= right for left, right in pairwise(x)):
            raise ValueError("Natural cubic spline x values must be strictly increasing.")
        if len(x) <= 2:
            second_derivatives = tuple(0.0 for _ in x)
            return cls(x_values=x, y_values=y, second_derivatives=second_derivatives)

        h = [right - left for left, right in pairwise(x)]
        alpha = [
            6.0 * ((y[index + 1] - y[index]) / h[index] - (y[index] - y[index - 1]) / h[index - 1])
            for index in range(1, len(x) - 1)
        ]

        lower = [0.0]
        diagonal = [1.0]
        upper = [0.0]
        rhs = [0.0]

        for index in range(1, len(x) - 1):
            lower.append(h[index - 1])
            diagonal.append(2.0 * (h[index - 1] + h[index]))
            upper.append(h[index] if index < len(x) - 2 else 0.0)
            rhs.append(alpha[index - 1])

        lower.append(0.0)
        diagonal.append(1.0)
        upper.append(0.0)
        rhs.append(0.0)

        second_derivatives = _solve_tridiagonal(lower, diagonal, upper, rhs)
        return cls(x_values=x, y_values=y, second_derivatives=second_derivatives)

    def evaluate(self, x_value: float) -> float:
        """Evaluate the spline or its boundary extension at one point.

        Args:
            x_value: Input position to evaluate.

        Returns:
            Interpolated or linearly extrapolated value.

        Raises:
            RuntimeError: If interval lookup unexpectedly fails for an in-range value.
        """
        if len(self.x_values) == 1:
            return self.y_values[0]
        x_value = float(x_value)
        if x_value <= self.x_values[0]:
            slope = self._segment_slope(segment_index=0, at_right=False)
            return self.y_values[0] + slope * (x_value - self.x_values[0])
        if x_value >= self.x_values[-1]:
            slope = self._segment_slope(segment_index=len(self.x_values) - 2, at_right=True)
            return self.y_values[-1] + slope * (x_value - self.x_values[-1])

        for segment_index, (left, right) in enumerate(pairwise(self.x_values)):
            if left <= x_value <= right:
                h = right - left
                alpha = (right - x_value) / h
                beta = (x_value - left) / h
                return (
                    alpha * self.y_values[segment_index]
                    + beta * self.y_values[segment_index + 1]
                    + (
                        ((alpha**3) - alpha) * self.second_derivatives[segment_index]
                        + ((beta**3) - beta) * self.second_derivatives[segment_index + 1]
                    )
                    * (h**2)
                    / 6.0
                )
        raise RuntimeError("Spline interval lookup failed for an in-range value.")

    def _segment_slope(self, segment_index: int, at_right: bool) -> float:
        """Return the derivative at one end of a segment.

        Args:
            segment_index: Zero-based segment index.
            at_right: Whether to evaluate the derivative at the right endpoint.

        Returns:
            Segment-end derivative.
        """
        left = self.x_values[segment_index]
        right = self.x_values[segment_index + 1]
        h = right - left
        delta = (self.y_values[segment_index + 1] - self.y_values[segment_index]) / h
        left_m = self.second_derivatives[segment_index]
        right_m = self.second_derivatives[segment_index + 1]
        if at_right:
            return delta + h * (2.0 * right_m + left_m) / 6.0
        return delta - h * (2.0 * left_m + right_m) / 6.0


def parse_structured_decision_payload(parameters: Mapping[str, object]) -> _ParsedDecisionPayload:
    """Parse one manifest parameter mapping into typed decision metadata.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed typed payload.

    Raises:
        ValueError: If any structured payload is malformed or internally inconsistent.
    """
    decision_variable_specs = _parse_decision_variable_specs(parameters)
    option_factors = _parse_option_factors(parameters)
    choice_benchmarks = _parse_choice_benchmarks(parameters)
    competitor_profiles = _parse_competitor_profiles(parameters)
    objective_specs = _parse_objective_specs(parameters)
    constraint_specs = _parse_constraint_specs(parameters)
    default_choice_metric = _parse_default_choice_metric(parameters, has_choice_benchmarks=bool(choice_benchmarks))
    response_count = _parse_response_count(parameters, has_choice_benchmarks=bool(choice_benchmarks))

    variable_symbols = {spec.symbol for spec in decision_variable_specs}
    factor_keys = {factor.key for factor in option_factors}
    choice_keys = {benchmark.key for benchmark in choice_benchmarks}
    symbolic_names = variable_symbols | factor_keys
    if choice_benchmarks:
        symbolic_names.add("material")
    objective_keys = set[str]()
    for objective in objective_specs:
        if objective.key in objective_keys:
            raise ValueError(f"Duplicate decision objective key: {objective.key!r}")
        objective_keys.add(objective.key)
        if objective.executable:
            if objective.sense != "maximize":
                raise ValueError(f"Executable decision objective {objective.key!r} must use sense 'maximize'.")
            if objective.domain == "discrete-option":
                if not option_factors:
                    raise ValueError(f"Executable decision objective {objective.key!r} requires option_factors.")
                if not competitor_profiles:
                    raise ValueError(f"Executable decision objective {objective.key!r} requires competitor_profiles.")
                if any(not factor.part_worths for factor in option_factors):
                    raise ValueError(f"Executable decision objective {objective.key!r} requires factor part_worths.")
                unknown = [name for name in objective.variables if name not in factor_keys]
                if unknown:
                    raise ValueError(
                        f"Executable decision objective {objective.key!r} references unknown factor keys: {unknown!r}"
                    )
                continue
            if objective.domain == "empirical-choice":
                if not choice_benchmarks:
                    raise ValueError(f"Executable decision objective {objective.key!r} requires choice_options.")
                unknown = [name for name in objective.variables if name != "material"]
                if unknown:
                    raise ValueError(
                        f"Executable decision objective {objective.key!r} references unknown variables: {unknown!r}"
                    )
                continue
            raise ValueError(
                f"Executable decision objective {objective.key!r} must use domain 'discrete-option' or "
                f"'empirical-choice'."
            )
        else:
            unknown = [name for name in objective.variables if name not in symbolic_names]
            if unknown:
                raise ValueError(f"Decision objective {objective.key!r} references unknown variables: {unknown!r}")

    constraint_keys = set[str]()
    for constraint in constraint_specs:
        if constraint.key in constraint_keys:
            raise ValueError(f"Duplicate decision constraint key: {constraint.key!r}")
        constraint_keys.add(constraint.key)
        unknown = [name for name in constraint.variables if name not in variable_symbols]
        if unknown:
            raise ValueError(f"Decision constraint {constraint.key!r} references unknown variables: {unknown!r}")

    if competitor_profiles and not option_factors:
        raise ValueError("competitor_profiles require option_factors.")
    ordered_factor_keys = tuple(factor.key for factor in option_factors)
    factor_key_set = set(ordered_factor_keys)
    for profile in competitor_profiles:
        if set(profile.values) != factor_key_set or len(profile.values) != len(ordered_factor_keys):
            raise ValueError(f"Decision profile {profile.name!r} must include exactly the option factor keys.")
    if choice_benchmarks and response_count <= 0:
        raise ValueError("choice_options require a positive response_count.")
    if len(choice_keys) != len(choice_benchmarks):
        raise ValueError("choice_options contain duplicate keys.")

    return _ParsedDecisionPayload(
        decision_variable_specs=decision_variable_specs,
        option_factors=option_factors,
        choice_benchmarks=choice_benchmarks,
        competitor_profiles=competitor_profiles,
        objective_specs=objective_specs,
        constraint_specs=constraint_specs,
        default_choice_metric=default_choice_metric,
        response_count=response_count,
    )


class DecisionProblem(ComputableProblem[DecisionCandidate, DecisionEvaluation]):
    """Concrete decision problem with a unified candidate/evaluation workflow."""

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> DecisionProblem:
        """Construct the problem directly from a packaged manifest.

        Args:
            manifest: Value for ``manifest``.

        Returns:
            Computed result for this callable.
        """
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            parameters=manifest.parameters,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
        )

    def __init__(
        self,
        *,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        parameters: Mapping[str, object],
        resource_bundle: PackageResourceBundle | None = None,
    ) -> None:
        """Parse the structured decision payload and cache shared lookups.

        Args:
            metadata: Value for ``metadata``.
            statement_markdown: Value for ``statement_markdown``.
            parameters: Value for ``parameters``.
            resource_bundle: Value for ``resource_bundle``.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.parameters = MappingProxyType(dict(parameters))
        payload = parse_structured_decision_payload(self.parameters)
        self._decision_variable_specs = payload.decision_variable_specs
        self._option_factors = payload.option_factors
        self._choice_benchmarks = payload.choice_benchmarks
        self._competitor_profiles = payload.competitor_profiles
        self._objective_specs = payload.objective_specs
        self._constraint_specs = payload.constraint_specs
        self._default_choice_metric = payload.default_choice_metric
        self._response_count = payload.response_count
        self._factor_splines = MappingProxyType(
            {
                factor.key: _NaturalCubicSpline.from_points(factor.levels, factor.part_worths)
                for factor in payload.option_factors
                if factor.part_worths
            }
        )
        choice_lookup: dict[str, DecisionChoiceBenchmark] = {}
        for benchmark in payload.choice_benchmarks:
            choice_lookup[benchmark.key.lower()] = benchmark
            choice_lookup[benchmark.label.lower()] = benchmark
        self._choice_lookup = MappingProxyType(choice_lookup)
        has_discrete = bool(self._option_factors)
        has_empirical = bool(self._choice_benchmarks)
        if has_discrete == has_empirical:
            raise ValueError(
                "DecisionProblem requires exactly one executable candidate source: "
                "either option_factors or choice_benchmarks."
            )
        self._candidate_kind: DecisionCandidateKind = "discrete-option" if has_discrete else "empirical-choice"

    @property
    def candidate_kind(self) -> DecisionCandidateKind:
        """Return the active decision-candidate mode.

        Returns:
            Computed result for this callable.
        """
        return self._candidate_kind

    @property
    def decision_variables(self) -> tuple[str, ...]:
        """Return the curated decision-variable descriptions.

        Returns:
            Decision-variable descriptions in source order.
        """
        return self._string_list("decision_variables")

    @property
    def decision_variable_specs(self) -> tuple[DecisionVariableSpec, ...]:
        """Return typed engineering variable specifications.

        Returns:
            Parsed engineering variable specs in source order.
        """
        return self._decision_variable_specs

    @property
    def objectives(self) -> tuple[str, ...]:
        """Return the stated objective descriptions.

        Returns:
            Objective descriptions in source order.
        """
        return self._string_list("objectives")

    @property
    def objective_specs(self) -> tuple[DecisionObjectiveSpec, ...]:
        """Return typed objective descriptors.

        Returns:
            Parsed objective specs in source order.
        """
        return self._objective_specs

    @property
    def constraints(self) -> tuple[str, ...]:
        """Return the curated constraint descriptions.

        Returns:
            Constraint descriptions in source order.
        """
        return self._string_list("constraints")

    @property
    def constraint_specs(self) -> tuple[DecisionConstraintSpec, ...]:
        """Return typed constraint descriptors.

        Returns:
            Parsed constraint specs in source order.
        """
        return self._constraint_specs

    @property
    def assumptions(self) -> tuple[str, ...]:
        """Return the modeling assumptions or caveats.

        Returns:
            Assumption or caveat strings in source order.
        """
        return self._string_list("assumptions")

    @property
    def option_factors(self) -> tuple[DecisionFactor, ...]:
        """Return the typed discrete conjoint factors.

        Returns:
            Parsed discrete factors in source order.
        """
        return self._option_factors

    @property
    def choice_benchmarks(self) -> tuple[DecisionChoiceBenchmark, ...]:
        """Return the empirical categorical choice benchmarks.

        Returns:
            Parsed empirical choice benchmarks in source order.
        """
        return self._choice_benchmarks

    @property
    def default_choice_metric(self) -> ChoiceMetric:
        """Return the default metric used for empirical choice ranking.

        Returns:
            Supported metric name.
        """
        return self._default_choice_metric

    @property
    def competitor_profiles(self) -> tuple[DecisionProfile, ...]:
        """Return the observed competitor profiles.

        Returns:
            Parsed competitor profiles in source order.
        """
        return self._competitor_profiles

    @property
    def option_count(self) -> int:
        """Return the total size of the explicit discrete option space.

        Returns:
            Product of all discrete factor cardinalities.
        """
        if not self.option_factors:
            return 0
        return int(prod(len(factor.levels) for factor in self.option_factors))

    @property
    def candidate_count(self) -> int:
        """Return the number of candidates exposed by the active decision mode.

        Returns:
            Computed result for this callable.
        """
        if self.candidate_kind == "discrete-option":
            return self.option_count
        return len(self.choice_benchmarks)

    def iter_candidates(self) -> Iterator[DecisionOption | str]:
        """Yield candidates in deterministic source order.

        Yields:
            Generated values from iter candidates.
        """
        if self.candidate_kind == "discrete-option":
            factor_keys = tuple(factor.key for factor in self.option_factors)
            level_domains = tuple(factor.levels for factor in self.option_factors)
            for combination in product(*level_domains):
                yield DecisionOption(values=dict(zip(factor_keys, combination, strict=True)))
            return

        for benchmark in self.choice_benchmarks:
            yield benchmark.key

    def evaluate(self, candidate: DecisionCandidate) -> DecisionEvaluation:
        """Evaluate one candidate using the active decision mode.

        Args:
            candidate: Value for ``candidate``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        if self.candidate_kind == "discrete-option":
            if isinstance(candidate, str) or not isinstance(candidate, (DecisionOption, Mapping)):
                raise TypeError(
                    "Discrete-option decision problems require a DecisionOption or factor-to-level mapping."
                )
            return self._evaluate_option(candidate)
        if not isinstance(candidate, str):
            raise TypeError("Empirical-choice decision problems require a string choice key.")
        return self._evaluate_choice(candidate)

    def iter_evaluations(self, metric: ChoiceMetric | None = None) -> Iterator[DecisionEvaluation]:
        """Yield evaluations for every candidate in deterministic order.

        Args:
            metric: Value for ``metric``.

        Yields:
            Generated values from iter evaluations.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        if self.candidate_kind == "discrete-option":
            if metric is not None:
                raise ProblemEvaluationError("Discrete-option decision problems do not support metric overrides.")
            for candidate in self.iter_candidates():
                yield self._evaluate_option(cast(DecisionOption, candidate))
            return

        selected_metric = self._normalize_choice_metric(metric)
        for benchmark in self.choice_benchmarks:
            yield self._build_choice_evaluation(benchmark, selected_metric)

    def rank_evaluations(self, metric: ChoiceMetric | None = None) -> tuple[DecisionEvaluation, ...]:
        """Return all candidate evaluations ranked by the active objective.

        Args:
            metric: Value for ``metric``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        if self.candidate_kind == "discrete-option":
            if metric is not None:
                raise ProblemEvaluationError("Discrete-option decision problems do not support metric overrides.")
            evaluations = tuple(self.iter_evaluations())
            return tuple(sorted(evaluations, key=lambda item: item.objective_value, reverse=True))

        ranked = list(enumerate(self.iter_evaluations(metric=metric)))
        ranked.sort(
            key=lambda item: (
                -item[1].objective_value,
                -cast(float, item[1].mean_rating),
                item[0],
            )
        )
        return tuple(evaluation for _, evaluation in ranked)

    def best_evaluation(self, metric: ChoiceMetric | None = None) -> DecisionEvaluation:
        """Return the highest-ranked evaluation in the active mode.

        Args:
            metric: Value for ``metric``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        ranked = self.rank_evaluations(metric=metric)
        if not ranked:
            raise ProblemEvaluationError("Decision problem does not define any evaluable candidates.")
        return ranked[0]

    def _evaluate_option(self, option: DecisionOption | Mapping[str, float]) -> DecisionEvaluation:
        """Evaluate one explicit discrete option against the competitor set.

        Args:
            option: Value for ``option``.

        Returns:
            Computed result for this callable.

        Raises:
            Exception: Raised when the callable encounters an invalid state.
        """
        objective = self._executable_objective()
        if objective.domain != "discrete-option":
            raise ProblemEvaluationError("Decision problem does not define an executable discrete-option objective.")

        candidate = self._coerce_option(option)
        utility = sum(self._factor_part_worth(factor, candidate.values[factor.key]) for factor in self.option_factors)
        denominator = exp(utility)
        for profile in self.competitor_profiles:
            denominator += exp(self._profile_utility(profile))
        predicted_share = exp(utility) / denominator
        expected_demand_units = _DISCRETE_MARKET_SIZE * predicted_share
        return DecisionEvaluation(
            candidate_kind="discrete-option",
            candidate=candidate,
            candidate_label=self._format_option_label(candidate),
            objective_metric=objective.key,
            option=candidate,
            utility=utility,
            predicted_share=predicted_share,
            expected_demand_units=expected_demand_units,
            objective_value=predicted_share,
        )

    def _evaluate_choice(
        self,
        choice: str,
        metric: ChoiceMetric | None = None,
    ) -> DecisionEvaluation:
        """Evaluate one empirical categorical choice option.

        Args:
            choice: Value for ``choice``.
            metric: Value for ``metric``.

        Returns:
            Computed result for this callable.
        """
        benchmark = self._coerce_choice(choice)
        selected_metric = self._normalize_choice_metric(metric)
        return self._build_choice_evaluation(benchmark, selected_metric)

    def _build_choice_evaluation(
        self,
        benchmark: DecisionChoiceBenchmark,
        metric: ChoiceMetric,
    ) -> DecisionEvaluation:
        """Build one empirical evaluation payload for a normalized benchmark.

        Args:
            benchmark: Value for ``benchmark``.
            metric: Value for ``metric``.

        Returns:
            Computed result for this callable.
        """
        return DecisionEvaluation(
            candidate_kind="empirical-choice",
            candidate=benchmark.key,
            candidate_label=benchmark.label,
            objective_metric=metric,
            choice_key=benchmark.key,
            choice_label=benchmark.label,
            top_choice_share=benchmark.top_choice_share,
            mean_rating=benchmark.mean_rating,
            median_rating=benchmark.median_rating,
            std_rating=benchmark.std_rating,
            response_count=self._response_count,
            objective_value=self._choice_metric_value(benchmark, metric),
        )

    def _rank_choice_evaluations(
        self,
        metric: ChoiceMetric | None = None,
    ) -> tuple[DecisionEvaluation, ...]:
        """Return all empirical choices ranked by one metric.

        Args:
            metric: Value for ``metric``.

        Returns:
            Computed result for this callable.
        """
        return self.rank_evaluations(metric=metric)

    def render_brief(
        self,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> str:
        """Render the decision statement plus its extracted structure.

        Args:
            include_citation: Whether to append bundled source citations.
            citation_mode: Citation rendering mode for the ``Sources`` section.

        Returns:
            Markdown brief suitable for review or reuse.
        """
        sections = [self.render_packet(include_citation=False)]

        context_lines: list[str] = []
        for key, label in (
            ("decision_maker", "Decision maker"),
            ("market_segment", "Market segment"),
            ("decision_scope", "Decision scope"),
        ):
            value = self._string_value(key)
            if value is not None:
                context_lines.append(f"- {label}: {value}")
        if context_lines:
            sections.append("## Context")
            sections.append("\n".join(context_lines))

        for heading, values in (
            ("Decision Variables", self.decision_variables),
            ("Objectives", self.objectives),
            ("Constraints", self.constraints),
            ("Assumptions", self.assumptions),
        ):
            if values:
                sections.append(f"## {heading}")
                sections.append(self._render_bullets(values))

        if self.objective_specs:
            sections.append("## Objective Model")
            sections.append(self._render_objective_specs())

        if self.constraint_specs:
            sections.append("## Constraint Equations")
            sections.append(self._render_constraint_specs())

        if self.option_factors:
            sections.append("## Option Space")
            sections.append(self._render_option_space())

        if self.choice_benchmarks:
            sections.append("## Choices")
            sections.append(self._render_choice_options())
            sections.append("## Empirical Benchmark")
            sections.append(self._render_empirical_benchmark())

        if include_citation and self.metadata.citations:
            if citation_mode in {"summary", "summary+raw"}:
                sections.append("## Sources")
                sections.append(self._render_citation_summaries())
            if citation_mode in {"raw", "summary+raw"}:
                sections.append("## BibTeX")
                sections.append(self._render_citation_raw_blocks())

        return "\n\n".join(sections)

    def to_mcp_server(
        self,
        *,
        server_name: str | None = None,
        include_citation: bool = True,
        citation_mode: Literal["summary", "summary+raw", "raw"] = "summary",
    ) -> FastMCP:
        """Expose this decision problem through FastMCP.

        The exported server exposes:
        - ``problem://design-brief`` resource (structured decision brief)
        - ``problem://decision-candidates`` resource (deterministic index mapping)
        - ``final_answer(choice_index, justification?)`` tool

        Args:
            server_name: Optional explicit server name.
            include_citation: Whether the brief includes citation sections.
            citation_mode: Citation rendering mode for the brief resource.

        Returns:
            Configured FastMCP server.
        """
        server = create_fastmcp_server(self, server_name=server_name)
        register_design_brief_resource(
            server,
            brief_text=self.render_brief(include_citation=include_citation, citation_mode=citation_mode),
        )

        indexed_candidates = tuple(enumerate(self.iter_candidates()))

        @server.resource(
            "problem://decision-candidates",
            name="decision-candidates",
            title="Decision Candidates",
            description="Deterministic zero-based candidate index mapping.",
            mime_type="application/json",
        )
        def decision_candidates() -> dict[str, object]:
            """Return the deterministic decision-candidate index mapping.

            Returns:
                MCP-ready payload describing the indexed candidates.
            """
            entries: list[dict[str, object]] = []
            for index, candidate in indexed_candidates:
                if isinstance(candidate, str):
                    label = self._coerce_choice(candidate).label
                else:
                    label = self._format_option_label(candidate)
                entries.append(
                    {
                        "choice_index": index,
                        "candidate": to_json_value(candidate),
                        "candidate_label": label,
                    }
                )

            return {
                "problem_id": self.metadata.problem_id,
                "candidate_kind": self.candidate_kind,
                "candidate_count": len(indexed_candidates),
                "candidates": entries,
            }

        def final_answer(choice_index: int, justification: str | None = None) -> dict[str, object]:
            """Submit one indexed final decision answer.

            Args:
                choice_index: Zero-based index of the selected candidate.
                justification: Optional justification text.

            Returns:
                MCP-ready submission payload for the selected candidate.

            Raises:
                ValueError: If ``choice_index`` is outside the valid range.
            """
            if choice_index < 0 or choice_index >= len(indexed_candidates):
                raise ValueError(
                    f"choice_index must be in [0, {len(indexed_candidates) - 1}] for this decision problem."
                )
            candidate = indexed_candidates[choice_index][1]
            evaluation = self.evaluate(candidate)
            return {
                "problem_id": self.metadata.problem_id,
                "problem_kind": self.metadata.kind.value,
                "candidate_kind": self.candidate_kind,
                "choice_index": choice_index,
                "candidate": to_json_value(candidate),
                "candidate_label": evaluation.candidate_label,
                "justification": normalized_optional_text(justification),
                "evaluation": to_json_value(evaluation),
            }

        server.add_tool(
            final_answer,
            name="final_answer",
            title="Submit Final Answer",
            description="Submit the final answer by zero-based candidate index.",
        )
        return server

    def _coerce_option(self, option: DecisionOption | Mapping[str, float]) -> DecisionOption:
        """Normalize one caller-supplied option to the declared factor space.

        Args:
            option: Candidate option object or factor-to-level mapping.

        Returns:
            Normalized option validated against the factor space.

        Raises:
            ValueError: If the option keys or values do not match the declared factor space.
        """
        raw_values = option.values if isinstance(option, DecisionOption) else option
        if not isinstance(raw_values, Mapping):
            raise ValueError("Option must be a mapping of factor keys to numeric levels.")
        factor_keys = tuple(factor.key for factor in self.option_factors)
        if set(raw_values) != set(factor_keys) or len(raw_values) != len(factor_keys):
            raise ValueError("Option must include exactly the declared factor keys.")

        normalized: dict[str, float] = {}
        for factor in self.option_factors:
            raw_value = raw_values[factor.key]
            value = float(raw_value)
            if value not in factor.levels:
                raise ValueError(f"Option value {value!r} is not a declared level for factor {factor.key!r}.")
            normalized[factor.key] = value
        return DecisionOption(values=normalized)

    def _executable_objective(self) -> DecisionObjectiveSpec:
        """Return the first executable objective descriptor.

        Returns:
            The first executable objective spec.

        Raises:
            ProblemEvaluationError: If no executable objective is defined.
        """
        for objective in self.objective_specs:
            if objective.executable:
                return objective
        raise ProblemEvaluationError("Decision problem does not define an executable objective.")

    def _coerce_choice(self, choice: str) -> DecisionChoiceBenchmark:
        """Normalize one caller-supplied empirical choice identifier.

        Args:
            choice: Canonical key or display label to resolve.

        Returns:
            Matching empirical choice benchmark.

        Raises:
            ValueError: If the requested choice name is unknown.
            ProblemEvaluationError: If the problem has no empirical choice benchmark data.
        """
        if not self.choice_benchmarks:
            raise ProblemEvaluationError("Decision problem does not define empirical choice benchmarks.")
        key = choice.strip().lower()
        if not key:
            raise ValueError("Choice must be a non-empty string.")
        benchmark = self._choice_lookup.get(key)
        if benchmark is None:
            raise ValueError(f"Unknown choice: {choice!r}")
        return benchmark

    def _normalize_choice_metric(
        self,
        metric: ChoiceMetric | None,
    ) -> ChoiceMetric:
        """Return one supported empirical choice metric name.

        Args:
            metric: Optional user-provided metric override.

        Returns:
            Supported metric name.

        Raises:
            ValueError: If the provided metric is unsupported.
        """
        normalized = self.default_choice_metric if metric is None else metric.strip().lower()
        if normalized not in _SUPPORTED_CHOICE_METRICS:
            raise ValueError(f"Unsupported choice metric: {metric!r}")
        return cast(ChoiceMetric, normalized)

    def _choice_metric_value(self, benchmark: DecisionChoiceBenchmark, metric: str) -> float:
        """Return one benchmark value keyed by metric name.

        Args:
            benchmark: Choice benchmark to read.
            metric: Supported metric name.

        Returns:
            Numeric benchmark value.

        Raises:
            ValueError: If the provided metric is unsupported.
        """
        if metric == _CHOICE_METRIC_TOP_CHOICE_SHARE:
            return benchmark.top_choice_share
        if metric == _CHOICE_METRIC_MEAN_RATING:
            return benchmark.mean_rating
        if metric == _CHOICE_METRIC_MEDIAN_RATING:
            return benchmark.median_rating
        raise ValueError(f"Unsupported choice metric: {metric!r}")

    def _format_option_label(self, option: DecisionOption) -> str:
        """Render one option in factor order as a stable label.

        Args:
            option: Value for ``option``.

        Returns:
            Computed result for this callable.
        """
        parts = [f"{factor.key}={_format_number(option.values[factor.key])}" for factor in self.option_factors]
        return ", ".join(parts)

    def _factor_part_worth(self, factor: DecisionFactor, value: float) -> float:
        """Return the exact discrete part-worth coefficient for one level.

        Args:
            factor: Discrete factor containing the level.
            value: Exact declared factor level.

        Returns:
            Part-worth coefficient for the requested level.

        Raises:
            ProblemEvaluationError: If the factor does not carry part-worth coefficients.
        """
        if not factor.part_worths:
            raise ProblemEvaluationError(f"Factor {factor.key!r} does not define part_worths.")
        level_index = factor.levels.index(value)
        return factor.part_worths[level_index]

    def _profile_utility(self, profile: DecisionProfile) -> float:
        """Return the spline-interpolated utility for one observed profile.

        Args:
            profile: Observed profile to score.

        Returns:
            Spline-interpolated utility.

        Raises:
            ProblemEvaluationError: If a required factor cannot be evaluated.
        """
        utility = 0.0
        for factor in self.option_factors:
            spline = self._factor_splines.get(factor.key)
            if spline is None:
                raise ProblemEvaluationError(f"Factor {factor.key!r} cannot be evaluated without part_worths.")
            utility += spline.evaluate(profile.values[factor.key])
        return utility

    def _render_constraint_specs(self) -> str:
        """Render typed constraint descriptors as bullets.

        Returns:
            Markdown bullet list for the typed constraints.
        """
        lines = []
        for constraint in self.constraint_specs:
            executable = "yes" if constraint.executable else "no"
            lines.append(
                f"- {constraint.label} (`{constraint.key}`, {constraint.relation}, {constraint.domain}, "
                f"executable={executable}): {constraint.expression}"
            )
        return "\n".join(lines)

    def _render_objective_specs(self) -> str:
        """Render typed objective descriptors as bullets.

        Returns:
            Markdown bullet list for the typed objectives.
        """
        lines = []
        for objective in self.objective_specs:
            executable = "yes" if objective.executable else "no"
            lines.append(
                f"- {objective.label} (`{objective.key}`, {objective.sense}, {objective.domain}, "
                f"executable={executable}): {objective.expression}"
            )
        return "\n".join(lines)

    def _render_option_space(self) -> str:
        """Render the factor space summary without expanding all combinations.

        Returns:
            Markdown bullet list summarizing the discrete option space.
        """
        lines: list[str] = []
        for factor in self.option_factors:
            unit_suffix = f" {factor.unit}" if factor.unit else ""
            levels_text = ", ".join(_format_number(value) for value in factor.levels)
            lines.append(f"- {factor.label} (`{factor.key}`{unit_suffix}): [{levels_text}]")
        lines.append(f"- Total discrete options: {self.option_count:,}")
        return "\n".join(lines)

    def _render_choice_options(self) -> str:
        """Render the empirical choice labels in source order.

        Returns:
            Markdown bullet list of the categorical options.
        """
        return "\n".join(f"- {benchmark.label} (`{benchmark.key}`)" for benchmark in self.choice_benchmarks)

    def _render_empirical_benchmark(self) -> str:
        """Render the empirical benchmark as a Markdown table.

        Returns:
            Markdown table sorted by the default choice metric.
        """
        evaluations = self._rank_choice_evaluations(metric=self.default_choice_metric)
        lines = [
            "| Choice | Key | Top Choice Share | Mean Rating | Median Rating | Std Rating |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
        for evaluation in evaluations:
            choice_label = cast(str, evaluation.choice_label)
            choice_key = cast(str, evaluation.choice_key)
            top_choice_share = cast(float, evaluation.top_choice_share)
            mean_rating = cast(float, evaluation.mean_rating)
            median_rating = cast(float, evaluation.median_rating)
            std_rating = cast(float, evaluation.std_rating)
            lines.append(
                "| "
                f"{choice_label} | "
                f"`{choice_key}` | "
                f"{top_choice_share:.6f} | "
                f"{mean_rating:.6f} | "
                f"{median_rating:.6f} | "
                f"{std_rating:.6f} |"
            )
        return "\n".join(lines)

    def _string_value(self, key: str) -> str | None:
        """Return one non-empty string parameter when present.

        Args:
            key: Parameter name to read from the structured metadata mapping.

        Returns:
            Stripped string content, or ``None`` when the parameter is missing or empty.
        """
        raw_value = self.parameters.get(key)
        if not isinstance(raw_value, str):
            return None
        value = raw_value.strip()
        return value or None

    def _string_list(self, key: str) -> tuple[str, ...]:
        """Return one normalized string-list parameter when present.

        Args:
            key: Parameter name to read from the structured metadata mapping.

        Returns:
            Non-empty string values coerced from the stored sequence, preserving order.
        """
        raw_value = self.parameters.get(key)
        if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
            return ()
        values: list[str] = []
        for entry in raw_value:
            item = str(entry).strip()
            if item:
                values.append(item)
        return tuple(values)

    def _render_bullets(self, items: tuple[str, ...]) -> str:
        """Render a tuple of strings as a Markdown bullet list.

        Args:
            items: Bullet body text in display order.

        Returns:
            Markdown bullet list text.
        """
        return "\n".join(f"- {item}" for item in items)


def load_decision_problem(manifest: ProblemManifest) -> DecisionProblem:
    """Construct one concrete decision problem from a packaged manifest.

    Args:
        manifest: Value for ``manifest``.

    Returns:
        Computed result for this callable.
    """
    return DecisionProblem.from_manifest(manifest)


def _freeze_numeric_mapping(values: Mapping[str, float]) -> Mapping[str, float]:
    """Return an immutable string-to-float mapping.

    Args:
        values: Raw mapping to normalize and freeze.

    Returns:
        Immutable mapping with stripped keys and float values.

    Raises:
        ValueError: If any key is empty after normalization.
    """
    normalized: dict[str, float] = {}
    for key, raw_value in values.items():
        normalized_key = str(key).strip()
        if not normalized_key:
            raise ValueError("Decision mappings require non-empty keys.")
        normalized[normalized_key] = float(raw_value)
    return MappingProxyType(normalized)


def _format_number(value: float) -> str:
    """Render one numeric value without unnecessary trailing zeros.

    Args:
        value: Numeric value to render.

    Returns:
        Compact decimal text.
    """
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"


def _normalize_string_tuple(raw_values: Sequence[object], context: str) -> tuple[str, ...]:
    """Return one normalized tuple of non-empty strings.

    Args:
        raw_values: Raw values to normalize.
        context: Context label for validation errors.

    Returns:
        Stripped non-empty strings in the original order.

    Raises:
        ValueError: If any entry becomes empty after normalization.
    """
    values: list[str] = []
    for raw_value in raw_values:
        value = str(raw_value).strip()
        if not value:
            raise ValueError(f"{context} entries must be non-empty strings.")
        values.append(value)
    return tuple(values)


def _parse_decision_variable_specs(parameters: Mapping[str, object]) -> tuple[DecisionVariableSpec, ...]:
    """Parse structured engineering variable specs.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed engineering variable specs.

    Raises:
        ValueError: If the structured payload is malformed.
    """
    raw_specs = _list_of_mappings(parameters.get("decision_variable_specs"), field_name="decision_variable_specs")
    specs: list[DecisionVariableSpec] = []
    seen_symbols: set[str] = set()
    for entry in raw_specs:
        spec = DecisionVariableSpec(
            symbol=str(entry.get("symbol", "")),
            label=str(entry.get("label", "")),
            unit=_optional_string(entry.get("unit")),
            lower_bound=_required_float(entry, "lower_bound"),
            upper_bound=_required_float(entry, "upper_bound"),
        )
        if spec.symbol in seen_symbols:
            raise ValueError(f"Duplicate decision variable symbol: {spec.symbol!r}")
        seen_symbols.add(spec.symbol)
        specs.append(spec)
    return tuple(specs)


def _parse_option_factors(parameters: Mapping[str, object]) -> tuple[DecisionFactor, ...]:
    """Parse structured discrete factor specs.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed discrete factor specs.

    Raises:
        ValueError: If the structured payload is malformed.
    """
    raw_factors = _list_of_mappings(parameters.get("option_factors"), field_name="option_factors")
    factors: list[DecisionFactor] = []
    seen_keys: set[str] = set()
    for entry in raw_factors:
        factor = DecisionFactor(
            key=str(entry.get("key", "")),
            label=str(entry.get("label", "")),
            unit=_optional_string(entry.get("unit")),
            levels=_float_tuple(entry.get("levels"), field_name="option_factors.levels"),
            part_worths=_float_tuple(entry.get("part_worths"), field_name="option_factors.part_worths"),
        )
        if factor.key in seen_keys:
            raise ValueError(f"Duplicate option factor key: {factor.key!r}")
        seen_keys.add(factor.key)
        factors.append(factor)
    return tuple(factors)


def _parse_choice_benchmarks(parameters: Mapping[str, object]) -> tuple[DecisionChoiceBenchmark, ...]:
    """Parse structured empirical categorical choice benchmarks.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed empirical choice benchmarks.

    Raises:
        ValueError: If the structured payload is malformed.
    """
    raw_options = _list_of_mappings(parameters.get("choice_options"), field_name="choice_options")
    benchmarks: list[DecisionChoiceBenchmark] = []
    seen_keys: set[str] = set()
    seen_labels: set[str] = set()
    for entry in raw_options:
        benchmark = DecisionChoiceBenchmark(
            key=str(entry.get("key", "")),
            label=str(entry.get("label", "")),
            top_choice_share=_required_float(entry, "top_choice_share"),
            mean_rating=_required_float(entry, "mean_rating"),
            median_rating=_required_float(entry, "median_rating"),
            std_rating=_required_float(entry, "std_rating"),
        )
        if benchmark.key in seen_keys:
            raise ValueError(f"Duplicate choice option key: {benchmark.key!r}")
        label_key = benchmark.label.lower()
        if label_key in seen_labels:
            raise ValueError(f"Duplicate choice option label: {benchmark.label!r}")
        seen_keys.add(benchmark.key)
        seen_labels.add(label_key)
        benchmarks.append(benchmark)
    return tuple(benchmarks)


def _parse_default_choice_metric(
    parameters: Mapping[str, object],
    has_choice_benchmarks: bool,
) -> ChoiceMetric:
    """Parse the default empirical choice metric.

    Args:
        parameters: Raw manifest parameter mapping.
        has_choice_benchmarks: Whether empirical choices are present.

    Returns:
        Supported metric name.

    Raises:
        ValueError: If the provided metric is unsupported.
    """
    raw_value = parameters.get("default_choice_metric")
    if raw_value is None:
        del has_choice_benchmarks
        return cast(ChoiceMetric, _CHOICE_METRIC_TOP_CHOICE_SHARE)
    value = str(raw_value).strip().lower()
    if value not in _SUPPORTED_CHOICE_METRICS:
        raise ValueError(f"Unsupported default_choice_metric: {value!r}")
    return cast(ChoiceMetric, value)


def _parse_response_count(parameters: Mapping[str, object], has_choice_benchmarks: bool) -> int:
    """Parse the empirical response count.

    Args:
        parameters: Raw manifest parameter mapping.
        has_choice_benchmarks: Whether empirical choices are present.

    Returns:
        Parsed integer response count.

    Raises:
        ValueError: If the count is negative, non-integral, or missing when required.
    """
    raw_value = parameters.get("response_count")
    if raw_value is None:
        return 0
    response_count = _coerce_int(raw_value, field_name="response_count")
    if has_choice_benchmarks and response_count <= 0:
        raise ValueError("response_count must be positive when choice_options are present.")
    if response_count < 0:
        raise ValueError("response_count must be non-negative.")
    return response_count


def _parse_competitor_profiles(parameters: Mapping[str, object]) -> tuple[DecisionProfile, ...]:
    """Parse structured competitor profiles.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed competitor profiles.

    Raises:
        ValueError: If the structured payload is malformed.
    """
    raw_profiles = _list_of_mappings(parameters.get("competitor_profiles"), field_name="competitor_profiles")
    profiles: list[DecisionProfile] = []
    seen_names: set[str] = set()
    for entry in raw_profiles:
        raw_values = entry.get("values")
        if not isinstance(raw_values, Mapping):
            raise ValueError("competitor_profiles values must be mappings.")
        profile = DecisionProfile(name=str(entry.get("name", "")), values=raw_values)
        if profile.name in seen_names:
            raise ValueError(f"Duplicate competitor profile name: {profile.name!r}")
        seen_names.add(profile.name)
        profiles.append(profile)
    return tuple(profiles)


def _parse_objective_specs(parameters: Mapping[str, object]) -> tuple[DecisionObjectiveSpec, ...]:
    """Parse structured objective specs.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed objective specs.
    """
    raw_specs = _list_of_mappings(parameters.get("objective_specs"), field_name="objective_specs")
    specs: list[DecisionObjectiveSpec] = []
    for entry in raw_specs:
        raw_variables = _string_tuple(entry.get("variables"), field_name="objective_specs.variables")
        specs.append(
            DecisionObjectiveSpec(
                key=str(entry.get("key", "")),
                label=str(entry.get("label", "")),
                sense=str(entry.get("sense", "")),
                domain=str(entry.get("domain", "")),
                expression=str(entry.get("expression", "")),
                variables=raw_variables,
                executable=bool(entry.get("executable", False)),
            )
        )
    return tuple(specs)


def _parse_constraint_specs(parameters: Mapping[str, object]) -> tuple[DecisionConstraintSpec, ...]:
    """Parse structured constraint specs.

    Args:
        parameters: Raw manifest parameter mapping.

    Returns:
        Parsed constraint specs.
    """
    raw_specs = _list_of_mappings(parameters.get("constraint_specs"), field_name="constraint_specs")
    specs: list[DecisionConstraintSpec] = []
    for entry in raw_specs:
        raw_variables = _string_tuple(entry.get("variables"), field_name="constraint_specs.variables")
        specs.append(
            DecisionConstraintSpec(
                key=str(entry.get("key", "")),
                label=str(entry.get("label", "")),
                relation=str(entry.get("relation", "")),
                domain=str(entry.get("domain", "")),
                expression=str(entry.get("expression", "")),
                variables=raw_variables,
                executable=bool(entry.get("executable", False)),
            )
        )
    return tuple(specs)


def _list_of_mappings(raw_value: object, field_name: str) -> tuple[Mapping[str, object], ...]:
    """Return one tuple of mapping entries from a raw manifest field.

    Args:
        raw_value: Raw manifest field to inspect.
        field_name: Field label for validation errors.

    Returns:
        Tuple of mapping entries.

    Raises:
        ValueError: If the raw field is not a sequence of mappings.
    """
    if raw_value is None:
        return ()
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence of mappings.")
    mappings: list[Mapping[str, object]] = []
    for entry in raw_value:
        if not isinstance(entry, Mapping):
            raise ValueError(f"{field_name} entries must be mappings.")
        mappings.append(entry)
    return tuple(mappings)


def _sequence(raw_value: object, field_name: str) -> tuple[object, ...]:
    """Return one sequence field as a tuple.

    Args:
        raw_value: Raw manifest field to inspect.
        field_name: Field label for validation errors.

    Returns:
        Tuple of raw sequence entries.

    Raises:
        ValueError: If the raw field is not a supported sequence.
    """
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
        raise ValueError(f"{field_name} must be a sequence.")
    return tuple(raw_value)


def _float_tuple(raw_value: object, field_name: str) -> tuple[float, ...]:
    """Return one raw numeric sequence as a tuple of floats.

    Args:
        raw_value: Raw manifest field to inspect.
        field_name: Field label for validation errors.

    Returns:
        Tuple of normalized float values.
    """
    return tuple(_coerce_float(value, field_name=field_name) for value in _sequence(raw_value, field_name=field_name))


def _string_tuple(raw_value: object, field_name: str) -> tuple[str, ...]:
    """Return one raw string sequence as a tuple of normalized strings.

    Args:
        raw_value: Raw manifest field to inspect.
        field_name: Field label for validation errors.

    Returns:
        Tuple of stripped strings.
    """
    return tuple(str(value).strip() for value in _sequence(raw_value, field_name=field_name))


def _optional_string(raw_value: object) -> str | None:
    """Normalize one optional string field.

    Args:
        raw_value: Raw optional scalar value.

    Returns:
        Stripped string content, or ``None`` when empty or missing.
    """
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    return value or None


def _required_float(entry: Mapping[str, object], key: str) -> float:
    """Read one required numeric field from a raw mapping.

    Args:
        entry: Raw mapping to read from.
        key: Required field name.

    Returns:
        Parsed float value.

    Raises:
        ValueError: If the field is missing or cannot be parsed as numeric.
    """
    if key not in entry:
        raise ValueError(f"Missing required numeric field: {key}")
    return _coerce_float(entry[key], field_name=key)


def _coerce_int(raw_value: object, field_name: str) -> int:
    """Coerce one raw scalar to int with a clear validation error.

    Args:
        raw_value: Raw scalar to convert.
        field_name: Field label for validation errors.

    Returns:
        Parsed integer value.

    Raises:
        ValueError: If the raw value is empty, non-numeric, or not integral.
    """
    numeric_value = _coerce_float(raw_value, field_name=field_name)
    if not numeric_value.is_integer():
        raise ValueError(f"{field_name} must be an integer.")
    return int(numeric_value)


def _coerce_float(raw_value: object, field_name: str) -> float:
    """Coerce one raw scalar to float with a clear validation error.

    Args:
        raw_value: Raw scalar to convert.
        field_name: Field label for validation errors.

    Returns:
        Parsed float value.

    Raises:
        ValueError: If the raw value is empty or non-numeric.
    """
    if isinstance(raw_value, bool):
        return float(raw_value)
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    if isinstance(raw_value, str):
        value = raw_value.strip()
        if not value:
            raise ValueError(f"{field_name} must not be an empty string.")
        return float(value)
    raise ValueError(f"{field_name} must be numeric.")


def _solve_tridiagonal(
    lower: Sequence[float],
    diagonal: Sequence[float],
    upper: Sequence[float],
    rhs: Sequence[float],
) -> tuple[float, ...]:
    """Solve one tridiagonal linear system with the Thomas algorithm.

    Args:
        lower: Lower-diagonal coefficients.
        diagonal: Main-diagonal coefficients.
        upper: Upper-diagonal coefficients.
        rhs: Right-hand-side vector.

    Returns:
        Solution vector as a tuple of floats.

    Raises:
        ValueError: If the system dimensions are inconsistent or singular.
    """
    size = len(diagonal)
    if not (len(lower) == len(upper) == len(rhs) == size):
        raise ValueError("Tridiagonal system inputs must all have the same length.")
    if size == 0:
        return ()

    c_prime = [0.0] * size
    d_prime = [0.0] * size
    if diagonal[0] == 0.0:
        raise ValueError("Tridiagonal system has a zero leading diagonal entry.")
    c_prime[0] = upper[0] / diagonal[0]
    d_prime[0] = rhs[0] / diagonal[0]

    for index in range(1, size):
        denominator = diagonal[index] - lower[index] * c_prime[index - 1]
        if denominator == 0.0:
            raise ValueError("Tridiagonal system is singular.")
        c_prime[index] = upper[index] / denominator if index < size - 1 else 0.0
        d_prime[index] = (rhs[index] - lower[index] * d_prime[index - 1]) / denominator

    solution = [0.0] * size
    solution[-1] = d_prime[-1]
    for index in range(size - 2, -1, -1):
        solution[index] = d_prime[index] - c_prime[index] * solution[index + 1]
    return tuple(solution)


def pairwise(values: Sequence[float]) -> Iterator[tuple[float, float]]:
    """Yield adjacent pairs from one sequence.

    Args:
        values: Ordered values to pair.

    Yields:
        Adjacent two-tuples in left-to-right order.
    """
    for index in range(len(values) - 1):
        yield values[index], values[index + 1]
