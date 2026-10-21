"""Buttons: slideshow navigation and reboot."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import PhotoframeClient
from .coordinator import PhotoframeConfigEntry
from .entity import PhotoframeEntity, frame_command


@dataclass(frozen=True, kw_only=True)
class PhotoframeButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[PhotoframeClient], Awaitable[None]]
    # nextAlbum/prevAlbum are no-ops on the frame until the album API lands
    # (dev-brewery/photoframe#80), so these only appear alongside it.
    needs_albums: bool = False


BUTTONS = (
    PhotoframeButtonDescription(
        key="next_image", press_fn=lambda c: c.control("nextImage")
    ),
    PhotoframeButtonDescription(
        key="previous_image", press_fn=lambda c: c.control("prevImage")
    ),
    PhotoframeButtonDescription(
        key="next_album", press_fn=lambda c: c.control("nextAlbum"), needs_albums=True
    ),
    PhotoframeButtonDescription(
        key="previous_album",
        press_fn=lambda c: c.control("prevAlbum"),
        needs_albums=True,
    ),
    PhotoframeButtonDescription(
        key="reboot",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        press_fn=lambda c: c.reboot(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhotoframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        PhotoframeButton(coordinator, d)
        for d in BUTTONS
        if coordinator.supports_albums or not d.needs_albums
    )


class PhotoframeButton(PhotoframeEntity, ButtonEntity):
    entity_description: PhotoframeButtonDescription

    def __init__(self, coordinator, description: PhotoframeButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @frame_command
    async def async_press(self) -> None:
        await self.entity_description.press_fn(self.coordinator.client)
