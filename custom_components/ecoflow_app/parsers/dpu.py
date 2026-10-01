"""Delta Pro Ultra - protobuf telemetry.

The Delta Pro Ultra (inverter + stacked battery packs) reports on
``cmd_func=2``:

* ``cmd_id=1`` AppShowHeartbeatReport       - SoC, port powers, remaining time
* ``cmd_id=2`` BackendRecordHeartbeatReport - voltages, currents, temperatures
* ``cmd_id=3`` AppParaHeartbeatReport       - settings (SoC limits, backup)
* ``cmd_id=4`` BPInfoReport                 - one entry per battery pack

It also sends a ``254/21`` DisplayPropertyUpload with the combined SoC and
limits, using the same numbering as the Delta 3 generation.

Field numbers from foxthefox/ioBroker.ecoflow-mqtt (MIT). Every known field
that has no dedicated sensor is exposed as a raw value.
"""

from __future__ import annotations

from typing import Any

from ..proto import FLOAT, MSG, Field, decode
from . import raw
from .schemas import (
    DPU_APP_PARA,
    DPU_APP_SHOW,
    DPU_BACKEND,
    DPU_BP_INFO,
    DPU_DISPLAY,
    GEN3_DISPLAY,
)

APP_SHOW_SCHEMA = DPU_APP_SHOW
BACKEND_SCHEMA = DPU_BACKEND
APP_PARA_SCHEMA = DPU_APP_PARA
BP_INFO_REPORT_SCHEMA: dict[int, Field] = {
    1: Field("bp_info", MSG, DPU_BP_INFO, repeated=True),
}
DISPLAY_SCHEMA: dict[int, Field] = {**GEN3_DISPLAY, **DPU_DISPLAY}

# Heartbeats only carry the fields that changed, so a missing field keeps its
# last value (the hub merges). A port that has never reported still needs a
# sensor, though: for those fields a 0 is returned under DEFAULTS_KEY, which
# the hub applies only to keys it has never seen.
DEFAULTS_KEY = "_defaults"
_FLOATS_SHOW = [f.name for f in DPU_APP_SHOW.values() if f.kind == FLOAT]
_FLOATS_BACKEND = [f.name for f in DPU_BACKEND.values() if f.kind == FLOAT]


def _with_defaults(fields: dict[str, Any], floats: list[str], mapper) -> dict[str, Any]:
    """Map ``fields``, plus 0-valued defaults for the floats it lacks."""
    out = mapper(fields)
    padded = {**{name: 0.0 for name in floats}, **fields}
    defaults = {k: v for k, v in mapper(padded).items() if k not in out}
    if defaults:
        out[DEFAULTS_KEY] = defaults
    return out


_APP_SHOW_POWERS: dict[str, str] = {
    "watts_in_sum": "input_power_w",
    "watts_out_sum": "output_power_w",
    "out_usb1_pwr": "usb_a1_out_power_w",
    "out_usb2_pwr": "usb_a2_out_power_w",
    "out_typec1_pwr": "usb_c1_out_power_w",
    "out_typec2_pwr": "usb_c2_out_power_w",
    "out_ads_pwr": "dc_anderson_out_power_w",
    "out_ac_l1_1_pwr": "ac_l1_1_out_power_w",
    "out_ac_l1_2_pwr": "ac_l1_2_out_power_w",
    "out_ac_l2_1_pwr": "ac_l2_1_out_power_w",
    "out_ac_l2_2_pwr": "ac_l2_2_out_power_w",
    "out_ac_tt_pwr": "ac_tt30_out_power_w",
    "out_ac_l14_pwr": "ac_l14_out_power_w",
    "out_ac_5p8_pwr": "power_in_out_out_power_w",
    "in_ac_5p8_pwr": "power_in_out_in_power_w",
    "in_ac_c20_pwr": "ac_in_power_w",
    "in_lv_mppt_pwr": "solar_lv_in_power_w",
    "in_hv_mppt_pwr": "solar_hv_in_power_w",
    "out_pr_pwr": "pr_out_power_w",
}

_APP_SHOW_PLAIN: dict[str, str] = {
    "soc": "soc",
    "remain_time": "remaining_time_min",
    "remain_combo": "remain_capacity_wh",
    "sys_err_code": "system_error_code",
    "c20_chg_max_watts": "ac_charge_power_max_w",
}

