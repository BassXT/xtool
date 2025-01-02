import logging
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

class XToolConfigFlow(config_entries.ConfigFlow, domain="xtool"):
    """Handle a config flow for XTool."""

    VERSION = 1

    def __init__(self):
        self._ip_address = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step of the config flow."""
        if user_input is not None:
            # Validierung der IP-Adresse
            self._ip_address = user_input[CONF_NAME]
            return self.async_create_entry(
                title="XTool",
                data={"ip_address": self._ip_address},
            )

        return self.async_show_form(
            step_id="user", data_schema=self._get_schema()
        )

    def _get_schema(self):
        """Return the schema for the config flow."""
        from homeassistant.helpers import config_validation as cv
        return {
            CONF_NAME: cv.string,
        }
