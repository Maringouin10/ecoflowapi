"""EcoFlow account API - the same calls the EcoFlow app / web portal makes.

Flow (no IoT developer keys needed):

1. ``POST /auth/login`` with e-mail + base64 password -> JWT + userId
2. ``GET /iot-service/user/device`` -> every device bound to / shared with
   the account (the developer API hides some models, this one does not)
3. ``GET /iot-auth/enterprise-development/user/certification`` -> MQTT
   account/password, AES-CFB encrypted with SHA256(JWT)

Adapted from shuette42/ecoflow-energy-ha (MIT), ``enhanced_auth.py`` and
``app_api.py``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

try:
    from cryptography.hazmat.decrepit.ciphers.modes import CFB
except ImportError:  # cryptography < 43
    from cryptography.hazmat.primitives.ciphers.modes import CFB

from .const import API_BASE_URLS

_LOGGER = logging.getLogger(__name__)

_LOGIN_PATH = "/auth/login"
_DEVICE_LIST_PATH = "/iot-service/user/device"
_CERT_PATH = "/iot-auth/enterprise-development/user/certification"
# Constant IV from the EcoFlow portal JavaScript bundle.
_AES_IV = b"ojsajkqjwk1w2dfg"
_TIMEOUT = aiohttp.ClientTimeout(total=15)


class EcoFlowAuthError(Exception):
    """E-mail or password refused."""


class EcoFlowApiError(Exception):
    """The cloud could not be reached or answered something unexpected."""


class EcoFlowAppApi:
    """Token-authenticated client for the EcoFlow account API."""

    def __init__(self, session: aiohttp.ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.token: str | None = None
        self.user_id: str | None = None
        self.base_url: str = API_BASE_URLS[0]

    async def login(self) -> None:
        """Sign in; raises EcoFlowAuthError or EcoFlowApiError."""
        payload = {
            "email": self._email,
            "password": base64.b64encode(self._password.encode()).decode(),
            "scene": "IOT_APP",
            "userType": "ECOFLOW",
        }
        auth_refused = False
        last_error = "no endpoint answered"
        for base_url in API_BASE_URLS:
            try:
                async with self._session.post(
                    f"{base_url}{_LOGIN_PATH}", json=payload, timeout=_TIMEOUT
                ) as resp:
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
                last_error = str(exc)
                continue
            if not isinstance(body, dict):
                last_error = "unexpected login response"
                continue
            if str(body.get("code")) != "0":
                last_error = f"code={body.get('code')} message={body.get('message')}"
                # A refused password is reported by every region alike.
                auth_refused = True
                continue
            data = body.get("data") or {}
            token = data.get("token")
            user_id = (data.get("user") or {}).get("userId")
            if not token or not user_id:
                last_error = "login response without token"
                continue
            self.token = token
            self.user_id = str(user_id)
            self.base_url = base_url
            return
        if auth_refused:
            raise EcoFlowAuthError(last_error)
        raise EcoFlowApiError(last_error)

    async def _get(self, path: str) -> Any:
        if not self.token:
            await self.login()
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with self._session.get(
                f"{self.base_url}{path}", headers=headers, timeout=_TIMEOUT
            ) as resp:
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise EcoFlowApiError(str(exc)) from exc
        if not isinstance(body, dict) or str(body.get("code")) != "0":
            code = body.get("code") if isinstance(body, dict) else None
            raise EcoFlowApiError(f"{path}: code={code}")
        return body.get("data")

    async def get_devices(self) -> list[dict[str, Any]]:
        """Return ``[{"sn", "name", "product_name", "online"}]``."""
        data = await self._get(_DEVICE_LIST_PATH)
        return parse_device_list(data)

    async def get_mqtt_credentials(self) -> dict[str, Any]:
        """Return the decrypted MQTT credentials (account, password, broker)."""
        data = await self._get(_CERT_PATH)
        if not isinstance(data, str) or not data:
            raise EcoFlowApiError("empty MQTT certification")
        creds = decrypt_certification(self.token or "", data)
        if not creds:
            raise EcoFlowApiError("MQTT certification could not be decrypted")
        account = creds.get("certificateAccount") or creds.get("userName")
        password = creds.get("certificatePassword") or creds.get("password")
        if not account or not password:
            raise EcoFlowApiError("MQTT certification without account")
        return {
            "account": account,
            "password": password,
            "host": _clean_host(creds.get("url")),
        }


def decrypt_certification(token: str, encrypted: str) -> dict[str, Any] | None:
    """AES-CFB128(key=SHA256(token), iv=constant), PKCS7, JSON."""
    try:
        key = hashlib.sha256(token.encode()).digest()
        decryptor = Cipher(algorithms.AES(key), CFB(_AES_IV)).decryptor()
        plain = decryptor.update(base64.b64decode(encrypted)) + decryptor.finalize()
        if plain:
            pad = plain[-1]
            if 0 < pad <= 16 and all(b == pad for b in plain[-pad:]):
                plain = plain[:-pad]
        result = json.loads(plain)
    except (ValueError, TypeError):
        return None
    return result if isinstance(result, dict) else None


def _clean_host(value: Any) -> str | None:
    """Return a bare broker host name from the certification answer."""
    if not isinstance(value, str):
        return None
    host = value.strip()
    for scheme in ("wss://", "ws://", "mqtts://", "mqtt://", "ssl://", "tcp://"):
        if host.lower().startswith(scheme):
            host = host[len(scheme) :]
    host = host.split("/", 1)[0].rsplit("@", 1)[-1].split(":", 1)[0]
    return host if host and "." in host and " " not in host else None


def parse_device_list(data: Any) -> list[dict[str, Any]]:
    """Flatten the ``{"bound": {...}, "share": {...}}`` device answer."""
    devices: list[dict[str, Any]] = []
    seen: set[str] = set()
    if not isinstance(data, dict):
        return devices

    def add(dev: Any, sn_hint: str | None = None) -> None:
        if not isinstance(dev, dict):
            return
        sn = dev.get("sn") or sn_hint
        if not sn or sn in seen:
            return
        seen.add(sn)
        product = dev.get("productName") or dev.get("product_name") or ""
        devices.append(
            {
                "sn": sn,
                "name": dev.get("deviceName") or dev.get("name") or product or sn,
                "product_name": product,
                "online": dev.get("online", 0),
            }
        )

    for category in ("bound", "share"):
        group = data.get(category)
        if isinstance(group, list):
            for dev in group:
                add(dev)
        elif isinstance(group, dict):
            for key, value in group.items():
                if isinstance(value, list):
                    for dev in value:
                        add(dev)
                else:
                    add(value, key)
    return devices
