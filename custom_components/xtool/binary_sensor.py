from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    """Set up the binary sensor (Power) for each XTool entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: XToolCoordinator = data["coordinator"]
    name: str = data["name"]
    entry_id: str = data["entry_id"]

    async_add_entities([XToolPowerBinarySensor(coordinator, name, entry_id)], True)


class XToolPowerBinarySensor(CoordinatorEntity[XToolCoordinator], BinarySensorEntity):
    """Shows whether the device is reachable/powered on."""

    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_has_entity_name = True  # -> entity_id prefix = <name_slug>_

    def __init__(self, coordinator: XToolCoordinator, name: str, entry_id: str) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._entry_id = entry_id

        self._attr_name = "Power"                  # visible as "<Name> Power"
        self._attr_unique_id = f"{entry_id}_power" # stable unique id

    @property
    def suggested_object_id(self) -> str:
        # IMPORTANT: do NOT include the name here.
        # HA will prefix with <name_slug>_ automatically because has_entity_name=True.
        # Result: binary_sensor.<name_slug>_<device_type>_power
        return f"{self.coordinator.device_type}_power"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._device_name,                       # device name = your given name
            "manufacturer": MANUFACTURER,
            "model": self.coordinator.device_type.upper(),
        }

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        if data.get("_unavailable"):
            return False
        if self.coordinator.device_type in ("f1", "p2", "apparel"):
            return bool(str(data.get("mode", "")).strip())
        if self.coordinator.device_type == "m1":
            return bool(str(data.get("STATUS", "")).strip())
        return False
