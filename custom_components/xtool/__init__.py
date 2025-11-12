from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import requests
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_IP_ADDRESS,
    CONF_DEVICE_TYPE,
    DEFAULT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

# Diese Integration hat keine YAML-Konfiguration und wird ausschließlich über Config Entries (UI) eingerichtet.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class XToolCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Koordinator, der die Statusdaten vom Gerät abfragt."""

    def __init__(self, hass: HomeAssistant, ip_address: str, device_type: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"xtool_{ip_address}",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.ip_address = ip_address
        self.device_type = device_type.lower()

    def _fetch_data_sync(self) -> dict[str, Any]:
        url = f"http://{self.ip_address}:8080/status"
        try:
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            data = resp.json()
            _LOGGER.debug("XTool %s response: %s", self.ip_address, data)
            return data
        except requests.exceptions.ConnectionError as err:
            _LOGGER.debug("XTool %s connection error: %s", self.ip_address, err)
            return {"_unavailable": True}
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("XTool %s error: %s", self.ip_address, err)
            return {"_unavailable": True}

    async def _async_update_data(self) -> dict[str, Any]:
        return await self.hass.async_add_executor_job(self._fetch_data_sync)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Eintrag einrichten."""
    ip = entry.data[CONF_IP_ADDRESS]
    dev_type = entry.data[CONF_DEVICE_TYPE]

    coordinator = XToolCoordinator(hass, ip, dev_type)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "name": entry.title,  # dein vergebener Name, z. B. "p2"
        "entry_id": entry.entry_id,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
