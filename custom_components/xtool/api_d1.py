from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiohttp import ClientSession, ClientTimeout


@dataclass
class XToolD1Api:
    host: str
    session: ClientSession

    @property
    def base(self) -> str:
        # D1 endpoints are typically on :8080
        return f"http://{self.host}:8080"

    async def _get(self, path: str) -> Any:
        url = f"{self.base}{path}"
        timeout = ClientTimeout(total=8)
        async with self.session.get(url, timeout=timeout) as resp:
            resp.raise_for_status()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "application/json" in ctype:
                return await resp.json()
            return (await resp.text()).strip()

    async def ping(self) -> bool:
        try:
            txt = await self._get("/ping")
            # many firmwares return "ok"
            return str(txt).strip().lower() in {"ok", "pong", "true", "1"}
        except Exception:
            return False

    async def get_machine_type(self) -> str | None:
        try:
            txt = await self._get("/getmachinetype")
            s = str(txt).strip()
            return s if s else None
        except Exception:
            return None

    async def get_progress(self) -> dict[str, Any] | None:
        # {"progress":"0","working":"0","line":"0"} - often strings
        try:
            data = await self._get("/progress")
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    async def get_working_state(self) -> str | None:
        # /system?action=get_working_sta -> returns "0"/"1"/"2" typically
        try:
            txt = await self._get("/system?action=get_working_sta")
            s = str(txt).strip()
            return s if s else None
        except Exception:
            return None

    async def get_peripheral_status(self) -> dict[str, Any] | None:
        # /peripherystatus -> dict of flags
        try:
            data = await self._get("/peripherystatus")
            return data if isinstance(data, dict) else None
        except Exception:
            return None
