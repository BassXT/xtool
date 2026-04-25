from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up switch entities."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    entities: list[SwitchEntity] = []

    # D1 and S1 have their own API stacks -> no v2 peripheral switches here
    if device_type in ("d1", "s1"):
        async_add_entities(entities, True)
        return

    # F1: no exhaust fan control 
    # M1 Ultra: keep as-is (it supports peripherals)
    if device_type != "f1":
        entities.append(XToolExhaustFanSwitch(coordinator, name, entry_id, device_type))

    async_add_entities(entities, True)


class XToolExhaustFanSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._entry_id = entry_id
        self._device_type = device_type
        self._attr_name = "Exhaust Fan"
        self._attr_unique_id = f"{entry_id}_exhaust_fan_switch"

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
            "model": self._device_type.upper(),
        }

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        # Only available if device is reachable AND the endpoint exists / state is present
        if bool(data.get("_unavailable")):
            return False
        return data.get("fan_state") is not None

    @property
    def is_on(self) -> bool | None:
        data = self.coordinator.data or {}
        state = data.get("fan_state")
        if state is None:
            return None
        return str(state).lower() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator._post,
            "/peripheral/smoking_fan",
            {"action": "on"},
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator._post,
            "/peripheral/smoking_fan",
            {"action": "off"},
        )
        await self.coordinator.async_request_refresh()
