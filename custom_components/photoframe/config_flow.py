"""Config flow for the photoframe integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PhotoframeAuthError, PhotoframeClient, PhotoframeError
from .const import DEFAULT_PORT, DOMAIN

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class PhotoframeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a frame by host and HTTP credentials."""

    VERSION = 1

    async def _validate(self, data: Mapping[str, Any]) -> str | None:
        """Return an error key, or None if the frame accepted the credentials."""
        client = PhotoframeClient(
            async_get_clientsession(self.hass),
            data[CONF_HOST],
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
            user_input[CONF_HOST] = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(
                f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            )
            self._abort_if_unique_id_configured()
            if (error := await self._validate(user_input)) is None:
                return self.async_create_entry(title="Photo frame", data=user_input)
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
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
