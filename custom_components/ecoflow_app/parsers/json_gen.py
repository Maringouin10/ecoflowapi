"""Delta 2 / River 2 generation - JSON telemetry.

On the app connection these devices publish JSON on
``/app/device/property/{sn}``::

    {"params": {"pd.soc": 85, "inv.outputWatts": 120, ...}, ...}

and answer a ``latestQuotas`` request on ``.../get_reply`` with the same keys
under ``data.quotaMap``. Some firmware sends one module per message instead,
``{"typeCode": "pdStatus", "params": {"soc": 85}}``; :func:`flatten` turns
that into the dotted form so a single field map covers both.

Field names and units cross-checked against shuette42/ecoflow-energy-ha
(MIT) and tolwi/hassio-ecoflow-cloud.
"""

from __future__ import annotations

from typing import Any

from . import raw

# typeCode -> dotted module prefix used by the app's quota map.
_TYPECODE_PREFIX: dict[str, str] = {
    "pdStatus": "pd",
    "invStatus": "inv",
    "mpptStatus": "mppt",
    "bmsStatus": "bms_bmsStatus",
    "emsStatus": "bms_emsStatus",
    "bmsSlaveStatus": "bms_slave",
    "bmsSlaveStatus_1": "bms_slave_bmsSlaveStatus_1",
    "bmsSlaveStatus_2": "bms_slave_bmsSlaveStatus_2",
}

# Dotted key -> (canonical key, divisor). divisor None = pass through.
_FIELDS: dict[str, tuple[str, float | None]] = {
    # pd - power distribution
    "pd.wattsInSum": ("input_power_w", None),
    "pd.wattsOutSum": ("output_power_w", None),
    "pd.remainTime": ("remaining_time_min", None),
    "pd.usb1Watts": ("usb_a1_out_power_w", None),
    "pd.usb2Watts": ("usb_a2_out_power_w", None),
    "pd.qcUsb1Watts": ("usb_qc1_out_power_w", None),
    "pd.qcUsb2Watts": ("usb_qc2_out_power_w", None),
    "pd.typec1Watts": ("usb_c1_out_power_w", None),
    "pd.typec2Watts": ("usb_c2_out_power_w", None),
    "pd.carWatts": ("dc12v_out_power_w", None),
    "pd.dcOutState": ("usb_out_enabled", None),
    "pd.carState": ("dc12v_out_enabled", None),
    "pd.bpPowerSoc": ("backup_reserve_soc", None),
    "pd.chgDsgState": ("chg_dsg_state", None),
    "pd.errCode": ("pd_error_code", None),
    # inv - inverter
    "inv.inputWatts": ("ac_in_power_w", None),
    "inv.outputWatts": ("ac_out_power_w", None),
    "inv.acInVol": ("ac_in_voltage_v", 1000.0),
    "inv.acInAmp": ("ac_in_current_a", 1000.0),
    "inv.acInFreq": ("ac_in_freq_hz", None),
    "inv.invOutVol": ("ac_out_voltage_v", 1000.0),
    "inv.invOutAmp": ("ac_out_current_a", 1000.0),
    "inv.invOutFreq": ("ac_out_freq_hz", None),
    "inv.outTemp": ("inverter_temp_c", None),
    "inv.cfgAcEnabled": ("ac_out_enabled", None),
    "inv.cfgAcXboost": ("xboost_enabled", None),
    "inv.errCode": ("inverter_error_code", None),
    # mppt - solar / DC
    "mppt.inWatts": ("solar_in_power_w", None),
    "mppt.inAmp": ("solar_in_current_a", 1000.0),
    "mppt.mpptTemp": ("mppt_temp_c", None),
    "mppt.cfgAcEnabled": ("ac_out_enabled", None),
    "mppt.cfgAcXboost": ("xboost_enabled", None),
    "mppt.cfgChgWatts": ("ac_charge_power_limit_w", None),
    "mppt.carState": ("dc12v_out_enabled", None),
    "mppt.faultCode": ("mppt_error_code", None),
    # bms - main battery
    "bms_bmsStatus.soc": ("main_battery_soc", None),
    "bms_bmsStatus.f32ShowSoc": ("main_battery_soc", None),
    "bms_bmsStatus.soh": ("soh", None),
    "bms_bmsStatus.cycles": ("cycles", None),
    "bms_bmsStatus.temp": ("battery_temp_c", None),
    "bms_bmsStatus.vol": ("battery_voltage_v", 1000.0),
    "bms_bmsStatus.amp": ("battery_current_a", 1000.0),
    "bms_bmsStatus.minCellTemp": ("min_cell_temp_c", None),
    "bms_bmsStatus.maxCellTemp": ("max_cell_temp_c", None),
    "bms_bmsStatus.minCellVol": ("min_cell_voltage_v", 1000.0),
    "bms_bmsStatus.maxCellVol": ("max_cell_voltage_v", 1000.0),
    "bms_bmsStatus.maxMosTemp": ("max_mos_temp_c", None),
    "bms_bmsStatus.remainCap": ("remain_capacity_mah", None),
    "bms_bmsStatus.fullCap": ("full_capacity_mah", None),
    "bms_bmsStatus.designCap": ("design_capacity_mah", None),
    "bms_bmsStatus.errCode": ("bms_error_code", None),
    # ems - energy management (combined view incl. extra batteries)
    "bms_emsStatus.lcdShowSoc": ("soc", None),
    "bms_emsStatus.f32LcdShowSoc": ("soc", None),
    "bms_emsStatus.chgRemainTime": ("charge_remaining_raw_min", None),
    "bms_emsStatus.dsgRemainTime": ("discharge_remaining_raw_min", None),
    "bms_emsStatus.maxChargeSoc": ("max_charge_soc", None),
    "bms_emsStatus.minDsgSoc": ("min_discharge_soc", None),
    "bms_emsStatus.chgState": ("ems_charge_state", None),
    "bms_emsStatus.fanLevel": ("fan_level", None),
}

