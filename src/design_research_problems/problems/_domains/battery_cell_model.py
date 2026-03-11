"""Effective single-cell helpers used by the shared battery solver."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import numpy

from design_research_problems._exceptions import MissingOptionalDependencyError
from design_research_problems._optional import import_optional_module
from design_research_problems.problems._domains.battery_layout import CELL_SPEC_18650


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


def _load_thevenin_parameter_values() -> tuple[Any, float, float]:
    """Return copied Thevenin parameter values plus 18650 normalization factors.

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
    parameter_values: Any = _copy_parameter_values(model.default_parameter_values)
    reference_capacity_ah = _parameter_value(parameter_values, "Cell capacity [A.h]", default=100.0)
    resistance_scale = max(1.0e-6, reference_capacity_ah / CELL_SPEC_18650.nominal_capacity_ah)
    ambient_temperature_k = _parameter_value(parameter_values, "Initial temperature [K]", default=298.15)
    return (parameter_values, resistance_scale, ambient_temperature_k)


@lru_cache(maxsize=1)
def load_18650_cell_model() -> BatteryCellModel:
    """Return one cached fixed-ambient 18650 surrogate for the shared pack solver.

    The preferred path samples PyBaMM's 1-RC Thevenin equivalent-circuit model at
    one ambient temperature and converts it into an SOC-indexed lookup table. The
    extracted resistance magnitudes are then anchored to this package's 18650
    constants so the pack benchmark stays self-consistent even though the curve
    shape comes from PyBaMM's default ECM parameterization.

    Returns:
        Computed result for this callable.

    Raises:
        Exception: Raised when the callable encounters an invalid state.
    """
    try:
        parameter_values, resistance_scale, ambient_temperature_k = _load_thevenin_parameter_values()
    except MissingOptionalDependencyError:
        raise
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM Thevenin parameter extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Battery problem evaluation requires a supported PyBaMM version "
            "with the expected Thevenin parameter interface."
        ) from exc

    try:
        soc_grid = tuple(index / 10.0 for index in range(11))

        open_circuit_voltage_v: list[float] = []
        series_resistance_ohm: list[float] = []
        transient_resistance_ohm: list[float] = []
        transient_capacitance_f: list[float] = []

        open_circuit_fn = parameter_values["Open-circuit voltage [V]"]
        series_resistance_fn = parameter_values["R0 [Ohm]"]
        transient_resistance_fn = parameter_values.get("R1 [Ohm]", None)
        transient_capacitance_fn = parameter_values.get("C1 [F]", None)

        for soc in soc_grid:
            open_circuit_voltage_v.append(_evaluate_parameter(parameter_values, open_circuit_fn(soc)))
            series_resistance_ohm.append(
                max(
                    1.0e-6,
                    abs(
                        _evaluate_parameter(
                            parameter_values,
                            series_resistance_fn(ambient_temperature_k, 0.0, soc),
                        )
                    )
                    * resistance_scale,
                )
            )
            if callable(transient_resistance_fn):
                transient_resistance_ohm.append(
                    max(
                        0.0,
                        abs(
                            _evaluate_parameter(
                                parameter_values,
                                transient_resistance_fn(ambient_temperature_k, 0.0, soc),
                            )
                        )
                        * resistance_scale,
                    )
                )
            else:
                transient_resistance_ohm.append(0.0)
            if callable(transient_capacitance_fn):
                transient_capacitance_f.append(
                    max(
                        1.0,
                        abs(
                            _evaluate_parameter(
                                parameter_values,
                                transient_capacitance_fn(ambient_temperature_k, 0.0, soc),
                            )
                        )
                        / resistance_scale,
                    )
                )
            else:
                transient_capacitance_f.append(1.0)

        nominal_index = min(range(len(soc_grid)), key=lambda index: abs(soc_grid[index] - 0.5))
        nominal_total_resistance = series_resistance_ohm[nominal_index] + transient_resistance_ohm[nominal_index]
        resistance_normalization = (
            1.0
            if nominal_total_resistance <= 1.0e-12
            else CELL_SPEC_18650.internal_resistance_ohm / nominal_total_resistance
        )
        capacitance_normalization = max(resistance_normalization, 1.0e-12)

        series_resistance_ohm = [
            max(1.0e-6, resistance * resistance_normalization) for resistance in series_resistance_ohm
        ]
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
            source="pybamm_thevenin",
        )
    except Exception as exc:
        raise MissingOptionalDependencyError(
            "PyBaMM Thevenin parameter extraction failed "
            f"({type(exc).__name__}: {exc}). "
            "Battery problem evaluation requires a supported PyBaMM version "
            "with the expected Thevenin parameter interface."
        ) from exc


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


__all__ = [
    "BatteryCellModel",
    "BatteryThermalPriors",
    "import_pybamm",
    "interpolate_cell_model",
    "interpolate_total_resistance",
    "load_18650_cell_model",
    "load_18650_thermal_priors",
]
