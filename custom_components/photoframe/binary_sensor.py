"""Diagnostic binary sensors: network and Raspberry Pi health flags."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import PhotoframeConfigEntry, PhotoframeData
from .entity import PhotoframeEntity


@dataclass(frozen=True, kw_only=True)
class PhotoframeBinarySensorDescription(BinarySensorEntityDescription):
    is_on_fn: Callable[[PhotoframeData], bool]


# The hardware flags come from `vcgencmd get_throttled` and are sticky since
# boot: "on" means it happened at some point, not that it is happening now.
BINARY_SENSORS = (
    PhotoframeBinarySensorDescription(
        key="network",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: d.network,
    ),
    PhotoframeBinarySensorDescription(
        key="undervoltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.hardware.get("undervoltage")),
    ),
    PhotoframeBinarySensorDescription(
        key="throttling",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.hardware.get("throttling")),
    ),
    PhotoframeBinarySensorDescription(
        key="temperature_limit",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda d: bool(d.hardware.get("temperature")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhotoframeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(PhotoframeBinarySensor(coordinator, d) for d in BINARY_SENSORS)


class PhotoframeBinarySensor(PhotoframeEntity, BinarySensorEntity):
    entity_description: PhotoframeBinarySensorDescription

    def __init__(
        self, coordinator, description: PhotoframeBinarySensorDescription
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        return self.entity_description.is_on_fn(self.coordinator.data)
