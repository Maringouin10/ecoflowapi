"""Model detection."""

from __future__ import annotations

import pytest

from custom_components.ecoflow_app.models import UNKNOWN_MODEL, detect_model


@pytest.mark.parametrize(
    ("name", "sn", "expected"),
    [
        ("DELTA 2", "R331ZAB1234", "delta_2"),
        ("DELTA 2 Max", "R351ZAB1234", "delta_2"),
        ("DELTA 3 Plus", "P351ZAB1234", "delta_3"),
        ("DELTA 3 Ultra", "XXXX1234", "delta_3_ultra"),
        ("DELTA Pro Ultra", "Y711ZAB1234", "delta_pro_ultra"),
        ("RIVER 2 Pro", "R621ZAB1234", "river_2"),
        ("RIVER 3 Plus", "R631ZAB1234", "river_3"),
        ("", "R655ZAB1234", "river_3"),
        ("", "R331ZAB1234", "delta_2"),
    ],
)
def test_detect(name: str, sn: str, expected: str) -> None:
    assert detect_model(name, sn).key == expected


def test_unknown() -> None:
    assert detect_model("Smart Plug", "HW52ZAB1234") is UNKNOWN_MODEL
