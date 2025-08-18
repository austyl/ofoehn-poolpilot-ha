from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    async_add_entities([
        TempSensor(coord, host, entry.entry_id, key="water_in_idx", name="Eau In"),
        TempSensor(coord, host, entry.entry_id, key="water_out_idx", name="Eau Out"),
        TempSensor(coord, host, entry.entry_id, key="air_idx", name="Air"),
    ], True)


class TempSensor(CoordinatorEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "O'Foehn PoolPilot",
            "manufacturer": "O'Foehn",
            "model": "PoolPilot",
        }

    @property
    def native_value(self):
        idx = self.coordinator.data["indices"][self._key]
        return self.coordinator.data["super"].get(idx)