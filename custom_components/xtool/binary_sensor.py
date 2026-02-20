from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    d = coordinator.data or {}

    entities: list[BinarySensorEntity] = []

    if device_type == "d1":
        entities += [
            D1PowerBinarySensor(coordinator, name, entry_id, device_type),
            D1RunningBinarySensor(coordinator, name, entry_id, device_type),
        ]

        # Optional flags (only if present)
        if d.get("tiltStopFlag") is not None:
            entities.append(D1FlagBinarySensor(coordinator, name, entry_id, device_type, "tiltStopFlag", "Tilt Stop", BinarySensorDeviceClass.PROBLEM))
        if d.get("limitStopFlag") is not None:
            entities.append(D1FlagBinarySensor(coordinator, name, entry_id, device_type, "limitStopFlag", "Limit Stop", BinarySensorDeviceClass.PROBLEM))
        if d.get("movingStopFlag") is not None:
            entities.append(D1FlagBinarySensor(coordinator, name, entry_id, device_type, "movingStopFlag", "Moving Stop", BinarySensorDeviceClass.PROBLEM))
        if d.get("sdCard") is not None:
            entities.append(D1FlagBinarySensor(coordinator, name, entry_id, device_type, "sdCard", "SD Card", BinarySensorDeviceClass.CONNECTIVITY))

        async_add_entities(entities, True)
        return

    # ---- P2/F1/M1 stack (existing)
    entities += [
        XToolPowerBinarySensor(coordinator, name, entry_id, device_type),
        XToolAlarmBinarySensor(coordinator, name, entry_id, device_type),
        XToolRunningBinarySensor(coordinator, name, entry_id, device_type),
    ]

    if d.get("lid_open") is not None:
        entities.append(XToolLidOpenBinarySensor(coordinator, name, entry_id, device_type))
    if d.get("machine_lock") is not None:
        entities.append(XToolMachineLockBinarySensor(coordinator, name, entry_id, device_type))
    if d.get("drawer_open") is not None:
        entities.append(XToolDrawerOpenBinarySensor(coordinator, name, entry_id, device_type))

    async_add_entities(entities, True)


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


# ----------------
# D1 entities
# ----------------
class D1PowerBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Power"
        self._attr_unique_id = f"{entry_id}_d1_power"

    @property
    def is_on(self) -> bool:
        return (not self._unavailable()) and bool(self.coordinator.last_update_success)


class D1RunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Running"
        self._attr_unique_id = f"{entry_id}_d1_running"

    @property
    def is_on(self) -> bool:
        return str(self._data().get("working_state") or "").lower() == "running"


class D1FlagBinarySensor(_BaseBinary):
    def __init__(
        self,
        coordinator,
        name: str,
        entry_id: str,
        device_type: str,
        key: str,
        label: str,
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._key = key
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_d1_{key}"
        self._attr_device_class = device_class

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get(self._key) is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get(self._key))


# -----------------------------
# P2/F1/M1 entities (existing)
# -----------------------------
class XToolPowerBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Power"
        self._attr_unique_id = f"{entry_id}_power"

    @property
    def is_on(self) -> bool:
        return (not self._unavailable()) and bool(self.coordinator.last_update_success)


class XToolAlarmBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Alarm"
        self._attr_unique_id = f"{entry_id}_alarm"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("alarm_present") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("alarm_present"))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._data()
        return {
            "warnings_count": d.get("warnings_count"),
            "warnings_summary": d.get("warnings_summary"),
            "warnings_changed": d.get("warnings_changed"),
            "warnings_hash": d.get("warnings_hash"),
            "task_id": d.get("task_id"),
            "alarm_current": d.get("alarm_current"),
        }


class XToolRunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Running"
        self._attr_unique_id = f"{entry_id}_running"

    @property
    def is_on(self) -> bool:
        raw = str(self._data().get("work_state_raw") or "").upper()
        return raw in {"WORK", "P_WORKING", "P_WORK", "P_MEASURE"}


class XToolLidOpenBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Lid Open"
        self._attr_unique_id = f"{entry_id}_lid_open"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("lid_open") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("lid_open"))


class XToolMachineLockBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Machine Lock"
        self._attr_unique_id = f"{entry_id}_machine_lock"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("machine_lock") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("machine_lock"))


class XToolDrawerOpenBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Drawer Open"
        self._attr_unique_id = f"{entry_id}_drawer_open"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("drawer_open") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("drawer_open"))
