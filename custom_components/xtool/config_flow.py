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
    # SUPPORTED_DEVICE_TYPES can be a dict or list/tuple/set.
    if isinstance(SUPPORTED_DEVICE_TYPES, dict):
        return list(SUPPORTED_DEVICE_TYPES.keys())
    return list(SUPPORTED_DEVICE_TYPES)


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Erstkonfiguration per UI."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            # S1 users may optionally have an AP2 air cleaner — ask on next step
            if user_input[CONF_DEVICE_TYPE] == "S1":
                return await self.async_step_s1_accessories()
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
                vol.Required(CONF_NAME): cv.string,       # e.g. "Laser Workshop"
                vol.Required(CONF_IP_ADDRESS): cv.string, # 192.168.x.x
                vol.Required(CONF_DEVICE_TYPE): vol.In(options),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_s1_accessories(self, user_input: dict | None = None) -> FlowResult:
        """Second step for S1: ask whether an AP2 air cleaner is attached."""
        if user_input is not None:
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data={
                    CONF_NAME: self._data[CONF_NAME],
                    CONF_IP_ADDRESS: self._data[CONF_IP_ADDRESS],
                    CONF_DEVICE_TYPE: self._data[CONF_DEVICE_TYPE],
                    CONF_HAS_AP2: user_input.get(CONF_HAS_AP2, False),
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_HAS_AP2, default=False): cv.boolean,
            }
        )
        return self.async_show_form(step_id="s1_accessories", data_schema=schema)
