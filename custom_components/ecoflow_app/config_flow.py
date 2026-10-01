"""Config flow: EcoFlow account, then the batteries to include."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
import voluptuous as vol

from .api import EcoFlowApiError, EcoFlowAppApi, EcoFlowAuthError
from .const import CONF_DEVICES, CONF_EMAIL, CONF_PASSWORD, DOMAIN
from .models import detect_model, is_supported

_LOGGER = logging.getLogger(__name__)

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _annotate(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add the detected model to each device of the cloud list."""
    out = []
    for dev in devices:
        model = detect_model(dev.get("product_name"), dev.get("sn"))
        out.append({**dev, "model": model.key if is_supported(model) else ""})
    return out


def _device_selector(devices: list[dict[str, Any]]) -> SelectSelector:
    options = []
    for dev in devices:
        product = dev.get("product_name") or "?"
        label = f"{dev['name']} - {product} ({dev['sn'][:4]}…)"
        if not dev.get("model"):
            label += " [non reconnu / not recognised]"
        options.append(SelectOptionDict(value=dev["sn"], label=label))
    return SelectSelector(
        SelectSelectorConfig(options=options, multiple=True, mode=SelectSelectorMode.LIST)
    )


async def _fetch(api: EcoFlowAppApi) -> list[dict[str, Any]]:
    await api.login()
    return _annotate(await api.get_devices())


class EcoFlowAppConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup of an EcoFlow account."""

    VERSION = 1

    def __init__(self) -> None:
        self._account: dict[str, Any] = {}
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the EcoFlow account."""
        errors: dict[str, str] = {}
        if user_input is not None:
            api = EcoFlowAppApi(
                async_get_clientsession(self.hass),
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            try:
                self._devices = await _fetch(api)
            except EcoFlowAuthError:
                errors["base"] = "invalid_auth"
            except EcoFlowApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(api.user_id)
                self._abort_if_unique_id_configured()
                if not self._devices:
                    return self.async_abort(reason="no_devices")
                self._account = user_input
                return await self.async_step_devices()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose the batteries to include."""
        errors: dict[str, str] = {}
        if user_input is not None:
            selected = set(user_input.get(CONF_DEVICES, []))
            if not selected:
                errors["base"] = "no_selection"
            else:
                return self.async_create_entry(
                    title=self._account[CONF_EMAIL],
                    data={
                        **self._account,
                        CONF_DEVICES: [d for d in self._devices if d["sn"] in selected],
                    },
                )
        default = [d["sn"] for d in self._devices if d.get("model")]
        return self.async_show_form(
            step_id="devices",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICES, default=default): _device_selector(self._devices)}
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """The password was refused."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the new password."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            api = EcoFlowAppApi(
                async_get_clientsession(self.hass),
                entry.data[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            try:
                await api.login()
            except EcoFlowAuthError:
                errors["base"] = "invalid_auth"
            except EcoFlowApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Change the device selection later."""
        return EcoFlowAppOptionsFlow()


class EcoFlowAppOptionsFlow(OptionsFlow):
    """Re-read the account's devices and change the selection."""

    def __init__(self) -> None:
        self._devices: list[dict[str, Any]] = []

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Show the device list."""
        errors: dict[str, str] = {}
        entry = self.config_entry
        current = entry.options.get(CONF_DEVICES, entry.data.get(CONF_DEVICES, []))
        if user_input is not None:
            selected = set(user_input.get(CONF_DEVICES, []))
            if not selected:
                errors["base"] = "no_selection"
            else:
                known = {d["sn"]: d for d in [*current, *self._devices]}
                return self.async_create_entry(
                    data={CONF_DEVICES: [known[sn] for sn in selected if sn in known]}
                )
        if not self._devices:
            api = EcoFlowAppApi(
                async_get_clientsession(self.hass),
                entry.data[CONF_EMAIL],
                entry.data[CONF_PASSWORD],
            )
            try:
                self._devices = await _fetch(api)
            except (EcoFlowAuthError, EcoFlowApiError) as exc:
                _LOGGER.debug("Could not refresh the device list: %s", exc)
                self._devices = list(current)
                errors["base"] = "cannot_connect"
        listed = {d["sn"] for d in self._devices}
        devices = self._devices + [d for d in current if d["sn"] not in listed]
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DEVICES, default=[d["sn"] for d in current]
                    ): _device_selector(devices)
                }
            ),
            errors=errors,
        )
