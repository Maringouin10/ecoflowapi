"""Build protobuf frames for tests."""

from __future__ import annotations

import struct

from custom_components.ecoflow_app.proto import (
    _encode_varint,
    encode_bytes_field,
    encode_varint_field,
)


def f32(number: int, value: float) -> bytes:
    """Encode a float field."""
    return _encode_varint((number << 3) | 5) + struct.pack("<f", value)


def u(number: int, value: int) -> bytes:
    """Encode a varint field."""
    return encode_varint_field(number, value)


def msg(number: int, body: bytes) -> bytes:
    """Encode a nested message / bytes field."""
    return encode_bytes_field(number, body)


def frame(cmd_func: int, cmd_id: int, pdata: bytes, *, seq: int = 1, xor: bool = False) -> bytes:
    """Wrap pdata in an EcoFlow HeaderMessage."""
    if xor:
        pdata = bytes(b ^ (seq & 0xFF) for b in pdata)
    header = (
        msg(1, pdata)
        + u(2, 2)
        + u(3, 32)
        + (u(6, 1) if xor else b"")
        + u(8, cmd_func)
        + u(9, cmd_id)
        + u(14, seq)
    )
    return msg(1, header)
