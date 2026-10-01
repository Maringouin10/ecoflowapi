"""Minimal schema-driven protobuf reader and the EcoFlow frame envelope.

No generated code and no ``protobuf`` dependency: a schema is a dict
``{field_number: Field}``, and fields that are not in it are skipped. That is
exactly what protobuf does with unknown fields, and it keeps the integration
working when a firmware adds new ones.

Envelope (every protobuf MQTT message from the app connection)::

    HeaderMessage { repeated Header header = 1; }
    Header { bytes pdata = 1; int32 src = 2; ... cmd_func = 8; cmd_id = 9;
             ... seq = 14; ... string device_sn = 25; }

When ``enc_type == 1`` and the frame does not come from the app
(``src != 32``), every byte of ``pdata`` is XOR-ed with the low byte of
``seq``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Any

# Field kinds
UINT = "uint"  # varint, unsigned
INT = "int"  # varint, two's complement (int32/int64)
SINT = "sint"  # varint, zig-zag (sint32/sint64)
BOOL = "bool"
FLOAT = "float"  # fixed32
DOUBLE = "double"  # fixed64
STRING = "string"
BYTES = "bytes"
MSG = "msg"


@dataclass(frozen=True)
class Field:
    """One field of a schema."""

    name: str
    kind: str = UINT
    schema: dict[int, Field] | None = None
    repeated: bool = False


@dataclass
class Frame:
    """One decoded header of an EcoFlow protobuf message."""

    cmd_func: int = 0
    cmd_id: int = 0
    src: int = 0
    dest: int = 0
    seq: int = 0
    enc_type: int = 0
    device_sn: str = ""
    pdata: bytes = b""
    extra: dict[str, Any] = field(default_factory=dict)


class DecodeError(ValueError):
    """Raised when bytes are not a well-formed protobuf message."""


def _varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        if pos >= len(buf) or shift > 63:
            raise DecodeError("truncated varint")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, pos
        shift += 7


def _signed(value: int) -> int:
    return value - (1 << 64) if value >= (1 << 63) else value


def _zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def _convert_varint(kind: str, value: int) -> Any:
    if kind == INT:
        return _signed(value)
    if kind == SINT:
        return _zigzag(value)
    if kind == BOOL:
        return bool(value)
    return value


def iter_fields(buf: bytes):
    """Yield ``(field_number, wire_type, value)`` for every field in ``buf``.

    ``value`` is an int for varint/fixed fields and bytes for
    length-delimited ones. Raises DecodeError on malformed input.
    """
    pos = 0
    end = len(buf)
    while pos < end:
        key, pos = _varint(buf, pos)
        number, wire = key >> 3, key & 0x07
        if number == 0:
            raise DecodeError("field number 0")
        if wire == 0:
            value, pos = _varint(buf, pos)
        elif wire == 1:
            if pos + 8 > end:
                raise DecodeError("truncated fixed64")
            value = int.from_bytes(buf[pos : pos + 8], "little")
            pos += 8
        elif wire == 2:
            length, pos = _varint(buf, pos)
            if pos + length > end:
                raise DecodeError("truncated length-delimited field")
            value = bytes(buf[pos : pos + length])
            pos += length
        elif wire == 5:
            if pos + 4 > end:
                raise DecodeError("truncated fixed32")
            value = int.from_bytes(buf[pos : pos + 4], "little")
            pos += 4
        else:
            raise DecodeError(f"unsupported wire type {wire}")
        yield number, wire, value


def _decode_value(spec: Field, wire: int, raw: Any) -> list[Any]:
    """Decode one wire value into a list of Python values (packed -> many)."""
    kind = spec.kind
    if wire == 0:
        return [_convert_varint(kind, raw)]
    if wire == 5:
        if kind == FLOAT:
            return [struct.unpack("<f", raw.to_bytes(4, "little"))[0]]
        return [raw]
    if wire == 1:
        if kind == DOUBLE:
            return [struct.unpack("<d", raw.to_bytes(8, "little"))[0]]
        return [raw]
    # wire == 2
    if kind == MSG:
        return [decode(raw, spec.schema or {})]
    if kind == STRING:
        return [raw.decode("utf-8", errors="replace")]
    if kind == BYTES:
        return [raw]
    # Packed repeated scalars.
    values: list[Any] = []
    if kind == FLOAT:
        for i in range(0, len(raw) - len(raw) % 4, 4):
            values.append(struct.unpack("<f", raw[i : i + 4])[0])
        return values
    if kind == DOUBLE:
        for i in range(0, len(raw) - len(raw) % 8, 8):
            values.append(struct.unpack("<d", raw[i : i + 8])[0])
        return values
    pos = 0
    while pos < len(raw):
        value, pos = _varint(raw, pos)
        values.append(_convert_varint(kind, value))
    return values


def decode(buf: bytes, schema: dict[int, Field]) -> dict[str, Any]:
    """Decode ``buf`` with ``schema``; unknown fields are ignored."""
    out: dict[str, Any] = {}
    for number, wire, raw in iter_fields(buf):
        spec = schema.get(number)
        if spec is None:
            continue
        values = _decode_value(spec, wire, raw)
        if spec.repeated:
            out.setdefault(spec.name, []).extend(values)
        elif values:
            out[spec.name] = values[-1]
    return out


def field_numbers(buf: bytes) -> list[int]:
    """Return the field numbers present in ``buf`` (for diagnostics)."""
    try:
        return sorted({number for number, _, _ in iter_fields(buf)})
    except DecodeError:
        return []


HEADER_SCHEMA: dict[int, Field] = {
    1: Field("pdata", BYTES),
    2: Field("src"),
    3: Field("dest"),
    4: Field("d_src"),
    5: Field("d_dest"),
    6: Field("enc_type"),
    7: Field("check_type"),
    8: Field("cmd_func"),
    9: Field("cmd_id"),
    10: Field("data_len"),
    11: Field("need_ack"),
    12: Field("is_ack"),
    14: Field("seq"),
    15: Field("product_id"),
    16: Field("version"),
    17: Field("payload_ver"),
    23: Field("from", STRING),
    24: Field("module_sn", STRING),
    25: Field("device_sn", STRING),
}


def decode_frames(payload: bytes) -> list[Frame]:
    """Split an MQTT protobuf payload into frames with plain ``pdata``.

    Raises DecodeError when the payload is not a HeaderMessage.
    """
    frames: list[Frame] = []
    for number, wire, raw in iter_fields(payload):
        if number != 1 or wire != 2:
            continue
        header = decode(raw, HEADER_SCHEMA)
        pdata = header.pop("pdata", b"")
        seq = int(header.get("seq", 0))
        enc_type = int(header.get("enc_type", 0))
        src = int(header.get("src", 0))
        if enc_type == 1 and src != 32 and pdata:
            key = seq & 0xFF
            pdata = bytes(b ^ key for b in pdata)
        frames.append(
            Frame(
                cmd_func=int(header.get("cmd_func", 0)),
                cmd_id=int(header.get("cmd_id", 0)),
                src=src,
                dest=int(header.get("dest", 0)),
                seq=seq,
                enc_type=enc_type,
                device_sn=str(header.get("device_sn", "")),
                pdata=pdata,
                extra=header,
            )
        )
    if not frames:
        raise DecodeError("no header in payload")
    return frames


# --- encoding (requests only) ----------------------------------------------


def _encode_varint(value: int) -> bytes:
    if value < 0:
        value += 1 << 64
    out = bytearray()
    while value > 0x7F:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def encode_varint_field(number: int, value: int) -> bytes:
    """Encode a varint field."""
    return _encode_varint(number << 3) + _encode_varint(value)


def encode_bytes_field(number: int, data: bytes) -> bytes:
    """Encode a length-delimited field."""
    return _encode_varint((number << 3) | 2) + _encode_varint(len(data)) + data


def build_get_all_request(seq: int) -> bytes:
    """Ask a protobuf device for a full state dump.

    Same frame the EcoFlow web portal sends (header with src/dest = 32 and no
    command); the answer arrives on ``.../thing/property/get_reply``.
    """
    header = (
        encode_varint_field(2, 32)
        + encode_varint_field(3, 32)
        + encode_varint_field(14, seq & 0x7FFFFFFF)
        + encode_bytes_field(23, b"app")
    )
    return encode_bytes_field(1, header)
