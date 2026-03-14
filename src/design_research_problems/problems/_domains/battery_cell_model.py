"""Effective single-cell helpers used by the shared battery solver."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy
from numpy.typing import NDArray

from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._domains.battery_defaults import (
    BATTERY_BACKEND_DEFAULTS,
    SUPPORTED_BATTERY_THERMAL_MODES,
)
from design_research_problems.problems._domains.battery_layout import CELL_SPEC_18650

BatteryBackendScalar = bool | int | float | str
BatteryBackendOptions = tuple[tuple[str, BatteryBackendScalar], ...]

_SUPPORTED_CELL_MODEL_MODES = frozenset(
    {
        "auto",
        "pybamm_ecm",
        "pybamm_ecm_2rc",
        "pybamm_direct",
        "pybamm_spm",
        "pybamm_dfn",
    }
)
_SUPPORTED_PARAMETERIZATION_PRESETS = frozenset({"fast", "medium", "slow"})
_PRESET_PARAMETER_SETS = {
    "fast": "Chen2020",
    "medium": "Marquis2019",
    "slow": "Prada2013",
}
_REQUIRED_ECM_PARAMETER_FUNCTION_KEYS = (
    "Open-circuit voltage [V]",
    "R0 [Ohm]",
    "R1 [Ohm]",
    "C1 [F]",
)
_TWO_RC_IDENTIFICATION_SOC_GRID = (0.9, 0.7, 0.5, 0.3, 0.1)
_TWO_RC_IDENTIFICATION_TEMPERATURES_C = (15.0, 25.0, 35.0)
_TWO_RC_REFERENCE_TEMPERATURE_C = 25.0
_TWO_RC_REFERENCE_SOC_GRID = tuple(index / 10.0 for index in range(11))


@dataclass(frozen=True)
class _BatteryCurrentTrace:
    """One sampled single-cell current trace used for ECM identification."""

    initial_soc: float
    temperature_c: float
    time_s: tuple[float, ...]
    current_a: tuple[float, ...]
    voltage_v: tuple[float, ...]


@dataclass(frozen=True)
class _TwoRcFitResult:
    """One fitted 2-RC parameter bundle at one SOC / temperature point."""

    initial_soc: float
    temperature_c: float
    series_resistance_ohm: float
    transient_resistance_ohm: float
    transient_capacitance_f: float
    secondary_transient_resistance_ohm: float
    secondary_transient_capacitance_f: float


@dataclass(frozen=True)
class BatteryParameterization:
    """Parameterization selectors for one battery backend configuration."""

    preset: str | None = None
    """Blessed preset identifier: ``fast``, ``medium``, or ``slow``."""
    parameter_set: str | None = None
    """Explicit PyBaMM parameter-set name override."""

    def resolved_parameter_set(self) -> str | None:
        """Return the concrete parameter-set name, if one is selected."""
        if self.parameter_set is not None:
            return self.parameter_set
        if self.preset is None:
            return None
        return _PRESET_PARAMETER_SETS[self.preset]

    def as_dict(self) -> dict[str, object]:
        """Return one manifest-compatible mapping."""
        payload: dict[str, object] = {}
        if self.preset is not None:
            payload["preset"] = self.preset
        if self.parameter_set is not None:
            payload["parameter_set"] = self.parameter_set
        return payload


@dataclass(frozen=True)
class BatteryBackendConfig:
    """Stable config surface for battery backend fidelity controls."""

    cell_model_mode: str = "auto"
    """Requested model mode."""
    parameterization: BatteryParameterization = BatteryParameterization()
    """Parameterization selector."""
    thermal_mode: str | None = None
    """Thermal handling mode for backend discharge simulation."""
    ambient_temp_c: float | None = None
    """Ambient temperature used by the electrical and thermal models."""
    parasitics: BatteryBackendOptions = ()
    """Optional parasitics settings accepted for forward compatibility."""
    solver_policy: BatteryBackendOptions = ()
    """Optional solver settings accepted for forward compatibility."""

    def as_dict(self) -> dict[str, object]:
        """Return one manifest-compatible mapping."""
        payload: dict[str, object] = {"cell_model_mode": self.cell_model_mode}
        parameterization_payload = self.parameterization.as_dict()
        if parameterization_payload:
            payload["parameterization"] = parameterization_payload
        if self.thermal_mode is not None:
            payload["thermal_mode"] = self.thermal_mode
        if self.ambient_temp_c is not None:
            payload["ambient_temp_c"] = self.ambient_temp_c
        if self.parasitics:
            payload["parasitics"] = dict(self.parasitics)
        if self.solver_policy:
            payload["solver_policy"] = dict(self.solver_policy)
        return payload


@dataclass(frozen=True)
class BatteryCellModel:
    """Interpolated single-cell characteristics for pack simulation."""

    soc_grid: tuple[float, ...]
    """Monotonic state-of-charge grid."""
    open_circuit_voltage_v: tuple[float, ...]
    """Open-circuit voltage values aligned to ``soc_grid``."""
    series_resistance_ohm: tuple[float, ...]
    """Effective series resistance values aligned to ``soc_grid``."""
    transient_resistance_ohm: tuple[float, ...]
    """Effective RC polarization resistance values aligned to ``soc_grid``."""
    transient_capacitance_f: tuple[float, ...]
    """Effective RC polarization capacitance values aligned to ``soc_grid``."""
    secondary_transient_resistance_ohm: tuple[float, ...] = ()
    """Optional second RC polarization resistance aligned to ``soc_grid``."""
    secondary_transient_capacitance_f: tuple[float, ...] = ()
    """Optional second RC polarization capacitance aligned to ``soc_grid``."""
    source: str = "custom"
    """Origin of the surrogate, such as ``pybamm_thevenin`` or one custom test stub."""
    warning_message: str | None = None
    """Non-fatal warning emitted while building the surrogate, when present."""
    resolved_mode: str | None = None
    """Resolved backend mode used to build this cell model."""
    resolved_parameter_set: str | None = None
    """Resolved concrete parameter set used for this model."""
    reference_temperature_c: float | None = None
    """Reference evaluation temperature for the stored lookup tables."""
    dynamic_parameters: _BatteryCellDynamicParameters | None = None
    """Optional temperature-aware parameter functions for runtime interpolation."""


@dataclass(frozen=True)
class _BatteryCellDynamicParameters:
    """Temperature-aware parameter bundle retained for runtime interpolation."""

    parameter_values: Any
    open_circuit_voltage_fn: object | None = None
    series_resistance_fn: object | None = None
    transient_resistance_fn: object | None = None
    transient_capacitance_fn: object | None = None
    secondary_transient_resistance_fn: object | None = None
    secondary_transient_capacitance_fn: object | None = None
    resistance_scale: float = 1.0
    resistance_normalization: float = 1.0
    capacitance_normalization: float = 1.0
    secondary_capacitance_normalization: float = 1.0
    temperature_grid_c: tuple[float, ...] = ()
    series_resistance_by_temperature_ohm: tuple[tuple[float, ...], ...] = ()
    transient_resistance_by_temperature_ohm: tuple[tuple[float, ...], ...] = ()
    transient_capacitance_by_temperature_f: tuple[tuple[float, ...], ...] = ()
    secondary_transient_resistance_by_temperature_ohm: tuple[tuple[float, ...], ...] = ()
    secondary_transient_capacitance_by_temperature_f: tuple[tuple[float, ...], ...] = ()


@dataclass(frozen=True)
class BatteryThermalPriors:
    """PyBaMM-derived thermal priors normalized for the packaged 18650 model."""

    soc_grid: tuple[float, ...]
    """SOC grid aligned to ``total_resistance_ohm``."""
    total_resistance_ohm: tuple[float, ...]
    """SOC-indexed effective total resistance used for thermal heating."""
    cell_to_jig_conductance_w_per_k: float
    """Baseline core/surface-to-coolant conductance per active cell."""
    jig_to_ambient_conductance_w_per_k: float
    """Baseline coolant-to-ambient conductance for the pack-level coolant node."""
    cell_thermal_mass_j_per_k: float
    """Normalized 18650-equivalent cell thermal mass."""
    jig_thermal_mass_j_per_k: float
    """Normalized 18650-equivalent coolant/jig thermal mass."""
    reference_ambient_temperature_c: float
    """Reference ambient temperature from the extracted Thevenin parameter set."""
    source: str = "pybamm_thevenin"
    """Origin label for provenance reporting."""
    warning_message: str | None = None
    """Optional warning when extraction falls back to defaults."""


def import_pybamm() -> Any:
    """Import ``pybamm`` lazily for battery evaluation.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    return import_optional_module(
        "pybamm",
        required_for="battery problem evaluation",
        extras=("battery",),
        make_target="install-pybamm",
    )


