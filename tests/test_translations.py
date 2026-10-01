"""Every entity has a name in English and French."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("homeassistant")

from custom_components.ecoflow_app.descriptions import (  # noqa: E402
    BINARY_SENSORS,
    ONLINE_DESCRIPTION,
    SENSORS,
)

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "ecoflow_app"


@pytest.mark.parametrize("path", ["strings.json", "translations/en.json", "translations/fr.json"])
def test_every_translation_key_is_present(path: str) -> None:
    data = json.loads((COMPONENT / path).read_text(encoding="utf-8"))
    sensors = data["entity"]["sensor"]
    binaries = data["entity"]["binary_sensor"]
    for description in SENSORS.values():
        assert description.translation_key in sensors, description.translation_key
        if description.options:
            assert set(description.options) <= set(sensors[description.translation_key]["state"])
        if description.index is not None:
            assert "{index}" in sensors[description.translation_key]["name"]
    for description in [*BINARY_SENSORS.values(), ONLINE_DESCRIPTION]:
        assert description.translation_key in binaries, description.translation_key


def test_strings_matches_english() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    english = json.loads((COMPONENT / "translations/en.json").read_text(encoding="utf-8"))
    assert strings == english
