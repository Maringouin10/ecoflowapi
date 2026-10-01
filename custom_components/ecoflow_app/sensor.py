"""Sensors: created per device from the keys it has reported."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .calc import ENERGY_SOURCES
from .const import DOMAIN, SIGNAL_NEW_KEYS
from .descriptions import SENSORS, EcoFlowSensorDescription
from .entity import EcoFlowEntity
from .hub import EcoFlowHub
from .parsers.raw import RAW_PREFIX

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
            if (sn, key) in created:
                continue
            description = SENSORS.get(key)
            if description is not None:
                entities.append(EcoFlowSensor(hub, sn, description))
            elif key.startswith(RAW_PREFIX):
                entities.append(EcoFlowRawSensor(hub, sn, _raw_description(hub, sn, key)))
            else:
                continue
            created.add((sn, key))
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


def _raw_description(hub: EcoFlowHub, sn: str, key: str) -> SensorEntityDescription:
    """Describe a field that has no dedicated sensor yet.

    Units are only given where the protocol name leaves no doubt: powers
    (``pow_*``, ``*_pwr``, ``*_watts``), BMS cell voltages (mV) and
    temperatures (°C).
    """
    name = key[len(RAW_PREFIX) :]
    numeric = hub.devices[sn].raw_numeric.get(key, True)
    device_class: SensorDeviceClass | None = None
    unit: str | None = None
    if numeric:
        lowered = name.lower()
        if lowered.startswith("pow_") or lowered.endswith(("_pwr", "_watts")):
            device_class, unit = SensorDeviceClass.POWER, UnitOfPower.WATT
        elif "cell_vol" in lowered and "num" not in lowered:
            device_class, unit = SensorDeviceClass.VOLTAGE, UnitOfElectricPotential.MILLIVOLT
        elif "temp" in lowered and not any(
            word in lowered for word in ("num", "icon", "flag", "err", "time")
        ):
            device_class, unit = SensorDeviceClass.TEMPERATURE, UnitOfTemperature.CELSIUS
    return SensorEntityDescription(
        key=key,
        name=name.replace("_", " "),
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=device_class,
        native_unit_of_measurement=unit,
        state_class=SensorStateClass.MEASUREMENT if numeric else None,
    )


class EcoFlowRawSensor(EcoFlowEntity, SensorEntity):
    """A reported field shown under its protocol name."""

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self._value
