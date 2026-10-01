"""Delta 2 / River 2 JSON telemetry."""

from __future__ import annotations

import json

from custom_components.ecoflow_app.models import model_by_key
from custom_components.ecoflow_app.parsers import parse_payload

DELTA2 = model_by_key("delta_2")
RIVER2 = model_by_key("river_2")


def _payload(params: dict, **extra) -> bytes:
    return json.dumps({"params": params, **extra}).encode()


def test_dotted_params_from_a_delta_2() -> None:
    values = parse_payload(
        _payload(
            {
                "pd.wattsInSum": 300,
                "pd.wattsOutSum": 120,
                "inv.outputWatts": 100,
                "inv.invOutVol": 230000,
                "mppt.inWatts": 280,
                "mppt.inVol": 420,
                "bms_emsStatus.lcdShowSoc": 64,
                "bms_bmsStatus.soc": 61,
                "bms_bmsStatus.vol": 51234,
                "bms_bmsStatus.temp": 27,
                "pd.chgDsgState": 2,
                "inv.cfgAcEnabled": 1,
                "pd.dcOutState": 0,
            }
        ),
        DELTA2,
    )
    v = values.values
    assert values.dialect == "json"
    assert v["input_power_w"] == 300
    assert v["ac_out_power_w"] == 100
    assert v["ac_out_voltage_v"] == 230.0
    assert v["solar_in_power_w"] == 280
    assert v["solar_in_voltage_v"] == 42.0
    assert v["soc"] == 64
    assert v["main_battery_soc"] == 61
    assert v["battery_voltage_v"] == 51.234
    assert v["chg_dsg_state"] == "charging"
    assert v["ac_out_enabled"] is True
    assert v["usb_out_enabled"] is False


def test_river_2_solar_voltage_is_millivolts() -> None:
    v = parse_payload(_payload({"mppt.inVol": 18500}), RIVER2).values
    assert v["solar_in_voltage_v"] == 18.5


def test_delta_2_extra_battery() -> None:
    v = parse_payload(
        _payload(
            {
                "bms_slave.soc": 55,
                "bms_slave.vol": 50100,
                "bms_slave.temp": 22,
                "bms_slave.cycles": 12,
                "bms_slave.inputWatts": 80,
            }
        ),
        DELTA2,
    ).values
    assert v["extra1_soc"] == 55
    assert v["extra1_voltage_v"] == 50.1
    assert v["extra1_cycles"] == 12
    assert v["extra1_in_power_w"] == 80


def test_absent_extra_battery_is_dropped() -> None:
    v = parse_payload(_payload({"bms_slave.soc": 0, "bms_slave.vol": 0}), DELTA2).values
    assert not any(key.startswith("extra1_") for key in v)


def test_type_code_messages() -> None:
    v = parse_payload(
        json.dumps({"typeCode": "invStatus", "params": {"outputWatts": 75}}).encode(), DELTA2
    ).values
    assert v == {"ac_out_power_w": 75}


def test_latest_quotas_reply() -> None:
    message = {
        "operateType": "latestQuotas",
        "data": {"online": 1, "quotaMap": {"pd.wattsOutSum": 42}},
    }
    result = parse_payload(json.dumps(message).encode(), DELTA2)
    assert result.online is True
    assert result.values == {"output_power_w": 42}


def test_garbage_is_ignored() -> None:
    assert parse_payload(b"{not json", DELTA2).values == {}
    assert parse_payload(b"\xff\xff\xff", DELTA2).values == {}
