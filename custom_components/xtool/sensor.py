from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
    # noqa: E402
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import XToolCoordinator
from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XToolCoordinator = data["coordinator"]
    name: str = data["name"]
    entry_id: str = data["entry_id"]

    entities: list[SensorEntity] = [XToolWorkStateSensor(coordinator, name, entry_id)]

    if coordinator.device_type == "m1":
        entities += [
            XToolCPUTempSensor(coordinator, name, entry_id),
            XToolWaterTempSensor(coordinator, name, entry_id),
            XToolPurifierSensor(coordinator, name, entry_id),
        ]

    async_add_entities(entities, True)


class _XToolBaseSensor(CoordinatorEntity[XToolCoordinator], SensorEntity):
    """Base with consistent device info and naming."""

    _attr_has_entity_name = True  # -> entity_id prefix = <name_slug>_

    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._entry_id = entry_id

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
            "model": self.coordinator.device_type.upper(),
        }


class XToolWorkStateSensor(_XToolBaseSensor):
    """Work state (Running, Idle, Sleep, Done, ...)."""

    _attr_icon = "mdi:laser-pointer"

    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator, name, entry_id)
        self._attr_name = "Status"                    # visible as "<Name> Status"
        self._attr_unique_id = f"{entry_id}_status"   # stable

    @property
    def suggested_object_id(self) -> str:
        # Result: sensor.<name_slug>_<device_type>_status
        return f"{self.coordinator.device_type}_status"

    @property
    def native_value(self) -> str:
        data = self.coordinator.data or {}
        if data.get("_unavailable"):
            return "Unavailable"

        if self.coordinator.device_type in ("f1", "p2", "apparel"):
            mode = str(data.get("mode", "")).strip().upper()
            if mode:
                return self._map_mode(mode)
            return "Unknown"

        if self.coordinator.device_type == "m1":
            status = str(data.get("STATUS", "")).strip().upper()
            if status:
                return self._map_status(status)
            return "Unknown"

        return "Unknown"

    def _map_mode(self, mode: str) -> str:
        mapping = {"P_WORK_DONE": "Done", "WORK": "Running", "P_SLEEP": "Sleep", "P_IDLE": "Idle"}
        return mapping.get(mode, "Unknown")

    def _map_status(self, status: str) -> str:
        mapping = {
            "P_FINISH": "Done",
            "P_WORKING": "Running",
            "P_SLEEP": "Sleep",
            "P_ONLINE_READY_WORK": "Ready",
            "P_IDLE": "Idle",
        }
        return mapping.get(status, "Unknown")


# ----- M1 extra sensors -----

class _M1Base(_XToolBaseSensor):
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self) -> dict[str, Any]:
        info = super().device_info
        info["model"] = "M1"
        return info


class XToolCPUTempSensor(_M1Base):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator, name, entry_id)
        self._attr_name = "CPU Temp"
        self._attr_unique_id = f"{entry_id}_cpu_temp"

    @property
    def suggested_object_id(self) -> str:
        # Result: sensor.<name_slug>_<device_type>_cpu_temp
        return f"{self.coordinator.device_type}_cpu_temp"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return None if data.get("_unavailable") else data.get("CPU_TEMP")


class XToolWaterTempSensor(_M1Base):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator, name, entry_id)
        self._attr_name = "Water Temp"
        self._attr_unique_id = f"{entry_id}_water_temp"

    @property
    def suggested_object_id(self) -> str:
        return f"{self.coordinator.device_type}_water_temp"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return None if data.get("_unavailable") else data.get("WATER_TEMP")


class XToolPurifierSensor(_M1Base):
    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator, name, entry_id)
        self._attr_name = "Purifier"
        self._attr_unique_id = f"{entry_id}_purifier"

    @property
    def suggested_object_id(self) -> str:
        return f"{self.coordinator.device_type}_purifier"

    @property
    def native_value(self) -> Any:
        data = self.coordinator.data or {}
        return None if data.get("_unavailable") else data.get("Purifier")
