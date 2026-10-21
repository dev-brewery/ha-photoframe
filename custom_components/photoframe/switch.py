"""Switches: the screen, plus on/off frame settings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import PhotoframeClient
from .coordinator import PhotoframeConfigEntry, PhotoframeData
from .entity import PhotoframeEntity, frame_command


def _flag(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true")


@dataclass(frozen=True, kw_only=True)
class PhotoframeSwitchDescription(SwitchEntityDescription):
    is_on_fn: Callable[[PhotoframeData], bool]
    set_fn: Callable[[PhotoframeClient, bool], Awaitable[None]]


SWITCHES = (
    PhotoframeSwitchDescription(
        key="screen",
        name=None,  # the device's main entity: "Photo frame" itself
        is_on_fn=lambda d: d.display,
        set_fn=lambda c, on: c.control("screenon" if on else "screenoff"),
    ),
    PhotoframeSwitchDescription(
        key="randomize_images",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: _flag(d.settings.get("randomize_images")),
        set_fn=lambda c, on: c.set_setting("randomize_images", int(on)),
    ),
    PhotoframeSwitchDescription(
        key="enable_cache",
        entity_category=EntityCategory.CONFIG,
        is_on_fn=lambda d: _flag(d.settings.get("enable-cache")),
        set_fn=lambda c, on: c.set_setting("enable-cache", int(on)),
    ),
    PhotoframeSwitchDescription(
        key="overscan",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        is_on_fn=lambda d: d.overscan,
        set_fn=lambda c, on: c.set_overscan(on),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhotoframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PhotoframeSwitch(coordinator, d) for d in SWITCHES)


class PhotoframeSwitch(PhotoframeEntity, SwitchEntity):
    entity_description: PhotoframeSwitchDescription

    def __init__(self, coordinator, description: PhotoframeSwitchDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.name is None:
            self._attr_name = None
            self._attr_translation_key = None

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)

    @frame_command
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.client, True)

    @frame_command
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.entity_description.set_fn(self.coordinator.client, False)