def battery_backend_config_from_mapping(value: object) -> BatteryBackendConfig:
    """Parse one ``battery_backend`` mapping into a typed configuration.

    Args:
        value: Raw manifest value for ``parameters.battery_backend``.

    Returns:
        Parsed typed backend configuration.
    """
    if value is None:
        return resolve_battery_backend_config(None)
    if not isinstance(value, Mapping):
        raise ValueError("battery_backend must be a mapping when provided.")
    mapping = dict(value)
    cell_model_mode = _coerce_string(
        mapping.get("cell_model_mode", "auto"),
        field_name="battery_backend.cell_model_mode",
    )
    parameterization = _parse_parameterization(mapping)
    thermal_mode = _coerce_optional_string(mapping.get("thermal_mode"), field_name="battery_backend.thermal_mode")
    ambient_raw = mapping.get("ambient_temp_c", mapping.get("ambient_temp_C"))
    ambient_temp_c = None if ambient_raw is None else float(ambient_raw)
    parasitics = _coerce_option_pairs(mapping.get("parasitics"), field_name="battery_backend.parasitics")
    solver_policy = _coerce_option_pairs(mapping.get("solver_policy"), field_name="battery_backend.solver_policy")
    return resolve_battery_backend_config(
        BatteryBackendConfig(
            cell_model_mode=cell_model_mode,
            parameterization=parameterization,
            thermal_mode=thermal_mode,
            ambient_temp_c=ambient_temp_c,
            parasitics=parasitics,
            solver_policy=solver_policy,
        )
    )


def resolve_battery_backend_config(config: BatteryBackendConfig | None) -> BatteryBackendConfig:
    """Return a normalized backend configuration with validated fields.

    Args:
        config: Optional raw config.

    Returns:
        Normalized config with validated mode and parameterization selectors.
    """
    candidate = BatteryBackendConfig() if config is None else config
    normalized_mode = candidate.cell_model_mode.strip().lower()
    if normalized_mode not in _SUPPORTED_CELL_MODEL_MODES:
        supported = ", ".join(sorted(_SUPPORTED_CELL_MODEL_MODES))
        raise ValueError(
            f"Unsupported battery cell_model_mode {candidate.cell_model_mode!r}. Expected one of: {supported}."
        )
    normalized_parameterization = _normalize_parameterization(candidate.parameterization)
    if candidate.thermal_mode is None:
        normalized_thermal_mode = BATTERY_BACKEND_DEFAULTS.thermal.default_mode
    else:
        normalized_thermal_mode = (
            _coerce_string(
                candidate.thermal_mode,
                field_name="battery_backend.thermal_mode",
            )
            .strip()
            .lower()
        )
    if normalized_thermal_mode not in SUPPORTED_BATTERY_THERMAL_MODES:
        supported_thermal_modes = ", ".join(sorted(SUPPORTED_BATTERY_THERMAL_MODES))
        raise ValueError(
            f"Unsupported battery thermal_mode {candidate.thermal_mode!r}. Expected one of: {supported_thermal_modes}."
        )
    ambient_temp_c = (
        BATTERY_BACKEND_DEFAULTS.thermal.ambient_temperature_c
        if candidate.ambient_temp_c is None
        else float(candidate.ambient_temp_c)
    )
    return BatteryBackendConfig(
        cell_model_mode=normalized_mode,
        parameterization=normalized_parameterization,
        thermal_mode=normalized_thermal_mode,
        ambient_temp_c=ambient_temp_c,
        parasitics=tuple(sorted(candidate.parasitics)),
        solver_policy=tuple(sorted(candidate.solver_policy)),
    )


@lru_cache(maxsize=32)
def _load_battery_cell_model_cached(config: BatteryBackendConfig) -> BatteryCellModel:
    """Return one cached cell model for the normalized config."""
    return _build_cell_model_from_config(config)


def load_battery_cell_model(config: BatteryBackendConfig | None = None) -> BatteryCellModel:
    """Return one cell model from the stable config surface.

    Args:
        config: Optional backend configuration.

    Returns:
        Effective cell model chosen by the config.
    """
    normalized = resolve_battery_backend_config(config)
    return _load_battery_cell_model_cached(normalized)


@lru_cache(maxsize=1)
def load_18650_cell_model() -> BatteryCellModel:
    """Return one cached default 18650 cell model.

    The default mode is ``auto`` and requires ``pybamm``.
    """
    return _build_cell_model_from_config(resolve_battery_backend_config(None))


def _build_cell_model_from_config(config: BatteryBackendConfig) -> BatteryCellModel:
    """Construct one cell model from one normalized backend config."""
    requested_mode = config.cell_model_mode
    resolved_mode = _resolve_effective_mode(requested_mode)
    resolved_parameter_set = config.parameterization.resolved_parameter_set()
    if resolved_mode == "pybamm_ecm":
        return _load_pybamm_ecm_cell_model(
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=None,
        )
    if resolved_mode == "pybamm_spm":
        return _load_pybamm_lithium_ion_cell_model(
            model_family="spm",
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=None,
        )
    if resolved_mode == "pybamm_ecm_2rc":
        return _load_pybamm_ecm_two_rc_cell_model(
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=None,
        )
    if resolved_mode == "pybamm_direct":
        raise ValueError(
            "pybamm_direct is a high-cost evaluator mode and does not expose a reusable surrogate cell model. "
            "Use evaluate_battery_circuit(..., backend_config=BatteryBackendConfig(cell_model_mode='pybamm_direct'))."
        )
    if resolved_mode == "pybamm_dfn":
        return _load_pybamm_lithium_ion_cell_model(
            model_family="dfn",
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=None,
        )
    raise MissingOptionalDependencyError(f"Unsupported resolved battery mode {resolved_mode!r}.")


def _resolve_effective_mode(requested_mode: str) -> str:
    """Return the effective cell model mode for one requested mode."""
    if requested_mode != "auto":
        return requested_mode
    return "pybamm_ecm"


def _load_thevenin_parameter_values(
    *,
    resolved_parameter_set: str | None = None,
    ambient_temperature_c: float | None = None,
) -> tuple[Any, float, float]:
    """Return copied Thevenin parameter values plus 18650 normalization factors.

    Args:
        resolved_parameter_set: Optional concrete PyBaMM parameter-set name.
        ambient_temperature_c: Optional ambient-temperature override in Celsius.

    Returns:
        Tuple containing copied parameter values, resistance scale, and ambient
        temperature in kelvin.

    Raises:
        MissingOptionalDependencyError: If a supported Thevenin factory is unavailable.
    """
    pybamm_module = import_pybamm()
    equivalent_circuit = getattr(pybamm_module, "equivalent_circuit", None)
    thevenin_factory = getattr(equivalent_circuit, "Thevenin", None)
    if not callable(thevenin_factory):
        raise MissingOptionalDependencyError(
            "A supported PyBaMM installation with equivalent_circuit.Thevenin is required "
            "for battery problem evaluation. Install design-research-problems[battery] "
            "to get the supported PyBaMM version range."
        )
    model = thevenin_factory(options={"number of rc elements": 1})
    parameter_values: Any
    if resolved_parameter_set is None:
        parameter_values = _copy_parameter_values(model.default_parameter_values)
    else:
        parameter_values = _load_named_parameter_values(
            pybamm_module=pybamm_module,
            parameter_set=resolved_parameter_set,
        )
    reference_capacity_ah = _parameter_value(parameter_values, "Cell capacity [A.h]", default=100.0)
    resistance_scale = max(1.0e-6, reference_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah)
    ambient_temperature_k = _resolve_ambient_temperature_k(
        parameter_values=parameter_values,
        ambient_temperature_c=ambient_temperature_c,
    )
    return (parameter_values, resistance_scale, ambient_temperature_k)


