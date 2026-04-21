from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    async_add_entities([PowerSwitch(coord, host), PoolLightSwitch(coord, host)], True)


class PowerSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Alimentation"

    def __init__(self, coordinator, host):
        super().__init__(coordinator)
        self._attr_unique_id = f"ofoehn_power_{host}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=DEFAULT_NAME,
            manufacturer="O'Foehn",
            model="PoolPilot",
        )

    @property
    def is_on(self):
        idx = self.coordinator.data["indices"]["power_idx"]
        try:
            return float(self.coordinator.data["super"].get(idx, 0)) > 0
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs):
        if self.is_on is False:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        if self.is_on is True:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()


class PoolLightSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Éclairage piscine"

    def __init__(self, coordinator: OFoehnCoordinator, host: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"ofoehn_light_{host}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, host)},
            name=DEFAULT_NAME,
            manufacturer="O'Foehn",
            model="PoolPilot",
        )

    @property
    def is_on(self):
        idx = self.coordinator.data["indices"]["light_idx"]
        try:
            return float(self.coordinator.data["accueil"].get(idx, 0)) > 0
        except (TypeError, ValueError):
            return None

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.set_light(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.set_light(False)
        await self.coordinator.async_request_refresh()
