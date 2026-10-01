"""Raw value flattening."""

from __future__ import annotations

from custom_components.ecoflow_app.parsers.raw import flatten


def test_flatten() -> None:
    fields = {
        "a": 1,
        "b": True,
        "c": 1.23456,
        "nested": {"x": 2, "items": [{"y": 3}]},
        "cells": [1, 2],
        "bms_sn": "SECRET",
        "sim_iccid": "SECRET",
        "used": 9,
        "blob": b"\x00",
    }
    assert flatten(fields, skip={"used"}, prefix="extra1_") == {
        "raw_extra1_a": 1,
        "raw_extra1_b": 1,
        "raw_extra1_c": 1.235,
        "raw_extra1_nested_x": 2,
        "raw_extra1_nested_items_1_y": 3,
        "raw_extra1_cells_1": 1,
        "raw_extra1_cells_2": 2,
    }
