"""Account-level hub: one MQTT session, every selected device.

Responsibilities:

* sign in, fetch the MQTT credentials and keep one session alive
  (reconnect with backoff and a fresh client ID, re-login on refused
  credentials, daily credential refresh);
* route each message to its device, parse it and merge the values (the
  protobuf devices send incremental frames, so merging is required);
* derive the values the Energy dashboard needs and integrate power into
  kWh, persisting the totals across restarts;
* remember which values each device has reported, so the matching entities
  are created again at startup before the first frame arrives.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.storage import Store

from .api import EcoFlowApiError, EcoFlowAppApi, EcoFlowAuthError
from .calc import ENERGY_SOURCES, derive, integrate
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CREDENTIAL_MAX_AGE_S,
    ENERGY_MAX_GAP_S,
    GET_ALL_KEEPALIVE_S,
    QUOTAS_KEEPALIVE_S,
    RECONNECT_MAX_DELAY_S,
    RECONNECT_MIN_DELAY_S,
    SIGNAL_NEW_KEYS,
    STALE_AFTER_S,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .models import DIALECT_JSON, DeviceModel, model_by_key
from .mqtt_client import AUTH_FAILURE_CODES, EcoFlowMqttClient, sn_from_topic
from .parsers import parse_payload
from .parsers.raw import RAW_PREFIX

_LOGGER = logging.getLogger(__name__)


def signal_update(entry_id: str, sn: str) -> str:
    """Dispatcher signal sent when a device's values change."""
    return f"ecoflow_app_update_{entry_id}_{sn}"


@dataclass
class DeviceState:
    """Everything known about one device."""

    sn: str
    name: str
    product_name: str
    model: DeviceModel
    values: dict[str, Any] = field(default_factory=dict)
    seen_keys: set[str] = field(default_factory=set)
    # raw key -> whether its value is numeric (kept so the entity keeps its
    # state class across restarts, before the first value arrives)
    raw_numeric: dict[str, bool] = field(default_factory=dict)
    last_seen: float = 0.0
    dialect: str = ""
    cloud_online: bool | None = None
    message_count: int = 0
    unknown_frames: dict[str, list[int]] = field(default_factory=dict)
    # energy key -> (monotonic time, power W) of the previous reading
    energy_last: dict[str, tuple[float, float]] = field(default_factory=dict)

    @property
    def fresh(self) -> bool:
        """Return whether the device reported recently."""
        return self.last_seen > 0 and time.monotonic() - self.last_seen < STALE_AFTER_S


