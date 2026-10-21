"""Entity tests: state from polling, commands sent to the frame's current address."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import (
    ALL_ALBUMS,
    CONF_DEVICE_TRACKER,
    DOMAIN,
)

from .conftest import (
    ENTRY_DATA,
    MAC,
    base,
    called,
    mock_commands,
    mock_frame,
    set_tracker,
    setup_entry,
)


def entity_id(
    hass: HomeAssistant, platform: str, key: str, mac: str = MAC
) -> str | None:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{mac}_{key}")


async def press(hass: HomeAssistant, entity: str) -> None:
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: entity}, blocking=True
    )


async def test_setup_creates_device_entities(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get(entity_id(hass, "switch", "screen"))
    assert state.state == STATE_ON
    # The screen switch carries the device's own name, which Google uses.
    assert state.attributes["friendly_name"] == "PhotoFrame"

    def state_of(platform: str, key: str) -> str:
        return hass.states.get(entity_id(hass, platform, key)).state

    assert state_of("number", "interval") == "60.0"
    assert state_of("select", "powersave") == "none"
    assert state_of("select", "image_sizing") == "blur"
    assert state_of("switch", "randomize_images") == STATE_ON
    assert state_of("binary_sensor", "throttling") == STATE_ON
    assert state_of("binary_sensor", "network") == STATE_ON


async def test_entity_ids_match_google_package(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """ha-config/packages/google_assistant.yaml relies on these IDs."""
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    assert entity_id(hass, "switch", "screen") == "switch.photoframe"
    assert entity_id(hass, "select", "album") == "select.photoframe_album"
    assert entity_id(hass, "button", "next_image") == "button.photoframe_next_photo"
    assert (
        entity_id(hass, "button", "previous_image")
        == "button.photoframe_previous_photo"
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


async def test_follows_the_frame_to_a_new_address(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    await setup_entry(hass)

    # DHCP hands the frame a new address; the router tracker follows it.
    new_ip = "192.0.2.99"
    set_tracker(hass, ip=new_ip)
    mock_frame(aioclient_mock, host=new_ip)
    mock_commands(aioclient_mock, "GET /control/nextImage", host=new_ip)

    await press(hass, entity_id(hass, "button", "next_image"))
    assert called(aioclient_mock, "GET", "/control/nextImage", host=new_ip)
    assert not called(aioclient_mock, "GET", "/control/nextImage")


async def test_frame_off_the_network_makes_entities_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass)
    screen = entity_id(hass, "switch", "screen")

    set_tracker(hass, ip=None)
    calls_before = aioclient_mock.call_count

    # Before the next poll: a command fails clearly and sends nothing.
    with pytest.raises(HomeAssistantError, match="no IP address"):
        await press(hass, entity_id(hass, "button", "next_image"))
    assert aioclient_mock.call_count == calls_before

    # The next poll marks the frame unavailable.
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(screen).state == STATE_UNAVAILABLE


async def test_two_frames_side_by_side(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    office_ip, office_mac = "192.0.2.20", "aa:bb:cc:dd:ee:ff"
    set_tracker(
        hass,
        "device_tracker.office_frame",
        ip=office_ip,
        mac="AA:BB:CC:DD:EE:FF",
        name="Office frame",
    )
    mock_frame(aioclient_mock)
    mock_frame(aioclient_mock, host=office_ip, albums=None)
    mock_commands(aioclient_mock, "GET /control/screenoff", host=office_ip)

    await setup_entry(hass)
    await setup_entry(
        hass,
        data={**ENTRY_DATA, CONF_DEVICE_TRACKER: "device_tracker.office_frame"},
        unique_id=office_mac,
        title="Office frame",
    )

    assert entity_id(hass, "switch", "screen") == "switch.photoframe"
    office_screen = entity_id(hass, "switch", "screen", mac=office_mac)
    assert office_screen == "switch.office_frame"
    # Each frame gets its own album support from its own API.
    assert entity_id(hass, "select", "album") is not None
    assert entity_id(hass, "select", "album", mac=office_mac) is None

    await hass.services.async_call(
        "switch", "turn_off", {ATTR_ENTITY_ID: office_screen}, blocking=True
    )
    assert called(aioclient_mock, "GET", "/control/screenoff", host=office_ip)
    assert not called(aioclient_mock, "GET", "/control/screenoff")


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
        await press(hass, entity_id(hass, "button", key))
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
    aioclient_mock.get(f"{base()}/control/nextImage", status=500)
    await setup_entry(hass)
    with pytest.raises(HomeAssistantError):
        await press(hass, entity_id(hass, "button", "next_image"))


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{base()}/details/version", status=401)
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass, expect_success=False)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
