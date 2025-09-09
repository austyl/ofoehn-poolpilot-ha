from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfTemperature, UnitOfElectricPotential
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up O'Foehn PoolPilot sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    async_add_entities(
        [
            TempSensor(coord, host, entry.entry_id, key="water_in_idx", name="Eau In"),
            TempSensor(coord, host, entry.entry_id, key="water_out_idx", name="Eau Out"),
            TempSensor(coord, host, entry.entry_id, key="air_idx", name="Air"),
            VoltageSensor(coord, host, entry.entry_id, key="voltage_idx", name="Tension"),
            TempSensor(coord, host, entry.entry_id, key="internal_idx", name="Temp Interne"),
            SetpointDiffSensor(coord, host, entry.entry_id),
            RegTextSensor(coord, host, entry.entry_id, key="mode", name="Mode"),
            RegTextSensor(coord, host, entry.entry_id, key="regulation", name="Régulation"),
            RegTextSensor(coord, host, entry.entry_id, key="next_action", name="Prochaine action"),
            RegTextSensor(coord, host, entry.entry_id, key="status", name="État général"),
            RawSensor(coord, host, entry.entry_id, key="super_raw", name="Super Raw"),
            RawSensor(coord, host, entry.entry_id, key="accueil_raw", name="Accueil Raw"),
            RawSensor(coord, host, entry.entry_id, key="reg_raw", name="Reg Raw"),
        ],
        True,
    )


class TempSensor(CoordinatorEntity, SensorEntity):
    """Sensor for a PoolPilot temperature reading."""
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
        idx = self.coordinator.data["indices"].get(self._key)
        value = None
        if idx is not None:
            value = self.coordinator.data["super"].get(idx)
            if value is not None:
                return value
        fallback_map = {
            "water_in_idx": "water_in",
            "water_out_idx": "water_out",
            "air_idx": "air_temp",
            "internal_idx": "internal_temp",
        }
        fb_key = fallback_map.get(self._key)
        if fb_key:
            return self.coordinator.data.get(fb_key)
        return value


class VoltageSensor(CoordinatorEntity, SensorEntity):
    """Sensor for the PoolPilot voltage."""
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

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
        idx = self.coordinator.data["indices"].get(self._key)
        value = None
        if idx is not None:
            value = self.coordinator.data["super"].get(idx)
            if value is not None:
                return value
        fallback_map = {"voltage_idx": "voltage"}
        fb_key = fallback_map.get(self._key)
        if fb_key:
            return self.coordinator.data.get(fb_key)
        return value


class SetpointDiffSensor(CoordinatorEntity, SensorEntity):
    """Sensor tracking the difference to the target setpoint."""
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str):
        super().__init__(coordinator)
        self._host = host
        self._attr_name = "O'Foehn Écart Consigne"
        self._attr_unique_id = f"ofoehn_setpoint_diff_{host}"

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
        water_in = self.coordinator.data.get("water_in")
        setpoint = self.coordinator.data.get("setpoint")
        if water_in is None or setpoint is None:
            return None
        return round(setpoint - water_in, 2)


class RegTextSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor exposing regulator text fields."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        return self.coordinator.data.get("reg", {}).get(self._key)


class RawSensor(CoordinatorEntity, SensorEntity):
    """Diagnostic sensor providing raw API responses."""
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
        value = self.coordinator.data.get(self._key)
        self._attr_extra_state_attributes = {"raw": value}
        if value is None:
            return None
        return value[:255]