def _load_named_parameter_values(*, pybamm_module: object, parameter_set: str) -> Any:
    """Return one copied ``pybamm.ParameterValues`` object for a named set."""
    parameter_values_factory = getattr(pybamm_module, "ParameterValues", None)
    if parameter_values_factory is None:
        raise MissingOptionalDependencyError("PyBaMM parameter-set overrides require pybamm.ParameterValues support.")
    try:
        parameter_values = parameter_values_factory(parameter_set)
    except Exception as exc:
        raise MissingOptionalDependencyError(
            f"PyBaMM parameter-set {parameter_set!r} could not be loaded ({type(exc).__name__}: {exc})."
        ) from exc
    return _copy_parameter_values(parameter_values)


def _load_pybamm_ecm_cell_model(
    *,
    resolved_parameter_set: str | None,
    ambient_temperature_c: float | None,
) -> BatteryCellModel:
    """Load one Thevenin-derived ECM model and normalize to packaged 18650 scale."""
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_thevenin_parameter_values(
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=ambient_temperature_c,
        )
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM Thevenin parameter extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Battery problem evaluation requires a supported PyBaMM version "
            "with the expected Thevenin parameter interface."
        ) from exc

    return _build_cell_model_from_parameter_values(
        parameter_values=parameter_values,
        resistance_scale=resistance_scale,
        ambient_temperature_k=ambient_temperature_k,
        source="pybamm_thevenin",
        resolved_mode="pybamm_ecm",
        resolved_parameter_set=resolved_parameter_set,
        required_function_keys=_REQUIRED_ECM_PARAMETER_FUNCTION_KEYS,
    )


def _load_pybamm_ecm_two_rc_cell_model(
    *,
    resolved_parameter_set: str | None,
    ambient_temperature_c: float | None,
) -> BatteryCellModel:
    """Fit one 2-RC surrogate from live single-cell PyBaMM traces."""
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_lithium_ion_parameter_values(
            model_family="spm",
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=ambient_temperature_c,
        )
        open_circuit_voltage_v = _build_reference_ocv_lookup(
            parameter_values=parameter_values,
            resolved_parameter_set=resolved_parameter_set,
        )
        traces = _generate_pybamm_two_rc_identification_traces(resolved_parameter_set=resolved_parameter_set)
        fit_results = tuple(
            _fit_two_rc_trace(
                trace,
                parameter_values=parameter_values,
                resistance_scale=resistance_scale,
                open_circuit_voltage_v=open_circuit_voltage_v,
            )
            for trace in traces
        )
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM 2-RC trace fitting failed "
            f"({type(exc).__name__}: {exc}). "
            "Battery problem evaluation requires a supported PyBaMM version "
            "with lithium_ion.SPM experiment support."
        ) from exc

    return _build_two_rc_cell_model_from_fit_results(
        parameter_values=parameter_values,
        fit_results=fit_results,
        open_circuit_voltage_v=open_circuit_voltage_v,
        ambient_temperature_k=ambient_temperature_k,
        source="pybamm_spm_fit_2rc",
        resolved_parameter_set=resolved_parameter_set,
    )


def _load_pybamm_lithium_ion_cell_model(
    *,
    model_family: str,
    resolved_parameter_set: str | None,
    ambient_temperature_c: float | None,
) -> BatteryCellModel:
    """Load one SPM/DFN-based cell model and map it into ECM lookup tables."""
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_lithium_ion_parameter_values(
            model_family=model_family,
            resolved_parameter_set=resolved_parameter_set,
            ambient_temperature_c=ambient_temperature_c,
        )
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        model_label = "SPM" if model_family == "spm" else "DFN"
        raise MissingOptionalDependencyError(
            f"PyBaMM {model_label} parameter extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Battery problem evaluation requires a supported PyBaMM version "
            f"with the expected lithium_ion.{model_label} interface."
        ) from exc

    resolved_mode = "pybamm_spm" if model_family == "spm" else "pybamm_dfn"
    source = resolved_mode
    return _build_cell_model_from_parameter_values(
        parameter_values=parameter_values,
        resistance_scale=resistance_scale,
        ambient_temperature_k=ambient_temperature_k,
        source=source,
        resolved_mode=resolved_mode,
        resolved_parameter_set=resolved_parameter_set,
        required_function_keys=_REQUIRED_ECM_PARAMETER_FUNCTION_KEYS,
    )


def _load_lithium_ion_parameter_values(
    *,
    model_family: str,
    resolved_parameter_set: str | None,
    ambient_temperature_c: float | None,
) -> tuple[Any, float, float]:
    """Return copied parameter values for one lithium-ion SPM/DFN model."""
    pybamm_module = import_pybamm()
    lithium_ion = getattr(pybamm_module, "lithium_ion", None)
    factory_name = "SPM" if model_family == "spm" else "DFN"
    model_factory = getattr(lithium_ion, factory_name, None)
    if not callable(model_factory):
        raise MissingOptionalDependencyError(
            f"A supported PyBaMM installation with lithium_ion.{factory_name} is required "
            "for battery problem evaluation."
        )
    model = model_factory()
    parameter_values: Any
    if resolved_parameter_set is None:
        parameter_values = _copy_parameter_values(model.default_parameter_values)
    else:
        parameter_values = _load_named_parameter_values(
            pybamm_module=pybamm_module,
            parameter_set=resolved_parameter_set,
        )
    reference_capacity_ah = _parameter_value(
        parameter_values,
        "Nominal cell capacity [A.h]",
        default=_parameter_value(parameter_values, "Cell capacity [A.h]", default=100.0),
    )
    resistance_scale = max(1.0e-6, reference_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah)
    ambient_temperature_k = _resolve_ambient_temperature_k(
        parameter_values=parameter_values,
        ambient_temperature_c=ambient_temperature_c,
    )
    return (parameter_values, resistance_scale, ambient_temperature_k)


def _generate_pybamm_two_rc_identification_traces(
    *,
    resolved_parameter_set: str | None,
) -> tuple[_BatteryCurrentTrace, ...]:
    """Return one compact live PyBaMM pulse/rest suite for 2-RC identification."""
    pybamm_module = import_pybamm()
    lithium_ion = getattr(pybamm_module, "lithium_ion", None)
    spm_factory = getattr(lithium_ion, "SPM", None)
    if not callable(spm_factory):
        raise MissingOptionalDependencyError(
            "A supported PyBaMM installation with lithium_ion.SPM is required for 2-RC identification."
        )

    traces: list[_BatteryCurrentTrace] = []
    for temperature_c in _TWO_RC_IDENTIFICATION_TEMPERATURES_C:
        for initial_soc in _TWO_RC_IDENTIFICATION_SOC_GRID:
            model = spm_factory()
            if resolved_parameter_set is None:
                parameter_values = _copy_parameter_values(model.default_parameter_values)
            else:
                parameter_values = _load_named_parameter_values(
                    pybamm_module=pybamm_module,
                    parameter_set=resolved_parameter_set,
                )
            _resolve_ambient_temperature_k(
                parameter_values=parameter_values,
                ambient_temperature_c=temperature_c,
            )
            experiment = pybamm_module.Experiment(
                _build_two_rc_identification_experiment_steps(
                    include_long_rest=(
                        abs(initial_soc - 0.5) <= 1.0e-9
                        and abs(temperature_c - _TWO_RC_REFERENCE_TEMPERATURE_C) <= 1.0e-9
                    )
                )
            )
            simulation = pybamm_module.Simulation(model, experiment=experiment, parameter_values=parameter_values)
            solution = simulation.solve(initial_soc=initial_soc)
            time_end = round(float(solution.t[-1]))
            sample_times = numpy.arange(0.0, float(time_end) + 1.0, 1.0, dtype=float)
            traces.append(
                _BatteryCurrentTrace(
                    initial_soc=initial_soc,
                    temperature_c=temperature_c,
                    time_s=tuple(float(value) for value in sample_times),
                    current_a=tuple(float(value) for value in solution["Current [A]"](sample_times)),
                    voltage_v=tuple(float(value) for value in solution["Voltage [V]"](sample_times)),
                )
            )
    return tuple(traces)


def _build_two_rc_identification_experiment_steps(*, include_long_rest: bool) -> list[str]:
    """Return one compact HPPC-like excitation design."""
    one_c_current_a = CELL_SPEC_18650.nominal_capacity_ah
    two_c_current_a = 2.0 * CELL_SPEC_18650.nominal_capacity_ah
    steps = [
        f"Discharge at {one_c_current_a:.3f} A for 10 seconds",
        "Rest for 60 seconds",
        f"Discharge at {one_c_current_a:.3f} A for 60 seconds",
        "Rest for 60 seconds",
        f"Discharge at {two_c_current_a:.3f} A for 10 seconds",
        "Rest for 60 seconds",
        f"Discharge at {two_c_current_a:.3f} A for 60 seconds",
        "Rest for 60 seconds",
    ]
    if include_long_rest:
        steps.append("Rest for 300 seconds")
    return steps


