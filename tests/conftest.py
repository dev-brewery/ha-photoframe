"""Fixtures for photoframe tests. The frame is always mocked; nothing is contacted."""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.photoframe.const import CONF_DEVICE_TRACKER, DOMAIN

TRACKER = "device_tracker.photoframe"
MAC_RAW = "B8-27-EB-8D-B6-6A"  # as the router tracker reports it
MAC = "b8:27:eb:8d:b6:6a"
HOST = "192.0.2.10"
PORT = 7777
ENTRY_DATA = {
    CONF_DEVICE_TRACKER: TRACKER,
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


@pytest.fixture(autouse=True)
async def frame_tracker(hass: HomeAssistant) -> None:
    """The frame's router device_tracker, home with an IP and MAC."""
    set_tracker(hass)


def set_tracker(
    hass: HomeAssistant,
    entity_id: str = TRACKER,
    *,
    ip: str | None = HOST,
    mac: str | None = MAC_RAW,
    name: str = "PhotoFrame",
) -> None:
    attrs: dict[str, Any] = {"friendly_name": name, "source_type": "router"}
    if ip:
        attrs["ip"] = ip
    if mac:
        attrs["mac"] = mac
    hass.states.async_set(entity_id, "home" if ip else "not_home", attrs)


def base(host: str = HOST, port: int = PORT) -> str:
    return f"http://{host}:{port}"


def mock_frame(
    aioclient_mock: AiohttpClientMocker,
    *,
    host: str = HOST,
    port: int = PORT,
    albums: dict[str, Any] | None = ALBUMS,
    display: bool = True,
) -> None:
    """Register the frame's read endpoints. albums=None means no album API."""
    url = base(host, port)
    aioclient_mock.get(f"{url}/details/display", json={"display": display})
    aioclient_mock.get(
        f"{url}/details/version",
        json={"date": "Tue Oct 7", "commit": "c768bde0123456789", "branch": "master"},
    )
    aioclient_mock.get(f"{url}/details/network", json={"network": True})
    aioclient_mock.get(
        f"{url}/details/hardware",
        json={
            "undervoltage": False,
            "frequency": False,
            "throttling": True,
            "temperature": False,
        },
    )
    aioclient_mock.get(f"{url}/setting", json=SETTINGS)
    aioclient_mock.get(f"{url}/rotation", json={"rotation": 90})
    aioclient_mock.get(f"{url}/overscan", json={"overscan": False})
    if albums is None:
        aioclient_mock.get(f"{url}/album", status=404)
    else:
        aioclient_mock.get(f"{url}/album", json=albums)


def mock_commands(
    aioclient_mock: AiohttpClientMocker, *urls: str, host: str = HOST
) -> None:
    for url in urls:
        method, path = url.split(" ", 1)
        body = {"status": True} if path.startswith("/setting") else {"ok": True}
        aioclient_mock.request(method, f"{base(host)}{path}", json=body)


async def setup_entry(
    hass: HomeAssistant,
    *,
    data: dict[str, Any] = ENTRY_DATA,
    unique_id: str = MAC,
    title: str = "PhotoFrame",
    expect_success: bool = True,
) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title=title, unique_id=unique_id, data=data)
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if expect_success:
        assert result
    return entry


def called(
    aioclient_mock: AiohttpClientMocker, method: str, path: str, host: str = HOST
) -> bool:
    return any(
        m == method and str(u) == f"{base(host)}{path}"
        for m, u, *_ in aioclient_mock.mock_calls
    )
