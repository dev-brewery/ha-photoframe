"""Config flow tests."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import CONF_DEVICE_TRACKER, DOMAIN

from .conftest import (
    ENTRY_DATA,
    MAC,
    TRACKER,
    base,
    mock_frame,
    set_tracker,
    setup_entry,
)


async def _submit(hass: HomeAssistant, data=ENTRY_DATA):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return await hass.config_entries.flow.async_configure(result["flow_id"], data)


async def test_user_flow_identifies_frame_by_tracker_mac(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    result = await _submit(hass)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "PhotoFrame"  # the tracker's name
    assert result["data"] == ENTRY_DATA  # no address stored
    assert result["result"].unique_id == MAC


async def test_user_flow_invalid_auth_then_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{base()}/details/display", status=401)
    result = await _submit(hass)
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    mock_frame(aioclient_mock)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{base()}/details/display", exc=aiohttp.ClientConnectionError)
    result = await _submit(hass)
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_tracker_without_ip(hass: HomeAssistant) -> None:
    set_tracker(hass, ip=None)
    result = await _submit(hass)
    assert result["errors"] == {"base": "no_ip"}


async def test_user_flow_tracker_without_mac(hass: HomeAssistant) -> None:
    set_tracker(hass, mac=None)
    result = await _submit(hass)
    assert result["errors"] == {"base": "no_mac"}


async def test_same_frame_at_new_address_is_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    # New DHCP lease, and a second tracker for the same frame (same MAC).
    set_tracker(hass, ip="192.0.2.99")
    set_tracker(hass, "device_tracker.raspberrypi", ip="192.0.2.99")

    for tracker in (TRACKER, "device_tracker.raspberrypi"):
        result = await _submit(hass, {**ENTRY_DATA, CONF_DEVICE_TRACKER: tracker})
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_reauth_updates_password(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"username": "frame", CONF_PASSWORD: "new-secret"}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-secret"


async def test_reconfigure_to_another_tracker_for_the_same_frame(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    mock_frame(aioclient_mock, host="192.0.2.50", port=7778)
    entry = await setup_entry(hass)
    set_tracker(hass, "device_tracker.raspberrypi", ip="192.0.2.50")

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_TRACKER: "device_tracker.raspberrypi", CONF_PORT: 7778},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_DEVICE_TRACKER] == "device_tracker.raspberrypi"
    assert entry.data[CONF_PORT] == 7778


async def test_reconfigure_rejects_a_different_frame(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    entry = await setup_entry(hass)
    set_tracker(hass, "device_tracker.other", ip="192.0.2.60", mac="AA-BB-CC-DD-EE-FF")

    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_DEVICE_TRACKER: "device_tracker.other", CONF_PORT: 7777},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "wrong_device"
    assert entry.data[CONF_DEVICE_TRACKER] == TRACKER
