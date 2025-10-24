import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import DOMAIN, CONF_DEVICE_TYPE, CONF_IP, SUPPORTED_DEVICE_TYPES


def _schema(defaults: dict | None = None) -> vol.Schema:
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
    """Config flow für xTool – erzeugt pro Gerät einen eigenen Config Entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Erster Dialog beim Hinzufügen (und auch bei 'Eintrag hinzufügen')."""
        errors = {}

        if user_input is not None:
            name = user_input[CONF_NAME].strip()
            ip = user_input[CONF_IP].strip()
            devtype = user_input[CONF_DEVICE_TYPE].strip()

            # EINDEUTIGKEIT: pro (Typ,IP) nur ein Eintrag
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

        return self.async_show_form(step_id="user", data_schema=_schema(), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return XToolOptionsFlow(config_entry)


class XToolOptionsFlow(config_entries.OptionsFlow):
    """Optionen erlauben späteres Bearbeiten der selben Felder."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Erster Optionsschritt (Zahnrad im Eintrag)."""
        if user_input is not None:
            # Optionen persistieren wir klassisch unter 'options';
            # sensor.py kann weiter 'entry.data' nutzen – oder du holst später aus 'entry.options' Vorrangwerte.
            return self.async_create_entry(title="", data=user_input)

        # Defaults aus Entry/Data bzw. bestehenden Optionen
        defaults = {
            CONF_NAME: self._entry.data.get(CONF_NAME),
            CONF_IP: self._entry.data.get(CONF_IP),
            CONF_DEVICE_TYPE: self._entry.data.get(CONF_DEVICE_TYPE),
            # Falls schon Optionen existieren, lieber die anzeigen:
            **self._entry.options,
        }
        return self.async_show_form(step_id="init", data_schema=_schema(defaults))
