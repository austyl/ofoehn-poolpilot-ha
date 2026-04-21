from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator
from .helpers import device_info_for_host


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OFoehnCoordinator = data["coordinator"]
    host = data["host"]
    connectivity = ConnectivityBinarySensor(coordinator, host)
    sensors = [
        connectivity,
        PumpBinarySensor(coordinator, host),
        HeatingBinarySensor(coordinator, host),
    ]
    async_add_entities(sensors, True)
    data["connectivity_sensor"] = connectivity


class ConnectivityBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "O'Foehn PoolPilot Connectivity"

    def __init__(self, coordinator: OFoehnCoordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_connectivity_{host}"
        self._last_check: bool | None = None

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def is_on(self) -> bool:
        if self._last_check is None:
            return self.coordinator.last_update_success
        return self._last_check

    async def async_check_connection(self) -> bool:
        self._last_check = await self.coordinator.api.check_connection()
        self.async_write_ha_state()
        return self._last_check


class PumpBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "O'Foehn Pompe"

    def __init__(self, coordinator: OFoehnCoordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_pump_{host}"

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def is_on(self) -> bool:
        idx = self.coordinator.data["indices"].get("pump_idx")
        if idx is None:
            return False
        return float(self.coordinator.data["super"].get(idx, 0)) > 0


class HeatingBinarySensor(CoordinatorEntity, BinarySensorEntity):
    _attr_name = "O'Foehn Chauffage"

    def __init__(self, coordinator: OFoehnCoordinator, host: str) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_heating_{host}"

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def is_on(self) -> bool:
        idx = self.coordinator.data["indices"].get("heating_idx")
        if idx is None:
            return False
        return float(self.coordinator.data["super"].get(idx, 0)) > 0
