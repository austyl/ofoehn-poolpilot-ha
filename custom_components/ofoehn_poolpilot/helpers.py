from __future__ import annotations

from .const import DOMAIN


def device_info_for_host(host: str) -> dict:
    """Return device information for a given host."""
    return {
        "identifiers": {(DOMAIN, host)},
        "name": "O'Foehn PoolPilot",
        "manufacturer": "O'Foehn",
        "model": "PoolPilot",
    }
