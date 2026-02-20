from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api_d1 import XToolD1Api
from .const import DEFAULT_UPDATE_INTERVAL


class XToolD1Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, ip_address: str) -> None:
        super().__init__(
            hass,
            name=f"xtool_d1_{ip_address}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.ip_address = ip_address
        self.api = XToolD1Api(ip_address, async_get_clientsession(hass))

        # cache static-ish
        self._machine_type: str | None = None

    def _map_working_state(self, sta: str | None) -> str:
        # based on common D1 mapping:
        # "0" idle, "1" running via API, "2" running via button
        mapping = {
            "0": "Idle",
            "1": "Running",
            "2": "Running",
        }
        return mapping.get(str(sta).strip(), "Unknown")

    async def _async_update_data(self) -> dict[str, Any]:
        # Read-only snapshot
        online = await self.api.ping()
        if not online:
            return {"_unavailable": True}

        # machine type (cache)
        if self._machine_type is None:
            self._machine_type = await self.api.get_machine_type()

        working_state_raw = await self.api.get_working_state()
        working_state = self._map_working_state(working_state_raw)

        progress = await self.api.get_progress() or {}
        periph = await self.api.get_peripheral_status() or {}

        # normalize ints when possible (values are often strings)
        def _to_int(v: Any) -> int | None:
            try:
                if v is None:
                    return None
                return int(float(str(v).strip()))
            except Exception:
                return None

        progress_pct = _to_int(progress.get("progress"))
        working_s = _to_int(progress.get("working"))
        line = _to_int(progress.get("line"))

        # peripheral flags: keep as-is, but normalize common keys to bool where possible
        def _to_bool(v: Any) -> bool | None:
            if v is None:
                return None
            s = str(v).strip().lower()
            if s in {"1", "true", "on", "yes"}:
                return True
            if s in {"0", "false", "off", "no"}:
                return False
            return None

        normalized = {
            "_unavailable": False,
            "machine_type": self._machine_type,
            "working_state_raw": working_state_raw,
            "working_state": working_state,
            "progress_pct": progress_pct,
            "working_s": working_s,
            "line": line,
            # keep original too
            "progress_raw": progress,
            "peripheral_raw": periph,
            # best-effort normalized flags (only if present)
            "sdCard": _to_bool(periph.get("sdCard")),
            "limitStopFlag": _to_bool(periph.get("limitStopFlag")),
            "tiltStopFlag": _to_bool(periph.get("tiltStopFlag")),
            "movingStopFlag": _to_bool(periph.get("movingStopFlag")),
        }

        return normalized
