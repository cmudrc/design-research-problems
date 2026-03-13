"""Fast-charge lithium-ion cell optimization benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import numpy
from numpy.typing import NDArray
from scipy.integrate import cumulative_trapezoid

from design_research_problems._catalog._manifest import ProblemManifest
from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._assets import PackageResourceBundle
from design_research_problems.problems._metadata import ProblemMetadata
from design_research_problems.problems._optimization import (
    Bounds,
    ConstraintDefinition,
    OptimizationProblem,
    OptimizationResult,
)

_INFEASIBILITY_PENALTY_SCALE = 1_000.0
_DEFAULT_PARAMETER_SET = "Chen2020"
_DEFAULT_FAILURE_CHARGE_TIME_MIN = 999.0
_DEFAULT_MAX_TEMPERATURE_C = 50.0
_DEFAULT_MAX_PLATING_MOL_M3 = 1.0e-5
_DEFAULT_MIN_ENERGY_DENSITY_WH_PER_L = 0.0
_DEFAULT_CHARGE_C_RATE = 1.5
_DEFAULT_AMBIENT_TEMPERATURE_C = 25.0
_DEFAULT_HEAT_TRANSFER_COEFFICIENT_W_PER_M2K = 10.0
_DEFAULT_PACKAGING_EFFICIENCY = 0.86
_DEFAULT_REST_BEFORE_CHARGE_MIN = 2.0
_DEFAULT_REST_AFTER_CHARGE_MIN = 30.0
_DEFAULT_TARGET_SOC_START = 0.10
_DEFAULT_TARGET_SOC_END = 0.80
_DEFAULT_MAX_VOLTAGE_V = 4.2
_DEFAULT_CV_CUTOFF_DENOMINATOR = 50.0
_DEFAULT_MESH_POINTS = 10


def _coerce_float(value: object, default: float) -> float:
    """Return one manifest-like float with a fallback default."""
    return default if value is None else float(cast(float | int | str, value))


def _coerce_int(value: object, default: int) -> int:
    """Return one manifest-like integer with a fallback default."""
    return default if value is None else int(cast(int | float | str, value))


@dataclass(frozen=True)
class FastChargeVariableSpec:
    """One bounded fast-charge design variable."""

    name: str
    parameter_name: str
    lower: float
    upper: float
    default: float


@dataclass(frozen=True)
class FastChargeMetricSummary:
    """Structured metrics returned by one fast-charge simulation."""

    charge_time_min: float
    max_plating_mol_m3: float
    max_temperature_c: float
    energy_density_wh_per_l: float
    success: bool
    failure_reason: str | None = None

    def as_dict(self) -> dict[str, float]:
        """Return the public metric payload."""
        return {
            "charge_time_min": float(self.charge_time_min),
            "max_plating_mol_m3": float(self.max_plating_mol_m3),
            "max_temperature_c": float(self.max_temperature_c),
            "energy_density_wh_per_l": float(self.energy_density_wh_per_l),
            "success": 1.0 if self.success else 0.0,
        }


_VARIABLE_SPECS: tuple[FastChargeVariableSpec, ...] = (
    FastChargeVariableSpec(
        name="negative_electrode_thickness_m",
        parameter_name="Negative electrode thickness [m]",
        lower=1.0e-5,
        upper=1.0e-3,
        default=8.52e-5,
    ),
    FastChargeVariableSpec(
        name="positive_electrode_thickness_m",
        parameter_name="Positive electrode thickness [m]",
        lower=1.0e-5,
        upper=1.0e-3,
        default=7.56e-5,
    ),
    FastChargeVariableSpec(
        name="separator_thickness_m",
        parameter_name="Separator thickness [m]",
        lower=5.0e-6,
        upper=5.0e-5,
        default=1.2e-5,
    ),
    FastChargeVariableSpec(
        name="negative_electrode_porosity",
        parameter_name="Negative electrode porosity",
        lower=0.10,
        upper=0.70,
        default=0.25,
    ),
    FastChargeVariableSpec(
        name="positive_electrode_porosity",
        parameter_name="Positive electrode porosity",
        lower=0.10,
        upper=0.70,
        default=0.335,
    ),
    FastChargeVariableSpec(
        name="negative_particle_radius_m",
        parameter_name="Negative electrode particle radius [m]",
        lower=1.0e-7,
        upper=5.0e-5,
        default=5.86e-6,
    ),
    FastChargeVariableSpec(
        name="positive_particle_radius_m",
        parameter_name="Positive electrode particle radius [m]",
        lower=1.0e-7,
        upper=5.0e-5,
        default=5.22e-6,
    ),
    FastChargeVariableSpec(
        name="negative_active_volume_fraction",
        parameter_name="Negative electrode active material volume fraction",
        lower=0.20,
        upper=0.85,
        default=0.75,
    ),
    FastChargeVariableSpec(
        name="positive_active_volume_fraction",
        parameter_name="Positive electrode active material volume fraction",
        lower=0.20,
        upper=0.85,
        default=0.665,
    ),
)

_FAST_CHARGE_EDIT_SEQUENCE: tuple[tuple[int, float], ...] = (
    (0, 0.90),
    (1, 0.90),
    (2, 0.90),
    (3, 1.10),
    (4, 1.10),
    (5, 0.90),
    (6, 0.90),
    (7, 0.95),
    (8, 0.95),
    (0, 0.95),
    (1, 0.95),
    (2, 0.95),
    (3, 1.05),
    (4, 1.05),
    (5, 0.95),
    (6, 0.95),
    (7, 0.98),
    (8, 0.98),
)


def import_pybamm_fast_charge() -> Any:
    """Import ``pybamm`` for the fast-charge benchmark."""
    return import_optional_module(
        "pybamm",
        required_for="battery fast-charge optimization",
        extras=("battery",),
        make_target="install-pybamm",
    )


def _failure_metrics(
    *,
    failure_reason: str,
    failure_charge_time_min: float,
    maximum_temperature_c: float,
    maximum_plating_mol_m3: float,
) -> FastChargeMetricSummary:
    """Return finite failure metrics for solver or setup failures."""
    return FastChargeMetricSummary(
        charge_time_min=float(failure_charge_time_min),
        max_plating_mol_m3=float(max(maximum_plating_mol_m3 * 10.0, 1.0)),
        max_temperature_c=float(max(maximum_temperature_c + 50.0, 100.0)),
        energy_density_wh_per_l=0.0,
        success=False,
        failure_reason=failure_reason,
    )


def _safe_solution_max(solution: Any, variable_names: tuple[str, ...], default: float) -> float:
    """Return the maximum of the first available PyBaMM solution variable."""
    for variable_name in variable_names:
        try:
            return float(numpy.max(solution[variable_name].entries))
        except KeyError:
            continue
    return float(default)


def _safe_solution_min(solution: Any, variable_names: tuple[str, ...], default: float) -> float:
    """Return the minimum of the first available PyBaMM solution variable."""
    for variable_name in variable_names:
        try:
            return float(numpy.min(solution[variable_name].entries))
        except KeyError:
            continue
    return float(default)


def _safe_parameter_value(parameters: Any, name: str, default: float) -> float:
    """Return one parameter value with a fallback default."""
    try:
        return float(parameters[name])
    except Exception:
        return float(default)


def evaluate_fast_charge_design(
    design_parameters: dict[str, float],
    *,
    parameter_set: str = _DEFAULT_PARAMETER_SET,
    initial_soc_fraction: float = 0.0,
    charge_c_rate: float = _DEFAULT_CHARGE_C_RATE,
    target_soc_start: float = _DEFAULT_TARGET_SOC_START,
    target_soc_end: float = _DEFAULT_TARGET_SOC_END,
    max_voltage_v: float = _DEFAULT_MAX_VOLTAGE_V,
    cv_cutoff_denominator: float = _DEFAULT_CV_CUTOFF_DENOMINATOR,
    ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
    heat_transfer_coefficient_w_per_m2k: float = _DEFAULT_HEAT_TRANSFER_COEFFICIENT_W_PER_M2K,
    packaging_efficiency: float = _DEFAULT_PACKAGING_EFFICIENCY,
    rest_before_charge_min: float = _DEFAULT_REST_BEFORE_CHARGE_MIN,
    rest_after_charge_min: float = _DEFAULT_REST_AFTER_CHARGE_MIN,
    mesh_points: int = _DEFAULT_MESH_POINTS,
    failure_charge_time_min: float = _DEFAULT_FAILURE_CHARGE_TIME_MIN,
    maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
    maximum_plating_mol_m3: float = _DEFAULT_MAX_PLATING_MOL_M3,
) -> FastChargeMetricSummary:
    """Simulate one fast-charge candidate using a PyBaMM DFN model."""
    pybamm = import_pybamm_fast_charge()
    try:
        options = {
            "thermal": "lumped",
            "lithium plating": "partially reversible",
            "SEI": "solvent-diffusion limited",
        }
        model = pybamm.lithium_ion.DFN(options)
        parameters = pybamm.ParameterValues(parameter_set)
        parameters.update(
            {
                "Dead lithium decay rate [s-1]": 1.0e-6,
                "Typical plated lithium concentration [mol.m-3]": 1_000.0,
                "Initial plated lithium concentration [mol.m-3]": 0.0,
                "Lithium metal partial molar volume [m3.mol-1]": 1.3e-5,
                "Exchange-current density for plating [A.m-2]": 0.001,
                "Exchange-current density for stripping [A.m-2]": 0.001,
                "Lithium plating transfer coefficient": 0.5,
                "Lithium stripping transfer coefficient": 0.5,
                "Ambient temperature [K]": 273.15 + float(ambient_temperature_c),
                "Total heat transfer coefficient [W.m-2.K-1]": float(heat_transfer_coefficient_w_per_m2k),
            },
            check_already_exists=False,
        )
        parameters.update(design_parameters, check_already_exists=False)
        parameters.set_initial_stoichiometries(float(initial_soc_fraction))

        experiment = pybamm.Experiment(
            [
                f"Rest for {rest_before_charge_min:g} min",
                f"Charge at {charge_c_rate:g}C until {max_voltage_v:g}V",
                f"Hold at {max_voltage_v:g}V until C/{cv_cutoff_denominator:g}",
                f"Rest for {rest_after_charge_min:g} min",
            ]
        )
        sim = pybamm.Simulation(
            model,
            parameter_values=parameters,
            experiment=experiment,
            var_pts={
                "x_n": mesh_points,
                "x_s": mesh_points,
                "x_p": mesh_points,
                "r_n": mesh_points,
                "r_p": mesh_points,
            },
        )
        try:
            solver = pybamm.IDAKLUSolver()
        except Exception:
            solver = pybamm.CasadiSolver(mode="safe", dt_max=120)
        solution = sim.solve(solver=solver)
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        return _failure_metrics(
            failure_reason=str(exc),
            failure_charge_time_min=failure_charge_time_min,
            maximum_temperature_c=maximum_temperature_c,
            maximum_plating_mol_m3=maximum_plating_mol_m3,
        )

    current_amps = numpy.array(solution["Current [A]"].entries, dtype=float)
    time_seconds = numpy.array(solution["Time [s]"].entries, dtype=float)
    time_hours = time_seconds / 3600.0
    ah_charged = cumulative_trapezoid(-current_amps, time_hours, initial=0.0)
    true_capacity_ah = float(numpy.max(ah_charged)) if ah_charged.size else 0.0
    soc_profile = ah_charged / true_capacity_ah if true_capacity_ah > 1.0e-12 else numpy.zeros_like(ah_charged)

    reached_target = bool(numpy.any(soc_profile >= target_soc_end))
    if reached_target:
        start_index = int(numpy.argmax(soc_profile >= target_soc_start))
        end_index = int(numpy.argmax(soc_profile >= target_soc_end))
        charge_time_min = float((time_seconds[end_index] - time_seconds[start_index]) / 60.0)
    else:
        charge_time_min = float(failure_charge_time_min)

    voltage = numpy.array(solution["Terminal voltage [V]"].entries, dtype=float)
    energy_wh = float(numpy.trapezoid(voltage * numpy.abs(current_amps), time_hours))
    cell_volume_m3 = _safe_parameter_value(parameters, "Cell volume [m3]", default=1.0e-5)
    energy_density_wh_per_l = (energy_wh / max(cell_volume_m3 * 1_000.0, 1.0e-12)) * float(packaging_efficiency)

    max_plating_mol_m3 = _safe_solution_max(
        solution,
        (
            "Negative lithium plating concentration [mol.m-3]",
            "X-averaged negative lithium plating concentration [mol.m-3]",
        ),
        default=0.0,
    )
    max_temperature_k = _safe_solution_max(
        solution,
        (
            "X-averaged cell temperature [K]",
            "Volume-averaged cell temperature [K]",
            "Cell temperature [K]",
        ),
        default=273.15 + ambient_temperature_c,
    )
    _safe_solution_min(
        solution,
        ("Negative electrode potential [V]",),
        default=0.0,
    )
    return FastChargeMetricSummary(
        charge_time_min=float(charge_time_min),
        max_plating_mol_m3=float(max_plating_mol_m3),
        max_temperature_c=float(max_temperature_k - 273.15),
        energy_density_wh_per_l=float(energy_density_wh_per_l),
        success=True,
        failure_reason=None if reached_target else "Charge protocol did not reach the target SOC window.",
    )


class BatteryFastChargeOptimizationProblem(OptimizationProblem):
    """Optimize cell-design parameters for fast charging under safety constraints."""

    def __init__(
        self,
        metadata: ProblemMetadata,
        statement_markdown: str = "",
        resource_bundle: PackageResourceBundle | None = None,
        *,
        parameter_set: str = _DEFAULT_PARAMETER_SET,
        initial_soc_fraction: float = 0.0,
        charge_c_rate: float = _DEFAULT_CHARGE_C_RATE,
        target_soc_start: float = _DEFAULT_TARGET_SOC_START,
        target_soc_end: float = _DEFAULT_TARGET_SOC_END,
        max_voltage_v: float = _DEFAULT_MAX_VOLTAGE_V,
        cv_cutoff_denominator: float = _DEFAULT_CV_CUTOFF_DENOMINATOR,
        maximum_temperature_c: float = _DEFAULT_MAX_TEMPERATURE_C,
        maximum_plating_mol_m3: float = _DEFAULT_MAX_PLATING_MOL_M3,
        minimum_energy_density_wh_per_l: float = _DEFAULT_MIN_ENERGY_DENSITY_WH_PER_L,
        ambient_temperature_c: float = _DEFAULT_AMBIENT_TEMPERATURE_C,
        heat_transfer_coefficient_w_per_m2k: float = _DEFAULT_HEAT_TRANSFER_COEFFICIENT_W_PER_M2K,
        packaging_efficiency: float = _DEFAULT_PACKAGING_EFFICIENCY,
        rest_before_charge_min: float = _DEFAULT_REST_BEFORE_CHARGE_MIN,
        rest_after_charge_min: float = _DEFAULT_REST_AFTER_CHARGE_MIN,
        mesh_points: int = _DEFAULT_MESH_POINTS,
        failure_charge_time_min: float = _DEFAULT_FAILURE_CHARGE_TIME_MIN,
    ) -> None:
        """Store benchmark configuration and bounded design variables."""
        super().__init__(
            metadata=metadata,
            statement_markdown=statement_markdown,
            resource_bundle=resource_bundle,
        )
        self.parameter_set = str(parameter_set)
        self.initial_soc_fraction = float(initial_soc_fraction)
        self.charge_c_rate = float(charge_c_rate)
        self.target_soc_start = float(target_soc_start)
        self.target_soc_end = float(target_soc_end)
        self.max_voltage_v = float(max_voltage_v)
        self.cv_cutoff_denominator = float(cv_cutoff_denominator)
        self.maximum_temperature_c = float(maximum_temperature_c)
        self.maximum_plating_mol_m3 = float(maximum_plating_mol_m3)
        self.minimum_energy_density_wh_per_l = float(minimum_energy_density_wh_per_l)
        self.ambient_temperature_c = float(ambient_temperature_c)
        self.heat_transfer_coefficient_w_per_m2k = float(heat_transfer_coefficient_w_per_m2k)
        self.packaging_efficiency = float(packaging_efficiency)
        self.rest_before_charge_min = float(rest_before_charge_min)
        self.rest_after_charge_min = float(rest_after_charge_min)
        self.mesh_points = max(4, int(mesh_points))
        self.failure_charge_time_min = float(failure_charge_time_min)
        self.bounds = Bounds(
            lb=numpy.array([spec.lower for spec in _VARIABLE_SPECS], dtype=float),
            ub=numpy.array([spec.upper for spec in _VARIABLE_SPECS], dtype=float),
        )
        self._evaluation_cache: dict[tuple[float, ...], FastChargeMetricSummary] = {}
        self.constraints = [
            ConstraintDefinition(kind="ineq", evaluate=self._success_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._temperature_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._plating_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._negative_volume_fraction_margin),
            ConstraintDefinition(kind="ineq", evaluate=self._positive_volume_fraction_margin),
        ]
        if self.minimum_energy_density_wh_per_l > 0.0:
            self.constraints.append(ConstraintDefinition(kind="ineq", evaluate=self._energy_density_margin))

    @classmethod
    def from_manifest(cls, manifest: ProblemManifest) -> BatteryFastChargeOptimizationProblem:
        """Construct one fast-charge optimizer from manifest data."""
        parameters = manifest.parameters
        return cls(
            metadata=manifest.metadata,
            statement_markdown=manifest.statement_markdown,
            resource_bundle=cls.resource_bundle_from_manifest(manifest),
            parameter_set=str(parameters.get("parameter_set", _DEFAULT_PARAMETER_SET)),
            initial_soc_fraction=_coerce_float(parameters.get("initial_soc_fraction"), 0.0),
            charge_c_rate=_coerce_float(parameters.get("charge_c_rate"), _DEFAULT_CHARGE_C_RATE),
            target_soc_start=_coerce_float(parameters.get("target_soc_start"), _DEFAULT_TARGET_SOC_START),
            target_soc_end=_coerce_float(parameters.get("target_soc_end"), _DEFAULT_TARGET_SOC_END),
            max_voltage_v=_coerce_float(parameters.get("max_voltage_v"), _DEFAULT_MAX_VOLTAGE_V),
            cv_cutoff_denominator=_coerce_float(
                parameters.get("cv_cutoff_denominator"),
                _DEFAULT_CV_CUTOFF_DENOMINATOR,
            ),
            maximum_temperature_c=_coerce_float(
                parameters.get("maximum_temperature_c"),
                _DEFAULT_MAX_TEMPERATURE_C,
            ),
            maximum_plating_mol_m3=_coerce_float(
                parameters.get("maximum_plating_mol_m3"),
                _DEFAULT_MAX_PLATING_MOL_M3,
            ),
            minimum_energy_density_wh_per_l=_coerce_float(
                parameters.get("minimum_energy_density_wh_per_l"),
                _DEFAULT_MIN_ENERGY_DENSITY_WH_PER_L,
            ),
            ambient_temperature_c=_coerce_float(
                parameters.get("ambient_temperature_c"),
                _DEFAULT_AMBIENT_TEMPERATURE_C,
            ),
            heat_transfer_coefficient_w_per_m2k=_coerce_float(
                parameters.get("heat_transfer_coefficient_w_per_m2k"),
                _DEFAULT_HEAT_TRANSFER_COEFFICIENT_W_PER_M2K,
            ),
            packaging_efficiency=_coerce_float(
                parameters.get("packaging_efficiency"),
                _DEFAULT_PACKAGING_EFFICIENCY,
            ),
            rest_before_charge_min=_coerce_float(
                parameters.get("rest_before_charge_min"),
                _DEFAULT_REST_BEFORE_CHARGE_MIN,
            ),
            rest_after_charge_min=_coerce_float(
                parameters.get("rest_after_charge_min"),
                _DEFAULT_REST_AFTER_CHARGE_MIN,
            ),
            mesh_points=_coerce_int(parameters.get("mesh_points"), _DEFAULT_MESH_POINTS),
            failure_charge_time_min=_coerce_float(
                parameters.get("failure_charge_time_min"),
                _DEFAULT_FAILURE_CHARGE_TIME_MIN,
            ),
        )

    def _normalize_vector(self, variables: NDArray[numpy.float64]) -> NDArray[numpy.float64]:
        """Return one clipped candidate vector with expected shape."""
        normalized = numpy.array(variables, dtype=float, copy=True)
        if normalized.shape != self.bounds.lb.shape:
            raise ValueError(
                f"Expected a {self.bounds.lb.shape[0]}-variable design vector, received shape {normalized.shape!r}."
            )
        return numpy.array(numpy.clip(normalized, self.bounds.lb, self.bounds.ub), dtype=float, copy=False)

    def _cache_key(self, variables: NDArray[numpy.float64]) -> tuple[float, ...]:
        """Return a rounded immutable key for the candidate cache."""
        normalized = self._normalize_vector(variables)
        return tuple(round(float(value), 12) for value in normalized)

    def decode_candidate(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return one candidate vector as a PyBaMM parameter mapping."""
        normalized = self._normalize_vector(variables)
        return {spec.parameter_name: float(normalized[index]) for index, spec in enumerate(_VARIABLE_SPECS)}

    def _metrics_from_variables(self, variables: NDArray[numpy.float64]) -> FastChargeMetricSummary:
        """Return cached fast-charge metrics for one design vector."""
        key = self._cache_key(variables)
        cached = self._evaluation_cache.get(key)
        if cached is not None:
            return cached
        metrics = evaluate_fast_charge_design(
            self.decode_candidate(self._normalize_vector(variables)),
            parameter_set=self.parameter_set,
            initial_soc_fraction=self.initial_soc_fraction,
            charge_c_rate=self.charge_c_rate,
            target_soc_start=self.target_soc_start,
            target_soc_end=self.target_soc_end,
            max_voltage_v=self.max_voltage_v,
            cv_cutoff_denominator=self.cv_cutoff_denominator,
            ambient_temperature_c=self.ambient_temperature_c,
            heat_transfer_coefficient_w_per_m2k=self.heat_transfer_coefficient_w_per_m2k,
            packaging_efficiency=self.packaging_efficiency,
            rest_before_charge_min=self.rest_before_charge_min,
            rest_after_charge_min=self.rest_after_charge_min,
            mesh_points=self.mesh_points,
            failure_charge_time_min=self.failure_charge_time_min,
            maximum_temperature_c=self.maximum_temperature_c,
            maximum_plating_mol_m3=self.maximum_plating_mol_m3,
        )
        self._evaluation_cache[key] = metrics
        return metrics

    def _success_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return positive when the simulation succeeded."""
        return 1.0 if self._metrics_from_variables(variables).success else -1.0

    def _temperature_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return remaining thermal headroom in degrees Celsius."""
        return self.maximum_temperature_c - self._metrics_from_variables(variables).max_temperature_c

    def _plating_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return remaining plating headroom in concentration units."""
        return self.maximum_plating_mol_m3 - self._metrics_from_variables(variables).max_plating_mol_m3

    def _energy_density_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return energy-density margin relative to the configured floor."""
        return self._metrics_from_variables(variables).energy_density_wh_per_l - self.minimum_energy_density_wh_per_l

    def _negative_volume_fraction_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return remaining negative-electrode inactive volume fraction."""
        normalized = self._normalize_vector(variables)
        return float(1.0 - normalized[3] - normalized[7])

    def _positive_volume_fraction_margin(self, variables: NDArray[numpy.float64]) -> float:
        """Return remaining positive-electrode inactive volume fraction."""
        normalized = self._normalize_vector(variables)
        return float(1.0 - normalized[4] - normalized[8])

    def objective_components(self, variables: NDArray[numpy.float64]) -> dict[str, float]:
        """Return the public fast-charge metric payload."""
        return self._metrics_from_variables(variables).as_dict()

    def generate_initial_solution(self, seed: int | None = None) -> NDArray[numpy.float64]:
        """Return the packaged Chen2020-like baseline design vector."""
        del seed
        return numpy.array([spec.default for spec in _VARIABLE_SPECS], dtype=float)

    def objective(self, variables: NDArray[numpy.float64]) -> float:
        """Return charge-time objective plus infeasibility penalty."""
        normalized = self._normalize_vector(variables)
        metrics = self._metrics_from_variables(normalized)
        penalty = _INFEASIBILITY_PENALTY_SCALE * self.constraint_violation(normalized)
        return float(metrics.charge_time_min + penalty)

    def solve(
        self,
        initial_solution: NDArray[numpy.float64] | None = None,
        seed: int | None = None,
        maxiter: int = 8,
    ) -> OptimizationResult:
        """Evaluate the baseline and a bounded sequence of one-step design edits."""
        del seed
        start = (
            self.generate_initial_solution() if initial_solution is None else self._normalize_vector(initial_solution)
        )
        best = numpy.array(start, dtype=float, copy=True)
        best_value = self.objective(best)
        nfev = 1
        evaluated = {self._cache_key(best)}
        if maxiter <= 0:
            max_violation = self.max_constraint_violation(best)
            return OptimizationResult(
                x=best,
                fun=best_value,
                success=max_violation <= 1.0e-9,
                message="Evaluated the packaged fast-charge baseline.",
                nit=0,
                nfev=nfev,
            )

        steps = 0
        for index, factor in _FAST_CHARGE_EDIT_SEQUENCE:
            if steps >= maxiter:
                break
            candidate = numpy.array(best, dtype=float, copy=True)
            candidate[index] = float(
                numpy.clip(candidate[index] * factor, self.bounds.lb[index], self.bounds.ub[index])
            )
            key = self._cache_key(candidate)
            if key in evaluated:
                continue
            evaluated.add(key)
            candidate_value = self.objective(candidate)
            nfev += 1
            steps += 1
            if candidate_value + 1.0e-12 < best_value:
                best = candidate
                best_value = candidate_value

        max_violation = self.max_constraint_violation(best)
        return OptimizationResult(
            x=best,
            fun=best_value,
            success=max_violation <= 1.0e-9,
            message=(
                "Evaluated fast-charge baseline and one-step design edits."
                if max_violation <= 1.0e-9
                else "Evaluated fast-charge baseline and returned a best-effort design."
            ),
            nit=steps,
            nfev=nfev,
        )


__all__ = [
    "BatteryFastChargeOptimizationProblem",
    "FastChargeMetricSummary",
    "FastChargeVariableSpec",
    "evaluate_fast_charge_design",
]
