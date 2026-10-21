"""Base entity for the photoframe integration."""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any, Concatenate

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PhotoframeError
from .const import DOMAIN
from .coordinator import PhotoframeCoordinator


class PhotoframeEntity(CoordinatorEntity[PhotoframeCoordinator]):
    """An entity belonging to one frame."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PhotoframeCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"
        self._attr_translation_key = key
        commit = coordinator.version.get("commit")
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="dev-brewery",
            model="photoframe",
            sw_version=commit[:7] if commit else None,
            configuration_url=f"http://{entry.unique_id}",
        )


def frame_command[E: PhotoframeEntity, **P](
    func: Callable[Concatenate[E, P], Awaitable[Any]],
) -> Callable[Concatenate[E, P], Coroutine[Any, Any, None]]:
    """Turn API errors into HomeAssistantError and refresh state afterwards."""

    @functools.wraps(func)
    async def wrapper(self: E, *args: P.args, **kwargs: P.kwargs) -> None:
        try:
            await func(self, *args, **kwargs)
        except PhotoframeError as err:
            raise HomeAssistantError(f"Photo frame command failed: {err}") from err
        await self.coordinator.async_request_refresh()

    return wrapper
