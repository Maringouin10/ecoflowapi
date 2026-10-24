"""Commands that switch the outputs of a device on or off.

Pure Python, like the parsers. Each dialect has its own way of saying the
same thing, and the command set below is what the EcoFlow app sends:

* ``gen3`` - protobuf set frame, one numeric field per output.
* ``json`` - ``operateType`` + ``params`` message.

* ``dpu``  - protobuf set frame on ``cmd_func=2``. Only the DC output is
  known (``cmd_id=68``); the AC command has never been published.

Devices that never report the state of an output (DELTA Pro Ultra, DELTA 3
Ultra) still get the switch; it then shows the last command sent.
"""

from __future__ import annotations

from collections.abc import Callable
import json
import time
from typing import Any

from .models import DIALECT_DPU, DIALECT_GEN3, DIALECT_JSON
from .proto import build_dpu_set_request, build_set_request

# value key (the state the switch shows) -> field of the gen3 set message
_GEN3_FIELDS: dict[str, int] = {
    "ac_out_enabled": 76,  # cfg_ac_out_open
    "dc12v_out_enabled": 18,  # cfg_dc12v_out_open
}

# value key -> cmd_id of the DELTA Pro Ultra set frame
_DPU_COMMANDS: dict[str, int] = {"dc12v_out_enabled": 68}

# value key -> (moduleType, operateType, params for a given on/off value)
_JSON_COMMANDS: dict[str, tuple[int, str, Callable[[int], dict[str, Any]]]] = {
    "ac_out_enabled": (
        5,
        "acOutCfg",
        lambda on: {"enabled": on, "out_voltage": -1, "out_freq": 255, "xboost": 255},
    ),
    "dc12v_out_enabled": (5, "mpptCar", lambda on: {"enabled": on}),
    "usb_out_enabled": (1, "dcOutCfg", lambda on: {"enabled": on}),
}


def switch_keys(dialect: str) -> set[str]:
    """Value keys that can be switched on a device speaking this dialect."""
    if dialect == DIALECT_GEN3:
        return set(_GEN3_FIELDS)
    if dialect == DIALECT_JSON:
        return set(_JSON_COMMANDS)
    if dialect == DIALECT_DPU:
        return set(_DPU_COMMANDS)
    return set()


def build_switch_command(dialect: str, sn: str, key: str, on: bool) -> str | bytes:
    """Return the MQTT payload that switches ``key`` on or off."""
    value = 1 if on else 0
    stamp = int(time.time() * 1000)
    if dialect == DIALECT_GEN3 and key in _GEN3_FIELDS:
        return build_set_request(sn, _GEN3_FIELDS[key], value, stamp)
    if dialect == DIALECT_DPU and key in _DPU_COMMANDS:
        return build_dpu_set_request(sn, _DPU_COMMANDS[key], value, stamp)
    if dialect == DIALECT_JSON and key in _JSON_COMMANDS:
        module, operate, params = _JSON_COMMANDS[key]
        return json.dumps(
            {
                "from": "Android",
                "id": str(stamp),
                "version": "1.0",
                "moduleType": module,
                "operateType": operate,
                "params": params(value),
            }
        )
    raise ValueError(f"no switch command for {key} on {dialect or 'unknown'} devices")
