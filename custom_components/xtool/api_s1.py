from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from aiohttp import ClientSession, ClientWebSocketResponse, WSMsgType

_LOGGER = logging.getLogger(__name__)

_WS_PORT = 8081
_CONNECT_TIMEOUT = 8.0
_SEND_TIMEOUT = 5.0

# Regex for M105 format "X0.00Y0.00Z0.00" (no spaces between axes)
_M105_RE = re.compile(r'([XYZ])([+-]?\d+\.\d+)')
# Regex for M313 "Zxx.xxx"
_M313_RE = re.compile(r'Z([+-]?\d+\.\d+)')
# Regex for M340 "Axx"
_M340_RE = re.compile(r'A(\S+)')
# Regex for M222 "Sxx"
_M222_RE = re.compile(r'S(\S+)')
# Regex for M810 filename (quoted)
_M810_RE = re.compile(r'"([^"]*)"')
# Regex for M303 "X... Y..."
_M303_RE = re.compile(r'X([+-]?\d+\.\d+)\s+Y([+-]?\d+\.\d+)')
# Regex for M9039 purifier: speed field "A{n}" (on) or "C{n}" (off), humidity "H{n}"
_M9039_SPEED_RE = re.compile(r'([AC])(\d+)')
_M9039_H_RE = re.compile(r'H(\d+)')


def _parse_m27(val: str) -> dict[str, Any]:
    """Parse 'X-0.010 Y99.200 Z0.000 U0.000' into pos_x/y/z/u floats."""
    out: dict[str, Any] = {}
    key_map = {"X": "pos_x", "Y": "pos_y", "Z": "pos_z", "U": "pos_u"}
    for part in val.split():
        if part and part[0] in key_map:
            try:
                out[key_map[part[0]]] = float(part[1:])
            except ValueError:
                pass
    return out


def _parse_m105(val: str) -> dict[str, Any]:
    """Parse 'X0.00Y0.00Z0.00' (no spaces) into temp_x/y/z floats."""
    out: dict[str, Any] = {}
    key_map = {"X": "temp_x", "Y": "temp_y", "Z": "temp_z"}
    for match in _M105_RE.finditer(val):
        axis, num = match.group(1), match.group(2)
        if axis in key_map:
            try:
                out[key_map[axis]] = float(num)
            except ValueError:
                pass
    return out


def _parse_m13(val: str) -> dict[str, Any]:
    """Parse 'A70 B70' into fan_a/fan_b ints."""
    out: dict[str, Any] = {}
    for part in val.split():
        if part.startswith("A"):
            try:
                out["fan_a"] = int(part[1:])
            except ValueError:
                pass
        elif part.startswith("B"):
            try:
                out["fan_b"] = int(part[1:])
            except ValueError:
                pass
    return out


