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
from .coordinator_s1 import XToolS1Coordinator
from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_IP_ADDRESS,
    CONF_DEVICE_TYPE,
    CONF_HAS_AP2,
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_SLOW_UPDATE_INTERVAL,
    HTTP_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _safe_json(resp: requests.Response) -> Any:
    """Safely parse JSON responses."""
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        return (resp.text or "").strip()


def _is_invalid_or_not_supported(payload: Any) -> bool:
    """Detect unsupported endpoints / invalid request payloads."""
    if isinstance(payload, str):
        s = payload.strip().lower()
        return s in {"invalid request", "not support", "not supported"}
    if isinstance(payload, dict) and payload.get("code") == 10:
        msg = str(payload.get("msg", "")).lower()
        return "device not support" in msg
    return False


class XToolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """
    Coordinator for P2/F1/M1/M1 Ultra (v2 endpoints) + legacy fallback.

    Behavior:
    - M1 Ultra: keep PR sleep logic (avoid peripheral GETs + POSTs while sleeping to allow real sleep).
    - Other devices: keep pre-PR behavior (poll peripherals regardless of sleep).
    - F1: no drawer and no exhaust fan entities -> we also skip polling those endpoints here.
    """

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
        items: list[tuple[str, str, str, str]] = []
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
        """Normalize lid/gap state."""
        lid_open = None
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            state = str(data.get("state", "")).lower()
            if state in {"on", "off"}:
                # M1 Ultra uses inverted logic on /peripheral/gap
                if self.device_type in ("m1u", "m1 ultra"):
                    lid_open = (state == "off")  # off = open (M1U)
                else:
                    lid_open = (state == "on")  # on = open (P2/F1/M1)
        return {"lid_open": lid_open}

    def _normalize_smoking_fan(self, raw: Any) -> dict[str, Any]:
        """Normalize exhaust fan state and connectivity."""
        out = {"fan_state": None, "fan_exist": None}
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw.get("data", {})
            s = str(data.get("state", "")).lower()
            if s in {"on", "off"}:
                out["fan_state"] = s
            if isinstance(data.get("exist"), bool):
                out["fan_exist"] = data.get("exist")
        return out

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
            else:
                out["ext_purifier_exist"] = (str(data.get("version", "{}")) != "{}")
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
        """Normalize bottom drawer state (not applicable for M1 Ultra / F1)."""
        drawer_open = None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            st = str(raw["data"].get("state", "")).lower()
            if st in {"on", "off"}:
                # on = open, off = closed (your confirmed semantics)
                drawer_open = (st == "on")
        return {"drawer_open": drawer_open}

    def _normalize_airassist(self, raw: Any) -> dict[str, Any]:
        """Normalize AirAssist connectivity and running state."""
        out = {
            "airassist_state": None,
            "airassist_exist": None,
            "airassist_power": None,
            "airassist_version": None,
            "airassist_fire_trigger": None,
        }
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw["data"]
            try:
                power = float(data.get("power", 0))
            except (ValueError, TypeError):
                power = 0.0

            # more stable across firmwares: "on" only if power > 0
            out["airassist_state"] = "on" if power > 0 else "off"

            version = str(data.get("version", "")).strip()
            out["airassist_exist"] = bool(version)

            out["airassist_power"] = power
            out["airassist_version"] = version
            out["airassist_fire_trigger"] = data.get("fireTiggerSta")
        return out

    def _fetch_data_sync(self) -> dict[str, Any]:
        self._tick += 1

        # Start from previous data (prevents flicker to None/Unavailable)
        normalized: dict[str, Any] = dict(self.data or {})
        normalized["_unavailable"] = False

        # 1) runningStatus always (silent; PR behavior)
        try:
            raw_run = self._get("/device/runningStatus")
            if _is_invalid_or_not_supported(raw_run):
                raise RuntimeError("v2 runningStatus not supported")

            normalized.update(self._normalize_running_status(raw_run))
            self._log_reachability(True)

        except requests.exceptions.ConnectionError as err:
            self._log_reachability(False)
            _LOGGER.debug("XTool %s connection error: %s", self.ip_address, err)
            normalized["_unavailable"] = True
            return normalized

        except Exception:
            # legacy fallback
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
                normalized["_unavailable"] = True
                return normalized
            except Exception as err2:  # noqa: BLE001
                self._log_reachability(False)
                _LOGGER.debug("XTool %s update failed: %s", self.ip_address, err2)
                normalized["_unavailable"] = True
                return normalized

        # Sleep detection (PR logic)
        mode = str(normalized.get("work_state_raw") or "").upper()
        is_sleeping = "SLEEP" in mode or "STANDBY" in mode
        is_m1u = self.device_type in ("m1u", "m1 ultra")

        # Warnings
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

        # Polling strategy:
        # - M1U: keep PR behavior (no peripherals/POSTs in sleep)
        # - Others: keep old behavior (poll even in sleep)
        should_poll_peripherals = (not is_sleeping) if is_m1u else True
        should_poll_slow_gets = (not is_sleeping) if is_m1u else True
        should_poll_slow_posts = (not is_sleeping)  # POST never while sleeping

        # 2) Peripherals
        if should_poll_peripherals:
            peripherals: list[tuple[str, Any]] = [
                ("/peripheral/gap", self._normalize_gap),
                ("/peripheral/ext_purifier", self._normalize_ext_purifier),
                ("/peripheral/machine_lock", self._normalize_machine_lock),
            ]

            # F1: no exhaust fan endpoint/entity
            if self.device_type != "f1":
                peripherals.insert(1, ("/peripheral/smoking_fan", self._normalize_smoking_fan))

            # AirAssist: not wanted on F1 (you said remove it)
            if self.device_type != "f1":
                peripherals.append(("/peripheral/airassist", self._normalize_airassist))

            # Drawer: not on M1U and not on F1
            if self.device_type not in ("m1u", "m1 ultra", "f1"):
                peripherals.append(("/peripheral/drawer", self._normalize_drawer))

            for path, normalizer in peripherals:
                try:
                    raw = self._get(path)
                    if not _is_invalid_or_not_supported(raw):
                        normalized.update(normalizer(raw))
                except Exception:
                    pass

            # 3) M1 Ultra specific endpoints (only when awake)
            if is_m1u:
                try:
                    raw_hatch = self._get("/peripheral/heighten")
                    if isinstance(raw_hatch, dict) and isinstance(raw_hatch.get("data"), dict):
                        door = str(raw_hatch["data"].get("door", "")).lower()
                        if door in ("on", "off"):
                            normalized["hatch_open"] = (door == "off")
                except Exception:
                    pass

                try:
                    raw_wh = self._post("/peripheral/workhead_ID", {"action": "get"})
                    if isinstance(raw_wh, dict) and isinstance(raw_wh.get("data"), dict):
                        normalized["workhead_drived"] = raw_wh["data"].get("drived")
                        normalized["workhead_driving"] = raw_wh["data"].get("driving")
                except Exception:
                    pass

                try:
                    raw_knife = self._post("/peripheral/knife_head", {"action": "get"})
                    if isinstance(raw_knife, dict) and isinstance(raw_knife.get("data"), dict):
                        normalized["knife_driving"] = raw_knife["data"].get("driving")
                except Exception:
                    pass

                try:
                    raw_ink = self._post("/peripheral/inkjet_printer", {"action": "get"})
                    if isinstance(raw_ink, dict) and isinstance(raw_ink.get("data"), dict):
                        normalized["inkjet_exist"] = raw_ink["data"].get("exist")
                except Exception:
                    pass

        # 4) Slow extras
        if self._tick == 1 or (self._tick % self._slow_every) == 0:
            if should_poll_slow_gets:
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

            # POST config never in sleep (esp. M1U sleep bug)
            if should_poll_slow_posts:
                try:
                    cfg = self._post(
                        "/config/get",
                        {
                            "alias": "config",
                            "type": "user",
                            "kv": [
                                "beepEnable",
                                "fillLightBrightness",
                                "purifierTimeout",
                                "taskId",
                                "workingMode",
                            ],
                        },
                    )
                    if not _is_invalid_or_not_supported(cfg) and isinstance(cfg, dict):
                        self._cached_config = cfg
                        normalized["config"] = cfg
                except Exception:
                    pass

        # Always expose cached values
        if "machine_info" not in normalized:
            normalized["machine_info"] = self._cached_machine_info
        if "working_info" not in normalized:
            normalized["working_info"] = self._cached_working_info
        if "config" not in normalized:
            normalized["config"] = self._cached_config

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

    if dev_type == "d1":
        coordinator: DataUpdateCoordinator = XToolD1Coordinator(hass, ip)
        await coordinator.async_config_entry_first_refresh()
    elif dev_type == "s1":
        has_ap2 = entry.data.get(CONF_HAS_AP2, False)
        coordinator = XToolS1Coordinator(hass, ip, has_ap2=has_ap2)
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