def _fit_two_rc_trace(
    trace: _BatteryCurrentTrace,
    *,
    parameter_values: Any,
    resistance_scale: float,
    open_circuit_voltage_v: tuple[float, ...],
) -> _TwoRcFitResult:
    """Fit one 2-RC surrogate to one sampled PyBaMM voltage trace."""
    from scipy.optimize import least_squares

    capacity_ah = _parameter_value(
        parameter_values,
        "Nominal cell capacity [A.h]",
        default=_parameter_value(parameter_values, "Cell capacity [A.h]", default=100.0),
    )
    ambient_temperature_k = 273.15 + float(trace.temperature_c)
    del ambient_temperature_k
    ocv_initial = _interpolate_scalar_series(_TWO_RC_REFERENCE_SOC_GRID, open_circuit_voltage_v, trace.initial_soc)
    current_abs_max = max((abs(value) for value in trace.current_a), default=capacity_ah)
    voltage_sag = max(0.0, ocv_initial - min(trace.voltage_v))
    total_resistance_guess = max(1.0e-4, min(0.5, voltage_sag / max(current_abs_max, 1.0e-6)))
    initial_guess = numpy.array(
        [
            0.45 * total_resistance_guess,
            0.35 * total_resistance_guess,
            8.0,
            0.20 * total_resistance_guess,
            120.0,
        ],
        dtype=float,
    )
    lower_bounds = numpy.array([1.0e-6, 1.0e-6, 0.5, 1.0e-6, 20.0], dtype=float)
    upper_bounds = numpy.array([1.0, 1.0, 30.0, 1.0, 2_000.0], dtype=float)
    fit = least_squares(
        _two_rc_trace_residuals,
        x0=initial_guess,
        bounds=(lower_bounds, upper_bounds),
        args=(trace, capacity_ah, open_circuit_voltage_v),
        max_nfev=2_000,
    )
    if not fit.success:
        raise MissingOptionalDependencyError(f"2-RC fitting did not converge for SOC={trace.initial_soc:.2f}.")

    series_resistance_ohm = max(1.0e-6, float(fit.x[0]) * resistance_scale)
    transient_resistance_ohm = max(1.0e-6, float(fit.x[1]) * resistance_scale)
    secondary_transient_resistance_ohm = max(1.0e-6, float(fit.x[3]) * resistance_scale)
    tau_fast_s = float(fit.x[2])
    tau_slow_s = max(float(fit.x[4]), tau_fast_s + 1.0e-6)
    transient_capacitance_f = max(1.0, tau_fast_s / transient_resistance_ohm)
    secondary_transient_capacitance_f = max(1.0, tau_slow_s / secondary_transient_resistance_ohm)
    return _TwoRcFitResult(
        initial_soc=trace.initial_soc,
        temperature_c=trace.temperature_c,
        series_resistance_ohm=series_resistance_ohm,
        transient_resistance_ohm=transient_resistance_ohm,
        transient_capacitance_f=transient_capacitance_f,
        secondary_transient_resistance_ohm=secondary_transient_resistance_ohm,
        secondary_transient_capacitance_f=secondary_transient_capacitance_f,
    )


def _two_rc_trace_residuals(
    values: numpy.ndarray,
    trace: _BatteryCurrentTrace,
    capacity_ah: float,
    open_circuit_voltage_v: tuple[float, ...],
) -> NDArray[numpy.float64]:
    """Return voltage residuals for one 2-RC fit candidate."""
    simulated = _simulate_two_rc_trace(
        time_s=trace.time_s,
        current_a=trace.current_a,
        initial_soc=trace.initial_soc,
        capacity_ah=capacity_ah,
        open_circuit_voltage_v=open_circuit_voltage_v,
        series_resistance_ohm=max(1.0e-6, float(values[0])),
        transient_resistance_ohm=max(1.0e-6, float(values[1])),
        transient_capacitance_f=max(1.0, float(values[2]) / max(float(values[1]), 1.0e-6)),
        secondary_transient_resistance_ohm=max(1.0e-6, float(values[3])),
        secondary_transient_capacitance_f=max(1.0, float(values[4]) / max(float(values[3]), 1.0e-6)),
    )
    residuals: NDArray[numpy.float64] = numpy.array(
        simulated - numpy.array(trace.voltage_v, dtype=float, copy=False),
        dtype=float,
        copy=False,
    )
    return residuals


def _simulate_two_rc_trace(
    *,
    time_s: tuple[float, ...],
    current_a: tuple[float, ...],
    initial_soc: float,
    capacity_ah: float,
    open_circuit_voltage_v: tuple[float, ...],
    series_resistance_ohm: float,
    transient_resistance_ohm: float,
    transient_capacitance_f: float,
    secondary_transient_resistance_ohm: float,
    secondary_transient_capacitance_f: float,
) -> NDArray[numpy.float64]:
    """Simulate one sampled 2-RC terminal-voltage trajectory."""
    voltage_trace = numpy.zeros(len(time_s), dtype=float)
    soc = float(initial_soc)
    primary_rc_voltage = 0.0
    secondary_rc_voltage = 0.0
    previous_time = float(time_s[0])

    for index, (time_point_s, current_value_a) in enumerate(zip(time_s, current_a, strict=True)):
        if index > 0:
            dt_s = max(float(time_point_s) - previous_time, 0.0)
            soc = min(1.0, max(0.0, soc - ((current_a[index - 1] * dt_s) / (capacity_ah * 3600.0))))
            primary_rc_voltage = _advance_rc_voltage(
                primary_rc_voltage,
                current_a[index - 1],
                transient_resistance_ohm,
                transient_capacitance_f,
                dt_s=dt_s,
            )
            secondary_rc_voltage = _advance_rc_voltage(
                secondary_rc_voltage,
                current_a[index - 1],
                secondary_transient_resistance_ohm,
                secondary_transient_capacitance_f,
                dt_s=dt_s,
            )
        ocv = _interpolate_scalar_series(_TWO_RC_REFERENCE_SOC_GRID, open_circuit_voltage_v, soc)
        voltage_trace[index] = (
            ocv - (float(current_value_a) * series_resistance_ohm) - primary_rc_voltage - secondary_rc_voltage
        )
        previous_time = float(time_point_s)
    return voltage_trace


def _advance_rc_voltage(
    current_voltage_v: float,
    current_a: float,
    resistance_ohm: float,
    capacitance_f: float,
    *,
    dt_s: float,
) -> float:
    """Advance one RC overpotential with an exact discrete update."""
    if resistance_ohm <= 1.0e-12 or capacitance_f <= 1.0e-12 or dt_s <= 0.0:
        return 0.0
    tau_seconds = resistance_ohm * capacitance_f
    alpha = float(numpy.exp(-dt_s / max(tau_seconds, 1.0e-12)))
    return (alpha * current_voltage_v) + ((1.0 - alpha) * current_a * resistance_ohm)


