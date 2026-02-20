from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import requests

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .coordinator_d1 import XToolD1Coordinator
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_IP_ADDRESS,
    CONF_DEVICE_TYPE,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_SLOW_UPDATE_INTERVAL,
    HTTP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return (resp.text or "").strip()


def _is_invalid_or_not_supported(payload: Any) -> bool:
    if isinstance(payload, str):
        s = payload.strip().lower()
        return s in {"invalid request", "not support", "not supported"}
    if isinstance(payload, dict) and payload.get("code") == 10:
        msg = str(payload.get("msg", "")).lower()
        return "device not support" in msg
    return False


class XToolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for P2/F1/M1 (v2 endpoints) + legacy fallback."""

    def __init__(self, hass: HomeAssistant, ip_address: str, device_type: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"xtool_{ip_address}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.ip_address = ip_address
        self.device_type = device_type.lower()

        self._reachable_last: bool | None = None

        self._slow_every = max(
            1, int(DEFAULT_SLOW_UPDATE_INTERVAL / max(1, DEFAULT_UPDATE_INTERVAL))
        )
        self._tick = 0

        self._cached_machine_info: dict[str, Any] | None = None
        self._cached_working_info: dict[str, Any] | None = None
        self._cached_config: dict[str, Any] | None = None

        self._warnings_hash_last: str | None = None

    def _get(self, path: str) -> Any:
        url = f"http://{self.ip_address}:8080{path}"
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return _safe_json(resp)

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        url = f"http://{self.ip_address}:8080{path}"
        resp = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return _safe_json(resp)

    def _warnings_list(self, alarm_obj: Any) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(alarm_obj, dict):
            return out

        alarm_list = alarm_obj.get("alarm")
        if isinstance(alarm_list, list):
            return [a for a in alarm_list if isinstance(a, dict)]

        for k, v in alarm_obj.items():
            if str(k).isdigit() and isinstance(v, dict):
                out.append(v)
        return out

    def _warnings_summary(self, warnings: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for w in warnings:
            module = str(w.get("module", "")).strip()
            typ = str(w.get("type", "")).strip()
            level = str(w.get("level", "")).strip()
            info = str(w.get("info", "")).strip()

            p = f"{module}:{typ}" if (module or typ) else "UNKNOWN"
            if level:
                p += f" ({level})"
            if info:
                p += f" - {info}"
            parts.append(p)
        return "; ".join(parts)

    def _warnings_hash(self, warnings: list[dict[str, Any]]) -> str:
        items = []
        for w in warnings:
            items.append(
                (
                    str(w.get("module", "")),
                    str(w.get("type", "")),
                    str(w.get("level", "")),
                    str(w.get("info", "")),
                )
            )
        items.sort()
        return "|".join(["/".join(i) for i in items])

    def _count_warnings(self, alarm_obj: Any) -> int:
        if not isinstance(alarm_obj, dict):
            return 0
        alarm_list = alarm_obj.get("alarm")
        if isinstance(alarm_list, list):
            return len(alarm_list)
        keys = [k for k in alarm_obj.keys() if str(k).isdigit()]
        return len(keys)

    def _normalize_running_status(self, raw: Any) -> dict[str, Any]:
        out: dict[str, Any] = {
            "work_state_raw": None,
            "task_id": None,
            "cpu_temp": None,
            "alarm_present": None,
            "alarm_current": None,
            "alarm_history": None,
            "dev_time": None,
        }

        if not isinstance(raw, dict):
            return out

        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        cur_mode = data.get("curMode") if isinstance(data.get("curMode"), dict) else {}

        out["cpu_temp"] = data.get("cpuTemp")
        out["dev_time"] = data.get("devTime")
        out["work_state_raw"] = cur_mode.get("mode")
        out["task_id"] = cur_mode.get("taskId")

        cur_alarm = data.get("curAlarmInfo")
        alarm_hist = data.get("alarmInfo")

        out["alarm_current"] = cur_alarm
        out["alarm_history"] = alarm_hist

        warnings = self._warnings_list(cur_alarm)
        out["alarm_present"] = len(warnings) > 0
        return out

    def _normalize_gap(self, raw: Any) -> dict[str, Any]:
        lid_open = None
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            state = str(data.get("state", "")).lower()
            if state in {"on", "off"}:
                lid_open = (state == "on")
        return {"lid_open": lid_open}

    def _normalize_smoking_fan(self, raw: Any) -> dict[str, Any]:
        fan_state = None
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            s = str(data.get("state", "")).lower()
            if s in {"on", "off"}:
                fan_state = s
        return {"fan_state": fan_state}

    def _normalize_ext_purifier(self, raw: Any) -> dict[str, Any]:
        out = {
            "ext_purifier_state": None,
            "ext_purifier_exist": None,
            "ext_purifier_power": None,
            "ext_purifier_current": None,
        }
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw["data"]
            st = str(data.get("state", "")).lower()
            if st in {"on", "off"}:
                out["ext_purifier_state"] = st
            exist = data.get("exist")
            if isinstance(exist, bool):
                out["ext_purifier_exist"] = exist
            out["ext_purifier_power"] = data.get("power")
            out["ext_purifier_current"] = data.get("current")
        return out

    def _normalize_machine_lock(self, raw: Any) -> dict[str, Any]:
        locked = None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            st = str(raw["data"].get("state", "")).lower()
            if st in {"on", "off"}:
                locked = (st == "on")
        return {"machine_lock": locked}

    def _normalize_drawer(self, raw: Any) -> dict[str, Any]:
        drawer_open = None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            st = str(raw["data"].get("state", "")).lower()
            if st in {"on", "off"}:
                drawer_open = (st == "on")
        return {"drawer_open": drawer_open}

    def _normalize_airassist(self, raw: Any) -> dict[str, Any]:
        out = {
            "airassist_state": None,
            "airassist_power": None,
            "airassist_version": None,
            "airassist_fire_trigger": None,
        }
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw["data"]
            st = str(data.get("state", "")).lower()
            if st in {"on", "off"}:
                out["airassist_state"] = st
            out["airassist_power"] = data.get("power")
            out["airassist_version"] = data.get("version")
            out["airassist_fire_trigger"] = data.get("fireTiggerSta")
        return out

    def _fetch_data_sync(self) -> dict[str, Any]:
        self._tick += 1

        normalized: dict[str, Any] = {
            "_unavailable": False,
            "work_state_raw": None,
            "task_id": None,
            "cpu_temp": None,
            "dev_time": None,
            "alarm_present": None,
            "warnings_count": 0,
            "warnings_details": None,
            "warnings_summary": None,
            "warnings_hash": None,
            "warnings_changed": None,
            "alarm_current": None,
            "alarm_history": None,
            "lid_open": None,
            "fan_state": None,
            "ext_purifier_state": None,
            "ext_purifier_exist": None,
            "ext_purifier_power": None,
            "ext_purifier_current": None,
            "machine_lock": None,
            "drawer_open": None,
            "airassist_state": None,
            "airassist_power": None,
            "airassist_version": None,
            "airassist_fire_trigger": None,
            "machine_info": self._cached_machine_info,
            "working_info": self._cached_working_info,
            "config": self._cached_config,
            "legacy": None,
        }

        try:
            raw_run = self._get("/device/runningStatus")
            if _is_invalid_or_not_supported(raw_run):
                raise RuntimeError("v2 runningStatus not supported")

            normalized.update(self._normalize_running_status(raw_run))
            self._log_reachability(True)

        except requests.exceptions.ConnectionError as err:
            self._log_reachability(False)
            _LOGGER.debug("XTool %s connection error: %s", self.ip_address, err)
            return {"_unavailable": True}

        except Exception:
            try:
                raw_status = self._get("/status")
                if _is_invalid_or_not_supported(raw_status):
                    raise RuntimeError("legacy /status not supported")

                normalized["legacy"] = raw_status

                if isinstance(raw_status, dict):
                    if "STATUS" in raw_status:
                        normalized["work_state_raw"] = str(raw_status.get("STATUS") or "").strip()
                    elif "mode" in raw_status:
                        normalized["work_state_raw"] = str(raw_status.get("mode") or "").strip()

                    if "CPU_TEMP" in raw_status:
                        normalized["cpu_temp"] = raw_status.get("CPU_TEMP")

                self._log_reachability(True)

            except requests.exceptions.ConnectionError as err2:
                self._log_reachability(False)
                _LOGGER.debug("XTool %s connection error (fallback): %s", self.ip_address, err2)
                return {"_unavailable": True}
            except Exception as err2:  # noqa: BLE001
                self._log_reachability(False)
                _LOGGER.debug("XTool %s update failed: %s", self.ip_address, err2)
                return {"_unavailable": True}

        normalized["warnings_count"] = self._count_warnings(normalized.get("alarm_current"))
        warnings = self._warnings_list(normalized.get("alarm_current"))
        normalized["warnings_details"] = warnings
        normalized["warnings_summary"] = self._warnings_summary(warnings)

        h = self._warnings_hash(warnings)
        normalized["warnings_hash"] = h
        normalized["warnings_changed"] = (
            self._warnings_hash_last is not None and h != self._warnings_hash_last
        )
        self._warnings_hash_last = h

        # fast best-effort peripherals
        for path, normalizer in (
            ("/peripheral/gap", self._normalize_gap),
            ("/peripheral/smoking_fan", self._normalize_smoking_fan),
            ("/peripheral/ext_purifier", self._normalize_ext_purifier),
            ("/peripheral/machine_lock", self._normalize_machine_lock),
            ("/peripheral/drawer", self._normalize_drawer),
            ("/peripheral/airassist", self._normalize_airassist),
        ):
            try:
                raw = self._get(path)
                if not _is_invalid_or_not_supported(raw):
                    normalized.update(normalizer(raw))
            except Exception:
                pass

        # slow extras: do on first tick AND then periodically
        if self._tick == 1 or (self._tick % self._slow_every) == 0:
            try:
                mi = self._get("/device/machineInfo")
                if not _is_invalid_or_not_supported(mi) and isinstance(mi, dict):
                    self._cached_machine_info = mi
                    normalized["machine_info"] = mi
            except Exception:
                pass

            try:
                wi = self._get("/device/workingInfo")
                if not _is_invalid_or_not_supported(wi) and isinstance(wi, dict):
                    self._cached_working_info = wi
                    normalized["working_info"] = wi
            except Exception:
                pass

            try:
                cfg = self._post(
                    "/config/get",
                    {
                        "alias": "config",
                        "type": "user",
                        "kv": ["beepEnable", "fillLightBrightness", "purifierTimeout", "taskId", "workingMode"],
                    },
                )
                if not _is_invalid_or_not_supported(cfg) and isinstance(cfg, dict):
                    self._cached_config = cfg
                    normalized["config"] = cfg
            except Exception:
                pass

        return normalized

    def _log_reachability(self, reachable: bool) -> None:
        if self._reachable_last is None:
            self._reachable_last = reachable
            return
        if reachable != self._reachable_last:
            self._reachable_last = reachable
            if reachable:
                _LOGGER.info("XTool %s is back online", self.ip_address)
            else:
                _LOGGER.warning("XTool %s is offline/unreachable", self.ip_address)

    async def _async_update_data(self) -> dict[str, Any]:
        return await self.hass.async_add_executor_job(self._fetch_data_sync)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ip = entry.data[CONF_IP_ADDRESS]
    dev_type = entry.data[CONF_DEVICE_TYPE].lower()

    # ✅ D1 uses a different API stack
    if dev_type == "d1":
        coordinator: DataUpdateCoordinator = XToolD1Coordinator(hass, ip)
        await coordinator.async_config_entry_first_refresh()
    else:
        coordinator = XToolCoordinator(hass, ip, dev_type)
        await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "name": entry.title,
        "entry_id": entry.entry_id,
        "device_type": dev_type,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
