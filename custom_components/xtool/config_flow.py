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
    CONF_HAS_AP2,
    SUPPORTED_DEVICE_TYPES,
)


def _device_type_options() -> list[str]:
    """Return selectable device type options from const.py."""
    if isinstance(SUPPORTED_DEVICE_TYPES, dict):
        return list(SUPPORTED_DEVICE_TYPES.keys())
    return list(SUPPORTED_DEVICE_TYPES)


def _map_device_type(display_or_value: str) -> str:
    """Map UI display name to internal device type code."""
    if isinstance(SUPPORTED_DEVICE_TYPES, dict):
        return SUPPORTED_DEVICE_TYPES.get(display_or_value, display_or_value)
    return display_or_value


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Initial configuration through UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            device_type = _map_device_type(user_input[CONF_DEVICE_TYPE])

            self._data = {
                CONF_NAME: user_input[CONF_NAME],
                CONF_IP_ADDRESS: user_input[CONF_IP_ADDRESS],
                CONF_DEVICE_TYPE: device_type,
            }

            if device_type == "s1":
                return await self.async_step_s1_accessories()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=self._data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_IP_ADDRESS): cv.string,
                vol.Required(CONF_DEVICE_TYPE): vol.In(_device_type_options()),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_s1_accessories(
        self,
        user_input: dict | None = None,
    ) -> FlowResult:
        """Second step for S1: ask whether an AP2 air cleaner is attached."""
        if user_input is not None:
            data = dict(self._data)
            data[CONF_HAS_AP2] = user_input.get(CONF_HAS_AP2, False)

            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=data,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HAS_AP2, default=False): cv.boolean,
            }
        )

        return self.async_show_form(step_id="s1_accessories", data_schema=schema)
