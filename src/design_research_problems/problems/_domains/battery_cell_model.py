"""Effective single-cell helpers used by the shared battery solver."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy

from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._domains.battery_layout import CELL_SPEC_18650

BatteryBackendScalar = bool | int | float | str
BatteryBackendOptions = tuple[tuple[str, BatteryBackendScalar], ...]

_SUPPORTED_CELL_MODEL_MODES = frozenset(
    {
        "auto",
        "pybamm_ecm",
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
    """Optional thermal mode placeholder accepted for forward compatibility."""
    ambient_temp_c: float | None = None
    """Optional ambient temperature placeholder accepted for forward compatibility."""
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
    source: str = "custom"
    """Origin of the surrogate, such as ``pybamm_thevenin`` or one custom test stub."""
    warning_message: str | None = None
    """Non-fatal warning emitted while building the surrogate, when present."""
    resolved_mode: str | None = None
    """Resolved backend mode used to build this cell model."""
    resolved_parameter_set: str | None = None
    """Resolved concrete parameter set used for this model."""


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
    normalized_thermal_mode = (
        None
        if candidate.thermal_mode is None
        else _coerce_string(candidate.thermal_mode, field_name="battery_backend.thermal_mode").strip().lower()
    )
    return BatteryBackendConfig(
        cell_model_mode=normalized_mode,
        parameterization=normalized_parameterization,
        thermal_mode=normalized_thermal_mode,
        ambient_temp_c=candidate.ambient_temp_c,
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
        return _load_pybamm_ecm_cell_model(resolved_parameter_set=resolved_parameter_set)
    if resolved_mode == "pybamm_spm":
        return _load_pybamm_lithium_ion_cell_model(
            model_family="spm",
            resolved_parameter_set=resolved_parameter_set,
        )
    if resolved_mode == "pybamm_dfn":
        return _load_pybamm_lithium_ion_cell_model(
            model_family="dfn",
            resolved_parameter_set=resolved_parameter_set,
        )
    raise MissingOptionalDependencyError(f"Unsupported resolved battery mode {resolved_mode!r}.")


def _resolve_effective_mode(requested_mode: str) -> str:
    """Return the effective cell model mode for one requested mode."""
    if requested_mode != "auto":
        return requested_mode
    return "pybamm_ecm"


def _load_thevenin_parameter_values(*, resolved_parameter_set: str | None = None) -> tuple[Any, float, float]:
    """Return copied Thevenin parameter values plus 18650 normalization factors.

    Args:
        resolved_parameter_set: Optional concrete PyBaMM parameter-set name.

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
    ambient_temperature_k = _parameter_value(parameter_values, "Initial temperature [K]", default=298.15)
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


def _load_pybamm_ecm_cell_model(*, resolved_parameter_set: str | None) -> BatteryCellModel:
    """Load one Thevenin-derived ECM model and normalize to packaged 18650 scale."""
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_thevenin_parameter_values(
            resolved_parameter_set=resolved_parameter_set,
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


def _load_pybamm_lithium_ion_cell_model(
    *,
    model_family: str,
    resolved_parameter_set: str | None,
) -> BatteryCellModel:
    """Load one SPM/DFN-based cell model and map it into ECM lookup tables."""
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_lithium_ion_parameter_values(
            model_family=model_family,
            resolved_parameter_set=resolved_parameter_set,
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
    ambient_temperature_k = _parameter_value(parameter_values, "Initial temperature [K]", default=298.15)
    return (parameter_values, resistance_scale, ambient_temperature_k)


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
    )


@lru_cache(maxsize=1)
def load_18650_thermal_priors() -> BatteryThermalPriors:
    """Return one cached PyBaMM-derived thermal prior bundle for Tier-4 modeling.

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
        parameter_values, resistance_scale, ambient_temperature_k = _load_thevenin_parameter_values()
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
        cell_model = load_18650_cell_model()
        total_resistance_ohm = tuple(
            max(1.0e-6, series + transient)
            for series, transient in zip(
                cell_model.series_resistance_ohm,
                cell_model.transient_resistance_ohm,
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


def interpolate_cell_model(model: BatteryCellModel, soc: float) -> tuple[float, float, float, float]:
    """Interpolate cell operating values at one SOC value.

    Args:
        model: Value for ``model``.
        soc: Value for ``soc``.

    Returns:
        Computed result for this callable.
    """
    clipped_soc = min(1.0, max(0.0, soc))
    if clipped_soc <= model.soc_grid[0]:
        return (
            model.open_circuit_voltage_v[0],
            model.series_resistance_ohm[0],
            model.transient_resistance_ohm[0],
            model.transient_capacitance_f[0],
        )
    if clipped_soc >= model.soc_grid[-1]:
        return (
            model.open_circuit_voltage_v[-1],
            model.series_resistance_ohm[-1],
            model.transient_resistance_ohm[-1],
            model.transient_capacitance_f[-1],
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
        return (
            lower_ocv + (ratio * (upper_ocv - lower_ocv)),
            lower_series_resistance + (ratio * (upper_series_resistance - lower_series_resistance)),
            lower_transient_resistance + (ratio * (upper_transient_resistance - lower_transient_resistance)),
            lower_transient_capacitance + (ratio * (upper_transient_capacitance - lower_transient_capacitance)),
        )

    return (
        CELL_SPEC_18650.nominal_voltage_v,
        CELL_SPEC_18650.internal_resistance_ohm,
        0.0,
        1.0,
    )


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
    "resolve_battery_backend_config",
]
