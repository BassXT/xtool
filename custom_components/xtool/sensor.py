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
        self._attributes = {}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state
    
    @property
    def extra_state_attributes(self):
        """Return additional attributes only if STATUS is used."""
        return self._attributes if self._attributes else None

    def update(self):
        """Fetch the latest data from the XTool."""
        try:
            response = requests.get(f"http://{self._ip_address}:8080/status", timeout=5)
            data = response.json()

            
            _LOGGER.debug("XTool API Response: %s", data)

            
            mode = str(data.get("mode", "")).strip().upper()
            status = str(data.get("STATUS", "")).strip().upper()

            if mode:
                _LOGGER.debug("Detected MODE value: %s", mode)
                self._state = self._map_mode(mode)
                self._attributes = {}  
            elif status:
                _LOGGER.debug("Detected STATUS value: %s", status)
                self._state = self._map_status(status)
                self._attributes = {
                    "cpu_temp": data.get("CPU_TEMP"),
                    "water_temp": data.get("WATER_TEMP"),
                    "purifier": data.get("Purifier")
                }
            else:
                _LOGGER.warning("Neither MODE nor STATUS found in API response!")
                self._state = "Unknown"
                self._attributes = {}
        except Exception as e:
            _LOGGER.error("Error fetching data from XTool: %s", e)
            self._state = "off"
            self._attributes = {}

    def _map_mode(self, mode):
        """Map API modes to readable states."""
        if mode == "P_WORK_DONE":
            return "Done"
        elif mode == "Work":
            return "Running"
        elif mode == "P_SLEEP":
            return "Sleep"
        elif mode == "P_IDLE":
            return "Idle"
        else:
            return "Unknown"

    def _map_status(self, status):
        """Map API STATUS values to readable states."""
        status_map = {
            "P_FINISH": "Done",
            "P_WORKING": "Running",
            "P_SLEEP": "Sleep",
            "P_ONLINE_READY_WORK": "Ready",
            "P_IDLE": "Idle"
        }
        
        # Debug-Log
        if status in status_map:
            _LOGGER.debug("Mapped STATUS: %s -> %s", status, status_map[status])
            return status_map[status]
        else:
            _LOGGER.warning("Unrecognized STATUS: %s", status)
            return "Unknown"

# Setup function for the integration
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the XTool sensor platform."""
    ip_address = config.get("ip_address")
    name = config.get("name")
    
    # Add the sensor to Home Assistant
    add_entities([XToolSensor(name, ip_address)])
