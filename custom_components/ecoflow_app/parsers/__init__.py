"""Turn raw MQTT payloads into canonical sensor values.

Everything in this package is pure Python and independent of Home Assistant,
so it can be unit-tested on recorded frames.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any

from ..models import DIALECT_DPU, DIALECT_GEN3, DIALECT_JSON, DeviceModel
from ..proto import DecodeError, decode_frames, field_numbers
from . import dpu, gen3, json_gen


@dataclass
class ParseResult:
    """What one MQTT message contained."""

    values: dict[str, Any] = field(default_factory=dict)
    # Values to use only for keys the device has never reported (a port
    # that is idle since startup, so absent from incremental frames).
    defaults: dict[str, Any] = field(default_factory=dict)
    # Detected dialect from the frame itself ("" if nothing was recognised).
    dialect: str = ""
    # (cmd_func, cmd_id) -> field numbers, for frames nobody parses yet.
    unknown_frames: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    # Device says it is online/offline (latestQuotas reply), None if unknown.
    online: bool | None = None


def parse_payload(payload: bytes, model: DeviceModel) -> ParseResult:
    """Parse one MQTT payload published for a device."""
    result = ParseResult()
    stripped = payload.lstrip()
    if stripped[:1] == b"{":
        try:
            message = json.loads(stripped)
        except (ValueError, UnicodeDecodeError):
            return result
        if not isinstance(message, dict):
            return result
        data = message.get("data")
        if isinstance(data, dict) and "online" in data:
            try:
                result.online = int(data["online"]) == 1
            except (TypeError, ValueError):
                pass
        quota = json_gen.flatten(message)
        if quota:
            result.dialect = DIALECT_JSON
            result.values = json_gen.parse(quota, solar_voltage_divisor=model.solar_voltage_divisor)
        return result

    try:
        frames = decode_frames(payload)
    except DecodeError:
        return result

    for frame in frames:
        parsed: dict[str, Any] | None = None
        try:
            # cmd_func pairs are not unique across product families, so the
            # model decides; an unrecognised model is routed by cmd_func.
            if model.dialect == DIALECT_DPU or (not model.dialect and frame.cmd_func == 2):
                parsed = dpu.parse_frame(frame.cmd_func, frame.cmd_id, frame.pdata)
                if parsed is not None:
                    result.dialect = DIALECT_DPU
            else:
                parsed = gen3.parse_frame(frame.cmd_func, frame.cmd_id, frame.pdata)
                if parsed is not None:
                    result.dialect = DIALECT_GEN3
        except DecodeError:
            parsed = None
        if parsed is None:
            if frame.pdata:
                result.unknown_frames[(frame.cmd_func, frame.cmd_id)] = field_numbers(frame.pdata)
            continue
        result.defaults.update(parsed.pop(dpu.DEFAULTS_KEY, {}))
        result.values.update(parsed)
    return result


__all__ = ["ParseResult", "parse_payload", "DIALECT_DPU", "DIALECT_GEN3", "DIALECT_JSON"]
