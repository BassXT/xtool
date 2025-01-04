import logging
import requests
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_NAME

_LOGGER = logging.getLogger(__name__)

# Sensor entity
class XToolSensor(Entity):
    """Representation of a Sensor for the XTool."""

    def __init__(self, name, ip_address):
        self._name = name
        self._ip_address = ip_address
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Fetch the latest data from the XTool."""
        try:
            response = requests.get(f"http://{self._ip_address}:8080/status")
            data = response.json()
            # Mapping der API-Modi auf den Status
            mode = data.get('mode')
            if mode == "P_WORK_DONE":
                self._state = "Done"
            elif mode == "Work":
                self._state = "Running"
            elif mode == "P_SLEEP":
                self._state = "Sleep"
            elif mode == "P_IDLE":
                self._state = "Idle"
            else:
                self._state = "Unknown"
        except Exception as e:
            _LOGGER.error("Error fetching data from XTool: %s", e)
            self._state = "off"

# Setup function for the integration
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the XTool sensor platform."""
    ip_address = config.get('ip_address')
    name = config.get('name')
    
    # Add the sensor to Home Assistant
    add_entities([XToolSensor(name, ip_address)])
