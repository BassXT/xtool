DOMAIN = "xtool"

PLATFORMS: list[str] = ["sensor", "binary_sensor", "camera"]

CONF_IP_ADDRESS = "ip_address"
CONF_DEVICE_TYPE = "device_type"

SUPPORTED_DEVICE_TYPES: dict[str, str] = {
    "P2": "p2",
    "P3": "p3",
    "F1": "f1",
    "F2": "f2",
    "F2 Ultra": "f2u",
    "F2 Ultra UV": "f2uuv",
    "M1": "m1",
    "M1 Ultra": "m1u",
    "D1": "d1",
    "Apparel Printer": "apparel"
}

MANUFACTURER = "xTool"

# Polling:
DEFAULT_UPDATE_INTERVAL = 10          # seconds
DEFAULT_SLOW_UPDATE_INTERVAL = 120    # seconds
HTTP_TIMEOUT = 5
