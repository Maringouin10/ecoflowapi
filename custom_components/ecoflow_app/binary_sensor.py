"""Binary sensors: output states, plugged inputs and device connectivity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_KEYS
from .descriptions import BINARY_SENSORS, ONLINE_DESCRIPTION
from .entity import EcoFlowEntity
from .hub import EcoFlowHub


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create binary sensors for known keys now and new ones later."""
    hub: EcoFlowHub = hass.data[DOMAIN][entry.entry_id]
    created: set[tuple[str, str]] = set()

    @callback
    def add(sn: str, keys: set[str]) -> None:
        entities: list[BinarySensorEntity] = []
        for key in sorted(keys):
            description = BINARY_SENSORS.get(key)
            if description is None or (sn, key) in created:
                continue
            created.add((sn, key))
            entities.append(EcoFlowBinarySensor(hub, sn, description))
        if entities:
            async_add_entities(entities)

    async_add_entities(EcoFlowOnlineSensor(hub, sn, ONLINE_DESCRIPTION) for sn in hub.devices)
    for sn, device in hub.devices.items():
        add(sn, device.seen_keys)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_KEYS.format(entry_id=entry.entry_id), add)
    )


class EcoFlowBinarySensor(EcoFlowEntity, BinarySensorEntity):
    """A reported on/off state."""

    @property
    def is_on(self) -> bool | None:
        """Return the state."""
        value = self._value
        return None if value is None else bool(value)


class EcoFlowOnlineSensor(EcoFlowEntity, BinarySensorEntity):
    """Whether the device is currently reporting over the cloud."""

    @property
    def available(self) -> bool:
        """Always available: it is the availability."""
        return True

    @property
    def is_on(self) -> bool:
        """Return whether the device reported recently."""
        return self.hub.is_available(self.sn)
