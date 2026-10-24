"""Switch commands, checked against the frames the app sends."""

from __future__ import annotations

import json

import pytest

from custom_components.ecoflow_app.commands import build_switch_command, switch_keys
from custom_components.ecoflow_app.models import DIALECT_DPU, DIALECT_GEN3, DIALECT_JSON
from custom_components.ecoflow_app.proto import decode_frames


def test_gen3_ac_on_is_a_set_frame() -> None:
    payload = build_switch_command(DIALECT_GEN3, "P351ZAB0000001", "ac_out_enabled", True)
    (frame,) = decode_frames(payload)
    assert (frame.cmd_func, frame.cmd_id) == (254, 17)
    assert frame.device_sn == "P351ZAB0000001"
    assert frame.pdata == bytes([0xE0, 0x04, 1])  # field 76, value 1
    assert frame.extra["need_ack"] == 1


def test_gen3_dc_off_sets_field_18_to_zero() -> None:
    payload = build_switch_command(DIALECT_GEN3, "P351ZAB0000001", "dc12v_out_enabled", False)
    (frame,) = decode_frames(payload)
    assert frame.pdata == bytes([18 << 3, 0])


def test_json_commands() -> None:
    ac = json.loads(build_switch_command(DIALECT_JSON, "R331ZAB0000002", "ac_out_enabled", True))
    assert (ac["moduleType"], ac["operateType"]) == (5, "acOutCfg")
    assert ac["params"]["enabled"] == 1
    dc = json.loads(build_switch_command(DIALECT_JSON, "R331ZAB0000002", "dc12v_out_enabled", False))
    assert (dc["moduleType"], dc["operateType"], dc["params"]) == (5, "mpptCar", {"enabled": 0})
    usb = json.loads(build_switch_command(DIALECT_JSON, "R331ZAB0000002", "usb_out_enabled", True))
    assert (usb["moduleType"], usb["operateType"]) == (1, "dcOutCfg")


def test_unknown_combinations_are_refused() -> None:
    assert switch_keys(DIALECT_DPU) == set()
    with pytest.raises(ValueError):
        build_switch_command(DIALECT_DPU, "Y711ZAB0000009", "ac_out_enabled", True)
    with pytest.raises(ValueError):
        build_switch_command(DIALECT_GEN3, "P351ZAB0000001", "usb_out_enabled", True)
