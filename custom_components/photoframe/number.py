"""Numbers: slideshow interval and display schedule hours."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PhotoframeConfigEntry
from .entity import PhotoframeEntity, frame_command


@dataclass(frozen=True, kw_only=True)
class PhotoframeNumberDescription(NumberEntityDescription):
    setting: str


NUMBERS = (
    PhotoframeNumberDescription(
        key="interval",
        setting="interval",
        entity_category=EntityCategory.CONFIG,
        device_class=NumberDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        native_min_value=5,
        native_max_value=86400,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    PhotoframeNumberDescription(
        key="display_on_hour",
        setting="display-on",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=23,
        native_step=1,
        mode=NumberMode.BOX,
    ),
    PhotoframeNumberDescription(
        key="display_off_hour",
        setting="display-off",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=23,
        native_step=1,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhotoframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PhotoframeNumber(coordinator, d) for d in NUMBERS)


class PhotoframeNumber(PhotoframeEntity, NumberEntity):
    entity_description: PhotoframeNumberDescription

    def __init__(self, coordinator, description: PhotoframeNumberDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.settings.get(self.entity_description.setting)
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @frame_command
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.set_setting(
            self.entity_description.setting, int(value)
        )
