"""Diagnostics download: connection state, parsed values, unknown frames."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .hub import EcoFlowHub

_REDACT = {CONF_EMAIL, CONF_PASSWORD, "sn", "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub: EcoFlowHub = hass.data[DOMAIN][entry.entry_id]
    devices = entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, []))
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options)}, _REDACT | {CONF_DEVICES}
        ),
        "configured_devices": [
            {
                "prefix": d.get("sn", "")[:4],
                "product_name": d.get("product_name"),
                "model": d.get("model"),
            }
            for d in devices
        ],
        "hub": hub.diagnostics(),
    }