def _build_two_rc_cell_model_from_fit_results(
    *,
    parameter_values: Any,
    fit_results: tuple[_TwoRcFitResult, ...],
    open_circuit_voltage_v: tuple[float, ...],
    ambient_temperature_k: float,
    source: str,
    resolved_parameter_set: str | None,
) -> BatteryCellModel:
    """Build one reference-plus-temperature 2-RC surrogate from fitted traces."""
    by_temperature: dict[float, list[_TwoRcFitResult]] = {}
    for fit in fit_results:
        by_temperature.setdefault(float(fit.temperature_c), []).append(fit)

    temperature_grid_c = tuple(sorted(by_temperature))
    series_tables: list[tuple[float, ...]] = []
    transient_tables: list[tuple[float, ...]] = []
    capacitance_tables: list[tuple[float, ...]] = []
    secondary_transient_tables: list[tuple[float, ...]] = []
    secondary_capacitance_tables: list[tuple[float, ...]] = []

    for temperature_c in temperature_grid_c:
        ordered = sorted(by_temperature[temperature_c], key=lambda item: item.initial_soc)
        source_soc_grid = tuple(item.initial_soc for item in ordered)
        series_tables.append(
            tuple(
                _interpolate_scalar_series(source_soc_grid, tuple(item.series_resistance_ohm for item in ordered), soc)
                for soc in _TWO_RC_REFERENCE_SOC_GRID
            )
        )
        transient_tables.append(
            tuple(
                _interpolate_scalar_series(
                    source_soc_grid,
                    tuple(item.transient_resistance_ohm for item in ordered),
                    soc,
                )
                for soc in _TWO_RC_REFERENCE_SOC_GRID
            )
        )
        capacitance_tables.append(
            tuple(
                _interpolate_scalar_series(
                    source_soc_grid,
                    tuple(item.transient_capacitance_f for item in ordered),
                    soc,
                )
                for soc in _TWO_RC_REFERENCE_SOC_GRID
            )
        )
        secondary_transient_tables.append(
            tuple(
                _interpolate_scalar_series(
                    source_soc_grid,
                    tuple(item.secondary_transient_resistance_ohm for item in ordered),
                    soc,
                )
                for soc in _TWO_RC_REFERENCE_SOC_GRID
            )
        )
        secondary_capacitance_tables.append(
            tuple(
                _interpolate_scalar_series(
                    source_soc_grid,
                    tuple(item.secondary_transient_capacitance_f for item in ordered),
                    soc,
                )
                for soc in _TWO_RC_REFERENCE_SOC_GRID
            )
        )

    reference_temp_index = min(
        range(len(temperature_grid_c)),
        key=lambda index: abs(temperature_grid_c[index] - 25.0),
    )
    nominal_index = min(
        range(len(_TWO_RC_REFERENCE_SOC_GRID)),
        key=lambda index: abs(_TWO_RC_REFERENCE_SOC_GRID[index] - 0.5),
    )
    nominal_total_resistance = (
        series_tables[reference_temp_index][nominal_index]
        + transient_tables[reference_temp_index][nominal_index]
        + secondary_transient_tables[reference_temp_index][nominal_index]
    )
    resistance_normalization = (
        1.0
        if nominal_total_resistance <= 1.0e-12
        else CELL_SPEC_18650.internal_resistance_ohm / nominal_total_resistance
    )
    capacitance_normalization = max(resistance_normalization, 1.0e-12)
    secondary_capacitance_normalization = max(resistance_normalization, 1.0e-12)

    series_tables = [
        tuple(max(1.0e-6, value * resistance_normalization) for value in values) for values in series_tables
    ]
    transient_tables = [
        tuple(max(0.0, value * resistance_normalization) for value in values) for values in transient_tables
    ]
    secondary_transient_tables = [
        tuple(max(0.0, value * resistance_normalization) for value in values) for values in secondary_transient_tables
    ]
    capacitance_tables = [
        tuple(
            max(1.0, value / capacitance_normalization) if transient_tables[row_index][column_index] > 1.0e-12 else 1.0
            for column_index, value in enumerate(values)
        )
        for row_index, values in enumerate(capacitance_tables)
    ]
    secondary_capacitance_tables = [
        tuple(
            max(1.0, value / secondary_capacitance_normalization)
            if secondary_transient_tables[row_index][column_index] > 1.0e-12
            else 1.0
            for column_index, value in enumerate(values)
        )
        for row_index, values in enumerate(secondary_capacitance_tables)
    ]

    dynamic_parameters = _BatteryCellDynamicParameters(
        parameter_values=parameter_values,
        open_circuit_voltage_fn=_mapping_get(parameter_values, "Open-circuit voltage [V]"),
        resistance_normalization=resistance_normalization,
        capacitance_normalization=capacitance_normalization,
        secondary_capacitance_normalization=secondary_capacitance_normalization,
        temperature_grid_c=temperature_grid_c,
        series_resistance_by_temperature_ohm=tuple(series_tables),
        transient_resistance_by_temperature_ohm=tuple(transient_tables),
        transient_capacitance_by_temperature_f=tuple(capacitance_tables),
        secondary_transient_resistance_by_temperature_ohm=tuple(secondary_transient_tables),
        secondary_transient_capacitance_by_temperature_f=tuple(secondary_capacitance_tables),
    )
    return BatteryCellModel(
        soc_grid=_TWO_RC_REFERENCE_SOC_GRID,
        open_circuit_voltage_v=open_circuit_voltage_v,
        series_resistance_ohm=series_tables[reference_temp_index],
        transient_resistance_ohm=transient_tables[reference_temp_index],
        transient_capacitance_f=capacitance_tables[reference_temp_index],
        secondary_transient_resistance_ohm=secondary_transient_tables[reference_temp_index],
        secondary_transient_capacitance_f=secondary_capacitance_tables[reference_temp_index],
        source=source,
        warning_message=None,
        resolved_mode="pybamm_ecm_2rc",
        resolved_parameter_set=resolved_parameter_set,
        reference_temperature_c=float(ambient_temperature_k - 273.15),
        dynamic_parameters=dynamic_parameters,
    )


def _build_reference_ocv_lookup(
    *,
    parameter_values: Any,
    resolved_parameter_set: str | None,
) -> tuple[float, ...]:
    """Return one reference OCV lookup table for the 2-RC fitter."""
    open_circuit_fn = _mapping_get(parameter_values, "Open-circuit voltage [V]")
    if open_circuit_fn is not None:
        return tuple(
            _evaluate_parameter_function(
                parameter_values=parameter_values,
                function_or_value=open_circuit_fn,
                ambient_temperature_k=273.15 + _TWO_RC_REFERENCE_TEMPERATURE_C,
                soc=soc,
                default=CELL_SPEC_18650.nominal_voltage_v,
                strict=True,
                parameter_name="Open-circuit voltage [V]",
            )
            for soc in _TWO_RC_REFERENCE_SOC_GRID
        )

    pybamm_module = import_pybamm()
    lithium_ion = getattr(pybamm_module, "lithium_ion", None)
    spm_factory = getattr(lithium_ion, "SPM", None)
    if not callable(spm_factory):
        raise MissingOptionalDependencyError(
            "A supported PyBaMM installation with lithium_ion.SPM is required for 2-RC OCV extraction."
        )

    ocv_values: list[float] = []
    for soc in _TWO_RC_REFERENCE_SOC_GRID:
        model = spm_factory()
        if resolved_parameter_set is None:
            ocv_parameter_values = _copy_parameter_values(model.default_parameter_values)
        else:
            ocv_parameter_values = _load_named_parameter_values(
                pybamm_module=pybamm_module,
                parameter_set=resolved_parameter_set,
            )
        _resolve_ambient_temperature_k(
            parameter_values=ocv_parameter_values,
            ambient_temperature_c=_TWO_RC_REFERENCE_TEMPERATURE_C,
        )
        solution = pybamm_module.Simulation(
            model,
            experiment=pybamm_module.Experiment(["Rest for 1 second"]),
            parameter_values=ocv_parameter_values,
        ).solve(initial_soc=soc)
        ocv_values.append(float(solution["Voltage [V]"](0.0)))
    return tuple(ocv_values)


def _interpolate_scalar_series(x_values: tuple[float, ...], y_values: tuple[float, ...], x_value: float) -> float:
    """Linearly interpolate one scalar series with endpoint clamping."""
    if x_value <= x_values[0]:
        return float(y_values[0])
    if x_value >= x_values[-1]:
        return float(y_values[-1])
    return float(numpy.interp(float(x_value), x_values, y_values))


def _resolve_ambient_temperature_k(
    *,
    parameter_values: Any,
    ambient_temperature_c: float | None,
) -> float:
    """Return the effective ambient temperature in kelvin for model extraction."""
    if ambient_temperature_c is None:
        return _parameter_value(parameter_values, "Initial temperature [K]", default=298.15)
    ambient_temperature_k = 273.15 + float(ambient_temperature_c)
    _try_set_parameter_value(parameter_values, "Initial temperature [K]", ambient_temperature_k)
    return ambient_temperature_k


