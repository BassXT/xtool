from __future__ import annotations
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_IP, CONF_DEVICE_TYPE, SUPPORTED_DEVICE_TYPES


# Schema für den Einrichtungsdialog
DEVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_IP): str,
        vol.Required(CONF_DEVICE_TYPE): vol.In(SUPPORTED_DEVICE_TYPES),
    }
)


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow für xTool – pro Gerät eigener Eintrag."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Zeigt den ersten Dialog und erstellt den Config Entry."""
        if user_input is None:
            # Erster Aufruf: Formular anzeigen
            return self.async_show_form(step_id="user", data_schema=DEVICE_SCHEMA)

        # Werte aus Formular holen
        name = str(user_input[CONF_NAME]).strip()
        ip = str(user_input[CONF_IP]).strip()
        devtype = str(user_input[CONF_DEVICE_TYPE]).strip()

        # Eindeutige ID (pro Gerätetyp + IP)
        await self.async_set_unique_id(f"{devtype.lower()}_{ip}")
        self._abort_if_unique_id_configured()

        # Entry erzeugen – hier landen die Werte, die dein sensor.py nutzt
        return self.async_create_entry(
            title=name,
            data={
                CONF_NAME: name,
                CONF_IP: ip,
                CONF_DEVICE_TYPE: devtype,
            },
        )
