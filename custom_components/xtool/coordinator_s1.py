from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api_s1 import XToolS1Api
from .const import DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

# Seconds to wait after requesting status before reading _state on first connect.
# Gives the device time to push back the M2003 response.
_INITIAL_WAIT = 1.5

_WORK_STATE_MAP = {
    "S3":  "Idle",
    "S10": "Measuring",
    "S1":  "Ready",
    "S13": "Starting",
    "S14": "Running",
    "S19": "Finishing",
}


class XToolS1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for the xTool S1 (WebSocket protocol on port 8081)."""

    def __init__(self, hass: HomeAssistant, ip_address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"xtool_s1_{ip_address}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.ip_address = ip_address
        self.api = XToolS1Api(ip_address, async_get_clientsession(hass))

        # Cache static fields so they survive a bad poll tick
        self._cached_serial: str | None = None
        self._cached_firmware: str | None = None

    @staticmethod
    def map_work_state(raw: str | None) -> str:
        """Map M222 state code to a human-readable string."""
        if raw is None:
            return "Unknown"
        return _WORK_STATE_MAP.get(str(raw).strip(), f"Unknown ({raw})")

    async def _async_update_data(self) -> dict[str, Any]:
        if not self.api.connected:
            ok = await self.api.connect()
            if not ok:
                raise UpdateFailed(f"Cannot connect to S1 at {self.ip_address}:8081")
            # Request a full status dump and wait briefly for the device to push it back
            await self.api.request_status()
            await asyncio.sleep(_INITIAL_WAIT)

        # Send keepalive / position refresh
        await self.api.ping()

        # Snapshot the state that the background listener has been updating
        data = dict(self.api.state)

        # Cache static fields
        if data.get("serial_number"):
            self._cached_serial = data["serial_number"]
        if data.get("firmware_version"):
            self._cached_firmware = data["firmware_version"]

        data.setdefault("serial_number", self._cached_serial)
        data.setdefault("firmware_version", self._cached_firmware)

        return data
