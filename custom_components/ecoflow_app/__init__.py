"""EcoFlow App - EcoFlow batteries in Home Assistant through the app's cloud.

Uses the EcoFlow account (e-mail + password) the way the EcoFlow app does,
instead of the IoT developer API, which does not expose every model.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_DEVICES, DOMAIN, PLATFORMS
from .hub import EcoFlowHub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Connect to the EcoFlow cloud and create the entities."""
    devices = entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, []))
    hub = EcoFlowHub(hass, entry, devices)
    await hub.async_setup()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = hub
    _enable_integration_disabled(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Disconnect and remove the entities."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hub: EcoFlowHub = hass.data[DOMAIN].pop(entry.entry_id)
        await hub.async_shutdown()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _enable_integration_disabled(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-enable entities that earlier versions disabled by default.

    Every value is enabled by default now; an entity the user disabled
    themselves stays disabled.
    """
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
