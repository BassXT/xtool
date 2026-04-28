from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor entities."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    d = coordinator.data or {}
    entities: list[BinarySensorEntity] = []

    # -------------------------
    # F1 V2 (NEU / CLEAN)
    # -------------------------
    if device_type == "f1_v2":
        entities.extend(
            [
                XToolPowerBinarySensor(coordinator, name, entry_id, device_type),
                XToolProblemBinarySensor(coordinator, name, entry_id, device_type),
                XToolRunningBinarySensor(coordinator, name, entry_id, device_type),
                XToolLidOpenBinarySensor(coordinator, name, entry_id, device_type),
                XToolMachineLockBinarySensor(coordinator, name, entry_id, device_type),

                # Flame Alarm (invertiert)
                XToolF1V2ConfigBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "flame_alarm_enabled",
                    "Flame Alarm",
                    BinarySensorDeviceClass.SAFETY,
                    invert=True,
                ),

                # Buzzer
                XToolF1V2ConfigBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "beep_enabled",
                    "Buzzer Reminder",
                    None,
                ),

                # Gap Check → Lid Stop (invertiert)
                XToolF1V2ConfigBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "gap_check_enabled",
                    "Stop when lid opened",
                    BinarySensorDeviceClass.SAFETY,
                    invert=True,
                ),

                # Working Mode → Stop when moved
                XToolF1V2WorkingModeBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                ),
            ]
        )
        async_add_entities(entities, True)
        return

    # -------------------------
    # S1
    # -------------------------
    if device_type == "s1":
        entities.extend(
            [
                S1PowerBinarySensor(coordinator, name, entry_id, device_type),
                S1RunningBinarySensor(coordinator, name, entry_id, device_type),
                S1AlarmBinarySensor(coordinator, name, entry_id, device_type),
                S1PurifierRunningBinarySensor(coordinator, name, entry_id, device_type),
            ]
        )
        async_add_entities(entities, True)
        return

    # -------------------------
    # D1
    # -------------------------
    if device_type == "d1":
        entities.extend(
            [
                D1PowerBinarySensor(coordinator, name, entry_id, device_type),
                D1RunningBinarySensor(coordinator, name, entry_id, device_type),
            ]
        )

        if d.get("tiltStopFlag") is not None:
            entities.append(
                D1FlagBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "tiltStopFlag",
                    "Tilt Stop",
                    BinarySensorDeviceClass.PROBLEM,
                )
            )

        async_add_entities(entities, True)
        return

    # -------------------------
    # Standard
    # -------------------------
    entities.extend(
        [
            XToolPowerBinarySensor(coordinator, name, entry_id, device_type),
            XToolAlarmBinarySensor(coordinator, name, entry_id, device_type),
            XToolRunningBinarySensor(coordinator, name, entry_id, device_type),
            XToolLidOpenBinarySensor(coordinator, name, entry_id, device_type),
        ]
    )

    if device_type != "p2":
        entities.append(XToolMachineLockBinarySensor(coordinator, name, entry_id, device_type))

    async_add_entities(entities, True)


# =========================================================
# BASE
# =========================================================

class _BaseBinary(CoordinatorEntity, BinarySensorEntity):
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


# =========================================================
# F1 V2 SPECIAL
# =========================================================

class XToolProblemBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Problem"
        self._attr_unique_id = f"{entry_id}_problem"

    @property
    def available(self):
        return not self._unavailable()

    @property
    def is_on(self):
        return bool(self._data().get("alarm_present"))


class XToolF1V2ConfigBinarySensor(_BaseBinary):
    def __init__(self, coordinator, name, entry_id, device_type, key, label, device_class, invert=False):
        super().__init__(coordinator, name, entry_id, device_type)
        self._key = key
        self._invert = invert
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_f1_v2_{key}"
        self._attr_device_class = device_class

    @property
    def available(self):
        return not self._unavailable() and self._data().get(self._key) is not None

    @property
    def is_on(self):
        value = bool(self._data().get(self._key))
        return not value if self._invert else value


class XToolF1V2WorkingModeBinarySensor(_BaseBinary):
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Stop when moved"
        self._attr_unique_id = f"{entry_id}_f1_v2_stop_when_moved"

    @property
    def available(self):
        return not self._unavailable() and self._data().get("working_mode") is not None

    @property
    def is_on(self):
        return str(self._data().get("working_mode") or "").upper() == "NORMAL"


# =========================================================
# COMMON
# =========================================================

class XToolPowerBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Power"
        self._attr_unique_id = f"{entry_id}_power"

    @property
    def is_on(self):
        return (not self._unavailable()) and bool(self.coordinator.last_update_success)


class XToolAlarmBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Alarm"
        self._attr_unique_id = f"{entry_id}_alarm"

    @property
    def is_on(self):
        return bool(self._data().get("alarm_present"))


class XToolRunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Running"
        self._attr_unique_id = f"{entry_id}_running"

    @property
    def is_on(self):
        return str(self._data().get("status") or "").lower() in {"framing", "ready", "working"}


class XToolLidOpenBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Lid"
        self._attr_unique_id = f"{entry_id}_lid_open"

    @property
    def is_on(self):
        return bool(self._data().get("lid_open"))


class XToolMachineLockBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator, name, entry_id, device_type):
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Machine Lock"
        self._attr_unique_id = f"{entry_id}_machine_lock"

    @property
    def is_on(self):
        return bool(self._data().get("machine_lock"))
