from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac

from .const import DOMAIN


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


def device_info_for_host(host: str) -> dict[str, Any]:
    """Backward-compatible device info helper."""
    return build_device_info(host, host, {})
