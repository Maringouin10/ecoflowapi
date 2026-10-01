"""Base entity shared by every platform."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, MANUFACTURER
from .hub import EcoFlowHub


class EcoFlowEntity(Entity):
    """An entity bound to one value key of one device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub: EcoFlowHub, sn: str, description: EntityDescription) -> None:
        self.hub = hub
        self.sn = sn
        self.entity_description = description
        device = hub.devices[sn]
        self._attr_unique_id = f"{sn}_{description.key}"
        index = getattr(description, "index", None)
        if index is not None:
            self._attr_translation_placeholders = {"index": str(index)}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            manufacturer=MANUFACTURER,
            name=device.name,
            model=device.product_name or device.model.name,
            serial_number=sn,
        )

    @property
    def available(self) -> bool:
        """Return whether the device is reporting."""
        return self.hub.is_available(self.sn)

    @property
    def _value(self) -> Any:
        return self.hub.devices[self.sn].values.get(self.entity_description.key)

    async def async_added_to_hass(self) -> None:
        """Follow the device's updates."""
        self.async_on_remove(self.hub.add_listener(self.sn, self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