# Extra battery modules: dotted prefix -> extra battery index.
_SLAVE_PREFIXES: dict[str, int] = {
    "bms_slave": 1,
    "bms_slave_bmsSlaveStatus_1": 1,
    "bms_slave_bmsSlaveStatus_2": 2,
}

_SLAVE_FIELDS: dict[str, tuple[str, float | None]] = {
    "soc": ("soc", None),
    "f32ShowSoc": ("soc", None),
    "soh": ("soh", None),
    "cycles": ("cycles", None),
    "temp": ("temp_c", None),
    "vol": ("voltage_v", 1000.0),
    "amp": ("current_a", 1000.0),
    "inputWatts": ("in_power_w", None),
    "outputWatts": ("out_power_w", None),
    "remainCap": ("remain_capacity_mah", None),
    "fullCap": ("full_capacity_mah", None),
    "designCap": ("design_capacity_mah", None),
    "maxCellTemp": ("max_cell_temp_c", None),
    "minCellTemp": ("min_cell_temp_c", None),
    "maxCellVol": ("max_cell_voltage_v", 1000.0),
    "minCellVol": ("min_cell_voltage_v", 1000.0),
    "errCode": ("error_code", None),
}

_CHG_DSG_STATE = {0: "idle", 1: "discharging", 2: "charging"}

# Booleans reported as 0/1 integers.
_BOOL_KEYS = {
    "usb_out_enabled",
    "dc12v_out_enabled",
    "ac_out_enabled",
    "xboost_enabled",
}


def flatten(message: dict[str, Any]) -> dict[str, Any]:
    """Return the dotted ``module.field`` map carried by one JSON message."""
    # latestQuotas reply: {"operateType": "latestQuotas", "data": {"quotaMap": {...}}}
    data = message.get("data")
    if isinstance(data, dict) and isinstance(data.get("quotaMap"), dict):
        return dict(data["quotaMap"])

    params = message.get("params")
    if not isinstance(params, dict):
        params = message.get("param")
    if not isinstance(params, dict):
        return {}

    type_code = message.get("typeCode")
    if isinstance(type_code, str) and type_code:
        prefix = _TYPECODE_PREFIX.get(type_code)
        if prefix is None:
            return {}
        return {f"{prefix}.{k}": v for k, v in params.items() if "." not in k}
    return dict(params)


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def parse(quota: dict[str, Any], *, solar_voltage_divisor: float = 10.0) -> dict[str, Any]:
    """Map a dotted quota map onto canonical sensor keys."""
    out: dict[str, Any] = {}
    unmapped: dict[str, Any] = {}
    for key, raw_value in quota.items():
        value = _number(raw_value)
        if value is None:
            unmapped[key.replace(".", "_")] = raw_value
            continue

        if key == "mppt.inVol":
            out["solar_in_voltage_v"] = value / solar_voltage_divisor
            continue

        mapped = _FIELDS.get(key)
        if mapped is not None:
            dest, divisor = mapped
            out[dest] = value / divisor if divisor else value
            continue

        prefix, _, field = key.rpartition(".")
        index = _SLAVE_PREFIXES.get(prefix)
        if index is not None and field in _SLAVE_FIELDS:
            dest, divisor = _SLAVE_FIELDS[field]
            out[f"extra{index}_{dest}"] = value / divisor if divisor else value
            continue
        unmapped[key.replace(".", "_")] = raw_value

    if "chg_dsg_state" in out:
        state = _CHG_DSG_STATE.get(int(out["chg_dsg_state"]))
        if state is None:
            del out["chg_dsg_state"]
        else:
            out["chg_dsg_state"] = state
    # The EMS charge state uses the same 0/1/2 values but is not always the
    # same as the PD one; keep it only as a fallback.
    ems_state = out.pop("ems_charge_state", None)
    if "chg_dsg_state" not in out and ems_state is not None:
        state = _CHG_DSG_STATE.get(int(ems_state))
        if state is not None:
            out["chg_dsg_state"] = state

    for key in _BOOL_KEYS & out.keys():
        out[key] = bool(out[key])

    # An extra battery that is not plugged in reports zeros; a SoC of 0 with
    # no voltage is "absent", not "empty".
    for index in (1, 2):
        if out.get(f"extra{index}_voltage_v") == 0 and not out.get(f"extra{index}_soc"):
            for key in [k for k in out if k.startswith(f"extra{index}_")]:
                del out[key]
            for prefix, slave_index in _SLAVE_PREFIXES.items():
                if slave_index == index:
                    for key in [k for k in unmapped if k.startswith(f"{prefix}_")]:
                        del unmapped[key]

    out.update(raw.flatten(unmapped))
    return out
