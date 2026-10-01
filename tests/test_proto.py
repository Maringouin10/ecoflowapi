"""Protobuf reader and envelope."""

from __future__ import annotations

import pytest

from custom_components.ecoflow_app.proto import (
    FLOAT,
    INT,
    MSG,
    SINT,
    DecodeError,
    Field,
    build_get_all_request,
    decode,
    decode_frames,
)

from .helpers import f32, frame, msg, u


def test_scalar_kinds() -> None:
    schema = {
        1: Field("a"),
        2: Field("b", INT),
        3: Field("c", SINT),
        4: Field("d", FLOAT),
    }
    buf = u(1, 300) + u(2, (1 << 64) - 5) + u(3, 9) + f32(4, 1.5) + u(99, 7)
    assert decode(buf, schema) == {"a": 300, "b": -5, "c": -5, "d": 1.5}


def test_nested_and_repeated() -> None:
    item = {1: Field("x"), 2: Field("y")}
    schema = {1: Field("items", MSG, item, repeated=True), 2: Field("cells", repeated=True)}
    packed = bytes([3, 4, 5])
    buf = msg(1, u(1, 1) + u(2, 2)) + msg(1, u(1, 3)) + msg(2, packed)
    assert decode(buf, schema) == {
        "items": [{"x": 1, "y": 2}, {"x": 3}],
        "cells": [3, 4, 5],
    }


def test_truncated_input_raises() -> None:
    with pytest.raises(DecodeError):
        decode(bytes([0x08]), {1: Field("a")})


def test_frames_are_split_and_xor_decoded() -> None:
    payload = frame(254, 21, u(1, 42), seq=0x1234, xor=True) + frame(32, 2, u(1, 7))
    frames = decode_frames(payload)
    assert [(f.cmd_func, f.cmd_id) for f in frames] == [(254, 21), (32, 2)]
    assert decode(frames[0].pdata, {1: Field("a")}) == {"a": 42}
    assert decode(frames[1].pdata, {1: Field("a")}) == {"a": 7}


def test_frames_from_the_app_are_not_xor_decoded() -> None:
    pdata = u(1, 42)
    header = msg(1, pdata) + u(2, 32) + u(6, 1) + u(8, 1) + u(9, 1) + u(14, 5)
    (only,) = decode_frames(msg(1, header))
    assert only.pdata == pdata


def test_not_a_frame() -> None:
    with pytest.raises(DecodeError):
        decode_frames(b"")


def test_get_all_request_shape() -> None:
    (request,) = decode_frames(build_get_all_request(123))
    assert request.src == 32
    assert request.dest == 32
    assert request.seq == 123
    assert request.extra["from"] == "app"
