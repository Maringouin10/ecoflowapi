"""Delta 3 / River 3 generation, on real captures."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.ecoflow_app.models import model_by_key
from custom_components.ecoflow_app.parsers import parse_payload

from .helpers import f32, frame, msg, u

FIXTURES = Path(__file__).parent / "fixtures"
DELTA3 = model_by_key("delta_3")


def test_xor_encoded_status_frame_from_a_delta_3() -> None:
    data = json.loads((FIXTURES / "p231_status_frame.json").read_text())
    result = parse_payload(bytes.fromhex(data["frame_hex"]), DELTA3)
    assert result.dialect == "gen3"
    values = result.values
    assert values["soc"] == 100.0
    assert values["ac_charge_power_limit_w"] == 1600
    assert values["max_charge_soc"] == 100
    assert values["chg_dsg_state"] == "idle"
    assert values["ac_out_freq_hz"] == 50


def test_delta_3_plus_frames() -> None:
    frames = json.loads((FIXTURES / "p351_frames_masked.json").read_text())["frames"]
    merged: dict = {}
    for item in frames:
        merged.update(parse_payload(bytes.fromhex(item["hex"]), DELTA3).values)
    assert merged["solar_in_power_w"] == 237.4
    assert merged["solar2_in_power_w"] == 246.5
    assert merged["ac_out_power_w"] == 226.0
    assert merged["chg_dsg_state"] == "charging"
    assert merged["charge_remaining_raw_min"] == 51
    assert merged["battery_voltage_v"] == 53.255
    assert merged["battery_charge_energy_lifetime_kwh"] == 11.561


def test_get_all_reply_carries_the_extra_battery() -> None:
    payload = (FIXTURES / "p351_two_packs_get_all.bin").read_bytes()
    values = parse_payload(payload, DELTA3).values
    assert values["soc"] == 52.1
    assert values["extra1_soc"] == 54.1
    assert values["extra1_in_power_w"] == 178
    assert values["extra1_cycles"] == 10
    # The built-in battery keeps its own keys.
    assert values["cycles"] == 11
    assert "design_capacity_mah" not in values or values["design_capacity_mah"] > 0


def test_river_3_lifetime_counters_and_negative_outputs() -> None:
    stats = msg(463, msg(1, u(1, 2) + u(2, 12345)) + msg(1, u(1, 7) + u(2, 6789)))
    pdata = f32(368, -150.0) + f32(262, 80.0) + u(76, 1) + stats
    values = parse_payload(frame(254, 21, pdata), model_by_key("river_3")).values
    assert values["ac_out_power_w"] == 150.0
    assert values["ac_out_enabled"] is True
    assert values["ac_out_energy_lifetime_kwh"] == 12.345
    assert values["solar_in_energy_lifetime_kwh"] == 6.789


def test_unknown_frames_are_reported() -> None:
    result = parse_payload(frame(254, 22, u(26, 1) + u(27, 2)), DELTA3)
    assert result.values == {}
    assert result.unknown_frames == {(254, 22): [26, 27]}