_BACKEND_FIELDS: dict[str, tuple[str, int]] = {
    "bat_vol": ("battery_voltage_v", 2),
    "bat_amp": ("battery_current_a", 2),
    "bms_input_watts": ("battery_charge_power_bms_w", 1),
    "bms_output_watts": ("battery_discharge_power_bms_w", 1),
    "in_ac_c20_vol": ("ac_in_voltage_v", 1),
    "in_ac_c20_amp": ("ac_in_current_a", 2),
    "out_ac_l1_1_vol": ("ac_out_voltage_v", 1),
    "out_ads_vol": ("dc_anderson_out_voltage_v", 2),
    "out_ads_amp": ("dc_anderson_out_current_a", 2),
    "out_usb1_vol": ("usb_a1_out_voltage_v", 2),
    "out_usb1_amp": ("usb_a1_out_current_a", 2),
    "out_usb2_vol": ("usb_a2_out_voltage_v", 2),
    "out_usb2_amp": ("usb_a2_out_current_a", 2),
    "out_typec1_vol": ("usb_c1_out_voltage_v", 2),
    "out_typec1_amp": ("usb_c1_out_current_a", 2),
    "out_typec2_vol": ("usb_c2_out_voltage_v", 2),
    "out_typec2_amp": ("usb_c2_out_current_a", 2),
    "in_ac_5p8_vol": ("power_in_out_in_voltage_v", 1),
    "in_ac_5p8_amp": ("power_in_out_in_current_a", 2),
    "in_lv_mppt_vol": ("solar_lv_in_voltage_v", 1),
    "in_lv_mppt_amp": ("solar_lv_in_current_a", 2),
    "in_hv_mppt_vol": ("solar_hv_in_voltage_v", 1),
    "in_hv_mppt_amp": ("solar_hv_in_current_a", 2),
    "pcs_dc_temp": ("pcs_dc_temp_c", 1),
    "pcs_ac_temp": ("pcs_ac_temp_c", 1),
    "mppt_lv_temp": ("mppt_lv_temp_c", 1),
    "mppt_hv_temp": ("mppt_hv_temp_c", 1),
    "pd_temp": ("pd_temp_c", 1),
}

# AC outlets: outlet key stem -> (voltage field, current field).
_AC_OUTLET_VI: dict[str, tuple[str, str]] = {
    "ac_l1_1_out": ("out_ac_l1_1_vol", "out_ac_l1_1_amp"),
    "ac_l1_2_out": ("out_ac_l1_2_vol", "out_ac_l1_2_amp"),
    "ac_l2_1_out": ("out_ac_l2_1_vol", "out_ac_l2_1_amp"),
    "ac_l2_2_out": ("out_ac_l2_2_vol", "out_ac_l2_2_amp"),
    "ac_tt30_out": ("out_ac_tt_vol", "out_ac_tt_amp"),
    "ac_l14_out": ("out_ac_l14_vol", "out_ac_l14_amp"),
    "power_in_out_out": ("out_ac_5p8_vol", "out_ac_5p8_amp"),
}

_APP_PARA_FIELDS: dict[str, str] = {
    "chg_max_soc": "max_charge_soc",
    "dsg_min_soc": "min_discharge_soc",
    "backup_ratio": "backup_reserve_soc",
    "chg_c20_set_watts": "ac_charge_power_limit_w",
    "chg_5p8_set_watts": "power_in_out_charge_power_limit_w",
    "ac_often_open_min_soc": "ac_always_on_min_soc",
    "power_standby_mins": "device_standby_min",
    "screen_standby_sec": "screen_timeout_s",
    "dc_standby_mins": "dc_standby_min",
    "ac_standby_mins": "ac_standby_min",
}
_APP_PARA_BOOLS: dict[str, str] = {
    "energy_manage_enable": "backup_reserve_enabled",
    "ac_xboost": "xboost_enabled",
    "ac_often_open_flg": "ac_always_on_enabled",
    "solar_only_flg": "solar_only_enabled",
}

