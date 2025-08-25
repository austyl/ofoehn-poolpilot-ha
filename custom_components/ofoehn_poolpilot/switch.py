from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]

    async_add_entities([PowerSwitch(coord, host), PoolLightSwitch(coord, host)], True)


class PowerSwitch(CoordinatorEntity, SwitchEntity):
    _attr_name = "PAC – Alimentation"
    def __init__(self, coordinator, host):
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_power_{host}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "O'Foehn PoolPilot",
            "manufacturer": "O'Foehn",
            "model": "PoolPilot",
        }

    @property
    def is_on(self):
        idx = self.coordinator.data["indices"]["power_idx"]
        return float(self.coordinator.data["super"].get(idx, 0)) > 0

    async def async_turn_on(self, **kwargs):
        if not self.is_on:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        if self.is_on:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()


class PoolLightSwitch(CoordinatorEntity, SwitchEntity):
    _attr_name = "Éclairage piscine"

    def __init__(self, coordinator: OFoehnCoordinator, host: str):
        super().__init__(coordinator)
        self._host = host
        self._attr_unique_id = f"ofoehn_light_{host}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._host)},
            "name": "O'Foehn PoolPilot",
            "manufacturer": "O'Foehn",
            "model": "PoolPilot",
        }

    @property
    def is_on(self):
        idx = self.coordinator.data["indices"]["light_idx"]
        return self.coordinator.data["accueil"].get(idx, 0) == 1

    async def async_turn_on(self, **kwargs):
        await self.coordinator.api.set_light(True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self.coordinator.api.set_light(False)
        await self.coordinator.async_request_refresh()