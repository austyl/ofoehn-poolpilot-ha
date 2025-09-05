from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    sensor = ConnectivityBinarySensor(coordinator, host)
    async_add_entities([sensor], True)
    data["connectivity_sensor"] = sensor


class ConnectivityBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "O'Foehn PoolPilot Connectivity"

    def __init__(self, coordinator: OFoehnCoordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_connectivity_{host}"
        self._last_check: bool | None = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "O'Foehn PoolPilot",
            "manufacturer": "O'Foehn",
            "model": "PoolPilot",
        }

    @property
    def is_on(self) -> bool:
        if self._last_check is None:
            return self.coordinator.last_update_success
        return self._last_check

    async def async_check_connection(self) -> bool:
        self._last_check = await self.coordinator.api.check_connection()
        self.async_write_ha_state()
        return self._last_check
