from __future__ import annotations

import logging
from typing import Optional
from datetime import timedelta

import requests

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_IP_ADDRESS,
    CONF_DEVICE_TYPE,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


STREAM_PATHS: dict[int, str] = {
    0: "/camera/snap?stream=0",  # overview
    1: "/camera/snap?stream=1",  # close-up
}

MIN_SNAPSHOT_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    ip_address: str = entry.data[CONF_IP_ADDRESS]
    device_type: str = entry.data[CONF_DEVICE_TYPE].lower()
    base_name: str = entry.title

    if device_type != "p2":
        _LOGGER.debug(
            "xTool device type '%s' is not P2 – no camera entities created.",
            device_type,
        )
        return

    _LOGGER.debug(
        "Setting up xTool P2 cameras: name=%s, ip=%s, entry_id=%s",
        base_name,
        ip_address,
        entry.entry_id,
    )

    cameras = [
        XToolCamera(hass, entry, ip_address, base_name, device_type, index=0),
        XToolCamera(hass, entry, ip_address, base_name, device_type, index=1),
    ]

    async_add_entities(cameras)


class XToolCamera(Camera):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        ip_address: str,
        base_name: str,
        device_type: str,
        index: int,
    ) -> None:
        super().__init__()

        self.hass = hass
        self._entry = entry
        self._ip = ip_address
        self._index = index
        self._device_type = device_type

        if index == 0:
            cam_name = "Overview Camera"
        else:
            cam_name = "Close-up Camera"

        self._attr_unique_id = f"{entry.entry_id}_camera_{index}"
        self._attr_name = f"{base_name} {cam_name}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=base_name,
            manufacturer=MANUFACTURER,
            model=device_type.upper(),
        )

        self._attr_available = True

        self._last_image: bytes | None = None
        self._last_updated = None

        _LOGGER.debug(
            "xTool P2 Camera %s initialized: ip=%s, unique_id=%s",
            index,
            ip_address,
            self._attr_unique_id,
        )

    @property
    def supported_features(self) -> CameraEntityFeature:
        return CameraEntityFeature(0)

    def camera_image(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> bytes | None:
        now = dt_util.utcnow()

        if (
            self._last_image is not None
            and self._last_updated is not None
            and now - self._last_updated < MIN_SNAPSHOT_INTERVAL
        ):
            return self._last_image

        image = self._fetch_snapshot(self._index)
        if image is not None:
            self._last_image = image
            self._last_updated = now

        return self._last_image

    def _fetch_snapshot(self, index: int) -> bytes | None:
        path = STREAM_PATHS.get(index)
        if not path:
            _LOGGER.error("Snapshot path missing for camera index %s", index)
            return None

        url = f"http://{self._ip}:8329{path}"
        _LOGGER.debug("Requesting xTool P2 snapshot (Camera %s) from URL: %s", index, url)

        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response.content
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Snapshot request failed (Camera %s, URL %s): %s",
                index,
                url,
                err,
            )
            return None
