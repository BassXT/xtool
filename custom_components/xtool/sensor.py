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
    """Set up the sensor entities."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    entities: list[SensorEntity] = []

    if device_type == "d1":
        entities.extend(
            [
                D1StatusSensor(coordinator, name, entry_id, device_type),
                D1ProgressSensor(coordinator, name, entry_id, device_type),
                D1WorkingTimeSensor(coordinator, name, entry_id, device_type),
                D1LineSensor(coordinator, name, entry_id, device_type),
                D1MachineTypeSensor(coordinator, name, entry_id, device_type),
            ]
        )
        async_add_entities(entities, True)
        return

    # Common (P2/F1/M1/M1U)
    entities.extend(
        [
            XToolWorkStateSensor(coordinator, name, entry_id, device_type),
            XToolCpuTempSensor(coordinator, name, entry_id, device_type),
            XToolWarningsCountSensor(coordinator, name, entry_id, device_type),
            XToolJobsSensor(coordinator, name, entry_id, device_type),
            XToolSystemRuntimeSensor(coordinator, name, entry_id, device_type),
        ]
    )

    # Peripherals Sensors
    if device_type == "f1":
        # F1: the device reports "fan" via ext_purifier_state -> show it as Exhaust Fan State
        entities.append(XToolF1ExhaustFanStateViaPurifierSensor(coordinator, name, entry_id, device_type))
        # F1: explicitly no AirAssist sensor (and you said no drawer etc. handled elsewhere)
    else:
        entities.extend(
            [
                XToolFanStateSensor(coordinator, name, entry_id, device_type),
                XToolExtPurifierStateSensor(coordinator, name, entry_id, device_type),
                XToolAirAssistSensor(coordinator, name, entry_id, device_type),
            ]
        )

    if device_type == "m1":
        entities.extend(
            [
                XToolLegacyWaterTempSensor(coordinator, name, entry_id, device_type),
                XToolLegacyPurifierSensor(coordinator, name, entry_id, device_type),
            ]
        )

    if device_type in ("m1u", "m1 ultra"):
        entities.extend(
            [
                XToolBasicCarriageSensor(coordinator, name, entry_id, device_type),
                XToolMultiFunctionCarriageSensor(coordinator, name, entry_id, device_type),
                XToolMultiFunctionModuleSensor(coordinator, name, entry_id, device_type),
            ]
        )

    async_add_entities(entities, True)


class _BaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for xTool sensors."""

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


# --- D1 ---
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
        return round(float(s) / 3600.0, 2) if s is not None else None


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


# --- P2/F1/M1/M1U ---
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


class XToolFanStateSensor(_BaseSensor):
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Exhaust Fan State"
        self._attr_unique_id = f"{entry_id}_fan_state"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        st = self._data().get("fan_state")
        if st == "on":
            return "On"
        if st == "off":
            return "Off"
        return st


class XToolExtPurifierStateSensor(_BaseSensor):
    _attr_icon = "mdi:air-filter"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "External Purifier State"
        self._attr_unique_id = f"{entry_id}_ext_purifier"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        st = self._data().get("ext_purifier_state")
        if st == "on":
            return "On"
        if st == "off":
            return "Off"
        return st


class XToolF1ExhaustFanStateViaPurifierSensor(_BaseSensor):
    """
    F1 special case:
    The device reports the fan state via ext_purifier_state endpoint,
    but in HA we want it to show up as "Exhaust Fan State".
    """

    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Exhaust Fan State"
        # keep the same unique_id as the purifier sensor would have used
        self._attr_unique_id = f"{entry_id}_ext_purifier"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        st = self._data().get("ext_purifier_state")
        if st == "on":
            return "On"
        if st == "off":
            return "Off"
        return st


class XToolAirAssistSensor(_BaseSensor):
    _attr_icon = "mdi:weather-windy"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "AirAssist State"
        self._attr_unique_id = f"{entry_id}_airassist"

    @property
    def native_value(self) -> Any:
        if self._unavailable():
            return None
        st = self._data().get("airassist_state")
        if st == "on":
            return "On"
        if st == "off":
            return "Off"
        return st


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


# --- M1 Ultra Accessory Sensors ---
class XToolBasicCarriageSensor(_BaseSensor):
    _attr_icon = "mdi:tools"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Basic Carriage"
        self._attr_unique_id = f"{entry_id}_basic_carriage"

    @property
    def native_value(self) -> str | None:
        if self._unavailable():
            return None
        val = self._data().get("workhead_driving")
        if val is None:
            return "Waiting for data..."
        try:
            val_int = int(val)
        except (ValueError, TypeError):
            return f"Unknown ({val})"

        mapping = {0: "Empty", 15: "Laser 10W", 16: "Laser 20W", 29: "Knife holder", 31: "Ink printer"}
        return mapping.get(val_int, f"Unknown ({val_int})")


class XToolMultiFunctionCarriageSensor(_BaseSensor):
    _attr_icon = "mdi:toolbox"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Multi-function Carriage"
        self._attr_unique_id = f"{entry_id}_multi_carriage"

    @property
    def native_value(self) -> str | None:
        if self._unavailable():
            return None
        val = self._data().get("workhead_drived")
        if val is None:
            return "Waiting for data..."
        try:
            val_int = int(val)
        except (ValueError, TypeError):
            return f"Unknown ({val})"

        mapping = {41: "Empty", 42: "Pen", 43: "Fine Point Blade", 44: "Hot Embossing"}
        return mapping.get(val_int, f"Unknown ({val_int})")


class XToolMultiFunctionModuleSensor(_BaseSensor):
    _attr_icon = "mdi:knife"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Multi-function Module"
        self._attr_unique_id = f"{entry_id}_multi_module"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        carriage_id = self._data().get("workhead_driving")
        if carriage_id is None:
            return False
        try:
            return int(carriage_id) == 29
        except (ValueError, TypeError):
            return False

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        val = self._data().get("knife_driving")
        if val is None:
            return "Waiting for data..."
        try:
            val_int = int(val)
        except (ValueError, TypeError):
            return f"Unknown ({val})"

        mapping = {0: "Empty / Not synced", 22: "Embossing", 23: "Knife blade", 24: "Rotary blade"}
        return mapping.get(val_int, f"Unknown ({val_int})")
