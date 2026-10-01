"""Delta 3 / River 3 generation (incl. Delta 3 Ultra) - protobuf telemetry.

Frames used:

* ``cmd_func=254 cmd_id=21`` DisplayPropertyUpload - main status. Sent in
  full every couple of minutes and incrementally (changed fields only) every
  few seconds, so the caller merges results instead of replacing them.
* ``cmd_func=254 cmd_id=22`` RuntimePropertyUpload - measured voltages,
  currents, temperatures, firmware versions.
* ``cmd_func=32 cmd_id=2``  CMS heartbeat - only the float SoC is used.
* ``cmd_func=32 cmd_id=50`` BMS heartbeat - one per battery pack: ``num`` 0
  is the built-in battery, 1.. are extra batteries.

Field numbers: River 3 and Delta 3 share the same numbering (verified field
by field between the two .proto files of tolwi/hassio-ecoflow-cloud); the
Delta Pro 3 additions (high/low voltage PV, extra-battery ports) do not
collide with it, so one schema serves the whole generation. PV2 and Type-C 3
come from shuette42/ecoflow-energy-ha (MIT). Every other known field is
exposed as a raw value (see ``raw.py`` and ``schemas.py``).
"""

from __future__ import annotations

from typing import Any

from ..proto import FLOAT, MSG, Field, decode
from . import raw
from .schemas import GEN3_BMS, GEN3_DISPLAY, GEN3_RUNTIME

DISPLAY_SCHEMA = GEN3_DISPLAY
RUNTIME_SCHEMA = GEN3_RUNTIME
BMS_HEARTBEAT_SCHEMA = GEN3_BMS

# The two public definitions of this frame disagree beyond the float SoC.
CMS_HEARTBEAT_SCHEMA: dict[int, Field] = {
    1: Field("v1p0", MSG, {15: Field("f32_lcd_show_soc", FLOAT)}),
}

# Port powers: absolute value, the direction is in the name. Some units report
# outputs as negative numbers.
_POWER_FIELDS: dict[str, str] = {
    "pow_in_sum_w": "input_power_w",
    "pow_out_sum_w": "output_power_w",
    "pow_get_ac_in": "ac_in_power_w",
    "pow_get_ac_out": "ac_out_power_w",
    "pow_get_ac_hv_out": "ac_hv_out_power_w",
    "pow_get_ac_lv_out": "ac_lv_out_power_w",
    "pow_get_pv": "solar_in_power_w",
    "pow_get_pv2": "solar2_in_power_w",
    "pow_get_pv_h": "solar_hv_in_power_w",
    "pow_get_pv_l": "solar_lv_in_power_w",
    "pow_get_12v": "dc12v_out_power_w",
    "pow_get_24v": "dc24v_out_power_w",
    "pow_get_typec1": "usb_c1_out_power_w",
    "pow_get_typec2": "usb_c2_out_power_w",
    "pow_get_typec3": "usb_c3_out_power_w",
    "pow_get_qcusb1": "usb_qc1_out_power_w",
    "pow_get_qcusb2": "usb_qc2_out_power_w",
}

# Signed powers: keep the sign, it is the information.
_SIGNED_POWER_FIELDS: dict[str, str] = {
    "pow_get_bms": "battery_power_w",
    "pow_get_4p8_1": "extra1_power_w",
    "pow_get_4p8_2": "extra2_power_w",
}

_PLAIN_FIELDS: dict[str, str] = {
    "cms_batt_soc": "soc",
    "bms_batt_soc": "main_battery_soc",
    "bms_design_cap": "design_capacity_mah",
    "cms_dsg_rem_time": "discharge_remaining_raw_min",
    "cms_chg_rem_time": "charge_remaining_raw_min",
    "cms_max_chg_soc": "max_charge_soc",
    "cms_min_dsg_soc": "min_discharge_soc",
    "bms_min_cell_temp": "min_cell_temp_c",
    "bms_max_cell_temp": "max_cell_temp_c",
    "bms_max_mos_temp": "max_mos_temp_c",
    "plug_in_info_ac_in_feq": "ac_in_freq_hz",
    "ac_out_freq": "ac_out_freq_hz",
    "plug_in_info_ac_in_chg_pow_max": "ac_charge_power_limit_w",
}

