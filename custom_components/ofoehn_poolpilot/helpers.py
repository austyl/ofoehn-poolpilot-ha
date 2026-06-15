from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator


def build_device_info(device_key: str, host: str, data: dict[str, Any]) -> dict[str, Any]:
    """Build stable device info for the heat pump."""
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, device_key)},
        "name": "O'Foehn PoolPilot",
        "manufacturer": "O'Foehn",
        "model": "PoolPilot",
        "configuration_url": f"http://{host}",
    }

    serial_number = data.get("serial_number")
    if serial_number:
        info["serial_number"] = serial_number

    sw_version = data.get("firmware_version") or data.get("module_version")
    if sw_version:
        info["sw_version"] = sw_version

    hw_version = data.get("hardware_code")
    if hw_version:
        info["hw_version"] = hw_version

    mac_address = data.get("mac_address")
    if mac_address:
        info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac_address))}

    return info


def get_donnee_float(
    data: dict[str, Any],
    idx_key: str,
    *,
    source: str = "super",
    fallback_key: str | None = None,
) -> float | None:
    """Read a numeric DONNEE index with an optional flat fallback key."""
    indices = data.get("indices") or {}
    idx = indices.get(idx_key)
    if idx is not None:
        bucket = data.get(source) or {}
        value = bucket.get(idx)
        if value is not None:
            return float(value)
    if fallback_key:
        fallback = data.get(fallback_key)
        if fallback is not None:
            return float(fallback)
    return None


def get_donnee_bool(
    data: dict[str, Any],
    idx_key: str,
    *,
    source: str = "super",
    fallback_key: str | None = None,
    default: bool | None = None,
) -> bool | None:
    """Read a boolean DONNEE index with an optional flat fallback key."""
    indices = data.get("indices") or {}
    idx = indices.get(idx_key)
    if idx is not None:
        bucket = data.get(source) or {}
        value = bucket.get(idx)
        if value is not None:
            try:
                return float(value) > 0
            except (TypeError, ValueError):
                pass
    if fallback_key is not None:
        fallback = data.get(fallback_key)
        if fallback is not None:
            return bool(fallback)
    return default


class OFoehnEntity(CoordinatorEntity):
    """Shared base for PoolPilot entities."""

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_key = device_key
        self._device_info = device_info

    @property
    def device_info(self) -> dict[str, Any]:
        return self._device_info

    @property
    def available(self) -> bool:
        data = self.coordinator.data or {}
        return self.coordinator.last_update_success and not data.get("super_stale", False)
