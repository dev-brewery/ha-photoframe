"""Upgrading a 0.1.0 entry (fixed host) to a device_tracker-based one."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import CONF_DEVICE_TRACKER, DOMAIN

from .conftest import HOST, MAC, PORT, TRACKER, mock_frame, set_tracker

OLD_UID = f"{HOST}:{PORT}"
V010_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_USERNAME: "frame",
    CONF_PASSWORD: "secret",
}


def _v010_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A 0.1.0 entry whose device the user renamed and put in an area."""
    entry = MockConfigEntry(
        domain=DOMAIN, title="Photo frame", unique_id=OLD_UID, data=V010_DATA
    )
    entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, OLD_UID)},
        name="Photo frame",
    )
    dr.async_get(hass).async_update_device(
        device.id, name_by_user="Living Room Photoframe", area_id="living_room"
    )
    ent = er.async_get(hass)
    ent.async_get_or_create(
        "switch",
        DOMAIN,
        f"{OLD_UID}_screen",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="living_room_photoframe",
    )
    ent.async_get_or_create(
        "button",
        DOMAIN,
        f"{OLD_UID}_next_image",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="living_room_photoframe_next_photo",
    )
    return entry


async def test_upgrade_keeps_device_and_entity_ids(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = _v010_entry(hass)
    (before,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.unique_id == MAC
    assert CONF_HOST not in entry.data
    assert entry.data[CONF_DEVICE_TRACKER] == TRACKER

    # Same device record: the user's name and area survive.
    (device,) = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    assert device.id == before.id
    assert device.identifiers == {(DOMAIN, MAC)}
    assert device.name_by_user == "Living Room Photoframe"
    assert device.area_id == "living_room"

    # Same entity IDs, now keyed on the MAC.
    ent = er.async_get(hass)
    assert ent.async_get_entity_id("switch", DOMAIN, f"{MAC}_screen") == (
        "switch.living_room_photoframe"
    )
    assert ent.async_get_entity_id("button", DOMAIN, f"{MAC}_next_image") == (
        "button.living_room_photoframe_next_photo"
    )
    assert ent.async_get_entity_id("switch", DOMAIN, f"{OLD_UID}_screen") is None
    assert hass.states.get("switch.living_room_photoframe").state == "on"


async def test_upgrade_waits_for_a_tracker_with_that_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    set_tracker(hass, ip="192.0.2.99")  # tracker hasn't seen the old address
    entry = _v010_entry(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.unique_id == OLD_UID
    assert entry.data == V010_DATA