_BOOL_FIELDS: dict[str, str] = {
    "cfg_ac_out_open": "ac_out_enabled",
    "dc_out_open": "dc12v_out_enabled",
    "xboost_en": "xboost_enabled",
    "plug_in_info_ac_in_flag": "ac_in_connected",
    "energy_backup_en": "backup_reserve_enabled",
}

_CHG_DSG_STATE = {0: "idle", 1: "discharging", 2: "charging"}

# Lifetime counters kept by the device (Wh), from display_statistics_sum.
_STATISTICS: dict[int, str] = {
    2: "ac_out_energy_lifetime_kwh",
    3: "dc12v_out_energy_lifetime_kwh",
    4: "usb_c_out_energy_lifetime_kwh",
    5: "usb_a_out_energy_lifetime_kwh",
    6: "ac_in_energy_lifetime_kwh",
    7: "solar_in_energy_lifetime_kwh",
}


# Source fields that already feed a named sensor (not repeated as raw).
_DISPLAY_USED = {
    *_POWER_FIELDS,
    *_SIGNED_POWER_FIELDS,
    *_PLAIN_FIELDS,
    *_BOOL_FIELDS,
    "bms_batt_soh",
    "cms_batt_soh",
    "backup_reverse_soc",
    "energy_backup_start_soc",
    "cms_chg_dsg_state",
    "bms_chg_dsg_state",
    "display_statistics_sum",
}
_BMS_USED = {
    "num",
    "vol",
    "amp",
    "temp",
    "cycles",
    "remain_cap",
    "full_cap",
    "design_cap",
    "max_cell_vol",
    "min_cell_vol",
    "max_cell_temp",
    "min_cell_temp",
    "max_mos_temp",
    "f32_show_soc",
    "soc",
    "soh",
    "input_watts",
    "output_watts",
    "accu_chg_energy",
    "accu_dsg_energy",
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_display(pdata: bytes) -> dict[str, Any]:
    """Parse a DisplayPropertyUpload (254/21)."""
    fields = decode(pdata, DISPLAY_SCHEMA)
    out: dict[str, Any] = {}

    for src, dest in _POWER_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(abs(float(fields[src])), 1)
    for src, dest in _SIGNED_POWER_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), 1)
    for src, dest in _PLAIN_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = float(fields[src])
    for src, dest in _BOOL_FIELDS.items():
        if src in fields:
            out[dest] = bool(fields[src])

    soh = fields.get("bms_batt_soh", fields.get("cms_batt_soh"))
    if _is_number(soh) and soh > 0:
        out["soh"] = round(float(soh), 1)

    backup = fields.get("backup_reverse_soc", fields.get("energy_backup_start_soc"))
    if _is_number(backup):
        out["backup_reserve_soc"] = float(backup)

    state = fields.get("cms_chg_dsg_state", fields.get("bms_chg_dsg_state"))
    if isinstance(state, int) and state in _CHG_DSG_STATE:
        out["chg_dsg_state"] = _CHG_DSG_STATE[state]

    if _is_number(out.get("main_battery_soc")):
        out["main_battery_soc"] = round(out["main_battery_soc"], 1)
    # Zero means "not reported" for these.
    for key in ("design_capacity_mah", "ac_in_freq_hz", "ac_out_freq_hz"):
        if out.get(key) == 0:
            del out[key]

    stats = fields.get("display_statistics_sum")
    if isinstance(stats, dict):
        for item in stats.get("list_info", []):
            key = _STATISTICS.get(item.get("statistics_object"))
            content = item.get("statistics_content")
            if key and _is_number(content) and content > 0:
                out[key] = round(content / 1000.0, 3)

    out.update(raw.flatten(fields, skip=_DISPLAY_USED))
    return out


# Runtime frame (254/22): measured voltages, currents and temperatures.
_RUNTIME_FIELDS: dict[str, tuple[str, int]] = {
    "temp_pcs_dc": ("pcs_dc_temp_c", 1),
    "temp_pcs_ac": ("pcs_ac_temp_c", 1),
    "temp_pv": ("mppt_temp_c", 1),
    "plug_in_info_ac_out_vol": ("ac_out_voltage_v", 1),
    "plug_in_info_ac_in_vol": ("ac_in_voltage_v", 1),
    "plug_in_info_pv_vol": ("solar_in_voltage_v", 1),
    "plug_in_info_12v_vol": ("dc12v_out_voltage_v", 2),
    "plug_in_info_12v_amp": ("dc12v_out_current_a", 2),
}


