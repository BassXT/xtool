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


def _device_type_options() -> list[str]:
    """Return selectable device type options from const.py."""
    # SUPPORTED_DEVICE_TYPES can be a dict or list/tuple/set.
    if isinstance(SUPPORTED_DEVICE_TYPES, dict):
        return list(SUPPORTED_DEVICE_TYPES.keys())
    return list(SUPPORTED_DEVICE_TYPES)


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstkonfiguration per UI."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                    CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                },
            )

        options = _device_type_options()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,       # z. B. "Laser Werkstatt"
                vol.Required(CONF_IP_ADDRESS): cv.string, # 192.168.x.x
                vol.Required(CONF_DEVICE_TYPE): vol.In(options),  # kein Default
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