_BP_CHG_STATE = {0: "idle", 1: "discharging", 2: "charging"}
_BP_USED = {"bp_no", "bp_soc", "bp_pwr", "bp_energy", "bp_temp", "remain_time", "bp_chg_sta"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_app_show(pdata: bytes) -> dict[str, Any]:
    """Parse AppShowHeartbeatReport (2/1)."""
    return _with_defaults(decode(pdata, APP_SHOW_SCHEMA), _FLOATS_SHOW, _map_app_show)


def _map_app_show(fields: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for src, dest in _APP_SHOW_POWERS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(abs(float(fields[src])), 1)
    for src, dest in _APP_SHOW_PLAIN.items():
        if _is_number(fields.get(src)):
            out[dest] = float(fields[src])
    if _is_number(fields.get("bp_num")):
        out["battery_pack_count"] = int(fields["bp_num"])
    if _is_number(fields.get("full_combo")) and fields["full_combo"] > 0:
        out["full_capacity_wh"] = float(fields["full_combo"])
    out.update(
        raw.flatten(fields, skip={*_APP_SHOW_POWERS, *_APP_SHOW_PLAIN, "bp_num", "full_combo"})
    )
    return out


def parse_backend(pdata: bytes) -> dict[str, Any]:
    """Parse BackendRecordHeartbeatReport (2/2)."""
    return _with_defaults(decode(pdata, BACKEND_SCHEMA), _FLOATS_BACKEND, _map_backend)


def _map_backend(fields: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for src, (dest, digits) in _BACKEND_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), digits)
    used = set(_BACKEND_FIELDS)
    for stem, (vol, amp) in _AC_OUTLET_VI.items():
        if _is_number(fields.get(vol)):
            out[f"{stem}_voltage_v"] = round(float(fields[vol]), 1)
        if _is_number(fields.get(amp)):
            out[f"{stem}_current_a"] = round(float(fields[amp]), 2)
        used |= {vol, amp}
    for src, dest in (("ac_in_freq", "ac_in_freq_hz"), ("ac_out_freq", "ac_out_freq_hz")):
        used.add(src)
        if _is_number(fields.get(src)) and fields[src] > 0:
            out[dest] = float(fields[src])
    if _is_number(fields.get("fan_state")):
        out["fan_level"] = float(fields["fan_state"])
        used.add("fan_state")
    out.update(raw.flatten(fields, skip=used))
    return out


def parse_app_para(pdata: bytes) -> dict[str, Any]:
    """Parse AppParaHeartbeatReport (2/3)."""
    fields = decode(pdata, APP_PARA_SCHEMA)
    out: dict[str, Any] = {}
    for src, dest in _APP_PARA_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = float(fields[src])
    for src, dest in _APP_PARA_BOOLS.items():
        if src in fields:
            out[dest] = bool(fields[src])
    out.update(raw.flatten(fields, skip={*_APP_PARA_FIELDS, *_APP_PARA_BOOLS}))
    return out


def parse_bp_info(pdata: bytes) -> dict[str, Any]:
    """Parse BPInfoReport (2/4): one set of keys per battery pack."""
    fields = decode(pdata, BP_INFO_REPORT_SCHEMA)
    out: dict[str, Any] = {}
    for item in fields.get("bp_info", []):
        number = item.get("bp_no")
        if not isinstance(number, int) or not 1 <= number <= 5:
            continue
        prefix = f"pack{number}_"
        if _is_number(item.get("bp_soc")):
            out[f"{prefix}soc"] = float(item["bp_soc"])
        if _is_number(item.get("bp_pwr")):
            out[f"{prefix}power_w"] = round(float(item["bp_pwr"]), 1)
        if _is_number(item.get("bp_energy")):
            out[f"{prefix}remain_energy_wh"] = round(float(item["bp_energy"]), 1)
        if _is_number(item.get("bp_temp")):
            out[f"{prefix}temp_c"] = float(item["bp_temp"])
        if _is_number(item.get("remain_time")):
            out[f"{prefix}remaining_time_min"] = float(item["remain_time"])
        state = _BP_CHG_STATE.get(item.get("bp_chg_sta", 0))
        if state is not None:
            out[f"{prefix}chg_dsg_state"] = state
        out.update(raw.flatten(item, skip=_BP_USED, prefix=prefix))
    return out


def parse_display(pdata: bytes) -> dict[str, Any]:
    """Parse the DisplayPropertyUpload (254/21) the DPU also sends."""
    fields = decode(pdata, DISPLAY_SCHEMA)
    out: dict[str, Any] = {}
    named = {
        "cms_batt_soc": "soc",
        "cms_max_chg_soc": "max_charge_soc",
        "cms_min_dsg_soc": "min_discharge_soc",
        "backup_reverse_soc": "backup_reserve_soc",
        "cms_batt_pow_in_max": "battery_charge_power_max_w",
        "cms_batt_pow_out_max": "battery_discharge_power_max_w",
        "cms_batt_full_energy": "full_capacity_wh",
    }
    for src, dest in named.items():
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), 1)
    out.update(raw.flatten(fields, skip=named))
    return out


def parse_frame(cmd_func: int, cmd_id: int, pdata: bytes) -> dict[str, Any] | None:
    """Return parsed values, or None when the frame is not one we read."""
    if cmd_func == 2:
        if cmd_id == 1:
            return parse_app_show(pdata)
        if cmd_id == 2:
            return parse_backend(pdata)
        if cmd_id == 3:
            return parse_app_para(pdata)
        if cmd_id == 4:
            return parse_bp_info(pdata)
        return None
    if cmd_func == 254 and cmd_id == 21:
        return parse_display(pdata)
    return None