def parse_runtime(pdata: bytes) -> dict[str, Any]:
    """Parse a RuntimePropertyUpload (254/22)."""
    fields = decode(pdata, RUNTIME_SCHEMA)
    out: dict[str, Any] = {}
    for src, (dest, digits) in _RUNTIME_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), digits)
    out.update(raw.flatten(fields, skip=_RUNTIME_FIELDS))
    return out


def parse_cms_heartbeat(pdata: bytes) -> dict[str, Any]:
    """Parse the CMS heartbeat (32/2): only the precise SoC is trusted."""
    fields = decode(pdata, CMS_HEARTBEAT_SCHEMA)
    pack = fields.get("v1p0")
    if isinstance(pack, dict) and _is_number(pack.get("f32_lcd_show_soc")):
        return {"soc": round(float(pack["f32_lcd_show_soc"]), 1)}
    return {}


def parse_bms_heartbeat(pdata: bytes) -> dict[str, Any]:
    """Parse a BMS heartbeat (32/50) for the built-in or an extra battery."""
    fields = decode(pdata, BMS_HEARTBEAT_SCHEMA)
    num = fields.get("num", 0)
    prefix = "" if num == 0 else f"extra{num}_"
    out: dict[str, Any] = {}

    def put(key: str, value: Any, divisor: float = 1.0) -> None:
        if _is_number(value):
            out[f"{prefix}{key}"] = float(value) / divisor

    put("voltage_v" if prefix else "battery_voltage_v", fields.get("vol"), 1000.0)
    put("current_a" if prefix else "battery_current_a", fields.get("amp"), 1000.0)
    put("temp_c" if prefix else "battery_temp_c", fields.get("temp"))
    put("cycles", fields.get("cycles"))
    put("remain_capacity_mah", fields.get("remain_cap"))
    put("full_capacity_mah", fields.get("full_cap"))
    if _is_number(fields.get("design_cap")) and fields["design_cap"] > 0:
        put("design_capacity_mah", fields["design_cap"])
    put("max_cell_voltage_v", fields.get("max_cell_vol"), 1000.0)
    put("min_cell_voltage_v", fields.get("min_cell_vol"), 1000.0)
    put("max_cell_temp_c", fields.get("max_cell_temp"))
    put("min_cell_temp_c", fields.get("min_cell_temp"))
    put("max_mos_temp_c", fields.get("max_mos_temp"))
    if prefix:
        # The built-in battery's SoC/SoH come from the status frame.
        soc = fields.get("f32_show_soc", fields.get("soc"))
        put("soc", round(float(soc), 1) if _is_number(soc) else None)
        if _is_number(fields.get("soh")) and fields["soh"] > 0:
            put("soh", fields["soh"])
        put("in_power_w", fields.get("input_watts"))
        put("out_power_w", fields.get("output_watts"))
    # Lifetime counters (Wh). Zero means "not reported", and publishing it
    # on a total_increasing sensor would look like a meter reset.
    for src, key in (
        ("accu_chg_energy", "battery_charge_energy_lifetime_kwh"),
        ("accu_dsg_energy", "battery_discharge_energy_lifetime_kwh"),
    ):
        value = fields.get(src)
        if _is_number(value) and value > 0:
            out[f"{prefix}{key}"] = round(value / 1000.0, 3)

    out.update(raw.flatten(fields, skip=_BMS_USED, prefix=prefix))
    return out


def parse_frame(cmd_func: int, cmd_id: int, pdata: bytes) -> dict[str, Any] | None:
    """Return parsed values, or None when the frame is not one we read."""
    if cmd_func == 254 and cmd_id == 21:
        return parse_display(pdata)
    if cmd_func == 254 and cmd_id == 22:
        return parse_runtime(pdata)
    if cmd_func == 32 and cmd_id == 2:
        return parse_cms_heartbeat(pdata)
    if cmd_func == 32 and cmd_id == 50:
        return parse_bms_heartbeat(pdata)
    return None