class XToolS1Api:
    """WebSocket API client for the xTool S1."""

    def __init__(self, ip_address: str, session: ClientSession) -> None:
        self._ip = ip_address
        self._session = session
        self._ws: ClientWebSocketResponse | None = None
        self._listen_task: asyncio.Task | None = None
        self._state: dict[str, Any] = {"_unavailable": True}

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.closed

    @property
    def state(self) -> dict[str, Any]:
        return self._state

    async def connect(self) -> bool:
        """Open WebSocket connection and start background listener."""
        url = f"ws://{self._ip}:{_WS_PORT}/"
        try:
            self._ws = await self._session.ws_connect(
                url, timeout=_CONNECT_TIMEOUT, heartbeat=30
            )
            self._state = {"_unavailable": False}
            self._listen_task = asyncio.ensure_future(self._listen_loop())
            _LOGGER.debug("S1 %s WebSocket connected", self._ip)
            return True
        except Exception as err:
            _LOGGER.debug("S1 %s WebSocket connect failed: %s", self._ip, err)
            self._ws = None
            return False

    async def disconnect(self) -> None:
        """Cancel listener and close WebSocket."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        self._listen_task = None
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def request_status(self) -> None:
        """Send M2003 to trigger a full status push from the device."""
        await self._send("M2003\n")

    async def ping(self) -> None:
        """Send M303 as keepalive/position refresh."""
        await self._send("M303\n")

    async def _send(self, text: str) -> None:
        if not self.connected:
            return
        try:
            await asyncio.wait_for(self._ws.send_str(text), timeout=_SEND_TIMEOUT)
        except Exception as err:
            _LOGGER.debug("S1 %s send error: %s", self._ip, err)

    async def _listen_loop(self) -> None:
        """Background task: read frames and update _state."""
        try:
            async for msg in self._ws:
                if msg.type == WSMsgType.TEXT:
                    self._handle_message(msg.data)
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR, WSMsgType.CLOSED):
                    break
        except asyncio.CancelledError:
            raise
        except Exception as err:
            _LOGGER.debug("S1 %s listen error: %s", self._ip, err)
        finally:
            _LOGGER.debug("S1 %s WebSocket listener stopped", self._ip)
            self._state["_unavailable"] = True
            self._ws = None

    def _handle_message(self, text: str) -> None:
        """Parse an incoming WebSocket frame and merge into _state."""
        text = text.strip()
        if not text:
            return

        try:
            if text.startswith("M2003{"):
                # Full status JSON: strip prefix, parse JSON
                json_str = text[len("M2003"):]
                data = json.loads(json_str)
                self._state.update(self._parse_m2003(data))
                self._state["_unavailable"] = False

            elif text.startswith("M222 "):
                m = _M222_RE.search(text[5:])
                if m:
                    self._state["work_state_raw"] = m.group(1)

            elif text.startswith("M810 "):
                m = _M810_RE.search(text[5:])
                if m:
                    val = m.group(1)
                    self._state["job_file"] = None if val.upper() == "NULL" else val

            elif text.startswith("M340 "):
                m = _M340_RE.search(text[5:])
                if m:
                    alarm_raw = m.group(1)
                    self._state["alarm_raw"] = alarm_raw
                    self._state["alarm_present"] = (alarm_raw != "A0" and alarm_raw != "0")

            elif text.startswith("M303 "):
                m = _M303_RE.search(text[5:])
                if m:
                    try:
                        self._state["pos_x"] = float(m.group(1))
                        self._state["pos_y"] = float(m.group(2))
                    except ValueError:
                        pass

            elif text.startswith("M313 "):
                m = _M313_RE.search(text[5:])
                if m:
                    try:
                        self._state["probe_z"] = float(m.group(1))
                    except ValueError:
                        pass

            elif text.startswith("M9039 "):
                body = text[6:]
                # A{n} = running at speed n (1-4), C{n} = off
                m = _M9039_SPEED_RE.search(body)
                if m:
                    prefix, num = m.group(1), int(m.group(2))
                    speed = 0 if prefix == "C" else num
                    self._state["purifier_speed"] = speed
                    self._state["purifier_on"] = speed > 0
                # H{n} = humidity percent
                h = _M9039_H_RE.search(body)
                if h:
                    self._state["purifier_humidity"] = int(h.group(1))

        except Exception as err:
            _LOGGER.debug("S1 %s message parse error: %s | text=%r", self._ip, err, text)

    def _parse_m2003(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map M2003 JSON fields to normalized _state keys."""
        out: dict[str, Any] = {}

        # Work state from M222 field (primary state indicator, M97 is ignored)
        m222 = data.get("M222")
        if m222 is not None:
            # M222 value in JSON may be "S3" or just "3" depending on firmware
            raw = str(m222).strip()
            if not raw.startswith("S"):
                raw = "S" + raw
            out["work_state_raw"] = raw

        # Position
        m27 = data.get("M27")
        if m27:
            out.update(_parse_m27(str(m27)))

        # Serial number
        m310 = data.get("M310")
        if m310:
            out["serial_number"] = str(m310).strip()

        # Firmware version
        m99 = data.get("M99")
        if m99:
            out["firmware_version"] = str(m99).strip()

        # Tool type
        m54 = data.get("M54")
        if m54:
            out["tool_type"] = str(m54).strip()

        # Temperatures
        m105 = data.get("M105")
        if m105:
            out.update(_parse_m105(str(m105)))

        # Fan speeds
        m13 = data.get("M13")
        if m13:
            out.update(_parse_m13(str(m13)))

        # Alarm state from M340 key
        m340 = data.get("M340")
        if m340 is not None:
            alarm_raw = str(m340).strip()
            out["alarm_raw"] = alarm_raw
            out["alarm_present"] = (alarm_raw != "A0" and alarm_raw != "0")

        # Job file from M810 key
        m810 = data.get("M810")
        if m810 is not None:
            val = str(m810).strip().strip('"')
            out["job_file"] = None if val.upper() == "NULL" else val

        return out
