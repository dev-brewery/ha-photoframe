"""Async client for the photoframe HTTP API (dev-brewery/photoframe).

Every endpoint takes its arguments in the URL path; none reads a request body.
All routes sit behind HTTP Basic auth.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import REQUEST_TIMEOUT


class PhotoframeError(Exception):
    """Base error for the photoframe API."""


class PhotoframeConnectionError(PhotoframeError):
    """The frame could not be reached or answered with a server error."""


class PhotoframeAuthError(PhotoframeError):
    """The frame rejected the credentials."""


class PhotoframeNotSupported(PhotoframeError):
    """The frame's software does not have this endpoint."""


def _segment(value: Any) -> str:
    """Encode one URL path segment.

    Werkzeug decodes %2F before routing, so a slash would split the segment.
    The frame turns '+' back into '/' for the one setting that needs it
    (timezone), so send slashes as '+'.
    """
    return quote(str(value).replace("/", "+"), safe="+")


class PhotoframeClient:
    """Talks to one frame.

    Frames get their address from DHCP, so the client never stores one:
    `host_fn` returns the frame's current address for every request and raises
    PhotoframeConnectionError when there is none.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host_fn: Callable[[], str],
        port: int,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._host_fn = host_fn
        self._port = port
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}

    async def _request(self, method: str, path: str) -> Any:
        url = f"http://{self._host_fn()}:{self._port}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                resp = await self._session.request(method, url, headers=self._headers)
                async with resp:
                    if resp.status == 401:
                        raise PhotoframeAuthError("Invalid username or password")
                    if resp.status == 404:
                        raise PhotoframeNotSupported(f"{method} {path} returned 404")
                    if resp.status >= 400:
                        raise PhotoframeConnectionError(
                            f"{method} {path} returned HTTP {resp.status}"
                        )
                    return await resp.json(content_type=None)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise PhotoframeConnectionError(f"{method} {path} failed: {err}") from err

    # Reads

    async def get_display(self) -> bool:
        return bool((await self._request("GET", "/details/display"))["display"])

    async def get_settings(self) -> dict[str, Any]:
        return await self._request("GET", "/setting")

    async def get_version(self) -> dict[str, str]:
        return await self._request("GET", "/details/version")

    async def get_network(self) -> bool:
        return bool((await self._request("GET", "/details/network"))["network"])

    async def get_hardware(self) -> dict[str, bool]:
        return await self._request("GET", "/details/hardware")

    async def get_rotation(self) -> int:
        return int((await self._request("GET", "/rotation"))["rotation"])

    async def get_overscan(self) -> bool:
        return bool((await self._request("GET", "/overscan"))["overscan"])

    async def get_albums(self) -> dict[str, Any]:
        """Return {"active": {...} | None, "albums": [...]}.

        Raises PhotoframeNotSupported until the frame has the album API
        proposed in dev-brewery/photoframe#80.
        """
        return await self._request("GET", "/album")

    # Commands

    async def control(self, command: str) -> None:
        await self._request("GET", f"/control/{_segment(command)}")

    async def set_setting(self, key: str, value: Any) -> None:
        result = await self._request(
            "PUT", f"/setting/{_segment(key)}/{_segment(value)}"
        )
        if not result.get("status", False):
            raise PhotoframeError(f"Frame rejected setting {key}={value}")

    async def set_rotation(self, degrees: int) -> None:
        await self._request("PUT", f"/rotation/{int(degrees)}")

    async def set_overscan(self, enabled: bool) -> None:
        await self._request("PUT", f"/overscan/{'true' if enabled else 'false'}")

    async def set_album(self, album_id: str | None) -> None:
        """Show only this album, or all albums when album_id is None."""
        await self._request("PUT", f"/album/{_segment(album_id or 'all')}")

    async def reboot(self) -> None:
        await self._request("GET", "/maintenance/reboot")
