import logging
from typing import Any, Dict

import async_timeout
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, CONF_IP, CONF_DEVICE_TYPE

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = 5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    cfg: Dict[str, Any] = {**entry.data, **entry.options}
    name: str = cfg[CONF_NAME]
    ip: str = cfg[CONF_IP]
    device_type: str = cfg[CONF_DEVICE_TYPE].lower()

    if device_type in ("f1", "p2"):
        entity = XToolFPSensor(hass, name, ip, device_type)
    elif device_type == "m1":
        entity = XToolM1Sensor(hass, name, ip, device_type)
    else:
        entity = XToolGenericSensor(hass, name, ip, device_type)

    async_add_entities([entity], True)


class XToolBase(SensorEntity):
    def __init__(self, hass: HomeAssistant, name: str, ip: str, device_type: str) -> None:
        self._hass = hass
        self._name_base = name
        self._ip = ip
        self._device_type = device_type
        self._attr_name = f"{name} Status"
        self._attr_unique_id = f"{device_type}_{ip}"
        self._state: str | None = None
        self._attr_extra_state_attributes: Dict[str, Any] | None = None

    @property
    def native_value(self) -> str | None:
        return self._state

    @property
    def device_info(self) -> Dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, f"{self._device_type}_{self._ip}")},
            "name": self._name_base,
            "manufacturer": "xTool",
            "model": self._device_type.upper(),
        }

    async def _fetch(self) -> Dict[str, Any] | None:
        url = f"http://{self._ip}:8080/status"
        session = async_get_clientsession(self._hass)
        try:
            with async_timeout.timeout(_TIMEOUT):
                async with session.get(url) as resp:
                    if resp.status != 200:
                        _LOGGER.warning("HTTP %s from %s", resp.status, url)
                        return None
                    return await resp.json(content_type=None)
        except Exception as exc:
            # Ruhiges Logging: nur ein Eintrag bei echtem Fehler
            _LOGGER.error("Request failed for %s: %s", url, exc)
            return None


class XToolFPSensor(XToolBase):
    async def async_update(self) -> None:
        data = await self._fetch()
        if not data:
            self._state = "Unavailable"
            self._attr_extra_state_attributes = None
            return

        mode = str(data.get("mode", "")).strip().upper()
        if not mode:
            self._state = "Unknown"
            self._attr_extra_state_attributes = None
            return

        mapped = {
            "P_WORK_DONE": "Done",
            "WORK": "Running",
            "P_SLEEP": "Sleep",
            "P_IDLE": "Idle",
        }.get(mode, "Unknown")

        if mapped == "Unknown":
            _LOGGER.warning("Unrecognized MODE '%s' for %s", mode, self._attr_unique_id)

        self._state = mapped
        self._attr_extra_state_attributes = None


class XToolM1Sensor(XToolBase):
    async def async_update(self) -> None:
        data = await self._fetch()
        if not data:
            self._state = "Unavailable"
            self._attr_extra_state_attributes = None
            return

        status = str(data.get("STATUS", "")).strip().upper()
        if not status:
            self._state = "Unknown"
            self._attr_extra_state_attributes = None
            return

        mapped = {
            "P_FINISH": "Done",
            "P_WORKING": "Running",
            "P_SLEEP": "Sleep",
            "P_ONLINE_READY_WORK": "Ready",
            "P_IDLE": "Idle",
        }.get(status, "Unknown")

        if mapped == "Unknown":
            _LOGGER.warning("Unrecognized STATUS '%s' for %s", status, self._attr_unique_id)

        self._state = mapped
        self._attr_extra_state_attributes = {
            "cpu_temp": data.get("CPU_TEMP"),
            "water_temp": data.get("WATER_TEMP"),
            "purifier": data.get("Purifier"),
        }


class XToolGenericSensor(XToolBase):
    async def async_update(self) -> None:
        data = await self._fetch()
        if not data:
            self._state = "Unavailable"
            self._attr_extra_state_attributes = None
            return
        self._state = "Unknown"
        self._attr_extra_state_attributes = None