def _build_cell_model_from_parameter_values(
    *,
    parameter_values: Any,
    resistance_scale: float,
    ambient_temperature_k: float,
    source: str,
    resolved_mode: str,
    resolved_parameter_set: str | None,
    required_function_keys: tuple[str, ...],
) -> BatteryCellModel:
    """Build one cell model lookup table bundle from parameter values."""
    soc_grid = tuple(index / 10.0 for index in range(11))
    open_circuit_fn = _mapping_get(parameter_values, "Open-circuit voltage [V]")
    series_resistance_fn = _mapping_get(parameter_values, "R0 [Ohm]")
    transient_resistance_fn = _mapping_get(parameter_values, "R1 [Ohm]")
    transient_capacitance_fn = _mapping_get(parameter_values, "C1 [F]")
    parameter_functions: dict[str, object] = {
        "Open-circuit voltage [V]": open_circuit_fn,
        "R0 [Ohm]": series_resistance_fn,
        "R1 [Ohm]": transient_resistance_fn,
        "C1 [F]": transient_capacitance_fn,
    }
    for key in required_function_keys:
        if parameter_functions.get(key) is None:
            raise MissingOptionalDependencyError(
                f"PyBaMM parameter values for mode {resolved_mode!r} do not expose {key!r}."
            )

    open_circuit_voltage_v: list[float] = []
    series_resistance_ohm: list[float] = []
    transient_resistance_ohm: list[float] = []
    transient_capacitance_f: list[float] = []

    for soc in soc_grid:
        ocv = _evaluate_parameter_function(
            parameter_values=parameter_values,
            function_or_value=open_circuit_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=soc,
            default=CELL_SPEC_18650.nominal_voltage_v,
            strict=("Open-circuit voltage [V]" in required_function_keys),
            parameter_name="Open-circuit voltage [V]",
        )
        open_circuit_voltage_v.append(ocv)

        series_resistance = _evaluate_parameter_function(
            parameter_values=parameter_values,
            function_or_value=series_resistance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=soc,
            default=CELL_SPEC_18650.internal_resistance_ohm,
            strict=("R0 [Ohm]" in required_function_keys),
            parameter_name="R0 [Ohm]",
        )
        series_resistance_ohm.append(max(1.0e-6, abs(series_resistance) * resistance_scale))

        transient_resistance = _evaluate_parameter_function(
            parameter_values=parameter_values,
            function_or_value=transient_resistance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=soc,
            default=0.0,
            strict=("R1 [Ohm]" in required_function_keys),
            parameter_name="R1 [Ohm]",
        )
        transient_resistance_ohm.append(max(0.0, abs(transient_resistance) * resistance_scale))

        transient_capacitance = _evaluate_parameter_function(
            parameter_values=parameter_values,
            function_or_value=transient_capacitance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=soc,
            default=1.0,
            strict=("C1 [F]" in required_function_keys),
            parameter_name="C1 [F]",
        )
        transient_capacitance_f.append(max(1.0, abs(transient_capacitance) / resistance_scale))

    nominal_index = min(range(len(soc_grid)), key=lambda index: abs(soc_grid[index] - 0.5))
    nominal_total_resistance = series_resistance_ohm[nominal_index] + transient_resistance_ohm[nominal_index]
    resistance_normalization = (
        1.0
        if nominal_total_resistance <= 1.0e-12
        else CELL_SPEC_18650.internal_resistance_ohm / nominal_total_resistance
    )
    capacitance_normalization = max(resistance_normalization, 1.0e-12)

    series_resistance_ohm = [max(1.0e-6, resistance * resistance_normalization) for resistance in series_resistance_ohm]
    transient_resistance_ohm = [
        max(0.0, resistance * resistance_normalization) for resistance in transient_resistance_ohm
    ]
    transient_capacitance_f = [
        max(1.0, capacitance / capacitance_normalization) if transient_resistance_ohm[index] > 1.0e-12 else 1.0
        for index, capacitance in enumerate(transient_capacitance_f)
    ]

    dynamic_parameters = _BatteryCellDynamicParameters(
        parameter_values=parameter_values,
        open_circuit_voltage_fn=open_circuit_fn,
        series_resistance_fn=series_resistance_fn,
        transient_resistance_fn=transient_resistance_fn,
        transient_capacitance_fn=transient_capacitance_fn,
        resistance_scale=resistance_scale,
        resistance_normalization=resistance_normalization,
        capacitance_normalization=capacitance_normalization,
    )
    return BatteryCellModel(
        soc_grid=soc_grid,
        open_circuit_voltage_v=tuple(open_circuit_voltage_v),
        series_resistance_ohm=tuple(series_resistance_ohm),
        transient_resistance_ohm=tuple(transient_resistance_ohm),
        transient_capacitance_f=tuple(transient_capacitance_f),
        source=source,
        warning_message=None,
        resolved_mode=resolved_mode,
        resolved_parameter_set=resolved_parameter_set,
        reference_temperature_c=float(ambient_temperature_k - 273.15),
        dynamic_parameters=dynamic_parameters,
    )


@lru_cache(maxsize=32)
def _load_battery_thermal_priors_cached(config: BatteryBackendConfig) -> BatteryThermalPriors:
    """Return one cached PyBaMM-derived thermal prior bundle for a normalized config.

    The extracted Thevenin thermal parameters are normalized to the packaged 18650
    capacity scale. Conductance terms scale approximately with capacity^(2/3) and
    thermal masses scale approximately with capacity.

    Returns:
        Thermal prior payload with SOC-indexed resistance and normalized
        conductance/mass terms.

    Raises:
        MissingOptionalDependencyError: If the PyBaMM Thevenin extraction path fails.
    """
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_thevenin_parameter_values(
            resolved_parameter_set=config.parameterization.resolved_parameter_set(),
            ambient_temperature_c=config.ambient_temp_c,
        )
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM thermal prior extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Tier-4 battery thermal evaluation requires a supported PyBaMM version "
            "with Thevenin thermal parameter access."
        ) from exc
    try:
        cell_model = load_battery_cell_model(config)
        total_resistance_ohm = tuple(
            max(1.0e-6, series + transient + secondary_transient)
            for series, transient, secondary_transient in zip(
                cell_model.series_resistance_ohm,
                cell_model.transient_resistance_ohm,
                (
                    cell_model.secondary_transient_resistance_ohm
                    if cell_model.secondary_transient_resistance_ohm
                    else tuple(0.0 for _ in cell_model.soc_grid)
                ),
                strict=True,
            )
        )
        thermal_conductance_scale = max(resistance_scale ** (2.0 / 3.0), 1.0e-6)
        thermal_mass_scale = max(resistance_scale, 1.0e-6)
        cell_to_jig = _parameter_value(parameter_values, "Cell-jig heat transfer coefficient [W/K]", default=10.0)
        jig_to_air = _parameter_value(parameter_values, "Jig-air heat transfer coefficient [W/K]", default=10.0)
        cell_mass = _parameter_value(parameter_values, "Cell thermal mass [J/K]", default=1000.0)
        jig_mass = _parameter_value(parameter_values, "Jig thermal mass [J/K]", default=500.0)
        return BatteryThermalPriors(
            soc_grid=cell_model.soc_grid,
            total_resistance_ohm=total_resistance_ohm,
            cell_to_jig_conductance_w_per_k=max(1.0e-6, cell_to_jig / thermal_conductance_scale),
            jig_to_ambient_conductance_w_per_k=max(1.0e-6, jig_to_air / thermal_conductance_scale),
            cell_thermal_mass_j_per_k=max(1.0, cell_mass / thermal_mass_scale),
            jig_thermal_mass_j_per_k=max(1.0, jig_mass / thermal_mass_scale),
            reference_ambient_temperature_c=float(ambient_temperature_k - 273.15),
            source=cell_model.source,
            warning_message=cell_model.warning_message,
        )
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM thermal prior extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Tier-4 battery thermal evaluation requires a supported PyBaMM version "
            "with Thevenin thermal parameter access."
        ) from exc


def load_battery_thermal_priors(config: BatteryBackendConfig | None = None) -> BatteryThermalPriors:
    """Return one thermal prior bundle for the requested backend configuration."""
    normalized = resolve_battery_backend_config(config)
    return _load_battery_thermal_priors_cached(normalized)


@lru_cache(maxsize=1)
def load_18650_thermal_priors() -> BatteryThermalPriors:
    """Return one cached default thermal prior bundle for the packaged 18650 model."""
    return load_battery_thermal_priors()


