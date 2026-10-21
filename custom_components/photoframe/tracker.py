"""Find a frame through its device_tracker.

Frames get their address from DHCP. The device_tracker (e.g. from the router
integration) follows the frame and reports its current `ip`, and its `mac`
is the frame's stable identity. No address is ever stored.
"""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from .api import PhotoframeConnectionError


def tracker_ip(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    return state.attributes.get("ip") if state else None


def tracker_mac(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    mac = state.attributes.get("mac") if state else None
    return format_mac(mac) if mac else None


def tracker_name(hass: HomeAssistant, entity_id: str) -> str | None:
    state = hass.states.get(entity_id)
    return state.name if state else None


def host_resolver(hass: HomeAssistant, entity_id: str):
    """Return a host_fn for PhotoframeClient bound to this tracker."""

    def resolve() -> str:
        if not (ip := tracker_ip(hass, entity_id)):
            raise PhotoframeConnectionError(
                f"{entity_id} reports no IP address; is the frame on the network?"
            )
        return ip

    return resolve
