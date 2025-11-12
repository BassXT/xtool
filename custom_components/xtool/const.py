DOMAIN = "xtool"

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

CONF_IP_ADDRESS = "ip_address"
CONF_DEVICE_TYPE = "device_type"

# nur die unterstützten Modelle
SUPPORTED_DEVICE_TYPES: dict[str, str] = {
    "p2": "P2",
    "f1": "F1",
    "m1": "M1",
    "apparel": "Apparel Printer",
}

MANUFACTURER = "xTool"
DEFAULT_UPDATE_INTERVAL = 10  # Sekunden
