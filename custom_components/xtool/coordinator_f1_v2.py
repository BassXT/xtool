from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import logging
import ssl
import time
from typing import Any
import uuid

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

XTOOL_WS_PORT = 28900
XTOOL_WS_PATH = "/websocket"

WSV2_FIRST_MESSAGE_USER_KEY = "bWFrZWJsb2NrLXh0b29s"
WSV2_USER_UUID = "mk-guest"

WSV2_HEARTBEAT_SECONDS = 3.0
WSV2_HEARTBEAT_TIMEOUT = 11.0
WSV2_REQUEST_TIMEOUT = 10.0
WSV2_PING_TRANSACTION_ID = 65510
WSV2_TRANSACTION_ID_WRAP = 65500

WSV2_FRAME_HEADER = bytes([0xBA, 0xBE])
WSV2_PROTOCOL_JSON = 4

VALID_SLEEP_RAW_STATES = {"P_SLEEP", "SLEEP"}

_CRC16_TABLE = [
    0x0000, 0xC0C1, 0xC181, 0x0140, 0xC301, 0x03C0, 0x0280, 0xC241,
    0xC601, 0x06C0, 0x0780, 0xC741, 0x0500, 0xC5C1, 0xC481, 0x0440,
    0xCC01, 0x0CC0, 0x0D80, 0xCD41, 0x0F00, 0xCFC1, 0xCE81, 0x0E40,
    0x0A00, 0xCAC1, 0xCB81, 0x0B40, 0xC901, 0x09C0, 0x0880, 0xC841,
    0xD801, 0x18C0, 0x1980, 0xD941, 0x1B00, 0xDBC1, 0xDA81, 0x1A40,
    0x1E00, 0xDEC1, 0xDF81, 0x1F40, 0xDD01, 0x1DC0, 0x1C80, 0xDC41,
    0x1400, 0xD4C1, 0xD581, 0x1540, 0xD701, 0x17C0, 0x1680, 0xD641,
    0xD201, 0x12C0, 0x1380, 0xD341, 0x1100, 0xD1C1, 0xD081, 0x1040,
    0xF001, 0x30C0, 0x3180, 0xF141, 0x3300, 0xF3C1, 0xF281, 0x3240,
    0x3600, 0xF6C1, 0xF781, 0x3740, 0xF501, 0x35C0, 0x3480, 0xF441,
    0x3C00, 0xFCC1, 0xFD81, 0x3D40, 0xFF01, 0x3FC0, 0x3E80, 0xFE41,
    0xFA01, 0x3AC0, 0x3B80, 0xFB41, 0x3900, 0xF9C1, 0xF881, 0x3840,
    0x2800, 0xE8C1, 0xE981, 0x2940, 0xEB01, 0x2BC0, 0x2A80, 0xEA41,
    0xEE01, 0x2EC0, 0x2F80, 0xEF41, 0x2D00, 0xEDC1, 0xEC81, 0x2C40,
    0xE401, 0x24C0, 0x2580, 0xE541, 0x2700, 0xE7C1, 0xE681, 0x2640,
    0x2200, 0xE2C1, 0xE381, 0x2340, 0xE101, 0x21C0, 0x2080, 0xE041,
    0xA001, 0x60C0, 0x6180, 0xA141, 0x6300, 0xA3C1, 0xA281, 0x6240,
    0x6600, 0xA6C1, 0xA781, 0x6740, 0xA501, 0x65C0, 0x6480, 0xA441,
    0x6C00, 0xACC1, 0xAD81, 0x6D40, 0xAF01, 0x6FC0, 0x6E80, 0xAE41,
    0xAA01, 0x6AC0, 0x6B80, 0xAB41, 0x6900, 0xA9C1, 0xA881, 0x6840,
    0x7800, 0xB8C1, 0xB981, 0x7940, 0xBB01, 0x7BC0, 0x7A80, 0xBA41,
    0xBE01, 0x7EC0, 0x7F80, 0xBF41, 0x7D00, 0xBDC1, 0xBC81, 0x7C40,
    0xB401, 0x74C0, 0x7580, 0xB541, 0x7700, 0xB7C1, 0xB681, 0x7640,
    0x7200, 0xB2C1, 0xB381, 0x7340, 0xB101, 0x71C0, 0x7080, 0xB041,
    0x5000, 0x90C1, 0x9181, 0x5140, 0x9301, 0x53C0, 0x5280, 0x9241,
    0x9601, 0x56C0, 0x5780, 0x9741, 0x5500, 0x95C1, 0x9481, 0x5440,
    0x9C01, 0x5CC0, 0x5D80, 0x9D41, 0x5F00, 0x9FC1, 0x9E81, 0x5E40,
    0x5A00, 0x9AC1, 0x9B81, 0x5B40, 0x9901, 0x59C0, 0x5880, 0x9841,
    0x8801, 0x48C0, 0x4980, 0x8941, 0x4B00, 0x8BC1, 0x8A81, 0x4A40,
    0x4E00, 0x8EC1, 0x8F81, 0x4F40, 0x8D01, 0x4DC0, 0x4C80, 0x8C41,
    0x4400, 0x84C1, 0x8581, 0x4540, 0x8701, 0x47C0, 0x4680, 0x8641,
    0x8201, 0x42C0, 0x4380, 0x8341, 0x4100, 0x81C1, 0x8081, 0x4040,
]


