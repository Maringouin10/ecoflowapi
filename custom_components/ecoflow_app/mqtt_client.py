"""MQTT over WebSocket to the EcoFlow broker, as the web portal does it.

One connection per EcoFlow account carries every device. The broker only
accepts a client ID generated for the account (see ``clientid.py``) and
refuses a reused one, so each (re)connect builds a brand-new paho client;
reconnecting is driven by the hub, not by paho.

Paho runs its own network thread: every callback handed in here is called on
that thread and must hand over to the event loop itself.

Connection handling adapted from shuette42/ecoflow-energy-ha (MIT),
``cloud_mqtt.py``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
import json
import logging
import ssl
import threading
import time
from typing import Any

import paho.mqtt.client as mqtt

from .clientid import generate_client_id
from .const import MQTT_HOST, MQTT_PORT_WSS, MQTT_WSS_PATH
from .proto import build_get_all_request

_LOGGER = logging.getLogger(__name__)

# CONNACK codes that mean "wrong credentials" (MQTT 3.1.1 and their MQTT 5
# equivalents as reported by paho 2.x).
AUTH_FAILURE_CODES = {4, 5, 134, 135}


def data_topic(sn: str) -> str:
    """Topic the device publishes its telemetry on."""
    return f"/app/device/property/{sn}"


def get_topic(user_id: str, sn: str) -> str:
    """Topic requests for a device are published on."""
    return f"/app/{user_id}/{sn}/thing/property/get"


def get_reply_topic(user_id: str, sn: str) -> str:
    """Topic the device answers requests on."""
    return f"/app/{user_id}/{sn}/thing/property/get_reply"


def sn_from_topic(topic: str) -> str | None:
    """Extract the serial number from a data or get_reply topic."""
    parts = topic.strip("/").split("/")
    if len(parts) == 4 and parts[:3] == ["app", "device", "property"]:
        return parts[3]
    if len(parts) == 6 and parts[0] == "app" and parts[3:5] == ["thing", "property"]:
        return parts[2]
    return None


class EcoFlowMqttClient:
    """A single paho session. Create a new instance for every connection."""

    def __init__(
        self,
        *,
        account: str,
        password: str,
        user_id: str,
        serials: Iterable[str],
        on_message: Callable[[str, bytes], None],
        on_status: Callable[[bool, int], None],
        host: str | None = None,
    ) -> None:
        self._account = account
        self._password = password
        self._user_id = user_id
        self._serials = list(serials)
        self._on_message = on_message
        self._on_status = on_status
        self._host = host or MQTT_HOST
        self._client: mqtt.Client | None = None
        self._connected = threading.Event()
        self._closed = False

    @property
    def connected(self) -> bool:
        """Return whether the broker accepted the session."""
        return self._connected.is_set()

    @property
    def host(self) -> str:
        """Return the broker host (public infrastructure, safe to log)."""
        return self._host

    # -- lifecycle (call from an executor, these block) ----------------------

    def connect(self) -> None:
        """Open the session and start paho's network thread."""
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=generate_client_id(self._user_id),
            transport="websockets",
            clean_session=True,
        )
        client.ws_set_options(path=MQTT_WSS_PATH)
        client.username_pw_set(self._account, self._password)
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
        # Paho must not reconnect on its own with the old client ID; the hub
        # replaces this client long before this delay runs out.
        client.reconnect_delay_set(min_delay=600, max_delay=600)
        client.on_connect = self._handle_connect
        client.on_disconnect = self._handle_disconnect
        client.on_message = self._handle_message
        self._client = client
        client.connect(self._host, MQTT_PORT_WSS, keepalive=30)
        client.loop_start()

    def close(self) -> None:
        """Stop the session for good."""
        self._closed = True
        client = self._client
        self._client = None
        self._connected.clear()
        if client is None:
            return
        try:
            client.disconnect()
        except Exception:  # noqa: BLE001 - shutting down regardless
            pass
        client.loop_stop()

    # -- paho callbacks (paho thread) ----------------------------------------

    def _handle_connect(self, client, userdata, flags, reason_code, properties=None):
        code = getattr(reason_code, "value", reason_code)
        if code != 0:
            _LOGGER.warning("EcoFlow MQTT refused the connection (rc=%s)", code)
            self._on_status(False, int(code))
            return
        for sn in self._serials:
            client.subscribe(data_topic(sn), qos=1)
            client.subscribe(get_reply_topic(self._user_id, sn), qos=1)
        self._connected.set()
        _LOGGER.debug("EcoFlow MQTT connected to %s, %d device(s)", self._host, len(self._serials))
        self._on_status(True, 0)
        self.request_all()

    def _handle_disconnect(self, client, userdata, flags, reason_code, properties=None):
        was_connected = self._connected.is_set()
        self._connected.clear()
        if self._closed:
            return
        code = getattr(reason_code, "value", reason_code)
        if was_connected:
            _LOGGER.info("EcoFlow MQTT disconnected (rc=%s)", code)
        self._on_status(False, int(code) if isinstance(code, int) else -1)

    def _handle_message(self, client, userdata, msg):
        try:
            self._on_message(msg.topic, msg.payload)
        except Exception:  # noqa: BLE001 - never let a bad frame kill paho
            _LOGGER.exception("Error while handling an EcoFlow message")

    # -- requests ------------------------------------------------------------

    def _publish(self, topic: str, payload: str | bytes) -> None:
        client = self._client
        if client is None or not self.connected:
            return
        client.publish(topic, payload, qos=1)

    def request_latest_quotas(self, sn: str) -> None:
        """Ask a device for all its values (answered by JSON devices)."""
        payload = json.dumps(
            {
                "from": "Android",
                "id": str(int(time.time() * 1000)),
                "moduleType": 0,
                "operateType": "latestQuotas",
                "params": {},
                "version": "1.0",
            }
        )
        self._publish(get_topic(self._user_id, sn), payload)

    def request_get_all(self, sn: str) -> None:
        """Ask a protobuf device for a full state dump."""
        payload = build_get_all_request(int(time.time() * 1000))
        self._publish(get_topic(self._user_id, sn), payload)

    def request_all(self, serials: Iterable[str] | None = None) -> None:
        """Send both requests to the given (default: every) device."""
        for sn in serials if serials is not None else self._serials:
            self.request_latest_quotas(sn)
            self.request_get_all(sn)


def describe(status: Any) -> str:
    """Short text for a connection status code (for logs/diagnostics)."""
    if status in AUTH_FAILURE_CODES:
        return "authentication refused"
    return f"rc={status}"
