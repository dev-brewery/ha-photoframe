"""The photoframe integration: a dev-brewery/photoframe frame as a HA device."""

from __future__ import annotations

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PhotoframeClient
from .coordinator import PhotoframeConfigEntry, PhotoframeCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: PhotoframeConfigEntry) -> bool:
    client = PhotoframeClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = PhotoframeCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PhotoframeConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
