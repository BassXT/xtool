from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
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
    """Set up the button entities."""
    store = hass.data[DOMAIN][entry.entry_id]
    coordinator = store["coordinator"]
    name: str = store["name"]
    entry_id: str = store["entry_id"]
    device_type: str = store.get("device_type", "").lower()

    # Only add the Sync button for the M1 Ultra
    if device_type in ("m1u", "m1 ultra"):
        async_add_entities([XToolSyncKnifeButton(coordinator, name, entry_id, device_type)])


class XToolSyncKnifeButton(CoordinatorEntity, ButtonEntity):
    """Button to sync/spin the knife module for detection."""
    _attr_has_entity_name = True
    _attr_icon = "mdi:sync"

    def __init__(self, coordinator, name: str, entry_id: str, device_type: str) -> None:
        super().__init__(coordinator)
        self._device_name = name
        self._entry_id = entry_id
        self._device_type = device_type
        self._attr_name = "Sync Knife Module"
        self._attr_unique_id = f"{entry_id}_sync_knife"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._device_name,
            "manufacturer": MANUFACTURER,
            "model": self._device_type.upper(),
        }

    @property
    def available(self) -> bool:
        """The button is only available when the Knife holder (ID 29) is inserted."""
        data = self.coordinator.data or {}
        if data.get("_unavailable"):
            return False
        
        # Check if the currently attached tool is the Knife Holder
        workhead = data.get("workhead_driving")
        if workhead is None:
            return False
        
        try:
            return int(workhead) == 29
        except (ValueError, TypeError):
            return False

    async def async_press(self) -> None:
        """Trigger the knife sync action."""
        # Send the get_sync command to spin and identify the specific knife blade
        await self.coordinator.hass.async_add_executor_job(
            self.coordinator._post, "/peripheral/knife_head", {"action": "get_sync"}
        )
        # Force a refresh to update the sensor immediately after syncing
        await self.coordinator.async_request_refresh()