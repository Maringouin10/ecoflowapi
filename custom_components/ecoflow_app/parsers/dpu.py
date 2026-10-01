"""Delta Pro Ultra - protobuf telemetry.

The Delta Pro Ultra (inverter + stacked battery packs) reports on
``cmd_func=2``:

* ``cmd_id=1`` AppShowHeartbeatReport       - SoC, port powers, remaining time
* ``cmd_id=2`` BackendRecordHeartbeatReport - voltages, currents, temperatures
* ``cmd_id=3`` AppParaHeartbeatReport       - settings (SoC limits, backup)
* ``cmd_id=4`` BPInfoReport                 - one entry per battery pack

It also sends a ``254/21`` DisplayPropertyUpload with the combined SoC and
limits, using the same numbering as the Delta 3 generation.

Field numbers from foxthefox/ioBroker.ecoflow-mqtt (MIT).
"""

from __future__ import annotations

from typing import Any

from ..proto import FLOAT, INT, MSG, SINT, STRING, Field, decode

APP_SHOW_SCHEMA: dict[int, Field] = {
    10: Field("wireless_4g_on", SINT),
    16: Field("sim_iccid", STRING),
    21: Field("soc"),
    22: Field("bp_num"),
    26: Field("remain_time"),
    27: Field("sys_err_code"),
    28: Field("full_combo"),
    29: Field("remain_combo"),
    41: Field("watts_in_sum", FLOAT),
    42: Field("watts_out_sum", FLOAT),
    43: Field("out_usb1_pwr", FLOAT),
    44: Field("out_usb2_pwr", FLOAT),
    45: Field("out_typec1_pwr", FLOAT),
    46: Field("out_typec2_pwr", FLOAT),
    47: Field("out_ads_pwr", FLOAT),
    48: Field("out_ac_l1_1_pwr", FLOAT),
    49: Field("out_ac_l1_2_pwr", FLOAT),
    50: Field("out_ac_l2_1_pwr", FLOAT),
    51: Field("out_ac_l2_2_pwr", FLOAT),
    52: Field("out_ac_tt_pwr", FLOAT),
    53: Field("out_ac_l14_pwr", FLOAT),
    54: Field("out_ac_5p8_pwr", FLOAT),
    55: Field("in_ac_5p8_pwr", FLOAT),
    56: Field("in_ac_c20_pwr", FLOAT),
    57: Field("in_lv_mppt_pwr", FLOAT),
    58: Field("in_hv_mppt_pwr", FLOAT),
    59: Field("out_pr_pwr", FLOAT),
}

BACKEND_SCHEMA: dict[int, Field] = {
    43: Field("ac_in_freq"),
    48: Field("ac_out_freq"),
    61: Field("bat_vol", FLOAT),
    62: Field("bat_amp", FLOAT),
    63: Field("bms_input_watts", FLOAT),
    64: Field("bms_output_watts", FLOAT),
    75: Field("out_ac_l1_1_vol", FLOAT),
    76: Field("out_ac_l1_1_amp", FLOAT),
    89: Field("in_ac_5p8_vol", FLOAT),
    90: Field("in_ac_5p8_amp", FLOAT),
    91: Field("in_ac_c20_vol", FLOAT),
    92: Field("in_ac_c20_amp", FLOAT),
    93: Field("in_lv_mppt_vol", FLOAT),
    94: Field("in_lv_mppt_amp", FLOAT),
    95: Field("in_hv_mppt_vol", FLOAT),
    96: Field("in_hv_mppt_amp", FLOAT),
    97: Field("pcs_dc_temp", FLOAT),
    98: Field("pcs_ac_temp", FLOAT),
    99: Field("mppt_lv_temp", FLOAT),
    100: Field("mppt_hv_temp", FLOAT),
    101: Field("pd_temp", INT),
}

APP_PARA_SCHEMA: dict[int, Field] = {
    3: Field("sys_backup_soc"),
    4: Field("energy_manage_enable"),
    5: Field("backup_ratio"),
    6: Field("ac_xboost"),
    9: Field("chg_max_soc"),
    10: Field("dsg_min_soc"),
    13: Field("chg_5p8_set_watts"),
    14: Field("chg_c20_set_watts"),
}

_BP_INFO = {
    1: Field("bp_no"),
    2: Field("bp_chg_sta"),
    3: Field("bp_soc"),
    4: Field("bp_pwr", FLOAT),
    5: Field("bp_energy", FLOAT),
    7: Field("remain_time"),
    10: Field("bp_err_code"),
    11: Field("bp_temp", INT),
}
BP_INFO_REPORT_SCHEMA: dict[int, Field] = {
    1: Field("bp_info", MSG, _BP_INFO, repeated=True),
}