def interpolate_total_resistance(model: BatteryThermalPriors, soc: float) -> float:
    """Interpolate effective total resistance from one SOC-indexed thermal prior.

    Args:
        model: Thermal prior bundle.
        soc: State of charge in [0, 1].

    Returns:
        Interpolated total effective resistance in ohms.
    """
    clipped_soc = min(1.0, max(0.0, soc))
    if clipped_soc <= model.soc_grid[0]:
        return float(model.total_resistance_ohm[0])
    if clipped_soc >= model.soc_grid[-1]:
        return float(model.total_resistance_ohm[-1])

    for index in range(1, len(model.soc_grid)):
        upper_soc = model.soc_grid[index]
        if clipped_soc > upper_soc:
            continue
        lower_soc = model.soc_grid[index - 1]
        span = upper_soc - lower_soc
        ratio = 0.0 if span <= 0.0 else (clipped_soc - lower_soc) / span
        lower_resistance = model.total_resistance_ohm[index - 1]
        upper_resistance = model.total_resistance_ohm[index]
        return float(lower_resistance + (ratio * (upper_resistance - lower_resistance)))
    return float(model.total_resistance_ohm[-1])


def _copy_parameter_values(parameter_values: Any) -> Any:
    """Return a detached parameter-values object when the backend supports it.

    Args:
        parameter_values: Value for ``parameter_values``.

    Returns:
        Computed result for this callable.
    """
    copy_method = getattr(parameter_values, "copy", None)
    if callable(copy_method):
        return copy_method()
    return parameter_values


def _try_set_parameter_value(parameter_values: Any, key: str, value: float) -> None:
    """Best-effort setter for mutable parameter-value containers."""
    update_method = getattr(parameter_values, "update", None)
    if callable(update_method):
        try:
            update_method({key: value})
            return
        except Exception:
            pass
    try:
        parameter_values[key] = value
    except Exception:
        return


def _coerce_scalar(value: object) -> float:
    """Convert a scalar-like backend value into a float.

    Args:
        value: Value for ``value``.

    Returns:
        Computed result for this callable.
    """
    array = numpy.asarray(value, dtype=float)
    return float(array.reshape(-1)[0])


def _parameter_value(parameter_values: Any, key: str, *, default: float) -> float:
    """Return one scalar parameter value from a mapping-like object.

    Args:
        parameter_values: Value for ``parameter_values``.
        key: Value for ``key``.
        default: Value for ``default``.

    Returns:
        Computed result for this callable.
    """
    if key not in parameter_values:
        return default
    return _coerce_scalar(parameter_values[key])


def _evaluate_parameter(parameter_values: Any, expression: object) -> float:
    """Evaluate one backend expression into a concrete float.

    Args:
        parameter_values: Value for ``parameter_values``.
        expression: Value for ``expression``.

    Returns:
        Computed result for this callable.
    """
    evaluate_method = getattr(parameter_values, "evaluate", None)
    if callable(evaluate_method):
        return _coerce_scalar(evaluate_method(expression))
    return _coerce_scalar(expression)


def _mapping_get(mapping: Any, key: str, default: object = None) -> object:
    """Return one mapping-like key with graceful fallback."""
    get_method = getattr(mapping, "get", None)
    if callable(get_method):
        return get_method(key, default)
    try:
        if key in mapping:
            return mapping[key]
    except Exception:
        return default
    return default


def _evaluate_parameter_function(
    *,
    parameter_values: Any,
    function_or_value: object,
    ambient_temperature_k: float,
    soc: float,
    default: float,
    strict: bool = False,
    parameter_name: str = "parameter function",
) -> float:
    """Evaluate one parameter function across common PyBaMM call signatures."""
    if callable(function_or_value):
        for args in (
            (ambient_temperature_k, 0.0, soc),
            (ambient_temperature_k, soc),
            (soc,),
            (),
        ):
            try:
                expression = function_or_value(*args)
            except TypeError:
                continue
            except Exception:
                continue
            try:
                return _evaluate_parameter(parameter_values, expression)
            except Exception:
                continue
        if strict:
            raise MissingOptionalDependencyError(
                f"PyBaMM parameter function {parameter_name!r} could not be evaluated for mode extraction."
            )
        return default
    if function_or_value is None:
        if strict:
            raise MissingOptionalDependencyError(
                f"PyBaMM parameter values do not expose {parameter_name!r} for mode extraction."
            )
        return default
    try:
        return _evaluate_parameter(parameter_values, function_or_value)
    except Exception as exc:
        if strict:
            raise MissingOptionalDependencyError(
                f"PyBaMM parameter value {parameter_name!r} could not be evaluated for mode extraction."
            ) from exc
        return default


def interpolate_cell_model(
    model: BatteryCellModel,
    soc: float,
    *,
    temperature_c: float | None = None,
) -> tuple[float, float, float, float, float, float]:
    """Interpolate cell operating values at one SOC and optional temperature."""
    clipped_soc = min(1.0, max(0.0, soc))
    if temperature_c is not None and model.dynamic_parameters is not None:
        return _interpolate_dynamic_cell_model(model, clipped_soc, temperature_c=temperature_c)
    return _interpolate_reference_cell_model(model, clipped_soc)


def _interpolate_reference_cell_model(
    model: BatteryCellModel,
    clipped_soc: float,
) -> tuple[float, float, float, float, float, float]:
    """Interpolate the stored reference lookup tables."""
    secondary_resistance = (
        model.secondary_transient_resistance_ohm
        if model.secondary_transient_resistance_ohm
        else tuple(0.0 for _ in model.soc_grid)
    )
    secondary_capacitance = (
        model.secondary_transient_capacitance_f
        if model.secondary_transient_capacitance_f
        else tuple(1.0 for _ in model.soc_grid)
    )
    if clipped_soc <= model.soc_grid[0]:
        return (
            model.open_circuit_voltage_v[0],
            model.series_resistance_ohm[0],
            model.transient_resistance_ohm[0],
            model.transient_capacitance_f[0],
            secondary_resistance[0],
            secondary_capacitance[0],
        )
    if clipped_soc >= model.soc_grid[-1]:
        return (
            model.open_circuit_voltage_v[-1],
            model.series_resistance_ohm[-1],
            model.transient_resistance_ohm[-1],
            model.transient_capacitance_f[-1],
            secondary_resistance[-1],
            secondary_capacitance[-1],
        )

    for index in range(1, len(model.soc_grid)):
        upper_soc = model.soc_grid[index]
        if clipped_soc > upper_soc:
            continue
        lower_soc = model.soc_grid[index - 1]
        span = upper_soc - lower_soc
        ratio = 0.0 if span <= 0.0 else (clipped_soc - lower_soc) / span
        lower_ocv = model.open_circuit_voltage_v[index - 1]
        upper_ocv = model.open_circuit_voltage_v[index]
        lower_series_resistance = model.series_resistance_ohm[index - 1]
        upper_series_resistance = model.series_resistance_ohm[index]
        lower_transient_resistance = model.transient_resistance_ohm[index - 1]
        upper_transient_resistance = model.transient_resistance_ohm[index]
        lower_transient_capacitance = model.transient_capacitance_f[index - 1]
        upper_transient_capacitance = model.transient_capacitance_f[index]
        lower_secondary_resistance = secondary_resistance[index - 1]
        upper_secondary_resistance = secondary_resistance[index]
        lower_secondary_capacitance = secondary_capacitance[index - 1]
        upper_secondary_capacitance = secondary_capacitance[index]
        return (
            lower_ocv + (ratio * (upper_ocv - lower_ocv)),
            lower_series_resistance + (ratio * (upper_series_resistance - lower_series_resistance)),
            lower_transient_resistance + (ratio * (upper_transient_resistance - lower_transient_resistance)),
            lower_transient_capacitance + (ratio * (upper_transient_capacitance - lower_transient_capacitance)),
            lower_secondary_resistance + (ratio * (upper_secondary_resistance - lower_secondary_resistance)),
            lower_secondary_capacitance + (ratio * (upper_secondary_capacitance - lower_secondary_capacitance)),
        )

    return (
        CELL_SPEC_18650.nominal_voltage_v,
        CELL_SPEC_18650.internal_resistance_ohm,
        0.0,
        1.0,
        0.0,
        1.0,
    )


