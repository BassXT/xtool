import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN, CONF_DEVICE_TYPE, CONF_IP, SUPPORTED_DEVICE_TYPES


class XToolConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            ip = user_input[CONF_IP]
            devtype = user_input[CONF_DEVICE_TYPE]

            # WICHTIG: ohne Unterstrich aufrufen
            await self.async_set_unique_id(f"{devtype}_{ip}")
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    CONF_NAME: user_input[CONF_NAME],
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

    async def async_step_import(self, import_config):
        name = import_config.get(CONF_NAME)
        ip = import_config[CONF_IP]
        devtype = import_config[CONF_DEVICE_TYPE]

        # WICHTIG: ohne Unterstrich aufrufen
        await self.async_set_unique_id(f"{devtype}_{ip}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=name or f"xTool {devtype}",
            data={
                CONF_NAME: name or f"xTool {devtype}",
                CONF_IP: ip,
                CONF_DEVICE_TYPE: devtype,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return XToolOptionsFlow(config_entry)


class XToolOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data = self._entry.data
        opts = self._entry.options
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=opts.get(CONF_NAME, data.get(CONF_NAME, "xTool"))): str,
                vol.Required(CONF_IP, default=opts.get(CONF_IP, data.get(CONF_IP, ""))): str,
                vol.Required(CONF_DEVICE_TYPE, default=opts.get(CONF_DEVICE_TYPE, data.get(CONF_DEVICE_TYPE, "f1"))): vol.In(SUPPORTED_DEVICE_TYPES),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
