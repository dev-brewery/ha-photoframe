"""Polling coordinator for the photoframe integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    PhotoframeAuthError,
    PhotoframeClient,
    PhotoframeError,
    PhotoframeNotSupported,
)
from .const import ALL_ALBUMS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type PhotoframeConfigEntry = ConfigEntry[PhotoframeCoordinator]


@dataclass
class PhotoframeData:
    """One poll of the frame."""

    display: bool
    settings: dict[str, Any]
    network: bool
    hardware: dict[str, bool]
    rotation: int
    overscan: bool
    # None when the frame has no album API yet.
    albums: list[dict[str, Any]] | None = None
    active_album_id: str | None = None
    album_names: dict[str, str] = field(default_factory=dict)  # option -> albumId

    @property
    def album_options(self) -> list[str]:
        return [ALL_ALBUMS, *self.album_names]

    @property
    def active_album_option(self) -> str:
        for option, album_id in self.album_names.items():
            if album_id == self.active_album_id:
                return option
        return ALL_ALBUMS


def _album_names(albums: list[dict[str, Any]]) -> dict[str, str]:
    """Map a unique, speakable option name to each albumId.

    Immich allows duplicate album names; later duplicates get a counter.
    """
    names: dict[str, str] = {}
    for album in albums:
        base = str(album.get("name") or album["albumId"]).strip()
        name, n = base, 2
        while name in names or name == ALL_ALBUMS:
            name, n = f"{base} ({n})", n + 1
        names[name] = album["albumId"]
    return names


class PhotoframeCoordinator(DataUpdateCoordinator[PhotoframeData]):
    """Polls the frame and owns its client."""

    config_entry: PhotoframeConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PhotoframeConfigEntry,
        client: PhotoframeClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client
        self.version: dict[str, str] = {}
        self.supports_albums = True

    async def _async_setup(self) -> None:
        try:
            self.version = await self.client.get_version()
        except PhotoframeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PhotoframeError as err:
            # The version is only cosmetic (device info); git may be missing.
            _LOGGER.debug("Could not read frame version: %s", err)

    async def _async_update_data(self) -> PhotoframeData:
        client = self.client
        try:
            data = PhotoframeData(
                display=await client.get_display(),
                settings=await client.get_settings(),
                network=await client.get_network(),
                hardware=await client.get_hardware(),
                rotation=await client.get_rotation(),
                overscan=await client.get_overscan(),
            )
            if self.supports_albums:
                try:
                    albums = await client.get_albums()
                except PhotoframeNotSupported:
                    _LOGGER.info(
                        "Frame has no album API (/album); album selection disabled"
                    )
                    self.supports_albums = False
                else:
                    data.albums = albums.get("albums") or []
                    data.album_names = _album_names(data.albums)
                    active = albums.get("active") or {}
                    data.active_album_id = active.get("albumId")
        except PhotoframeAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except PhotoframeError as err:
            raise UpdateFailed(str(err)) from err
        return data
