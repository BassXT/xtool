from __future__ import annotations

import asyncio
from datetime import timedelta
import json
import logging
import os
import ssl
import time
from typing import Any
import uuid

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

XTOOL_WS_PORT = 28900
XTOOL_WS_HANDSHAKE = "bWFrZWJsb2NrLXh0b29s"  # base64: makeblock-xtools
XTOOL_WS_PING = b"\xC0\x00"


class XToolF1V2Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Event based coordinator for F1 firmware 40.51+."""

    def __init__(self, hass: HomeAssistant, ip_address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"xtool_f1_v2_{ip_address}",
            update_interval=timedelta(seconds=3600),
        )
        self.ip_address = ip_address
        self.device_type = "f1_v2"
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._state: dict[str, Any] = {
            "_unavailable": True,
            "work_state_raw": None,
            "status": "unknown",
            "lid_open": None,
            "machine_lock": None,
            "alarm_present": False,
            "running": False,
            "button_last": None,
            "last_result": None,
            "last_job_time": None,
            "config": {},
        }

    async def async_start(self) -> None:
        self.async_set_updated_data(dict(self._state))
        self._task = self.hass.loop.create_task(self._run())

    async def async_stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _async_update_data(self) -> dict[str, Any]:
        return dict(self._state)

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._listen_once()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("F1 V2 websocket disconnected: %s", err)
                self._state["_unavailable"] = True
                self.async_set_updated_data(dict(self._state))
                await asyncio.sleep(3)

    async def _listen_once(self) -> None:
        url = (
            f"wss://{self.ip_address}:{XTOOL_WS_PORT}/websocket"
            f"?id={uuid.uuid4()}&function=instruction"
        )

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.ws_connect(
                url,
                ssl=ssl_ctx,
                heartbeat=None,
                max_msg_size=0,
            ) as ws:
                self._state["_unavailable"] = False
                self.async_set_updated_data(dict(self._state))

                await ws.send_str(XTOOL_WS_HANDSHAKE)

                ping_task = self.hass.loop.create_task(self._heartbeat(ws))

                try:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            event = self._parse_frame(msg.data)
                            if event:
                                self._handle_event(event)
                        elif msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                event = json.loads(msg.data)
                                self._handle_event(event)
                            except Exception:
                                pass
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSED,
                            aiohttp.WSMsgType.ERROR,
                            aiohttp.WSMsgType.CLOSE,
                        ):
                            break
                finally:
                    ping_task.cancel()

    async def _heartbeat(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        while not self._stop_event.is_set():
            await asyncio.sleep(2)
            await ws.send_bytes(XTOOL_WS_PING)

    def _parse_frame(self, raw: bytes) -> dict[str, Any] | None:
        idx = raw.find(b"{")
        if idx == -1:
            return None
        try:
            return json.loads(raw[idx:].decode("utf-8"))
        except Exception:
            return None

    def _set_status(self, status: str, raw: str | None = None) -> None:
        self._state["status"] = status
        self._state["work_state_raw"] = raw or status
        self._state["running"] = status in {"framing", "ready", "working"}

    def _handle_event(self, event: dict[str, Any]) -> None:
        url = event.get("url")
        method = event.get("method")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        module = data.get("module")
        typ = data.get("type")
        info = data.get("info")

        changed = False

        if url == "/work/mode" and module == "STATUS_CONTROLLER" and typ == "MODE_CHANGE":
            if isinstance(info, dict):
                mode = str(info.get("mode", "")).upper()
                if mode == "P_SLEEP":
                    self._set_status("sleeping", mode)
                elif mode == "P_WORK":
                    self._set_status("ready", mode)
                elif mode == "P_WORKING":
                    self._set_status("working", mode)
                elif mode in {"P_IDLE", "IDLE"}:
                    self._set_status("idle", mode)
                changed = True

        elif url == "/device/status" and module == "STATUS_CONTROLLER":
            info_str = str(info).lower()

            if typ == "WORK_PREPARED":
                if info_str == "framing":
                    self._set_status("framing_prepared", "WORK_PREPARED")
                elif info_str == "working":
                    self._set_status("ready", "WORK_PREPARED")
                changed = True

            elif typ == "WORK_STARTED":
                if info_str == "framing":
                    self._set_status("framing", "WORK_STARTED")
                elif info_str == "working":
                    self._set_status("working", "WORK_STARTED")
                changed = True

            elif typ == "WORK_FINISHED":
                if info_str == "framing":
                    self._set_status("idle", "WORK_FINISHED")
                elif info_str == "working":
                    self._set_status("finished", "WORK_FINISHED")
                changed = True

        elif url == "/work/result" and module == "WORK_RESULT" and typ == "WORK_FINISHED":
            if isinstance(info, dict):
                self._state["last_result"] = info.get("result")
                self._state["last_job_time"] = info.get("timeUse")
                self._state["task_id"] = info.get("taskId")
                changed = True

        elif url == "/device/config" and module == "DEVICE_CONFIG" and typ == "INFO":
            if isinstance(info, dict):
                self._state["config"] = info
                self._state["flame_alarm_enabled"] = info.get("flameAlarm")
                self._state["beep_enabled"] = info.get("beepEnable")
                self._state["gap_check_enabled"] = info.get("gapCheck")
                self._state["gap_check_with_key_enabled"] = info.get("gapCheckWithKey")
                self._state["machine_lock_check_enabled"] = info.get("machineLockCheck")
                self._state["purifier_timeout"] = info.get("purifierTimeout")
                self._state["working_mode"] = info.get("workingMode")
                changed = True

        elif url == "/gap/status" and module == "GAP":
            if typ == "CLOSE":
                self._state["lid_open"] = False
                changed = True
            elif typ == "OPEN":
                self._state["lid_open"] = True
                changed = True

        elif url == "/machine_lock/status" and module == "MACHINE_LOCK":
            if typ == "OPEN":
                self._state["machine_lock"] = False
                changed = True
            elif typ == "CLOSE":
                self._state["machine_lock"] = True
                changed = True

        elif url == "/button/status" and module == "BUTTON":
            self._state["button_last"] = {
                "type": typ,
                "info": info,
                "timestamp": event.get("timestamp") or int(time.time() * 1000),
            }
            changed = True

        if changed:
            self._state["_unavailable"] = False
            self.async_set_updated_data(dict(self._state))
