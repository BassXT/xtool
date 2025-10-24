from __future__ import annotations
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_IP,
    CONF_DEVICE_TYPE,
    SUPPORTED_DEVICE_TYPES,
)

SINGLETON_UNIQUE_ID = "xtool_singleton"
OPT_DEVICES_KEY = "devices"  # list[dict]: {name, ip, device_type}


def _schema_add_device(defaults: dict[str, Any] | None = None) -> vol.Schema:
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): str,
            vol.Required(CONF_IP, default=defaults.get(CONF_IP, "")): str,
            vol.Required(
                CONF_DEVICE_TYPE,
                default=defaults.get(CONF_DEVICE_TYPE, SUPPORTED_DEVICE_TYPES[0]),
            ): vol.In(SUPPORTED_DEVICE_TYPES),
        }
    )


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstellt einen einzigen zentralen Config-Eintrag; Geräteverwaltung läuft über OptionsFlow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Wir legen direkt einen "leeren" Eintrag an, der später Geräte in options hält.
        # (Optional könntest du hier noch einen Bestätigungsdialog anzeigen.)
        await self.async_set_unique_id(SINGLETON_UNIQUE_ID)
        self._abort_if_unique_id_configured()

        title = "xTool"  # kannst du dynamisieren, wenn gewünscht
        return self.async_create_entry(title=title, data={})


    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return XToolOptionsFlow(config_entry)


class XToolOptionsFlow(config_entries.OptionsFlow):
    """Verwaltet Geräte (Add/Edit/Delete) in entry.options[OPT_DEVICES_KEY]."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self.devices: list[dict[str, Any]] = list(config_entry.options.get(OPT_DEVICES_KEY, []))
        self._edit_index: int | None = None
        self._remove_index: int | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        # Hauptmenü
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_device", "edit_device_pick", "remove_device_pick", "list_devices"],
        )

    #
    # ---- ADD DEVICE ----
    #
    async def async_step_add_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            # einfache Duplikatsprüfung (IP)
            ip = user_input[CONF_IP].strip()
            if any(d.get(CONF_IP, "").strip() == ip for d in self.devices):
                errors["base"] = "duplicate_ip"

            if not errors:
                self.devices.append(
                    {
                        CONF_NAME: user_input[CONF_NAME].strip(),
                        CONF_IP: ip,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    }
                )
                return await self._save_and_return()

        return self.async_show_form(
            step_id="add_device",
            data_schema=_schema_add_device(),
            errors=errors,
            description_placeholders={
                "supported": ", ".join(SUPPORTED_DEVICE_TYPES),
            },
        )

    #
    # ---- EDIT DEVICE ----
    #
    async def async_step_edit_device_pick(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self.devices:
            # Kein Gerät vorhanden → zurück zum Menü mit Hinweis
            return self.async_show_form(
                step_id="edit_device_pick",
                data_schema=vol.Schema({}),
                description_placeholders={"info": "Keine Geräte vorhanden."},
                errors={"base": "no_devices"},
            )

        choices = {str(i): f"{d.get(CONF_NAME,'?')} ({d.get(CONF_DEVICE_TYPE,'?')} @ {d.get(CONF_IP,'?')})"
                   for i, d in enumerate(self.devices)}
        schema = vol.Schema(
            {
                vol.Required("index"): vol.In(choices),
            }
        )
        if user_input is not None:
            self._edit_index = int(user_input["index"])
            return await self.async_step_edit_device()

        return self.async_show_form(step_id="edit_device_pick", data_schema=schema)

    async def async_step_edit_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._edit_index is None or self._edit_index < 0 or self._edit_index >= len(self.devices):
            return await self.async_step_init()

        current = self.devices[self._edit_index]
        errors: dict[str, str] = {}

        if user_input is not None:
            ip_new = user_input[CONF_IP].strip()
            # Duplikat vermeiden (gleiche IP bei anderem Index)
            for i, d in enumerate(self.devices):
                if i != self._edit_index and d.get(CONF_IP, "").strip() == ip_new:
                    errors["base"] = "duplicate_ip"
                    break

            if not errors:
                current.update(
                    {
                        CONF_NAME: user_input[CONF_NAME].strip(),
                        CONF_IP: ip_new,
                        CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                    }
                )
                return await self._save_and_return()

        return self.async_show_form(
            step_id="edit_device",
            data_schema=_schema_add_device(current),
            errors=errors,
        )

    #
    # ---- REMOVE DEVICE ----
    #
    async def async_step_remove_device_pick(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self.devices:
            return self.async_show_form(
                step_id="remove_device_pick",
                data_schema=vol.Schema({}),
                description_placeholders={"info": "Keine Geräte vorhanden."},
                errors={"base": "no_devices"},
            )

        choices = {str(i): f"{d.get(CONF_NAME,'?')} ({d.get(CONF_DEVICE_TYPE,'?')} @ {d.get(CONF_IP,'?')})"
                   for i, d in enumerate(self.devices)}
        schema = vol.Schema(
            {
                vol.Required("index"): vol.In(choices),
            }
        )

        if user_input is not None:
            idx = int(user_input["index"])
            if 0 <= idx < len(self.devices):
                self.devices.pop(idx)
                return await self._save_and_return()
            return await self.async_step_init()

        return self.async_show_form(step_id="remove_device_pick", data_schema=schema)

    #
    # ---- LIST DEVICES (nur Info-Seite) ----
    #
    async def async_step_list_devices(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        text_lines = []
        if not self.devices:
            text_lines.append("Keine Geräte konfiguriert.")
        else:
            for i, d in enumerate(self.devices):
                text_lines.append(
                    f"{i}: {d.get(CONF_NAME,'?')} | {d.get(CONF_DEVICE_TYPE,'?')} @ {d.get(CONF_IP,'?')}"
                )

        # Leeres Schema → nur Text/Hinweis
        return self.async_show_form(
            step_id="list_devices",
            data_schema=vol.Schema({}),
            description_placeholders={"devices": "\n".join(text_lines)},
        )

    #
    # ---- SAVE ----
    #
    async def _save_and_return(self) -> FlowResult:
        data = {OPT_DEVICES_KEY: self.devices}
        return self.async_create_entry(title="", data=data)