def _json_compact(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _crc16(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = (_CRC16_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)) & 0xFFFF
    return crc


def _encode_frame(payload: bytes, protocol_type: int = WSV2_PROTOCOL_JSON) -> bytes:
    header = bytearray(10)
    header[0:2] = WSV2_FRAME_HEADER

    length = len(payload)
    header[2] = (length >> 16) & 0xFF
    header[3] = (length >> 8) & 0xFF
    header[4] = length & 0xFF
    header[5] = protocol_type & 0x7F

    payload_crc = _crc16(payload)
    header[6] = (payload_crc >> 8) & 0xFF
    header[7] = payload_crc & 0xFF

    header_crc = _crc16(bytes(header[0:8]))
    header[8] = (header_crc >> 8) & 0xFF
    header[9] = header_crc & 0xFF

    return bytes(header) + payload


def _decode_frames(buffer: bytes) -> tuple[list[tuple[int, bytes]], bytes]:
    frames: list[tuple[int, bytes]] = []
    pos = 0
    n = len(buffer)

    while pos + 10 <= n:
        if buffer[pos] != 0xBA or buffer[pos + 1] != 0xBE:
            pos += 1
            continue

        length = (
            (buffer[pos + 2] << 16)
            | (buffer[pos + 3] << 8)
            | buffer[pos + 4]
        )
        total = 10 + length

        if pos + total > n:
            break

        header = buffer[pos : pos + 8]
        header_crc = (buffer[pos + 8] << 8) | buffer[pos + 9]

        if _crc16(header) != header_crc:
            pos += 1
            continue

        crc_disabled = bool(buffer[pos + 5] & 0x80)
        protocol_type = buffer[pos + 5] & 0x7F
        payload = buffer[pos + 10 : pos + total]

        if not crc_disabled:
            payload_crc = (buffer[pos + 6] << 8) | buffer[pos + 7]
            if _crc16(payload) != payload_crc:
                pos += 1
                continue

        frames.append((protocol_type, payload))
        pos += total

    return frames, buffer[pos:]


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _local_timezone() -> str:
    try:
        tz = datetime.now().astimezone().tzinfo
        return str(tz) if tz is not None else ""
    except Exception:
        return ""


class _PendingRequest:
    def __init__(self, timeout: float) -> None:
        self.future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self.deadline = time.monotonic() + timeout


class XToolF1V2Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Event based coordinator for xTool F1 firmware 40.51+ using WS-V2."""

    def __init__(self, hass: HomeAssistant, ip_address: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"xtool_f1_v2_{ip_address}",
            update_interval=timedelta(seconds=3600),
        )

        self.ip_address = ip_address
        self.device_type = "f1_v2"

        self._session: aiohttp.ClientSession | None = None
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._rx_buffer = bytearray()
        self._pending: dict[int, _PendingRequest] = {}
        self._heartbeat_pending: asyncio.Future[dict[str, Any]] | None = None
        self._transaction_counter = 0

        self._state: dict[str, Any] = {
            "_unavailable": True,
            "connection_state": "disconnected",
            "work_state_raw": None,
            "status": "unknown",
            "lid_open": None,
            "machine_lock": None,
            "alarm_present": False,
            "running": False,
            "button_last": None,
            "last_result": None,
            "last_job_time": None,
            "task_id": None,
            "config": {},
            "machine_info": {},
            "runtime_info": {},
            "last_unhandled_mode": None,
            "last_unhandled_event": None,
        }

    async def async_start(self) -> None:
        self.async_set_updated_data(dict(self._state))

        if self._task is None or self._task.done():
            self._task = self.hass.loop.create_task(self._run())

    async def async_stop(self) -> None:
        self._stop_event.set()

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._close_ws()

    async def _async_update_data(self) -> dict[str, Any]:
        return dict(self._state)

    def _next_transaction_id(self) -> int:
        self._transaction_counter += 1
        if self._transaction_counter > WSV2_TRANSACTION_ID_WRAP:
            self._transaction_counter = 1
        return self._transaction_counter

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                await self._listen_once()
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("F1 V2 websocket disconnected: %s", err)
                self._handle_disconnect()
                await self._close_ws()
                await asyncio.sleep(10)

    async def _listen_once(self) -> None:
        url = (
            f"wss://{self.ip_address}:{XTOOL_WS_PORT}{XTOOL_WS_PATH}"
            f"?id={uuid.uuid4()}&function=instruction"
        )

        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)

        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=timeout)

        _LOGGER.debug("Connecting F1 V2 websocket: %s", url)

        self._ws = await self._session.ws_connect(
            url,
            ssl=_ssl_context(),
            heartbeat=20.0,
            max_msg_size=0,
            headers={"Origin": "atomm://renderer"},
        )

        self._state["connection_state"] = "connected"
        self._state["_unavailable"] = False
        self.async_set_updated_data(dict(self._state))

        await self._send_parity()
        await self._initial_poll()

        self._heartbeat_task = self.hass.loop.create_task(self._heartbeat_loop())

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.BINARY:
                    self._handle_binary(msg.data)
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    self._handle_text(msg.data)
                elif msg.type in (
                    aiohttp.WSMsgType.CLOSED,
                    aiohttp.WSMsgType.ERROR,
                    aiohttp.WSMsgType.CLOSING,
                    aiohttp.WSMsgType.CLOSE,
                ):
                    break
        finally:
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()
                try:
                    await self._heartbeat_task
                except asyncio.CancelledError:
                    pass
            self._heartbeat_task = None

    async def _close_ws(self) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        self._heartbeat_task = None

        if self._ws and not self._ws.closed:
            try:
                await self._ws.close()
            except Exception:
                pass

        self._ws = None

        for pending in self._pending.values():
            if not pending.future.done():
                pending.future.set_exception(ConnectionError("WebSocket closed"))

        self._pending.clear()

        if self._heartbeat_pending is not None and not self._heartbeat_pending.done():
            self._heartbeat_pending.set_exception(ConnectionError("WebSocket closed"))

        self._heartbeat_pending = None
        self._rx_buffer = bytearray()
        self._transaction_counter = 0

        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception:
                pass

        self._session = None

    async def _request(
        self,
        url: str,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: float = WSV2_REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        if self._ws is None or self._ws.closed:
            raise ConnectionError("F1 V2 websocket is not connected")

        transaction_id = self._next_transaction_id()

        payload = {
            "type": "request",
            "method": method.upper(),
            "url": url,
            "params": params or {},
            "data": data or {},
            "timestamp": int(time.time() * 1000),
            "transactionId": transaction_id,
        }

        pending = _PendingRequest(timeout)
        self._pending[transaction_id] = pending

        frame = _encode_frame(_json_compact(payload).encode("utf-8"))

        _LOGGER.debug("F1 V2 TX %s %s txn=%s", method, url, transaction_id)

        try:
            await self._ws.send_bytes(frame)
        except Exception as err:
            self._pending.pop(transaction_id, None)
            raise ConnectionError(f"F1 V2 send failed: {err}") from err

        try:
            response = await asyncio.wait_for(pending.future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending.pop(transaction_id, None)
            raise

        code = response.get("code", 0) if isinstance(response, dict) else 0
        if code != 0:
            msg = response.get("msg") or response.get("message") or "unknown"
            raise RuntimeError(f"F1 V2 {method} {url} returned code {code}: {msg}")

        result = response.get("data") if isinstance(response, dict) else {}
        return result if isinstance(result, dict) else {}

    async def _send_parity(self) -> None:
        _LOGGER.debug("Sending F1 V2 parity handshake")

        await self._request(
            "/v1/user/parity",
            "GET",
            data={
                "userID": WSV2_USER_UUID,
                "userKey": WSV2_FIRST_MESSAGE_USER_KEY,
                "timezone": _local_timezone(),
            },
            timeout=10.0,
        )

        _LOGGER.debug("F1 V2 parity handshake OK")

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await asyncio.sleep(WSV2_HEARTBEAT_SECONDS)

                if self._ws is None or self._ws.closed:
                    return

                payload = {
                    "type": "request",
                    "method": "GET",
                    "url": "/v1/user/ping",
                    "transactionId": WSV2_PING_TRANSACTION_ID,
                    "data": {},
                    "params": {},
                    "timestamp": int(time.time() * 1000),
                }

                self._heartbeat_pending = asyncio.Future()
                frame = _encode_frame(_json_compact(payload).encode("utf-8"))

                try:
                    await self._ws.send_bytes(frame)
                    await asyncio.wait_for(
                        self._heartbeat_pending,
                        timeout=WSV2_HEARTBEAT_TIMEOUT,
                    )
                except Exception as err:
                    _LOGGER.debug("F1 V2 heartbeat failed: %s", err)
                    await self._close_ws()
                    return
                finally:
                    self._heartbeat_pending = None

        except asyncio.CancelledError:
            raise

    async def _initial_poll(self) -> None:
        try:
            machine_info = await self._request("/v1/device/machineInfo", "GET")
            self._state["machine_info"] = machine_info
        except Exception as err:
            _LOGGER.debug("F1 V2 machineInfo failed: %s", err)

        try:
            runtime_info = await self._request("/v1/device/runtime-infos", "GET")
            self._state["runtime_info"] = runtime_info
            self._handle_runtime_info(runtime_info)
        except Exception as err:
            _LOGGER.debug("F1 V2 runtime-infos failed: %s", err)

        for ptype in ("gap", "machine_lock"):
            try:
                data = await self._request(
                    "/v1/peripheral/param",
                    "GET",
                    params={"type": ptype},
                )
                self._handle_peripheral_param(ptype, data)
            except Exception as err:
                _LOGGER.debug("F1 V2 peripheral %s failed: %s", ptype, err)

        self._state["_unavailable"] = False
        self._state["connection_state"] = "connected"
        self.async_set_updated_data(dict(self._state))

    def _handle_binary(self, raw: bytes) -> None:
        self._rx_buffer.extend(raw)
        frames, remainder = _decode_frames(bytes(self._rx_buffer))
        self._rx_buffer = bytearray(remainder)

        for protocol_type, payload in frames:
            if protocol_type != WSV2_PROTOCOL_JSON:
                continue

            try:
                event = json.loads(payload.decode("utf-8"))
            except Exception:
                _LOGGER.debug("Unable to parse F1 V2 binary payload", exc_info=True)
                continue

            if isinstance(event, dict):
                self._dispatch_event(event)

    def _handle_text(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except Exception:
            _LOGGER.debug("Unable to parse F1 V2 text message", exc_info=True)
            return

        if isinstance(event, dict):
            self._dispatch_event(event)

    def _dispatch_event(self, event: dict[str, Any]) -> None:
        if event.get("type") == "response":
            txn = self._coerce_transaction_id(event.get("transactionId"))

            if txn is None:
                data = event.get("data")
                if isinstance(data, dict):
                    txn = self._coerce_transaction_id(data.get("transactionId"))

            if txn == WSV2_PING_TRANSACTION_ID:
                if (
                    self._heartbeat_pending is not None
                    and not self._heartbeat_pending.done()
                ):
                    self._heartbeat_pending.set_result(event)
                return

            if txn is not None:
                pending = self._pending.pop(txn, None)
                if pending is not None and not pending.future.done():
                    pending.future.set_result(event)
                return

        self._handle_event(event)

    @staticmethod
    def _coerce_transaction_id(value: Any) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return None

    def _handle_disconnect(self) -> None:
        self._state["connection_state"] = "disconnected"
        self._state["running"] = False

        if self._is_sleep_state():
            self._set_status("sleep", self._state.get("work_state_raw") or "P_SLEEP")
            self._state["_unavailable"] = False
        else:
            self._state["_unavailable"] = True

        self.async_set_updated_data(dict(self._state))

    def _is_sleep_state(self) -> bool:
        status = str(self._state.get("status") or "").lower()
        raw = str(self._state.get("work_state_raw") or "").upper()
        return status == "sleep" or raw in VALID_SLEEP_RAW_STATES

    def _set_status(self, status: str, raw: str | None = None) -> None:
        self._state["status"] = status
        self._state["work_state_raw"] = raw or status
        self._state["running"] = status in {
            "framing",
            "prepared",
            "working",
        }

    def _remember_unhandled_event(
        self,
        event: dict[str, Any],
        mode: str | None = None,
    ) -> None:
        self._state["last_unhandled_event"] = event

        if mode:
            self._state["last_unhandled_mode"] = mode

        _LOGGER.debug("Unhandled F1 V2 event/mode kept without status change: %s", event)

    def _handle_runtime_info(self, data: dict[str, Any]) -> None:
        cur_mode = data.get("curMode") if isinstance(data.get("curMode"), dict) else {}
        mode = str(cur_mode.get("mode") or "").upper()

        if mode:
            self._handle_mode(mode)

        task_id = cur_mode.get("taskId")
        if task_id is not None:
            self._state["task_id"] = task_id

    def _handle_peripheral_param(self, ptype: str, data: dict[str, Any]) -> None:
        state = str(data.get("state") or "").lower()

        if ptype == "gap":
            # Bei WS-V2/F1: off = offen, on = geschlossen
            if state == "off":
                self._state["lid_open"] = True
            elif state == "on":
                self._state["lid_open"] = False

        elif ptype == "machine_lock":
            # on = locked, off = unlocked
            if state == "on":
                self._state["machine_lock"] = True
            elif state == "off":
                self._state["machine_lock"] = False

    def _handle_mode(self, mode: str) -> bool:
        if mode == "P_SLEEP":
            self._set_status("sleep", mode)
        elif mode in {
            "P_WORK",
            "P_IDLE",
            "P_ONLINE_READY_WORK",
            "P_OFFLINE_READY_WORK",
            "P_READY",
        }:
            self._set_status("ready", mode)
        elif mode == "P_WORKING":
            if self._state.get("status") == "framing":
                self._state["work_state_raw"] = mode
                self._state["running"] = True
            else:
                self._set_status("working", mode)
        elif mode in {"P_WORK_DONE", "P_FINISH"}:
            self._set_status("finished", mode)
        elif mode == "P_ERROR":
            self._set_status("error", mode)
        elif mode == "P_MEASURE":
            self._set_status("measuring", mode)
        elif mode == "P_BOOT":
            self._set_status("initializing", mode)
        elif mode == "P_UPGRADE":
            self._set_status("firmware_update", mode)
        else:
            return False

        return True

    def _handle_event(self, event: dict[str, Any]) -> None:
        url = event.get("url")
        data = event.get("data") if isinstance(event.get("data"), dict) else {}
        module = data.get("module")
        typ = data.get("type")
        info = data.get("info")
        changed = False

        if url == "/work/mode" and module == "STATUS_CONTROLLER" and typ == "MODE_CHANGE":
            if not isinstance(info, dict):
                self._remember_unhandled_event(event)
                return

            mode_raw = info.get("mode")

            if not mode_raw:
                _LOGGER.debug("Ignoring F1 V2 /work/mode without mode: %s", info)
                return

            mode = str(mode_raw).upper()

            if not self._handle_mode(mode):
                self._remember_unhandled_event(event, mode)
                return

            task_id = info.get("taskId")
            if task_id is not None:
                self._state["task_id"] = task_id

            changed = True

        elif url == "/device/status" and module == "STATUS_CONTROLLER":
            info_str = str(info).lower()

            if typ == "WORK_PREPARED":
                if info_str == "framing":
                    self._set_status("framing", "WORK_PREPARED")
                elif info_str == "working":
                    self._set_status("prepared", "WORK_PREPARED")
                else:
                    self._set_status("prepared", "WORK_PREPARED")
                changed = True

            elif typ == "HEAT_STOPED":
                if info_str == "working":
                    self._set_status("working", "HEAT_STOPED")
                    changed = True

            elif typ == "WORK_STARTED":
                if info_str == "framing":
                    self._set_status("framing", "WORK_STARTED")
                elif info_str == "working":
                    self._set_status("working", "WORK_STARTED")
                else:
                    self._set_status("working", "WORK_STARTED")
                changed = True

            elif typ == "WORK_FINISHED":
                if info_str == "framing":
                    self._set_status("ready", "WORK_FINISHED")
                elif info_str == "working":
                    self._set_status("finished", "WORK_FINISHED")
                else:
                    self._set_status("finished", "WORK_FINISHED")
                changed = True

            else:
                self._remember_unhandled_event(event)
                return

        elif url == "/work/result" and module == "WORK_RESULT" and typ == "WORK_FINISHED":
            if isinstance(info, dict):
                self._state["last_result"] = info.get("result")
                self._state["last_job_time"] = info.get("timeUse")
                self._state["task_id"] = info.get("taskId")

            self._set_status("finished", "WORK_FINISHED")
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

            if self._is_sleep_state():
                self._set_status("ready", "BUTTON_WAKE")

            changed = True

        else:
            self._remember_unhandled_event(event)
            return

        if changed:
            self._state["_unavailable"] = False
            self._state["connection_state"] = "connected"
            self.async_set_updated_data(dict(self._state))