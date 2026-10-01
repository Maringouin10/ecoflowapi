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
from homeassistant.helpers import entity_registry as er  # noqa: E402
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
    # An entity an earlier version disabled by default comes back enabled;
    # one the user disabled stays disabled.
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "P351ZAB0000001_usb_c1_out_power_w",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "P351ZAB0000001_usb_c2_out_power_w",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

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
        # Every decoded field exists, the unnamed ones as raw sensors.
        assert states["sensor.garage_cell_vol_1"] == "3353"
        assert hass.states.get("sensor.garage_cell_vol_1").attributes["unit_of_measurement"] == "mV"
        assert states["sensor.garage_ac_output_voltage"] == "230.1"

        def disabled_by(unique_id: str):
            entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
            return registry.async_get(entity_id).disabled_by

        assert disabled_by("P351ZAB0000001_usb_c1_out_power_w") is None
        assert disabled_by("P351ZAB0000001_usb_c2_out_power_w") is er.RegistryEntryDisabler.USER

        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_dpu_outlet_keeps_its_value_between_incremental_frames(hass: HomeAssistant) -> None:
    from .helpers import f32, frame, u

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1234",
        data={
            "email": "me@example.com",
            "password": "pw",
            "devices": [
                {
                    "sn": "Y711ZAB0000009",
                    "name": "DPU",
                    "product_name": "DELTA Pro Ultra",
                    "model": "delta_pro_ultra",
                }
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
        topic = "/app/device/property/Y711ZAB0000009"

        on_message(topic, frame(2, 1, u(21, 80) + f32(48, 150.0) + f32(50, 12.0)))
        await hass.async_block_till_done()
        # Next frame only carries the USB port that changed.
        on_message(topic, frame(2, 1, f32(43, 5.0)))
        await hass.async_block_till_done()

        def state(entity_id: str) -> str:
            return hass.states.get(entity_id).state

        assert state("sensor.dpu_ac_outlet_l1_1_power") == "150.0"
        assert state("sensor.dpu_ac_outlet_l2_1_power") == "12.0"
        assert state("sensor.dpu_ac_output_power") == "162.0"
        # Never reported: created with 0 W, and still 0 W.
        assert state("sensor.dpu_dc_output_power_anderson") == "0.0"
        assert state("sensor.dpu_dc_output_power_total") == "5.0"

        assert await hass.config_entries.async_unload(entry.entry_id)
