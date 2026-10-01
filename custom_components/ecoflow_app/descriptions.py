"""Entity catalog: canonical value key -> how Home Assistant shows it.

Entities are created from this catalog as soon as a device reports the
matching key (and again at every startup for keys reported before), so a
model never gets entities for ports it does not have.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)

CHG_DSG_OPTIONS = ["idle", "charging", "discharging"]
DIAG = EntityCategory.DIAGNOSTIC


@dataclass(frozen=True, kw_only=True)
class EcoFlowSensorDescription(SensorEntityDescription):
    """Sensor description with an optional index placeholder."""

    index: int | None = None


def _power(key: str, enabled: bool = True) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=enabled,
    )


def _energy(key: str, enabled: bool = True) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        entity_registry_enabled_default=enabled,
    )


def _percent(
    key: str, battery: bool = False, diag: bool = False, enabled: bool = True
) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.BATTERY if battery else None,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=DIAG if diag else None,
        entity_registry_enabled_default=enabled,
    )


def _temp(key: str, enabled: bool = True) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_category=DIAG,
        entity_registry_enabled_default=enabled,
    )


def _voltage(key: str, enabled: bool = True, precision: int = 1) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=precision,
        entity_category=DIAG,
        entity_registry_enabled_default=enabled,
    )


def _current(key: str, enabled: bool = True) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=DIAG,
        entity_registry_enabled_default=enabled,
    )


def _frequency(key: str) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=DIAG,
        entity_registry_enabled_default=True,
    )


def _minutes(key: str, enabled: bool = True) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
        entity_registry_enabled_default=enabled,
    )


def _plain(
    key: str,
    unit: str | None = None,
    enabled: bool = True,
    state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key=key,
        native_unit_of_measurement=unit,
        state_class=state_class,
        suggested_display_precision=0,
        entity_category=DIAG,
        entity_registry_enabled_default=enabled,
    )


def _state(key: str) -> EcoFlowSensorDescription:
    return EcoFlowSensorDescription(
        key=key,
        translation_key="chg_dsg_state",
        device_class=SensorDeviceClass.ENUM,
        options=CHG_DSG_OPTIONS,
    )


_BASE_SENSORS: list[EcoFlowSensorDescription] = [
    # Battery
    _percent("soc", battery=True),
    _percent("main_battery_soc", battery=True, diag=True),
    _percent("soh", diag=True),
    _state("chg_dsg_state"),
    _minutes("charge_remaining_min"),
    _minutes("discharge_remaining_min"),
    _minutes("remaining_time_min"),
    _plain("cycles", state_class=SensorStateClass.TOTAL_INCREASING),
    _temp("battery_temp_c"),
    _temp("min_cell_temp_c"),
    _temp("max_cell_temp_c"),
    _temp("max_mos_temp_c"),
    _voltage("battery_voltage_v", precision=2),
    _current("battery_current_a"),
    _voltage("min_cell_voltage_v", precision=3),
    _voltage("max_cell_voltage_v", precision=3),
    _plain("remain_capacity_mah", "mAh"),
    _plain("full_capacity_mah", "mAh"),
    _plain("design_capacity_mah", "mAh"),
    _plain("remain_capacity_wh", UnitOfEnergy.WATT_HOUR),
    _plain("full_capacity_wh", UnitOfEnergy.WATT_HOUR),
    _plain("battery_pack_count", state_class=None),
    _power("battery_power_w"),
    _power("battery_charge_power_bms_w"),
    _power("battery_discharge_power_bms_w"),
    _power("battery_charge_power_max_w"),
    _power("battery_discharge_power_max_w"),
    # Limits / settings (read-only for now)
    _percent("max_charge_soc", diag=True),
    _percent("min_discharge_soc", diag=True),
    _percent("backup_reserve_soc", diag=True),
    _percent("ac_always_on_min_soc", diag=True),
    _plain("device_standby_min", UnitOfTime.MINUTES, state_class=None),
    _plain("ac_standby_min", UnitOfTime.MINUTES, state_class=None),
    _plain("dc_standby_min", UnitOfTime.MINUTES, state_class=None),
    _plain("screen_timeout_s", UnitOfTime.SECONDS, state_class=None),
    _power("ac_charge_power_limit_w"),
    # Totals
    _power("input_power_w"),
    _power("output_power_w"),
    _power("battery_charge_power_w"),
    _power("battery_discharge_power_w"),
    # AC
    _power("ac_in_power_w"),
    _power("ac_out_power_w"),
    _power("ac_hv_out_power_w"),
    _power("ac_lv_out_power_w"),
    _power("ac_l1_1_out_power_w"),
    _power("ac_l1_2_out_power_w"),
    _power("ac_l2_1_out_power_w"),
    _power("ac_l2_2_out_power_w"),
    _power("ac_tt30_out_power_w"),
    _power("ac_l14_out_power_w"),
    _power("power_in_out_in_power_w"),
    _power("power_in_out_out_power_w"),
    *[
        d
        for stem in (
            "ac_l1_1_out",
            "ac_l1_2_out",
            "ac_l2_1_out",
            "ac_l2_2_out",
            "ac_tt30_out",
            "ac_l14_out",
            "power_in_out_out",
            "power_in_out_in",
        )
        for d in (_voltage(f"{stem}_voltage_v"), _current(f"{stem}_current_a"))
    ],
    _power("power_in_out_charge_power_limit_w"),
    _power("ac_charge_power_max_w"),
    _voltage("ac_in_voltage_v"),
    _current("ac_in_current_a"),
    _voltage("ac_out_voltage_v"),
    _current("ac_out_current_a"),
    _frequency("ac_in_freq_hz"),
    _frequency("ac_out_freq_hz"),
    # Solar
    _power("solar_in_power_w"),
    _power("solar2_in_power_w"),
    _power("solar_hv_in_power_w"),
    _power("solar_lv_in_power_w"),
    _power("solar_total_power_w"),
    _voltage("solar_in_voltage_v"),
    _current("solar_in_current_a"),
    _voltage("solar_hv_in_voltage_v"),
    _current("solar_hv_in_current_a"),
    _voltage("solar_lv_in_voltage_v"),
    _current("solar_lv_in_current_a"),
    # DC / USB
    _power("dc_out_power_w"),
    _power("dc12v_out_power_w"),
    _voltage("dc12v_out_voltage_v", precision=2),
    _current("dc12v_out_current_a"),
    _voltage("dc_anderson_out_voltage_v", precision=2),
    _current("dc_anderson_out_current_a"),
    _voltage("usb_a1_out_voltage_v", precision=2),
    _current("usb_a1_out_current_a"),
    _voltage("usb_a2_out_voltage_v", precision=2),
    _current("usb_a2_out_current_a"),
    _voltage("usb_c1_out_voltage_v", precision=2),
    _current("usb_c1_out_current_a"),
    _voltage("usb_c2_out_voltage_v", precision=2),
    _current("usb_c2_out_current_a"),
    _power("pr_out_power_w"),
    _power("dc24v_out_power_w"),
    _power("dc_anderson_out_power_w"),
    _power("usb_a1_out_power_w"),
    _power("usb_a2_out_power_w"),
    _power("usb_qc1_out_power_w"),
    _power("usb_qc2_out_power_w"),
    _power("usb_c1_out_power_w"),
    _power("usb_c2_out_power_w"),
    _power("usb_c3_out_power_w"),
    # Temperatures
    _temp("inverter_temp_c"),
    _temp("mppt_temp_c"),
    _temp("pcs_dc_temp_c"),
    _temp("pcs_ac_temp_c"),
    _temp("mppt_lv_temp_c"),
    _temp("mppt_hv_temp_c"),
    _temp("pd_temp_c"),
    _plain("fan_level"),
    # Error codes
    _plain("pd_error_code", state_class=None),
    _plain("inverter_error_code", state_class=None),
    _plain("mppt_error_code", state_class=None),
    _plain("bms_error_code", state_class=None),
    _plain("system_error_code", state_class=None),
    # Energy (integrated by the integration, for the Energy dashboard)
    _energy("input_energy_kwh"),
    _energy("output_energy_kwh"),
    _energy("ac_in_energy_kwh"),
    _energy("ac_out_energy_kwh"),
    _energy("solar_in_energy_kwh"),
    _energy("battery_charge_energy_kwh"),
    _energy("battery_discharge_energy_kwh"),
    # Energy counters kept by the device itself
    _energy("ac_in_energy_lifetime_kwh"),
    _energy("ac_out_energy_lifetime_kwh"),
    _energy("solar_in_energy_lifetime_kwh"),
    _energy("dc12v_out_energy_lifetime_kwh"),
    _energy("usb_c_out_energy_lifetime_kwh"),
    _energy("usb_a_out_energy_lifetime_kwh"),
    _energy("battery_charge_energy_lifetime_kwh"),
    _energy("battery_discharge_energy_lifetime_kwh"),
]


def _indexed(
    template: EcoFlowSensorDescription, prefix: str, index: int
) -> EcoFlowSensorDescription:
    return replace(
        template,
        key=f"{prefix}{index}_{template.key}",
        translation_key=f"{prefix}_{template.translation_key}",
        index=index,
    )


# Extra batteries (Delta 2 / Delta 3 family): extra{n}_<key>
_EXTRA_TEMPLATES: list[EcoFlowSensorDescription] = [
    _percent("soc", battery=True),
    _percent("soh", diag=True),
    _plain("cycles", state_class=SensorStateClass.TOTAL_INCREASING),
    _temp("temp_c"),
    _voltage("voltage_v", precision=2),
    _current("current_a"),
    _power("in_power_w"),
    _power("out_power_w"),
    _power("power_w"),
    _plain("remain_capacity_mah", "mAh"),
    _plain("full_capacity_mah", "mAh"),
    _plain("design_capacity_mah", "mAh"),
    _temp("max_cell_temp_c"),
    _temp("min_cell_temp_c"),
    _voltage("max_cell_voltage_v", precision=3),
    _voltage("min_cell_voltage_v", precision=3),
    _plain("error_code", state_class=None),
    _energy("battery_charge_energy_lifetime_kwh"),
    _energy("battery_discharge_energy_lifetime_kwh"),
]

# Battery packs (Delta Pro Ultra): pack{n}_<key>
_PACK_TEMPLATES: list[EcoFlowSensorDescription] = [
    _percent("soc", battery=True),
    _power("power_w"),
    _plain("remain_energy_wh", UnitOfEnergy.WATT_HOUR),
    _temp("temp_c"),
    _minutes("remaining_time_min"),
    _state("chg_dsg_state"),
]

SENSORS: dict[str, EcoFlowSensorDescription] = {d.key: d for d in _BASE_SENSORS}
for _n in range(1, 3):
    for _t in _EXTRA_TEMPLATES:
        _d = _indexed(_t, "extra", _n)
        SENSORS[_d.key] = _d
for _n in range(1, 6):
    for _t in _PACK_TEMPLATES:
        _d = _indexed(_t, "pack", _n)
        SENSORS[_d.key] = _d


BINARY_SENSORS: dict[str, BinarySensorEntityDescription] = {
    d.key: d
    for d in (
        BinarySensorEntityDescription(
            key="ac_out_enabled",
            translation_key="ac_out_enabled",
            device_class=BinarySensorDeviceClass.POWER,
        ),
        BinarySensorEntityDescription(
            key="dc12v_out_enabled",
            translation_key="dc12v_out_enabled",
            device_class=BinarySensorDeviceClass.POWER,
        ),
        BinarySensorEntityDescription(
            key="usb_out_enabled",
            translation_key="usb_out_enabled",
            device_class=BinarySensorDeviceClass.POWER,
        ),
        BinarySensorEntityDescription(
            key="xboost_enabled", translation_key="xboost_enabled", entity_category=DIAG
        ),
        BinarySensorEntityDescription(
            key="backup_reserve_enabled",
            translation_key="backup_reserve_enabled",
            entity_category=DIAG,
        ),
        BinarySensorEntityDescription(
            key="ac_always_on_enabled", translation_key="ac_always_on_enabled", entity_category=DIAG
        ),
        BinarySensorEntityDescription(
            key="solar_only_enabled", translation_key="solar_only_enabled", entity_category=DIAG
        ),
        BinarySensorEntityDescription(
            key="ac_in_connected",
            translation_key="ac_in_connected",
            device_class=BinarySensorDeviceClass.PLUG,
        ),
    )
}

# Always created: whether the device is reporting.
ONLINE_DESCRIPTION = BinarySensorEntityDescription(
    key="online",
    translation_key="online",
    device_class=BinarySensorDeviceClass.CONNECTIVITY,
    entity_category=DIAG,
)
