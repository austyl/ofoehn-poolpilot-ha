from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator
from .helpers import OFoehnEntity, get_donnee_bool


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: OFoehnCoordinator = data["coordinator"]
    device_key = data["device_key"]
    device_info = data["device_info"]
    connectivity = ConnectivityBinarySensor(coordinator, device_key, device_info)
    sensors = [
        connectivity,
        PumpBinarySensor(coordinator, device_key, device_info),
        HeatingBinarySensor(coordinator, device_key, device_info),
    ]
    async_add_entities(sensors, True)
    data["connectivity_sensor"] = connectivity


class ConnectivityBinarySensor(OFoehnEntity, BinarySensorEntity):
    _attr_name = "O'Foehn PoolPilot Connectivity"

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        super().__init__(coordinator, device_key, device_info)
        self._attr_unique_id = f"ofoehn_connectivity_{device_key}"
        self._last_check: bool | None = None

    @property
    def is_on(self) -> bool:
        if self._last_check is None:
            return self.coordinator.last_update_success
        return self._last_check

    async def async_check_connection(self) -> bool:
        self._last_check = await self.coordinator.api.check_connection()
        self.async_write_ha_state()
        return self._last_check


class PumpBinarySensor(OFoehnEntity, BinarySensorEntity):
    _attr_name = "O'Foehn Pompe"

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        super().__init__(coordinator, device_key, device_info)
        self._attr_unique_id = f"ofoehn_pump_{device_key}"

    @property
    def is_on(self) -> bool:
        result = get_donnee_bool(
            self.coordinator.data,
            "pump_idx",
            fallback_key="pump_on",
            default=False,
        )
        return bool(result)


class HeatingBinarySensor(OFoehnEntity, BinarySensorEntity):
    _attr_name = "O'Foehn Chauffage"

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
    ) -> None:
        super().__init__(coordinator, device_key, device_info)
        self._attr_unique_id = f"ofoehn_heating_{device_key}"

    @property
    def is_on(self) -> bool:
        result = get_donnee_bool(
            self.coordinator.data,
            "heating_idx",
            fallback_key=None,
            default=None,
        )
        if result is not None:
            return result
        data = self.coordinator.data
        return bool(data.get("compressor_1_on") or data.get("compressor_2_on"))
