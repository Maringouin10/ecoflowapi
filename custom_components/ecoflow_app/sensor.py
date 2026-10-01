"""Sensors: created per device from the keys it has reported."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .calc import ENERGY_SOURCES
from .const import DOMAIN, SIGNAL_NEW_KEYS
from .descriptions import SENSORS, EcoFlowSensorDescription
from .entity import EcoFlowEntity
from .hub import EcoFlowHub

_ENERGY_KEYS = set(ENERGY_SOURCES.values())


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create sensors for known keys now and for new keys as they appear."""
    hub: EcoFlowHub = hass.data[DOMAIN][entry.entry_id]
    created: set[tuple[str, str]] = set()

    @callback
    def add(sn: str, keys: set[str]) -> None:
        entities = []
        for key in sorted(keys):
            description = SENSORS.get(key)
            if description is None or (sn, key) in created:
                continue
            created.add((sn, key))
            entities.append(EcoFlowSensor(hub, sn, description))
        if entities:
            async_add_entities(entities)

    for sn, device in hub.devices.items():
        add(sn, device.seen_keys)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_KEYS.format(entry_id=entry.entry_id), add)
    )


class EcoFlowSensor(EcoFlowEntity, SensorEntity):
    """One measured or computed value."""

    entity_description: EcoFlowSensorDescription

    @property
    def available(self) -> bool:
        """Energy totals stay readable while the device is silent."""
        if self.entity_description.key in _ENERGY_KEYS:
            return self._value is not None
        return super().available

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self._value
