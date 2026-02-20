from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import UnitOfTemperature, UnitOfTime, PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    d = coordinator.data or {}

    entities: list[SensorEntity] = []

    if device_type == "d1":
        entities += [
            D1StatusSensor(coordinator, name, entry_id, device_type),
            D1ProgressSensor(coordinator, name, entry_id, device_type),
            D1WorkingTimeSensor(coordinator, name, entry_id, device_type),
            D1LineSensor(coordinator, name, entry_id, device_type),
            D1MachineTypeSensor(coordinator, name, entry_id, device_type),
        ]
        async_add_entities(entities, True)
        return

    # ---- P2/F1/M1 existing sensor set (minimal)
    entities += [
        XToolWorkStateSensor(coordinator, name, entry_id, device_type),
        XToolCpuTempSensor(coordinator, name, entry_id, device_type),
        XToolWarningsCountSensor(coordinator, name, entry_id, device_type),
        XToolJobsSensor(coordinator, name, entry_id, device_type),
        XToolSystemRuntimeSensor(coordinator, name, entry_id, device_type),
    ]

    if d.get("fan_state") is not None:
        entities.append(XToolFanStateSensor(coordinator, name, entry_id, device_type))
    if d.get("ext_purifier_state") is not None or d.get("ext_purifier_exist") is not None:
        entities.append(XToolExtPurifierStateSensor(coordinator, name, entry_id, device_type))
    if d.get("airassist_state") is not None or d.get("airassist_version") is not None:
        entities.append(XToolAirAssistSensor(coordinator, name, entry_id, device_type))

    if device_type == "m1":
        entities += [
            XToolLegacyWaterTempSensor(coordinator, name, entry_id, device_type),
            XToolLegacyPurifierSensor(coordinator, name, entry_id, device_type),
        ]

    async_add_entities(entities, True)


class _BaseSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._entry_id = entry_id
        self._device_type = device_type

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
            "model": self._device_type.upper(),
        }

    def _data(self) -> dict[str, Any]:
        return self.coordinator.data or {}

    def _unavailable(self) -> bool:
        return bool(self._data().get("_unavailable"))


# ----------------
# D1 Sensors
# ----------------
class D1StatusSensor(_BaseSensor):
    _attr_icon = "mdi:laser-pointer"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry_id}_d1_status"

    @property
    def native_value(self) -> str:
        if self._unavailable():
            return "Unavailable"
        return str(self._data().get("working_state") or "Unknown")


class D1ProgressSensor(_BaseSensor):
    _attr_icon = "mdi:progress-clock"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Progress"
        self._attr_unique_id = f"{entry_id}_d1_progress"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("progress_pct")


class D1WorkingTimeSensor(_BaseSensor):
    _attr_icon = "mdi:timer-outline"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Working Time"
        self._attr_unique_id = f"{entry_id}_d1_working_time"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        s = self._data().get("working_s")
        if s is None:
            return None
        return round(float(s) / 3600.0, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self._data().get("working_s")
        if s is None:
            return {}
        hours = float(s) / 3600.0
        return {"seconds": s, "days": round(hours / 24.0, 2)}


class D1LineSensor(_BaseSensor):
    _attr_icon = "mdi:format-list-numbered"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Line"
        self._attr_unique_id = f"{entry_id}_d1_line"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("line")


class D1MachineTypeSensor(_BaseSensor):
    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Machine Type"
        self._attr_unique_id = f"{entry_id}_d1_machine_type"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("machine_type")


# -----------------------------
# P2/F1/M1 Sensors (existing)
# -----------------------------
class XToolWorkStateSensor(_BaseSensor):
    _attr_icon = "mdi:laser-pointer"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Status"
        self._attr_unique_id = f"{entry_id}_status"

    def _map_mode(self, mode: str) -> str:
        mapping = {
            "P_ERROR": "Error",
            "WORK": "Running",
            "P_WORK": "Running",
            "P_WORKING": "Running",
            "P_WORK_DONE": "Done",
            "P_FINISH": "Done",
            "P_IDLE": "Idle",
            "P_SLEEP": "Sleep",
            "P_ONLINE_READY_WORK": "Ready",
            "P_OFFLINE_READY_WORK": "Ready",
            "P_READY": "Ready",
            "P_MEASURE": "Measuring",
        }
        return mapping.get(mode, "Unknown")

    def _map_status(self, status: str) -> str:
        mapping = {
            "P_ONLINE_READY_WORK": "Ready",
            "P_OFFLINE_READY_WORK": "Ready",
            "P_WORK_DONE": "Done",
            "P_IDLE": "Idle",
            "P_SLEEP": "Sleep",
            "P_MEASURE": "Measuring",
            "P_ERROR": "Error",
        }
        return mapping.get(status, self._map_mode(status))

    @property
    def native_value(self) -> str:
        d = self._data()
        if d.get("_unavailable"):
            return "Unavailable"

        if self._device_type == "m1":
            legacy = d.get("legacy") if isinstance(d.get("legacy"), dict) else {}
            status = str(legacy.get("STATUS", "")).strip().upper()
            if status:
                return self._map_status(status)
            raw = str(d.get("work_state_raw") or "").strip().upper()
            return self._map_mode(raw) if raw else "Unknown"

        raw = str(d.get("work_state_raw") or "").strip().upper()
        return self._map_mode(raw) if raw else "Unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        return {
            "work_state_raw": d.get("work_state_raw"),
            "task_id": d.get("task_id"),
            "warnings_count": d.get("warnings_count"),
            "warnings_summary": d.get("warnings_summary"),
        }


class XToolCpuTempSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "CPU Temp"
        self._attr_unique_id = f"{entry_id}_cpu_temp"

    @property
    def native_value(self) -> Any:
        d = self._data()
        if self._unavailable():
            return None
        if d.get("cpu_temp") is not None:
            return d.get("cpu_temp")
        legacy = d.get("legacy") if isinstance(d.get("legacy"), dict) else {}
        return legacy.get("CPU_TEMP")


class XToolWarningsCountSensor(_BaseSensor):
    _attr_icon = "mdi:alert"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Warnings"
        self._attr_unique_id = f"{entry_id}_warnings"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("warnings_count")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        return {
            "warnings_summary": d.get("warnings_summary"),
            "warnings_details": d.get("warnings_details"),
            "warnings_changed": d.get("warnings_changed"),
            "warnings_hash": d.get("warnings_hash"),
        }


class XToolJobsSensor(_BaseSensor):
    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Jobs"
        self._attr_unique_id = f"{entry_id}_jobs"

    @property
    def native_value(self) -> Any:
        d = self._data()
        if self._unavailable():
            return None
        wi = d.get("working_info")
        if isinstance(wi, dict) and isinstance(wi.get("data"), dict):
            return wi["data"].get("numOnlineWorking")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        wi = d.get("working_info")
        if not (isinstance(wi, dict) and isinstance(wi.get("data"), dict)):
            return {}
        return {
            "online": wi["data"].get("numOnlineWorking"),
            "offline": wi["data"].get("numOfflineWorking"),
            "timeModeWorking": wi["data"].get("timeModeWorking"),
            "timeSystemWork": wi["data"].get("timeSystemWork"),
        }


class XToolSystemRuntimeSensor(_BaseSensor):
    _attr_icon = "mdi:clock-outline"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "System Runtime"
        self._attr_unique_id = f"{entry_id}_runtime_system"

    @property
    def native_value(self) -> Any:
        d = self._data()
        if self._unavailable():
            return None
        wi = d.get("working_info")
        if isinstance(wi, dict) and isinstance(wi.get("data"), dict):
            seconds = wi["data"].get("timeSystemWork")
            if seconds is None:
                return None
            return round(float(seconds) / 3600.0, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        wi = d.get("working_info")
        if not (isinstance(wi, dict) and isinstance(wi.get("data"), dict)):
            return {}
        seconds = wi["data"].get("timeSystemWork")
        if seconds is None:
            return {}
        hours = float(seconds) / 3600.0
        return {"seconds": seconds, "days": round(hours / 24.0, 2)}


class XToolFanStateSensor(_BaseSensor):
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Exhaust Fan"
        self._attr_unique_id = f"{entry_id}_fan_state"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("fan_state")


class XToolExtPurifierStateSensor(_BaseSensor):
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "External Purifier"
        self._attr_unique_id = f"{entry_id}_ext_purifier"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("ext_purifier_state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        return {
            "exist": d.get("ext_purifier_exist"),
            "power": d.get("ext_purifier_power"),
            "current": d.get("ext_purifier_current"),
        }


class XToolAirAssistSensor(_BaseSensor):
    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "AirAssist"
        self._attr_unique_id = f"{entry_id}_airassist"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        return self._data().get("airassist_state")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        return {
            "power": d.get("airassist_power"),
            "version": d.get("airassist_version"),
            "fire_trigger_state": d.get("airassist_fire_trigger"),
        }


class XToolLegacyWaterTempSensor(_BaseSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer-water"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Water Temp"
        self._attr_unique_id = f"{entry_id}_water_temp"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        legacy = self._data().get("legacy") if isinstance(self._data().get("legacy"), dict) else {}
        return legacy.get("WATER_TEMP")


class XToolLegacyPurifierSensor(_BaseSensor):
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Purifier"
        self._attr_unique_id = f"{entry_id}_purifier"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        legacy = self._data().get("legacy") if isinstance(self._data().get("legacy"), dict) else {}
        return legacy.get("Purifier")
