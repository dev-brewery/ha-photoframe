"""The photoframe integration: a dev-brewery/photoframe frame as a HA device."""

from __future__ import annotations

import logging

from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PhotoframeClient
from .const import CONF_DEVICE_TRACKER, DOMAIN
from .coordinator import PhotoframeConfigEntry, PhotoframeCoordinator
from .tracker import host_resolver, tracker_mac

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: PhotoframeConfigEntry) -> bool:
    if CONF_DEVICE_TRACKER not in entry.data:
        await _async_adopt_tracker(hass, entry)
    client = PhotoframeClient(
        async_get_clientsession(hass),
        host_resolver(hass, entry.data[CONF_DEVICE_TRACKER]),
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


async def _async_adopt_tracker(
    hass: HomeAssistant, entry: PhotoframeConfigEntry
) -> None:
    """Upgrade a 0.1.0 entry, which stored a fixed host, to a device_tracker.

    The stored host is used once, to find the tracker that currently reports
    it, and then dropped. The entry, device and entities are re-keyed from
    "host:port" to the tracker's MAC, keeping their registry entries, so
    names, areas and entity IDs are unchanged.

    Trackers may not have reported yet during startup, so setup is retried
    until one does.
    """
    host = entry.data[CONF_HOST]
    trackers = sorted(
        state.entity_id
        for state in hass.states.async_all("device_tracker")
        if state.attributes.get("ip") == host
        and tracker_mac(hass, state.entity_id) is not None
    )
    macs = {tracker_mac(hass, t) for t in trackers}
    if len(macs) != 1:
        raise ConfigEntryNotReady(
            f"Upgrading this frame needs exactly one device_tracker reporting "
            f"{host} with a MAC address; found {trackers or 'none'}"
        )
    tracker, mac = trackers[0], macs.pop()
    old_uid = entry.unique_id

    @callback
    def rekey(entity: er.RegistryEntry) -> dict[str, str] | None:
        if entity.unique_id.startswith(f"{old_uid}_"):
            return {"new_unique_id": mac + entity.unique_id[len(old_uid) :]}
        return None

    await er.async_migrate_entries(hass, entry.entry_id, rekey)

    devices = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        if (DOMAIN, old_uid) in device.identifiers:
            devices.async_update_device(device.id, new_identifiers={(DOMAIN, mac)})

    data = {k: v for k, v in entry.data.items() if k != CONF_HOST}
    hass.config_entries.async_update_entry(
        entry, data={**data, CONF_DEVICE_TRACKER: tracker}, unique_id=mac
    )
    _LOGGER.info("Upgraded photo frame %s to use %s (%s)", host, tracker, mac)
