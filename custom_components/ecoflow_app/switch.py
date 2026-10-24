"""Switches for the outputs (AC, 12 V DC, USB) that can be commanded."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SIGNAL_NEW_KEYS
from .entity import EcoFlowEntity
from .hub import EcoFlowHub
from .models import DIALECT_JSON

SWITCHES: dict[str, SwitchEntityDescription] = {
    key: SwitchEntityDescription(
        key=key, translation_key=key, device_class=SwitchDeviceClass.SWITCH
    )
    for key in ("ac_out_enabled", "dc12v_out_enabled", "usb_out_enabled")
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the switches of each device.

    JSON devices get one once the output's state has been reported. The
    others get it at once, as some never report the state of an output.
    """
    hub: EcoFlowHub = hass.data[DOMAIN][entry.entry_id]
    created: set[tuple[str, str]] = set()

    def always(sn: str) -> set[str]:
        device = hub.devices[sn]
        if (device.dialect or device.model.dialect) == DIALECT_JSON:
            return set()
        return hub.switch_keys(sn)

    @callback
    def add(sn: str, keys: set[str]) -> None:
        entities = []
        for key in sorted(hub.switch_keys(sn) & (keys | always(sn))):
            if (sn, key) in created:
                continue
            created.add((sn, key))
            entities.append(EcoFlowSwitch(hub, sn, SWITCHES[key]))
        if entities:
            async_add_entities(entities)

    for sn, device in hub.devices.items():
        add(sn, device.seen_keys)

    entry.async_on_unload(
        async_dispatcher_connect(hass, SIGNAL_NEW_KEYS.format(entry_id=entry.entry_id), add)
    )


class EcoFlowSwitch(EcoFlowEntity, SwitchEntity):
    """An output that can be switched on and off."""

    @property
    def _state(self) -> Any:
        device = self.hub.devices[self.sn]
        key = self.entity_description.key
        value = device.values.get(key)
        return device.commanded.get(key) if value is None else value

    @property
    def assumed_state(self) -> bool:
        """The device never reported this output: show the last command."""
        return self._value is None

    @property
    def is_on(self) -> bool | None:
        """Return the output state."""
        value = self._state
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Switch the output on."""
        await self.hub.async_set_switch(self.sn, self.entity_description.key, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Switch the output off."""
        await self.hub.async_set_switch(self.sn, self.entity_description.key, False)
