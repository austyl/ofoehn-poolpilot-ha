from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    async_add_entities([
        TempSensor(coord, host, key="water_in_idx", name="Eau In"),
        TempSensor(coord, host, key="water_out_idx", name="Eau Out"),
        TempSensor(coord, host, key="air_idx", name="Air"),
    ], True)


class TempSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OFoehnCoordinator, host: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"ofoehn_{key}_{host}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=DEFAULT_NAME,
            manufacturer="O'Foehn",
            model="PoolPilot",
        )

    @property
    def native_value(self):
        idx = self.coordinator.data["indices"][self._key]
        return self.coordinator.data["super"].get(idx)
