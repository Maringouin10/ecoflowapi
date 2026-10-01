"""Config flow and end-to-end behaviour inside Home Assistant."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries  # noqa: E402
from homeassistant.core import HomeAssistant  # noqa: E402
from homeassistant.data_entry_flow import FlowResultType  # noqa: E402
from pytest_homeassistant_custom_component.common import MockConfigEntry  # noqa: E402

from custom_components.ecoflow_app.api import EcoFlowAuthError  # noqa: E402
from custom_components.ecoflow_app.const import DOMAIN  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
API = "custom_components.ecoflow_app.api.EcoFlowAppApi"

CLOUD_DEVICES = [
    {"sn": "P351ZAB0000001", "name": "Garage", "product_name": "DELTA 3 Plus", "online": 1},
    {"sn": "R331ZAB0000002", "name": "Van", "product_name": "DELTA 2", "online": 1},
    {"sn": "HW52ZAB0000003", "name": "Plug", "product_name": "Smart Plug", "online": 1},
]


@pytest.fixture(autouse=True)
def _custom(enable_custom_integrations: Any) -> None:
    """Allow loading the custom integration."""


async def _login(self) -> None:
    self.token = "token"
    self.user_id = "1234"


async def test_user_flow_selects_supported_devices(hass: HomeAssistant) -> None:
    with (
        patch(f"{API}.login", _login),
        patch(f"{API}.get_devices", return_value=CLOUD_DEVICES),
        patch("custom_components.ecoflow_app.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "me@example.com", "password": "pw"}
        )
        assert result["step_id"] == "devices"
        schema = result["data_schema"].schema
        default = next(iter(schema)).default()
        assert default == ["P351ZAB0000001", "R331ZAB0000002"]
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"devices": ["P351ZAB0000001"]}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "1234"
    (device,) = result["data"]["devices"]
    assert device["model"] == "delta_3"


async def test_user_flow_bad_password(hass: HomeAssistant) -> None:
    async def refuse(self) -> None:
        raise EcoFlowAuthError("code=1")

    with patch(f"{API}.login", refuse):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "me@example.com", "password": "bad"}
        )
    assert result["errors"] == {"base": "invalid_auth"}


class FakeMqtt:
    """Stands in for EcoFlowMqttClient."""

    instances: list[FakeMqtt] = []

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        self.connected = False
        self.host = "mqtt.example"
        FakeMqtt.instances.append(self)

    def connect(self) -> None:
        self.connected = True
        self.kwargs["on_status"](True, 0)

    def close(self) -> None:
        self.connected = False

    def request_all(self, serials=None) -> None:
        pass

    def request_latest_quotas(self, sn: str) -> None:
        pass


async def test_messages_create_entities(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            "email": "me@example.com",
            "password": "pw",
            "devices": [
                {
                    "sn": "P351ZAB0000001",
                    "name": "Garage",
                    "product_name": "DELTA 3 Plus",
                    "model": "delta_3",
                },
                {
                    "sn": "R331ZAB0000002",
                    "name": "Van",
                    "product_name": "DELTA 2",
                    "model": "delta_2",
                },
            ],
        },
    )
    entry.add_to_hass(hass)

    async def creds(self) -> dict:
        return {"account": "a", "password": "b", "host": None}

    FakeMqtt.instances.clear()
    with (
        patch(f"{API}.login", _login),
        patch(f"{API}.get_mqtt_credentials", creds),
        patch("custom_components.ecoflow_app.hub.EcoFlowMqttClient", FakeMqtt),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        on_message = FakeMqtt.instances[0].kwargs["on_message"]
        payload = (FIXTURES / "p351_two_packs_get_all.bin").read_bytes()
        on_message("/app/1234/P351ZAB0000001/thing/property/get_reply", payload)
        on_message(
            "/app/device/property/R331ZAB0000002",
            json.dumps({"params": {"pd.wattsOutSum": 42, "bms_emsStatus.lcdShowSoc": 77}}).encode(),
        )
        await hass.async_block_till_done()

        states = {s.entity_id: s.state for s in hass.states.async_all("sensor")}
        assert states["sensor.garage_state_of_charge"] == "52.1"
        assert states["sensor.garage_extra_battery_1_state_of_charge"] == "54.1"
        assert states["sensor.garage_solar_input_power"] == "208.6"
        assert states["sensor.van_total_output_power"] == "42.0"
        assert states["sensor.van_state_of_charge"] == "77.0"
        assert hass.states.get("binary_sensor.garage_online").state == "on"

        assert await hass.config_entries.async_unload(entry.entry_id)
