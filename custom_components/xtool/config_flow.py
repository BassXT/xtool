from __future__ import annotations
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_NAME as XTOOL_CONF_NAME,   # falls du CONF_NAME auch in const definierst
    CONF_IP,
    CONF_DEVICE_TYPE,
    SUPPORTED_DEVICE_TYPES,
)

# Einheitliches Schema für Neu-/Bearbeiten
def _device_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=d.get(CONF_NAME, "")): str,
            vol.Required(CONF_IP, default=d.get(CONF_IP, "")): str,
            vol.Required(
                CONF_DEVICE_TYPE,
                default=d.get(CONF_DEVICE_TYPE, SUPPORTED_DEVICE_TYPES[0]),
            ): vol.In(SUPPORTED_DEVICE_TYPES),
        }
    )


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config-Flow: pro Gerät eigener Config Entry (kein Singleton)."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Erster Schritt: Dialog anzeigen und Entry anlegen."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=_device_schema())

        name = str(user_input[CONF_NAME]).strip()
        ip = str(user_input[CONF_IP]).strip()
        devtype = str(user_input[CONF_DEVICE_TYPE]).strip()

        # Duplikate verhindern: gleiche (Typ, IP) nur einmal
        unique_id = f"{devtype.lower()}_{ip}"
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name,
            data={
                CONF_NAME: name,
                CONF_IP: ip,
                CONF_DEVICE_TYPE: devtype,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return XToolOptionsFlow(config_entry)


class XToolOptionsFlow(config_entries.OptionsFlow):
    """Erlaubt nachträgliches Bearbeiten der drei Felder für DIESEN Entry."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Einziger Options-Schritt: gleiche Felder wie im Setup."""
        if user_input is not None:
            # Optionen speichern. (Sensor liest weiter aus entry.data;
            # wenn du später Options-Werte priorisieren willst, kannst du die dort auswerten.)
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_NAME: self._entry.data.get(CONF_NAME, ""),
            CONF_IP: self._entry.data.get(CONF_IP, ""),
            CONF_DEVICE_TYPE: self._entry.data.get(CONF_DEVICE_TYPE, SUPPORTED_DEVICE_TYPES[0]),
            # Vorhandene Optionen als Defaults überlagern
            **self._entry.options,
        }
        return self.async_show_form(step_id="init", data_schema=_device_schema(defaults))