def _interpolate_dynamic_cell_model(
    model: BatteryCellModel,
    clipped_soc: float,
    *,
    temperature_c: float,
) -> tuple[float, float, float, float, float, float]:
    """Evaluate temperature-aware parameter functions at runtime."""
    dynamic = model.dynamic_parameters
    if dynamic is None:
        return _interpolate_reference_cell_model(model, clipped_soc)

    (
        reference_ocv,
        reference_series,
        reference_transient,
        reference_capacitance,
        reference_secondary_transient,
        reference_secondary_capacitance,
    ) = _interpolate_reference_cell_model(model, clipped_soc)
    ambient_temperature_k = 273.15 + float(temperature_c)
    open_circuit_voltage_v = _evaluate_parameter_function(
        parameter_values=dynamic.parameter_values,
        function_or_value=dynamic.open_circuit_voltage_fn,
        ambient_temperature_k=ambient_temperature_k,
        soc=clipped_soc,
        default=reference_ocv,
    )
    if dynamic.temperature_grid_c and dynamic.series_resistance_by_temperature_ohm:
        series_resistance = _interpolate_temperature_lookup(
            dynamic.temperature_grid_c,
            dynamic.series_resistance_by_temperature_ohm,
            clipped_soc,
            temperature_c=temperature_c,
            default=reference_series,
        )
        transient_resistance = _interpolate_temperature_lookup(
            dynamic.temperature_grid_c,
            dynamic.transient_resistance_by_temperature_ohm,
            clipped_soc,
            temperature_c=temperature_c,
            default=reference_transient,
        )
        transient_capacitance = _interpolate_temperature_lookup(
            dynamic.temperature_grid_c,
            dynamic.transient_capacitance_by_temperature_f,
            clipped_soc,
            temperature_c=temperature_c,
            default=reference_capacitance,
        )
        secondary_transient_resistance = _interpolate_temperature_lookup(
            dynamic.temperature_grid_c,
            dynamic.secondary_transient_resistance_by_temperature_ohm,
            clipped_soc,
            temperature_c=temperature_c,
            default=reference_secondary_transient,
        )
        secondary_transient_capacitance = _interpolate_temperature_lookup(
            dynamic.temperature_grid_c,
            dynamic.secondary_transient_capacitance_by_temperature_f,
            clipped_soc,
            temperature_c=temperature_c,
            default=reference_secondary_capacitance,
        )
    else:
        series_resistance = _evaluate_parameter_function(
            parameter_values=dynamic.parameter_values,
            function_or_value=dynamic.series_resistance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=clipped_soc,
            default=reference_series,
        )
        transient_resistance = _evaluate_parameter_function(
            parameter_values=dynamic.parameter_values,
            function_or_value=dynamic.transient_resistance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=clipped_soc,
            default=reference_transient,
        )
        transient_capacitance = _evaluate_parameter_function(
            parameter_values=dynamic.parameter_values,
            function_or_value=dynamic.transient_capacitance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=clipped_soc,
            default=reference_capacitance,
        )
        secondary_transient_resistance = _evaluate_parameter_function(
            parameter_values=dynamic.parameter_values,
            function_or_value=dynamic.secondary_transient_resistance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=clipped_soc,
            default=reference_secondary_transient,
        )
        secondary_transient_capacitance = _evaluate_parameter_function(
            parameter_values=dynamic.parameter_values,
            function_or_value=dynamic.secondary_transient_capacitance_fn,
            ambient_temperature_k=ambient_temperature_k,
            soc=clipped_soc,
            default=reference_secondary_capacitance,
        )

    scaled_series_resistance = max(
        1.0e-6,
        abs(series_resistance) * dynamic.resistance_scale * dynamic.resistance_normalization,
    )
    scaled_transient_resistance = max(
        0.0,
        abs(transient_resistance) * dynamic.resistance_scale * dynamic.resistance_normalization,
    )
    scaled_transient_capacitance = (
        max(
            1.0,
            abs(transient_capacitance) / dynamic.resistance_scale / dynamic.capacitance_normalization,
        )
        if scaled_transient_resistance > 1.0e-12
        else 1.0
    )
    scaled_secondary_transient_resistance = max(
        0.0,
        abs(secondary_transient_resistance) * dynamic.resistance_scale * dynamic.resistance_normalization,
    )
    scaled_secondary_transient_capacitance = (
        max(
            1.0,
            abs(secondary_transient_capacitance)
            / dynamic.resistance_scale
            / max(dynamic.secondary_capacitance_normalization, 1.0e-12),
        )
        if scaled_secondary_transient_resistance > 1.0e-12
        else 1.0
    )
    return (
        open_circuit_voltage_v,
        scaled_series_resistance,
        scaled_transient_resistance,
        scaled_transient_capacitance,
        scaled_secondary_transient_resistance,
        scaled_secondary_transient_capacitance,
    )


def _interpolate_temperature_lookup(
    temperature_grid_c: tuple[float, ...],
    lookup_table: tuple[tuple[float, ...], ...],
    soc: float,
    *,
    temperature_c: float,
    default: float,
) -> float:
    """Interpolate one SOC-indexed lookup table over temperature and SOC."""
    if not temperature_grid_c or not lookup_table:
        return float(default)
    if len(temperature_grid_c) != len(lookup_table):
        return float(default)
    by_temperature = tuple(
        _interpolate_scalar_series(_TWO_RC_REFERENCE_SOC_GRID, values, soc) for values in lookup_table
    )
    return _interpolate_scalar_series(temperature_grid_c, by_temperature, float(temperature_c))


def _parse_parameterization(mapping: Mapping[str, object]) -> BatteryParameterization:
    """Parse one optional parameterization payload from the backend mapping."""
    parameterization_payload = mapping.get("parameterization")
    if parameterization_payload is None:
        preset = _coerce_optional_string(
            mapping.get("parameterization_preset"),
            field_name="battery_backend.parameterization_preset",
        )
        parameter_set = _coerce_optional_string(
            mapping.get("parameter_set"),
            field_name="battery_backend.parameter_set",
        )
        return _normalize_parameterization(BatteryParameterization(preset=preset, parameter_set=parameter_set))
    if isinstance(parameterization_payload, str):
        return _normalize_parameterization(BatteryParameterization(preset=parameterization_payload))
    if not isinstance(parameterization_payload, Mapping):
        raise ValueError("battery_backend.parameterization must be a mapping or string preset.")
    payload = dict(parameterization_payload)
    preset = _coerce_optional_string(payload.get("preset"), field_name="battery_backend.parameterization.preset")
    parameter_set = _coerce_optional_string(
        payload.get("parameter_set"),
        field_name="battery_backend.parameterization.parameter_set",
    )
    return _normalize_parameterization(BatteryParameterization(preset=preset, parameter_set=parameter_set))


def _normalize_parameterization(value: BatteryParameterization) -> BatteryParameterization:
    """Return one validated normalized parameterization object."""
    preset = None if value.preset is None else value.preset.strip().lower()
    if preset is not None and preset not in _SUPPORTED_PARAMETERIZATION_PRESETS:
        supported = ", ".join(sorted(_SUPPORTED_PARAMETERIZATION_PRESETS))
        raise ValueError(f"Unsupported battery parameterization preset {value.preset!r}. Expected one of: {supported}.")
    parameter_set = None if value.parameter_set is None else value.parameter_set.strip()
    if parameter_set == "":
        parameter_set = None
    return BatteryParameterization(preset=preset, parameter_set=parameter_set)


def _coerce_string(value: object, *, field_name: str) -> str:
    """Return one required non-empty string field."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized


def _coerce_optional_string(value: object, *, field_name: str) -> str | None:
    """Return one optional string field."""
    if value is None:
        return None
    return _coerce_string(value, field_name=field_name)


def _coerce_option_pairs(value: object, *, field_name: str) -> BatteryBackendOptions:
    """Return one normalized sorted mapping payload as tuple pairs."""
    if value is None:
        return ()
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping when provided.")
    payload: list[tuple[str, BatteryBackendScalar]] = []
    for key, entry in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field_name} keys must be strings.")
        payload.append((key, _coerce_option_scalar(entry, field_name=field_name, key=key)))
    return tuple(sorted(payload, key=lambda item: item[0]))


def _coerce_option_scalar(value: object, *, field_name: str, key: str) -> BatteryBackendScalar:
    """Return one backend option scalar."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value
    raise ValueError(f"{field_name}[{key!r}] must be one of: bool, int, float, or str.")


__all__ = [
    "BatteryBackendConfig",
    "BatteryCellModel",
    "BatteryParameterization",
    "BatteryThermalPriors",
    "battery_backend_config_from_mapping",
    "import_pybamm",
    "interpolate_cell_model",
    "interpolate_total_resistance",
    "load_18650_cell_model",
    "load_18650_thermal_priors",
    "load_battery_cell_model",
    "load_battery_thermal_priors",
    "resolve_battery_backend_config",
]
