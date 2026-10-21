"""Entity tests: state from polling, commands sent to the right endpoints."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import ALL_ALBUMS, DOMAIN

from .conftest import (
    BASE,
    ENTRY_DATA,
    HOST,
    PORT,
    called,
    mock_commands,
    mock_frame,
    setup_entry,
)

UID = f"{HOST}:{PORT}"


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{UID}_{key}")


async def test_setup_creates_device_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    screen = entity_id(hass, "switch", "screen")
    assert screen is not None
    state = hass.states.get(screen)
    assert state.state == STATE_ON
    # The screen switch carries the device's own name, which Google uses.
    assert state.attributes["friendly_name"] == "Photo frame"

    assert hass.states.get(entity_id(hass, "number", "interval")).state == "60.0"
    assert hass.states.get(entity_id(hass, "select", "powersave")).state == "none"
    assert hass.states.get(entity_id(hass, "select", "image_sizing")).state == "blur"
    assert (
        hass.states.get(entity_id(hass, "switch", "randomize_images")).state == STATE_ON
    )
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "throttling")).state
        == STATE_ON
    )
    assert (
        hass.states.get(entity_id(hass, "binary_sensor", "network")).state == STATE_ON
    )


async def test_entity_ids_match_google_package(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """ha-config/packages/google_assistant.yaml relies on these IDs."""
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    assert entity_id(hass, "switch", "screen") == "switch.photo_frame"
    assert entity_id(hass, "select", "album") == "select.photo_frame_album"
    assert entity_id(hass, "button", "next_image") == "button.photo_frame_next_photo"
    assert (
        entity_id(hass, "button", "previous_image")
        == "button.photo_frame_previous_photo"
    )


async def test_requests_carry_basic_auth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    # base64("frame:secret")
    assert {h["Authorization"] for *_, h in aioclient_mock.mock_calls} == {
        "Basic ZnJhbWU6c2VjcmV0"
    }


async def test_album_select_lists_albums_and_dedupes_names(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    state = hass.states.get(entity_id(hass, "select", "album"))
    assert state.attributes["options"] == [
        ALL_ALBUMS,
        "Family",
        "Vacation",
        "Vacation (2)",
    ]
    assert state.state == "Vacation"
    assert entity_id(hass, "button", "next_album") is not None


@pytest.mark.parametrize(
    ("option", "path"),
    [
        ("Vacation (2)", "/album/a3"),
        ("Family", "/album/a1"),
        (ALL_ALBUMS, "/album/all"),
    ],
)
async def test_album_select_sends_album_id(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, option: str, path: str
) -> None:
    mock_frame(aioclient_mock)
    mock_commands(aioclient_mock, f"PUT {path}")
    await setup_entry(hass)
    await hass.services.async_call(
        "select",
        "select_option",
        {ATTR_ENTITY_ID: entity_id(hass, "select", "album"), "option": option},
        blocking=True,
    )
    assert called(aioclient_mock, "PUT", path)


async def test_without_album_api_no_album_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock, albums=None)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert entity_id(hass, "select", "album") is None
    assert entity_id(hass, "button", "next_album") is None
    assert entity_id(hass, "button", "next_image") is not None


@pytest.mark.parametrize(
    ("service", "path"),
    [("turn_off", "/control/screenoff"), ("turn_on", "/control/screenon")],
)
async def test_screen_switch(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, service: str, path: str
) -> None:
    mock_frame(aioclient_mock)
    mock_commands(aioclient_mock, f"GET {path}")
    await setup_entry(hass)
    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: entity_id(hass, "switch", "screen")},
        blocking=True,
    )
    assert called(aioclient_mock, "GET", path)


async def test_buttons(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    mock_commands(aioclient_mock, "GET /control/nextImage", "GET /maintenance/reboot")
    await setup_entry(hass)
    for key, path in (
        ("next_image", "/control/nextImage"),
        ("reboot", "/maintenance/reboot"),
    ):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id(hass, "button", key)},
            blocking=True,
        )
        assert called(aioclient_mock, "GET", path)


async def test_settings_are_sent_in_the_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    mock_commands(
        aioclient_mock,
        "PUT /setting/interval/120",
        "PUT /setting/powersave/sensor+schedule",
        "PUT /setting/randomize_images/0",
    )
    await setup_entry(hass)
    await hass.services.async_call(
        "number",
        "set_value",
        {ATTR_ENTITY_ID: entity_id(hass, "number", "interval"), "value": 120},
        blocking=True,
    )
    await hass.services.async_call(
        "select",
        "select_option",
        {
            ATTR_ENTITY_ID: entity_id(hass, "select", "powersave"),
            "option": "sensor_schedule",
        },
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {ATTR_ENTITY_ID: entity_id(hass, "switch", "randomize_images")},
        blocking=True,
    )
    assert called(aioclient_mock, "PUT", "/setting/interval/120")
    assert called(aioclient_mock, "PUT", "/setting/powersave/sensor+schedule")
    assert called(aioclient_mock, "PUT", "/setting/randomize_images/0")


async def test_command_failure_raises(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    aioclient_mock.get(f"{BASE}/control/nextImage", status=500)
    await setup_entry(hass)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "button",
            "press",
            {ATTR_ENTITY_ID: entity_id(hass, "button", "next_image")},
            blocking=True,
        )


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE}/details/version", status=401)
    mock_frame(aioclient_mock)
    entry = await setup_entry_expect_fail(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]


async def setup_entry_expect_fail(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=UID, data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
