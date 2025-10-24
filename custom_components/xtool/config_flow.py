import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from .const import DOMAIN, CONF_DEVICE_TYPE, CONF_IP, SUPPORTED_DEVICE_TYPES

class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """UI-Flow: Ein Gerät (Entry) hinzufügen."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            ip = user_input[CONF_IP].strip()
            devtype = user_input[CONF_DEVICE_TYPE].strip()

            # Eindeutigkeit: dieselbe (Typ,IP)-Kombi nur einmal zulassen
            await self.async_set_unique_id(f"{devtype}_{ip}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME].strip(),
                data={
                    CONF_NAME: user_input[CONF_NAME].strip(),
                    CONF_IP: ip,
                    CONF_DEVICE_TYPE: devtype,
                },
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_IP): str,
                vol.Required(CONF_DEVICE_TYPE): vol.In(SUPPORTED_DEVICE_TYPES),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)
