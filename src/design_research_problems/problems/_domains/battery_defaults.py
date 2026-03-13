"""Shared first-pass battery modeling defaults for 18650-class packs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BatteryJointProcessPrior:
    """One lognormal engineering prior for a joining process."""

    dist: str
    median_ohm: float
    sigma_log: float


@dataclass(frozen=True)
class BatteryContactGrowthDefaults:
    """First-pass multiplicative contact-growth defaults."""

    pressure_exponent: float = 0.7
    fretting_coeff_per_cycle: float = 5.0e-5
    corrosion_coeff_per_exposure_unit: float = 0.1
    scenario_multipliers: dict[str, float] = field(
        default_factory=lambda: {
            "fresh": 1.0,
            "mild_pressure_loss": 1.5,
            "moderate_fretting_or_oxide": 2.0,
            "severe_fretting_or_corrosion": 5.0,
            "bad_contact": 10.0,
        }
    )


@dataclass(frozen=True)
class BatteryElectricalDefaults:
    """Electrical defaults for interconnects and idealization thresholds."""

    rho_20_ohm_m: dict[str, float] = field(
        default_factory=lambda: {
            "Cu": 1.68e-8,
            "Al": 2.65e-8,
            "Ni": 6.99e-8,
        }
    )
    alpha_t_per_k: dict[str, float] = field(
        default_factory=lambda: {
            "Cu": 3.9e-3,
            "Al": 4.3e-3,
            "Ni": 6.0e-3,
        }
    )
    r_weld_ohm: float = 5.0e-5
    r_weld_band_ohm: tuple[float, float] = (1.0e-5, 5.0e-4)
    r_contact_ohm: float = 5.0e-4
    r_contact_serviceable_ohm: float = 3.0e-3
    r_contact_band_ohm: tuple[float, float] = (1.0e-4, 1.0e-2)
    r_contact_bad_ohm: float = 1.0e-2
    ideal_series_threshold_ohm: float = 1.0e-4
    ideal_parallel_threshold_ohm: float = 3.0e-5
    joint_priors: dict[str, BatteryJointProcessPrior] = field(
        default_factory=lambda: {
            "USW": BatteryJointProcessPrior(dist="lognormal", median_ohm=5.0e-5, sigma_log=0.75),
            "Laser": BatteryJointProcessPrior(dist="lognormal", median_ohm=1.0e-4, sigma_log=0.80),
            "MicroRSW": BatteryJointProcessPrior(dist="lognormal", median_ohm=1.5e-4, sigma_log=0.85),
        }
    )
    contact_growth: BatteryContactGrowthDefaults = field(default_factory=BatteryContactGrowthDefaults)


@dataclass(frozen=True)
class BatteryVariationDefaults:
    """Fresh-pack cell-to-cell variation defaults."""

    r_dc_rel_sigma: float = 0.04
    capacity_rel_sigma: float = 0.02
    soc_abs_sigma: float = 0.005


@dataclass(frozen=True)
class BatteryGeometryDefaults:
    """Geometry and keep-out defaults for cylindrical packs."""

    radial_gap_min_mm: float = 0.75
    axial_gap_min_mm: float = 1.5
    fixture_keepout_min_mm: float = 1.5


@dataclass(frozen=True)
class BatteryThermalDefaults:
    """Thermal defaults for coarse backend and pack screening."""

    default_mode: str = "isothermal"
    ambient_temperature_c: float = 25.0
    advisable_operating_range_c: tuple[float, float] = (15.0, 35.0)
    g_side_air_w_per_k: float = 0.03
    g_end_air_w_per_k: float = 0.02
    g_holder_w_per_k: float = 0.03
    g_plate_w_per_k: float = 0.12
    r_tc_m2k_per_w: float = 1.0e-3
    entropic_heat_mandatory_below_c_rate: float = 0.5
    entropic_heat_recommended_below_c_rate: float = 1.0


@dataclass(frozen=True)
class BatteryConstraintDefaults:
    """First-pass feasibility thresholds for thermal screening."""

    pack_dt_max_c: float = 5.0
    t_cell_max_c: float = 50.0
    plating_hard_fail_ne_potential_v_vs_li: float = 0.0
    plating_warning_ne_potential_v_vs_li: float = 0.03
    plating_comfort_target_v_vs_li: float = 0.05


@dataclass(frozen=True)
class BatteryModelSelectionDefaults:
    """Triggers for fidelity upgrades and graph-solve retirement."""

    one_rc_voltage_rmse_target_mv: float = 20.0
    one_rc_temperature_mae_target_c: float = 1.0
    hysteresis_residual_trigger_mv: float = 10.0
    graph_solve_rdc_rel_sigma_trigger: float = 0.05
    graph_solve_capacity_rel_sigma_trigger: float = 0.03
    graph_solve_soc_abs_spread_trigger: float = 0.02
    graph_solve_branch_path_spread_ohm_trigger: float = 1.0e-4
    graph_solve_pack_dt_trigger_c: float = 3.0


@dataclass(frozen=True)
class BatteryBackendDefaults:
    """Container for shared backend-facing battery defaults."""

    electrical: BatteryElectricalDefaults = field(default_factory=BatteryElectricalDefaults)
    variation: BatteryVariationDefaults = field(default_factory=BatteryVariationDefaults)
    geometry: BatteryGeometryDefaults = field(default_factory=BatteryGeometryDefaults)
    thermal: BatteryThermalDefaults = field(default_factory=BatteryThermalDefaults)
    constraints: BatteryConstraintDefaults = field(default_factory=BatteryConstraintDefaults)
    model_selection: BatteryModelSelectionDefaults = field(default_factory=BatteryModelSelectionDefaults)


BATTERY_BACKEND_DEFAULTS = BatteryBackendDefaults()
"""Shared default values for battery backend configuration and screening."""


SUPPORTED_BATTERY_THERMAL_MODES = frozenset({"isothermal", "lumped"})
"""Thermal modes supported by the explicit battery backend."""


__all__ = [
    "BATTERY_BACKEND_DEFAULTS",
    "SUPPORTED_BATTERY_THERMAL_MODES",
    "BatteryBackendDefaults",
    "BatteryConstraintDefaults",
    "BatteryContactGrowthDefaults",
    "BatteryElectricalDefaults",
    "BatteryGeometryDefaults",
    "BatteryJointProcessPrior",
    "BatteryModelSelectionDefaults",
    "BatteryThermalDefaults",
    "BatteryVariationDefaults",
]