class EcoFlowHub:
    """Owns the MQTT session and the state of every selected device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        devices: list[dict[str, Any]],
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.devices: dict[str, DeviceState] = {
            d["sn"]: DeviceState(
                sn=d["sn"],
                name=d.get("name") or d["sn"],
                product_name=d.get("product_name", ""),
                model=model_by_key(d.get("model", "")),
            )
            for d in devices
        }
        self._api = EcoFlowAppApi(
            async_get_clientsession(hass),
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{STORAGE_KEY}.{entry.entry_id}"
        )
        self._mqtt: EcoFlowMqttClient | None = None
        self._creds: dict[str, Any] | None = None
        self._creds_time = 0.0
        self._reconnect_delay = RECONNECT_MIN_DELAY_S
        self._reconnect_unsub: CALLBACK_TYPE | None = None
        self._unsubs: list[CALLBACK_TYPE] = []
        self._connect_lock = asyncio.Lock()
        self._closing = False
        self.connected = False
        self.last_error: str | None = None

    # -- setup / teardown ----------------------------------------------------

    async def async_setup(self) -> None:
        """Restore state, sign in and connect. Raises on bad credentials."""
        stored = await self._store.async_load() or {}
        for sn, saved in (stored.get("devices") or {}).items():
            device = self.devices.get(sn)
            if device is None:
                continue
            device.seen_keys = set(saved.get("seen_keys", []))
            device.raw_numeric = dict(saved.get("raw_numeric", {}))
            for key, value in (saved.get("energy") or {}).items():
                if isinstance(value, (int, float)):
                    device.values[key] = float(value)

        try:
            await self._refresh_credentials()
        except EcoFlowAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc
        except EcoFlowApiError as exc:
            raise ConfigEntryNotReady(str(exc)) from exc

        await self._connect()

        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._keepalive_quotas, timedelta(seconds=QUOTAS_KEEPALIVE_S)
            )
        )
        self._unsubs.append(
            async_track_time_interval(
                self.hass, self._keepalive_get_all, timedelta(seconds=GET_ALL_KEEPALIVE_S)
            )
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._periodic, timedelta(seconds=60))
        )

    async def async_shutdown(self) -> None:
        """Disconnect and persist."""
        self._closing = True
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        if self._reconnect_unsub:
            self._reconnect_unsub()
            self._reconnect_unsub = None
        if self._mqtt is not None:
            mqtt_client, self._mqtt = self._mqtt, None
            await self.hass.async_add_executor_job(mqtt_client.close)
        await self._store.async_save(self._snapshot())

    # -- persistence ---------------------------------------------------------

    def _snapshot(self) -> dict[str, Any]:
        return {
            "devices": {
                sn: {
                    "seen_keys": sorted(device.seen_keys),
                    "raw_numeric": device.raw_numeric,
                    "energy": {
                        key: device.values[key]
                        for key in ENERGY_SOURCES.values()
                        if isinstance(device.values.get(key), (int, float))
                    },
                }
                for sn, device in self.devices.items()
            }
        }

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._snapshot, 30)

    # -- connection ----------------------------------------------------------

    async def _refresh_credentials(self) -> None:
        await self._api.login()
        self._creds = await self._api.get_mqtt_credentials()
        self._creds_time = time.monotonic()

    async def _connect(self) -> None:
        async with self._connect_lock:
            if self._closing:
                return
            old, self._mqtt = self._mqtt, None
            if old is not None:
                await self.hass.async_add_executor_job(old.close)
            assert self._creds is not None and self._api.user_id is not None
            client = EcoFlowMqttClient(
                account=self._creds["account"],
                password=self._creds["password"],
                user_id=self._api.user_id,
                serials=list(self.devices),
                on_message=self._on_message_threadsafe,
                on_status=self._on_status_threadsafe,
                host=self._creds.get("host"),
            )
            self._mqtt = client
            try:
                await self.hass.async_add_executor_job(client.connect)
            except (OSError, ValueError) as exc:
                self.last_error = f"connect failed: {exc}"
                _LOGGER.warning("EcoFlow MQTT connection failed: %s", exc)
                self._schedule_reconnect()

    def _on_status_threadsafe(self, connected: bool, code: int) -> None:
        self.hass.loop.call_soon_threadsafe(self._on_status, connected, code)

    @callback
    def _on_status(self, connected: bool, code: int) -> None:
        if self._closing:
            return
        self.connected = connected
        if connected:
            self._reconnect_delay = RECONNECT_MIN_DELAY_S
            self.last_error = None
        else:
            self.last_error = f"disconnected (rc={code})"
            self._schedule_reconnect(refresh=code in AUTH_FAILURE_CODES)
        for sn in self.devices:
            async_dispatcher_send(self.hass, signal_update(self.entry.entry_id, sn))

    @callback
    def _schedule_reconnect(self, refresh: bool = False) -> None:
        if self._closing or self._reconnect_unsub is not None:
            return
        delay = self._reconnect_delay
        self._reconnect_delay = min(self._reconnect_delay * 2, RECONNECT_MAX_DELAY_S)

        async def _run(_now: Any) -> None:
            self._reconnect_unsub = None
            try:
                if refresh or time.monotonic() - self._creds_time > CREDENTIAL_MAX_AGE_S:
                    await self._refresh_credentials()
            except EcoFlowAuthError:
                _LOGGER.error("EcoFlow refused the account password, re-authentication needed")
                self.entry.async_start_reauth(self.hass)
                return
            except EcoFlowApiError as exc:
                self.last_error = str(exc)
                self._schedule_reconnect(refresh=True)
                return
            await self._connect()

        _LOGGER.debug("EcoFlow MQTT reconnect in %ss", delay)
        self._reconnect_unsub = async_call_later(self.hass, delay, _run)

    # -- keepalive -----------------------------------------------------------

    async def _keepalive_quotas(self, _now: Any) -> None:
        client = self._mqtt
        if client is None or not client.connected:
            return
        serials = [
            sn
            for sn, d in self.devices.items()
            if d.dialect in ("", DIALECT_JSON) and d.model.dialect in ("", DIALECT_JSON)
        ]
        if serials:
            await self.hass.async_add_executor_job(self._request_quotas, client, serials)

    @staticmethod
    def _request_quotas(client: EcoFlowMqttClient, serials: list[str]) -> None:
        for sn in serials:
            client.request_latest_quotas(sn)

    async def _keepalive_get_all(self, _now: Any) -> None:
        client = self._mqtt
        if client is None or not client.connected:
            return
        await self.hass.async_add_executor_job(client.request_all)

    async def _periodic(self, _now: Any) -> None:
        # Refresh credentials before they expire, then reconnect with them.
        if time.monotonic() - self._creds_time > CREDENTIAL_MAX_AGE_S:
            try:
                await self._refresh_credentials()
            except (EcoFlowApiError, EcoFlowAuthError) as exc:
                _LOGGER.debug("Credential refresh failed: %s", exc)
            else:
                await self._connect()
        # Let entities re-evaluate availability of silent devices.
        for sn, device in self.devices.items():
            if not device.fresh:
                device.energy_last.clear()
                async_dispatcher_send(self.hass, signal_update(self.entry.entry_id, sn))

    # -- messages ------------------------------------------------------------

    def _on_message_threadsafe(self, topic: str, payload: bytes) -> None:
        self.hass.loop.call_soon_threadsafe(self._on_message, topic, payload)

    @callback
    def _on_message(self, topic: str, payload: bytes) -> None:
        sn = sn_from_topic(topic)
        device = self.devices.get(sn or "")
        if device is None:
            return
        result = parse_payload(payload, device.model)
        if result.online is not None:
            device.cloud_online = result.online
        for (func, cmd), numbers in result.unknown_frames.items():
            device.unknown_frames[f"{func}/{cmd}"] = numbers
        if not result.values:
            return
        if result.dialect:
            device.dialect = result.dialect

        now = time.monotonic()
        device.last_seen = now
        device.message_count += 1
        device.values.update(result.values)
        for key, value in result.defaults.items():
            device.values.setdefault(key, value)
        device.values.update(derive(device.values, result.values))
        integrate(device.values, device.energy_last, now, ENERGY_MAX_GAP_S)

        new_keys = {
            k for k, v in device.values.items() if v is not None and not k.startswith("_")
        } - device.seen_keys
        if new_keys:
            for key in new_keys:
                if key.startswith(RAW_PREFIX):
                    value = device.values[key]
                    device.raw_numeric[key] = isinstance(value, (int, float))
            device.seen_keys |= new_keys
            async_dispatcher_send(
                self.hass,
                SIGNAL_NEW_KEYS.format(entry_id=self.entry.entry_id),
                sn,
                new_keys,
            )
        self._schedule_save()
        async_dispatcher_send(self.hass, signal_update(self.entry.entry_id, sn))

    # -- helpers for entities -----------------------------------------------

    def is_available(self, sn: str) -> bool:
        """Return whether values of this device can be trusted right now."""
        device = self.devices.get(sn)
        return bool(device and self.connected and device.fresh)

    def add_listener(self, sn: str, update: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to a device's updates."""
        return async_dispatcher_connect(self.hass, signal_update(self.entry.entry_id, sn), update)

    def diagnostics(self) -> dict[str, Any]:
        """Data for the diagnostics download (no credentials)."""
        return {
            "connected": self.connected,
            "broker": self._mqtt.host if self._mqtt else None,
            "last_error": self.last_error,
            "devices": {
                sn[:4] + "…": {
                    "model": device.model.key,
                    "product_name": device.product_name,
                    "dialect": device.dialect,
                    "cloud_online": device.cloud_online,
                    "messages": device.message_count,
                    "seconds_since_last_message": (
                        round(time.monotonic() - device.last_seen) if device.last_seen else None
                    ),
                    "values": device.values,
                    "unknown_frames": device.unknown_frames,
                }
                for sn, device in self.devices.items()
            },
        }
