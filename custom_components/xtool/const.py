# Constants for the xTool integration
DOMAIN = "xtool"

# Supported Home Assistant platforms
PLATFORMS: list[str] = ["sensor", "binary_sensor", "camera", "switch", "button"]

CONF_IP_ADDRESS = "ip_address"
CONF_DEVICE_TYPE = "device_type"
CONF_HAS_AP2 = "has_ap2"  # Whether the S1 has an AP2 air cleaner attached

# Mapping of display names to internal device type codes
SUPPORTED_DEVICE_TYPES: dict[str, str] = {
    "P2": "p2",
    "P3": "p3",
    "F1": "f1",
    "F1 V2 / Firmware 40.51+": "f1_v2",
    "F2": "f2",
    "F2 Ultra": "f2u",
    "F2 Ultra UV": "f2uuv",
    "M1": "m1",
    "M1 Ultra": "m1u",
    "S1": "s1",
    "D1": "d1",
    "Apparel Printer": "apparel"
}

MANUFACTURER = "xTool"

# Update intervals for polling
DEFAULT_UPDATE_INTERVAL = 10          # Fast update interval in seconds
DEFAULT_SLOW_UPDATE_INTERVAL = 120    # Slow update interval (e.g. for static settings)
HTTP_TIMEOUT = 5