DISPLAY_SCHEMA: dict[int, Field] = {
    262: Field("cms_batt_soc", FLOAT),
    270: Field("cms_max_chg_soc"),
    271: Field("cms_min_dsg_soc"),
    461: Field("backup_reverse_soc"),
}

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
}

# AC outlets that add up to the total AC output.
_AC_OUTLETS = (
    "out_ac_l1_1_pwr",
    "out_ac_l1_2_pwr",
    "out_ac_l2_1_pwr",
    "out_ac_l2_2_pwr",
    "out_ac_tt_pwr",
    "out_ac_l14_pwr",
)

_BACKEND_FIELDS: dict[str, tuple[str, int]] = {
    "bat_vol": ("battery_voltage_v", 2),
    "bat_amp": ("battery_current_a", 2),
    "in_ac_c20_vol": ("ac_in_voltage_v", 1),
    "in_ac_c20_amp": ("ac_in_current_a", 2),
    "out_ac_l1_1_vol": ("ac_out_voltage_v", 1),
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

_BP_CHG_STATE = {0: "idle", 1: "discharging", 2: "charging"}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def parse_app_show(pdata: bytes) -> dict[str, Any]:
    """Parse AppShowHeartbeatReport (2/1)."""
    fields = decode(pdata, APP_SHOW_SCHEMA)
    out: dict[str, Any] = {}
    for src, dest in _APP_SHOW_POWERS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(abs(float(fields[src])), 1)
    if _is_number(fields.get("watts_out_sum")):
        # The heartbeat is a full snapshot (it always carries the totals); an
        # outlet that is missing from it is an outlet at 0 W.
        out["ac_out_power_w"] = round(
            sum(abs(float(fields[k])) for k in _AC_OUTLETS if _is_number(fields.get(k))),
            1,
        )
    if _is_number(fields.get("soc")):
        out["soc"] = float(fields["soc"])
    if _is_number(fields.get("bp_num")):
        out["battery_pack_count"] = int(fields["bp_num"])
    if _is_number(fields.get("remain_time")):
        out["remaining_time_min"] = float(fields["remain_time"])
    if _is_number(fields.get("full_combo")) and fields["full_combo"] > 0:
        out["full_capacity_wh"] = float(fields["full_combo"])
    if _is_number(fields.get("remain_combo")):
        out["remain_capacity_wh"] = float(fields["remain_combo"])
    if _is_number(fields.get("sys_err_code")):
        out["system_error_code"] = int(fields["sys_err_code"])
    return out


def parse_backend(pdata: bytes) -> dict[str, Any]:
    """Parse BackendRecordHeartbeatReport (2/2)."""
    fields = decode(pdata, BACKEND_SCHEMA)
    out: dict[str, Any] = {}
    for src, (dest, digits) in _BACKEND_FIELDS.items():
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), digits)
    for src, dest in (("ac_in_freq", "ac_in_freq_hz"), ("ac_out_freq", "ac_out_freq_hz")):
        if _is_number(fields.get(src)) and fields[src] > 0:
            out[dest] = float(fields[src])
    return out


def parse_app_para(pdata: bytes) -> dict[str, Any]:
    """Parse AppParaHeartbeatReport (2/3)."""
    fields = decode(pdata, APP_PARA_SCHEMA)
    out: dict[str, Any] = {}
    for src, dest in (
        ("chg_max_soc", "max_charge_soc"),
        ("dsg_min_soc", "min_discharge_soc"),
        ("backup_ratio", "backup_reserve_soc"),
        ("chg_c20_set_watts", "ac_charge_power_limit_w"),
    ):
        if _is_number(fields.get(src)):
            out[dest] = float(fields[src])
    if "energy_manage_enable" in fields:
        out["backup_reserve_enabled"] = bool(fields["energy_manage_enable"])
    if "ac_xboost" in fields:
        out["xboost_enabled"] = bool(fields["ac_xboost"])
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
    return out


def parse_display(pdata: bytes) -> dict[str, Any]:
    """Parse the DisplayPropertyUpload (254/21) the DPU also sends."""
    fields = decode(pdata, DISPLAY_SCHEMA)
    out: dict[str, Any] = {}
    for src, dest in (
        ("cms_batt_soc", "soc"),
        ("cms_max_chg_soc", "max_charge_soc"),
        ("cms_min_dsg_soc", "min_discharge_soc"),
        ("backup_reverse_soc", "backup_reserve_soc"),
    ):
        if _is_number(fields.get(src)):
            out[dest] = round(float(fields[src]), 1)
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
