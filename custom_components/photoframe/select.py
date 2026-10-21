"""Selects: the album shown, plus multiple-choice frame settings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import PhotoframeClient
from .const import (
    ALL_ALBUMS,
    DOMAIN,
    IMAGE_SIZING_OPTIONS,
    OFFLINE_BEHAVIOR_OPTIONS,
    POWERSAVE_OPTIONS,
    ROTATION_OPTIONS,
)
from .coordinator import PhotoframeConfigEntry, PhotoframeData
from .entity import PhotoframeEntity, frame_command


@dataclass(frozen=True, kw_only=True)
class PhotoframeSettingSelectDescription(SelectEntityDescription):
    current_fn: Callable[[PhotoframeData], str | None]
    select_fn: Callable[[PhotoframeClient, str], Awaitable[None]]


SETTING_SELECTS = (
    PhotoframeSettingSelectDescription(
        key="image_sizing",
        entity_category=EntityCategory.CONFIG,
        options=IMAGE_SIZING_OPTIONS,
        current_fn=lambda d: d.settings.get("imagesizing"),
        select_fn=lambda c, o: c.set_setting("imagesizing", o),
    ),
    PhotoframeSettingSelectDescription(
        key="powersave",
        entity_category=EntityCategory.CONFIG,
        options=POWERSAVE_OPTIONS,
        current_fn=lambda d: (d.settings.get("powersave") or "none").replace("+", "_"),
        select_fn=lambda c, o: c.set_setting("powersave", o.replace("_", "+")),
    ),
    PhotoframeSettingSelectDescription(
        key="offline_behavior",
        entity_category=EntityCategory.CONFIG,
        options=OFFLINE_BEHAVIOR_OPTIONS,
        current_fn=lambda d: d.settings.get("offline-behavior"),
        select_fn=lambda c, o: c.set_setting("offline-behavior", o),
    ),
    PhotoframeSettingSelectDescription(
        key="rotation",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=ROTATION_OPTIONS,
        current_fn=lambda d: str(d.rotation),
        select_fn=lambda c, o: c.set_rotation(int(o)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhotoframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [
        PhotoframeSettingSelect(coordinator, d) for d in SETTING_SELECTS
    ]
    if coordinator.supports_albums:
        entities.append(PhotoframeAlbumSelect(coordinator))
    async_add_entities(entities)


class PhotoframeSettingSelect(PhotoframeEntity, SelectEntity):
    entity_description: PhotoframeSettingSelectDescription

    def __init__(
        self, coordinator, description: PhotoframeSettingSelectDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def current_option(self) -> str | None:
        value = self.entity_description.current_fn(self.coordinator.data)
        return value if value in self.options else None

    @frame_command
    async def async_select_option(self, option: str) -> None:
        await self.entity_description.select_fn(self.coordinator.client, option)


class PhotoframeAlbumSelect(PhotoframeEntity, SelectEntity):
    """Which Immich album the frame shows. Exposed to Google as a mode."""

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "album")

    @property
    def options(self) -> list[str]:
        return self.coordinator.data.album_options

    @property
    def current_option(self) -> str:
        return self.coordinator.data.active_album_option

    @frame_command
    async def async_select_option(self, option: str) -> None:
        if option == ALL_ALBUMS:
            album_id = None
        elif (album_id := self.coordinator.data.album_names.get(option)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_album",
                translation_placeholders={"album": option},
            )
        await self.coordinator.client.set_album(album_id)
