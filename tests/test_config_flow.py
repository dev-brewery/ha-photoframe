"""Config flow tests."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import DOMAIN

from .conftest import BASE, ENTRY_DATA, HOST, PORT, mock_frame, setup_entry


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ENTRY_DATA, "host": f"  {HOST} "}
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Photo frame"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == f"{HOST}:{PORT}"


async def test_user_flow_invalid_auth_then_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(f"{BASE}/details/display", status=401)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    assert result["type"] is FlowResultType.FORM
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
    aioclient_mock.get(f"{BASE}/details/display", exc=aiohttp.ClientConnectionError)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    mock_frame(aioclient_mock)
    await setup_entry(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )
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
