"""Fixtures for photoframe tests. The frame is always mocked; nothing is contacted."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import DOMAIN

HOST = "192.0.2.10"
PORT = 7777
BASE = f"http://{HOST}:{PORT}"
ENTRY_DATA = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_USERNAME: "frame",
    CONF_PASSWORD: "secret",
}

SETTINGS = {
    "interval": 60,
    "display-on": 4,
    "display-off": 22,
    "imagesizing": "blur",
    "powersave": "",
    "offline-behavior": "wait",
    "randomize_images": 1,
    "enable-cache": 1,
    "timezone": "America/New_York",
}
ALBUMS = {
    "active": {"albumId": "a2", "name": "Vacation"},
    "albums": [
        {"albumId": "a1", "name": "Family", "assetCount": 10},
        {"albumId": "a2", "name": "Vacation", "assetCount": 20},
        {"albumId": "a3", "name": "Vacation", "assetCount": 5},
    ],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def mock_frame(
    aioclient_mock: AiohttpClientMocker,
    *,
    albums: dict[str, Any] | None = ALBUMS,
    display: bool = True,
) -> None:
    """Register the frame's read endpoints. albums=None means no album API."""
    aioclient_mock.get(f"{BASE}/details/display", json={"display": display})
    aioclient_mock.get(
        f"{BASE}/details/version",
        json={"date": "Tue Oct 7", "commit": "c768bde0123456789", "branch": "master"},
    )
    aioclient_mock.get(f"{BASE}/details/network", json={"network": True})
    aioclient_mock.get(
        f"{BASE}/details/hardware",
        json={
            "undervoltage": False,
            "frequency": False,
            "throttling": True,
            "temperature": False,
        },
    )
    aioclient_mock.get(f"{BASE}/setting", json=SETTINGS)
    aioclient_mock.get(f"{BASE}/rotation", json={"rotation": 90})
    aioclient_mock.get(f"{BASE}/overscan", json={"overscan": False})
    if albums is None:
        aioclient_mock.get(f"{BASE}/album", status=404)
    else:
        aioclient_mock.get(f"{BASE}/album", json=albums)


def mock_commands(aioclient_mock: AiohttpClientMocker, *urls: str) -> None:
    for url in urls:
        method, path = url.split(" ", 1)
        body = {"status": True} if path.startswith("/setting") else {"ok": True}
        aioclient_mock.request(method, f"{BASE}{path}", json=body)


async def setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Photo frame",
        unique_id=f"{HOST}:{PORT}",
        data=ENTRY_DATA,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def called(aioclient_mock: AiohttpClientMocker, method: str, path: str) -> bool:
    return any(
        m == method and str(u) == f"{BASE}{path}"
        for m, u, *_ in aioclient_mock.mock_calls
    )
