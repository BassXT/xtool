from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_TYPE,
    SUPPORTED_DEVICE_TYPES,
)


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstkonfiguration per UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            # title = Name, den du vergibst -> Basis für entity_ids
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                    CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,                    # z. B. "p2"
                vol.Required(CONF_IP_ADDRESS): cv.string,              # 192.168.x.x
                vol.Required(CONF_DEVICE_TYPE, default="p2"): vol.In(  # nur gültige Modelle
                    SUPPORTED_DEVICE_TYPES
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
