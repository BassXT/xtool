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

    if device_type == "f1_v2":
    entities.extend(
        [
            XToolPowerBinarySensor(coordinator, name, entry_id, device_type),
            XToolProblemBinarySensor(coordinator, name, entry_id, device_type),
            XToolRunningBinarySensor(coordinator, name, entry_id, device_type),
            XToolLidOpenBinarySensor(coordinator, name, entry_id, device_type),
            XToolMachineLockBinarySensor(coordinator, name, entry_id, device_type),
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
            XToolF1V2ConfigBinarySensor(
                coordinator,
                name,
                entry_id,
                device_type,
                "beep_enabled",
                "Buzzer Reminder",
                None,
            ),
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
            XToolF1V2WorkingModeBinarySensor(
                coordinator,
                name,
                entry_id,
                device_type,
            ),
        ]
    )
    async_add_entities(entities, True)
    returnies(entities, True)
        return
        
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
        if d.get("limitStopFlag") is not None:
            entities.append(
                D1FlagBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "limitStopFlag",
                    "Limit Stop",
                    BinarySensorDeviceClass.PROBLEM,
                )
            )
        if d.get("movingStopFlag") is not None:
            entities.append(
                D1FlagBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "movingStopFlag",
                    "Moving Stop",
                    BinarySensorDeviceClass.PROBLEM,
                )
            )
        if d.get("sdCard") is not None:
            entities.append(
                D1FlagBinarySensor(
                    coordinator,
                    name,
                    entry_id,
                    device_type,
                    "sdCard",
                    "SD Card",
                    BinarySensorDeviceClass.CONNECTIVITY,
                )
            )

        async_add_entities(entities, True)
        return

    # --- Standard entities for P2, F1, M1, M1 Ultra ---
    entities.extend(
        [
            XToolPowerBinarySensor(coordinator, name, entry_id, device_type),
            XToolAlarmBinarySensor(coordinator, name, entry_id, device_type),
            XToolRunningBinarySensor(coordinator, name, entry_id, device_type),
            XToolLidOpenBinarySensor(coordinator, name, entry_id, device_type),
        ]
    )

    # Machine Lock: NOT on P2 (your requirement)
    if device_type != "p2":
        entities.append(XToolMachineLockBinarySensor(coordinator, name, entry_id, device_type))

    # Drawer: not on M1 Ultra and not on F1
    if device_type not in ("m1u", "m1 ultra", "f1"):
        entities.append(XToolDrawerOpenBinarySensor(coordinator, name, entry_id, device_type))

    # M1 Ultra specific accessory sensors
    if device_type in ("m1u", "m1 ultra"):
        entities.extend(
            [
                XToolAirAssistConnectedBinarySensor(coordinator, name, entry_id, device_type),
                XToolFanConnectedBinarySensor(coordinator, name, entry_id, device_type),
                XToolExtPurifierConnectedBinarySensor(coordinator, name, entry_id, device_type),
                XToolHatchBinarySensor(coordinator, name, entry_id, device_type),
                XToolInkModuleCableBinarySensor(coordinator, name, entry_id, device_type),
            ]
        )

    async_add_entities(entities, True)


class _BaseBinary(CoordinatorEntity, BinarySensorEntity):
    """Base class for xTool binary sensors."""

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

class XToolF1V2ConfigBinarySensor(_BaseBinary):
    def __init__(
        self,
        coordinator,
        name: str,
        entry_id: str,
        device_type: str,
        key: str,
        label: str,
        device_class: BinarySensorDeviceClass | None,
        invert: bool = False,
    ) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._key = key
        self._invert = invert
        self._attr_name = label
        self._attr_unique_id = f"{entry_id}_f1_v2_{key}"
        self._attr_device_class = device_class

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get(self._key) is not None

    @property
    def is_on(self) -> bool:
        value = bool(self._data().get(self._key))
        return not value if self._invert else value

class XToolProblemBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Problem"
        self._attr_unique_id = f"{entry_id}_problem"

    @property
    def available(self) -> bool:
        return not self._unavailable()

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("alarm_present"))

class XToolF1V2WorkingModeBinarySensor(_BaseBinary):
    _attr_icon = "mdi:motion-sensor"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Stop when moved"
        self._attr_unique_id = f"{entry_id}_f1_v2_stop_when_moved"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("working_mode") is not None

    @property
    def is_on(self) -> bool:
        mode = str(self._data().get("working_mode") or "").upper()

        # xTool:
        # NORMAL = stop when moved enabled
        # HANDLE = handheld mode, stop when moved disabled
        return mode == "NORMAL"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "mode_raw": self._data().get("working_mode"),
        }
        
# --- S1 ---
class S1PowerBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.POWER

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Power"
        self._attr_unique_id = f"{entry_id}_s1_power"

    @property
    def is_on(self) -> bool:
        return (not self._unavailable()) and bool(self.coordinator.last_update_success)


class S1RunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Running"
        self._attr_unique_id = f"{entry_id}_s1_running"

    @property
    def is_on(self) -> bool:
        # S13=Starting, S14=Running, S19=Finishing are all "active" states
        return self._data().get("work_state_raw") in ("S13", "S14", "S19")


class S1AlarmBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Alarm"
        self._attr_unique_id = f"{entry_id}_s1_alarm"

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and not self._unavailable()

    @property
    def is_on(self) -> bool:
        return self._data().get("alarm_present") is True


class S1PurifierRunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:air-purifier"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Air Cleaner"
        self._attr_unique_id = f"{entry_id}_s1_purifier_running"

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and not self._unavailable()
            and self._data().get("purifier_on") is not None
        )

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("purifier_on"))


# --- D1 ---
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


# --- P2/F1/M1 ---
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
        return not self._unavailable()

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("alarm_present"))


class XToolRunningBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Running"
        self._attr_unique_id = f"{entry_id}_running"

    @property
    def available(self) -> bool:
        return not self._unavailable()

    @property
    def is_on(self) -> bool:
        status = str(self._data().get("status") or "").lower()
        if status in {"framing", "framing_prepared", "ready", "working"}:
            return True

        raw = str(self._data().get("work_state_raw") or "").upper()
        return raw in {"WORK", "P_WORKING", "P_WORK", "P_MEASURE"}

class XToolLidOpenBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Lid"
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
        # Rename: "Drawer" (not "Drawer Open")
        self._attr_name = "Drawer"
        self._attr_unique_id = f"{entry_id}_drawer_open"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("drawer_open") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("drawer_open"))


# --- M1 Ultra Accessory Sensors ---
class XToolHatchBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Hatch"
        self._attr_unique_id = f"{entry_id}_hatch"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("hatch_open") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("hatch_open"))


class XToolAirAssistConnectedBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "AirAssist Connected"
        self._attr_unique_id = f"{entry_id}_airassist_connected"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("airassist_exist") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("airassist_exist"))


class XToolFanConnectedBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Exhaust Fan Connected"
        self._attr_unique_id = f"{entry_id}_fan_connected"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("fan_exist") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("fan_exist"))


class XToolExtPurifierConnectedBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "External Purifier Connected"
        self._attr_unique_id = f"{entry_id}_ext_purifier_connected"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("ext_purifier_exist") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("ext_purifier_exist"))


class XToolInkModuleCableBinarySensor(_BaseBinary):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator, name, entry_id, device_type)
        self._attr_name = "Ink Module Cable"
        self._attr_unique_id = f"{entry_id}_ink_cable"

    @property
    def available(self) -> bool:
        if self._unavailable():
            return False
        return self._data().get("inkjet_exist") is not None

    @property
    def is_on(self) -> bool:
        return bool(self._data().get("inkjet_exist"))
