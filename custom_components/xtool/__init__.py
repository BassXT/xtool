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
    DOMAIN, PLATFORMS, CONF_IP_ADDRESS, CONF_DEVICE_TYPE,
    DEFAULT_UPDATE_INTERVAL, DEFAULT_SLOW_UPDATE_INTERVAL, HTTP_TIMEOUT
)

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _safe_json(resp: requests.Response) -> Any:
    """Helper to safely parse JSON responses."""
    try:
        return resp.json()
    except Exception:
        return (resp.text or "").strip()


def _is_invalid_or_not_supported(payload: Any) -> bool:
    """Check if the API returned an unsupported or invalid request error."""
    if isinstance(payload, str):
        s = payload.strip().lower()
        return s in {"invalid request", "not support", "not supported"}
    if isinstance(payload, dict) and payload.get("code") == 10:
        return "device not support" in str(payload.get("msg", "")).lower()
    return False


class XToolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for P2/F1/M1/M1 Ultra (v2 endpoints) + legacy fallback."""
    def __init__(self, hass: HomeAssistant, ip_address: str, device_type: str) -> None:
        super().__init__(
            hass, _LOGGER, name=f"xtool_{ip_address}", 
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
        )
        self.ip_address = ip_address
        self.device_type = device_type.lower()
        self._reachable_last: bool | None = None
        self._slow_every = max(1, int(DEFAULT_SLOW_UPDATE_INTERVAL / max(1, DEFAULT_UPDATE_INTERVAL)))
        self._tick = 0
        self._cached_machine_info: dict[str, Any] | None = None
        self._cached_working_info: dict[str, Any] | None = None
        self._cached_config: dict[str, Any] | None = None
        self._warnings_hash_last: str | None = None

    def _get(self, path: str) -> Any:
        """Send a GET request to the device."""
        url = f"http://{self.ip_address}:8080{path}"
        resp = requests.get(url, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return _safe_json(resp)

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        """Send a POST request to the device."""
        url = f"http://{self.ip_address}:8080{path}"
        resp = requests.post(url, json=payload, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        return _safe_json(resp)

    def _warnings_list(self, alarm_obj: Any) -> list[dict[str, Any]]:
        """Extract warning objects into a standard list."""
        if not isinstance(alarm_obj, dict):
            return []
        alarm_list = alarm_obj.get("alarm")
        if isinstance(alarm_list, list):
            return [a for a in alarm_list if isinstance(a, dict)]
        return [v for k, v in alarm_obj.items() if str(k).isdigit() and isinstance(v, dict)]

    def _warnings_summary(self, warnings: list[dict[str, Any]]) -> str:
        """Create a readable summary string of all active warnings."""
        parts = []
        for w in warnings:
            m = str(w.get("module", "")).strip()
            t = str(w.get("type", "")).strip()
            l = str(w.get("level", "")).strip()
            i = str(w.get("info", "")).strip()
            p = f"{m}:{t}" if (m or t) else "UNKNOWN"
            if l: p += f" ({l})"
            if i: p += f" - {i}"
            parts.append(p)
        return "; ".join(parts)

    def _warnings_hash(self, warnings: list[dict[str, Any]]) -> str:
        """Generate a hash string to detect changes in warnings."""
        items = [
            (str(w.get("module", "")), str(w.get("type", "")), str(w.get("level", "")), str(w.get("info", ""))) 
            for w in warnings
        ]
        items.sort()
        return "|".join(["/".join(i) for i in items])

    def _count_warnings(self, alarm_obj: Any) -> int:
        """Count the number of active warnings."""
        if not isinstance(alarm_obj, dict):
            return 0
        alarm_list = alarm_obj.get("alarm")
        if isinstance(alarm_list, list):
            return len(alarm_list)
        return len([k for k in alarm_obj.keys() if str(k).isdigit()])

    def _normalize_running_status(self, raw: Any) -> dict[str, Any]:
        """Normalize the runningStatus response."""
        out: dict[str, Any] = {
            "work_state_raw": None, "task_id": None, "cpu_temp": None, 
            "alarm_present": None, "alarm_current": None, "alarm_history": None, "dev_time": None
        }
        if not isinstance(raw, dict):
            return out
        data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
        cur_mode = data.get("curMode") if isinstance(data.get("curMode"), dict) else {}
        
        out["cpu_temp"] = data.get("cpuTemp")
        out["dev_time"] = data.get("devTime")
        out["work_state_raw"] = cur_mode.get("mode")
        out["task_id"] = cur_mode.get("taskId")
        out["alarm_current"] = data.get("curAlarmInfo")
        out["alarm_history"] = data.get("alarmInfo")
        out["alarm_present"] = len(self._warnings_list(out["alarm_current"])) > 0
        return out

    def _normalize_gap(self, raw: Any) -> dict[str, Any]:
        """Normalize lid/gap state."""
        lid_open = None
        if isinstance(raw, dict):
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            if str(data.get("state", "")).lower() in {"on", "off"}:
                lid_open = (str(data.get("state", "")).lower() == "off") # off means open for M1U
        return {"lid_open": lid_open}

    def _normalize_smoking_fan(self, raw: Any) -> dict[str, Any]:
        """Normalize exhaust fan state and connectivity."""
        out = {"fan_state": None, "fan_exist": None}
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw.get("data", {})
            if str(data.get("state", "")).lower() in {"on", "off"}:
                out["fan_state"] = str(data.get("state", "")).lower()
            if isinstance(data.get("exist"), bool):
                out["fan_exist"] = data.get("exist")
        return out

    def _normalize_ext_purifier(self, raw: Any) -> dict[str, Any]:
        """Normalize external purifier state."""
        out = {
            "ext_purifier_state": None, "ext_purifier_exist": None, 
            "ext_purifier_power": None, "ext_purifier_current": None
        }
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw["data"]
            if str(data.get("state", "")).lower() in {"on", "off"}:
                out["ext_purifier_state"] = str(data.get("state", "")).lower()
            if isinstance(data.get("exist"), bool):
                out["ext_purifier_exist"] = data.get("exist")
            else:
                out["ext_purifier_exist"] = (data.get("version", "{}") != "{}")
            out["ext_purifier_power"] = data.get("power")
            out["ext_purifier_current"] = data.get("current")
        return out

    def _normalize_machine_lock(self, raw: Any) -> dict[str, Any]:
        """Normalize machine physical lock."""
        locked = None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            if str(raw["data"].get("state", "")).lower() in {"on", "off"}:
                locked = (str(raw["data"].get("state", "")).lower() == "on")
        return {"machine_lock": locked}

    def _normalize_drawer(self, raw: Any) -> dict[str, Any]:
        """Normalize bottom drawer state (Not applicable for M1 Ultra)."""
        drawer_open = None
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            if str(raw["data"].get("state", "")).lower() in {"on", "off"}:
                drawer_open = (str(raw["data"].get("state", "")).lower() == "off")
        return {"drawer_open": drawer_open}

    def _normalize_airassist(self, raw: Any) -> dict[str, Any]:
        """Normalize AirAssist connectivity and running state."""
        out = {
            "airassist_state": None, "airassist_exist": None, 
            "airassist_power": None, "airassist_version": None, "airassist_fire_trigger": None
        }
        if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
            data = raw["data"]
            try: 
                power = float(data.get("power", 0))
            except (ValueError, TypeError): 
                power = 0.0
            
            # The AirAssist is only actively blowing if power > 0
            out["airassist_state"] = "on" if power > 0 else "off"
            version = str(data.get("version", "")).strip()
            out["airassist_exist"] = bool(version)
            out["airassist_power"] = power
            out["airassist_version"] = version
            out["airassist_fire_trigger"] = data.get("fireTiggerSta")
        return out

    def _fetch_data_sync(self) -> dict[str, Any]:
        """Main polling function running in an executor job."""
        self._tick += 1
        
        # Load previous data to prevent sensors from becoming "Unavailable"
        normalized: dict[str, Any] = {}
        if self.data:
            normalized = dict(self.data)
        normalized["_unavailable"] = False

        # 1. Fetch runningStatus (Silent fetch, doesn't wake up the device)
        try:
            raw_run = self._get("/device/runningStatus")
            if _is_invalid_or_not_supported(raw_run):
                raise RuntimeError("v2 runningStatus not supported")
            normalized.update(self._normalize_running_status(raw_run))
            self._log_reachability(True)
        except requests.exceptions.ConnectionError as err:
            self._log_reachability(False)
            normalized["_unavailable"] = True
            return normalized
        except Exception:
            # Fallback for older legacy devices
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
            except Exception:
                self._log_reachability(False)
                normalized["_unavailable"] = True
                return normalized

        # Check if the machine is in sleep mode
        mode = str(normalized.get("work_state_raw") or "").upper()
        is_sleeping = "SLEEP" in mode or "STANDBY" in mode

        # Process Warnings
        normalized["warnings_count"] = self._count_warnings(normalized.get("alarm_current"))
        warnings = self._warnings_list(normalized.get("alarm_current"))
        normalized["warnings_details"] = warnings
        normalized["warnings_summary"] = self._warnings_summary(warnings)
        h = self._warnings_hash(warnings)
        normalized["warnings_hash"] = h
        normalized["warnings_changed"] = (self._warnings_hash_last is not None and h != self._warnings_hash_last)
        self._warnings_hash_last = h

        # 2. Fetch peripherals ONLY if the machine is currently awake
        if not is_sleeping:
            
            # Prepare the list of endpoints to poll
            peripherals = [
                ("/peripheral/gap", self._normalize_gap),
                ("/peripheral/smoking_fan", self._normalize_smoking_fan),
                ("/peripheral/ext_purifier", self._normalize_ext_purifier),
                ("/peripheral/machine_lock", self._normalize_machine_lock),
                ("/peripheral/airassist", self._normalize_airassist),
            ]
            
            # The M1 Ultra does not have a drawer, skip polling it to save requests
            if self.device_type not in ("m1u", "m1 ultra"):
                peripherals.append(("/peripheral/drawer", self._normalize_drawer))

            for path, normalizer in peripherals:
                try:
                    raw = self._get(path)
                    if not _is_invalid_or_not_supported(raw):
                        normalized.update(normalizer(raw))
                except Exception:
                    pass

            # 3. M1 Ultra specific POST requests (Carriages, Hatch, Knifes)
            if self.device_type in ("m1u", "m1 ultra"):
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
                    # Retrieves the currently detected knife (requires physical sync first)
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

            # 4. Slow polling endpoints (Machine Info, Config)
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
                        {"alias": "config", "type": "user", "kv": ["beepEnable", "workingMode"]}
                    )
                    if not _is_invalid_or_not_supported(cfg) and isinstance(cfg, dict):
                        self._cached_config = cfg
                        normalized["config"] = cfg
                except Exception:
                    pass

        return normalized

    def _log_reachability(self, reachable: bool) -> None:
        """Log online/offline status changes."""
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
    """Set up the XTool integration from a config entry."""
    ip = entry.data[CONF_IP_ADDRESS]
    dev_type = entry.data[CONF_DEVICE_TYPE].lower()

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
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok