"""Expose every decoded field that has no dedicated sensor.

Raw keys start with ``raw_`` and become diagnostic sensors named after the
field, so nothing the device reports is hidden even before it gets a proper
name, unit and translation.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

RAW_PREFIX = "raw_"
_MAX_LIST = 32
# Identifiers that must not end up in the UI / recorder.
_PRIVATE_MARKERS = ("_sn", "sn_", "iccid", "serial")


def _private(name: str) -> bool:
    lowered = name.lower()
    return lowered == "sn" or any(m in lowered for m in _PRIVATE_MARKERS)


def _scalar(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return round(value, 3)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and len(value) <= 64:
        return value
    return None


def flatten(fields: dict[str, Any], skip: Iterable[str] = (), prefix: str = "") -> dict[str, Any]:
    """Return ``raw_<prefix><name>`` for every field not in ``skip``.

    Nested messages become ``<name>_<sub>``, lists ``<name>_<n>`` (1-based).
    """
    skipped = set(skip)
    out: dict[str, Any] = {}

    def walk(name: str, value: Any) -> None:
        if _private(name):
            return
        if isinstance(value, dict):
            for sub, sub_value in value.items():
                walk(f"{name}_{sub}", sub_value)
        elif isinstance(value, list):
            for index, item in enumerate(value[:_MAX_LIST], start=1):
                walk(f"{name}_{index}", item)
        else:
            scalar = _scalar(value)
            if scalar is not None:
                out[f"{RAW_PREFIX}{prefix}{name}"] = scalar

    for name, value in fields.items():
        if name not in skipped:
            walk(name, value)
    return out
