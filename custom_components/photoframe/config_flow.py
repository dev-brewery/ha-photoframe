"""Config flow for the photoframe integration.

A frame is chosen by its device_tracker, never by address: the tracker's MAC
is the frame's unique ID and its current IP is looked up on every request.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PhotoframeAuthError, PhotoframeClient, PhotoframeError
from .const import CONF_DEVICE_TRACKER, DEFAULT_PORT, DOMAIN
from .tracker import host_resolver, tracker_ip, tracker_mac, tracker_name

_LOGGER = logging.getLogger(__name__)

LOCATION_SCHEMA = {
    vol.Required(CONF_DEVICE_TRACKER): selector.EntitySelector(
        selector.EntitySelectorConfig(domain="device_tracker")
    ),
    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
}
CREDENTIALS_SCHEMA = {
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
}
USER_SCHEMA = vol.Schema({**LOCATION_SCHEMA, **CREDENTIALS_SCHEMA})
RECONFIGURE_SCHEMA = vol.Schema(LOCATION_SCHEMA)
REAUTH_SCHEMA = vol.Schema(CREDENTIALS_SCHEMA)


class PhotoframeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a frame by its device_tracker and HTTP credentials."""

    VERSION = 1

    def _tracker_error(self, data: Mapping[str, Any]) -> str | None:
        tracker = data[CONF_DEVICE_TRACKER]
        if tracker_mac(self.hass, tracker) is None:
            return "no_mac"
        if tracker_ip(self.hass, tracker) is None:
            return "no_ip"
        return None

    async def _validate(self, data: Mapping[str, Any]) -> str | None:
        """Return an error key, or None if the frame accepted the credentials."""
        if error := self._tracker_error(data):
            return error
        client = PhotoframeClient(
            async_get_clientsession(self.hass),
            host_resolver(self.hass, data[CONF_DEVICE_TRACKER]),
            data[CONF_PORT],
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
        )
        try:
            await client.get_display()
        except PhotoframeAuthError:
            return "invalid_auth"
        except PhotoframeError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error talking to the frame")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            tracker = user_input[CONF_DEVICE_TRACKER]
            if (mac := tracker_mac(self.hass, tracker)) is not None:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
            if (error := await self._validate(user_input)) is None:
                return self.async_create_entry(
                    title=tracker_name(self.hass, tracker) or "Photo frame",
                    data=user_input,
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point the entry at another tracker or port for the same frame."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if (mac := tracker_mac(self.hass, data[CONF_DEVICE_TRACKER])) is not None:
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_mismatch(reason="wrong_device")
            if (error := await self._validate(data)) is None:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                RECONFIGURE_SCHEMA, user_input or entry.data
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            if (error := await self._validate(data)) is None:
                return self.async_update_reload_and_abort(entry, data=data)
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                REAUTH_SCHEMA, {CONF_USERNAME: entry.data[CONF_USERNAME]}
            ),
            errors=errors,
        )
