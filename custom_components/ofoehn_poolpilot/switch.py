from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator
from .helpers import OFoehnEntity, get_donnee_bool


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    device_key = data["device_key"]
    device_info = data["device_info"]

    async_add_entities(
        [PowerSwitch(coord, device_key, device_info), PoolLightSwitch(coord, device_key, device_info)],
        True,
    )


class PowerSwitch(OFoehnEntity, SwitchEntity):
    _attr_name = "PAC – Alimentation"

    def __init__(self, coordinator: OFoehnCoordinator, device_key: str, device_info: dict):
        super().__init__(coordinator, device_key, device_info)
        self._attr_unique_id = f"ofoehn_power_{device_key}"

    @property
    def is_on(self):
        result = get_donnee_bool(
            self.coordinator.data,
            "power_idx",
            fallback_key="power_on",
            default=True,
        )
        return bool(result)

    async def async_turn_on(self, **kwargs):
        if not self.is_on:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        if self.is_on:
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()


class PoolLightSwitch(OFoehnEntity, SwitchEntity):
    _attr_name = "Éclairage piscine"

    def __init__(self, coordinator: OFoehnCoordinator, device_key: str, device_info: dict):
        super().__init__(coordinator, device_key, device_info)
        self._attr_unique_id = f"ofoehn_light_{device_key}"

    @property
    def is_on(self):
        idx = self.coordinator.data["indices"]["light_idx"]
        return self.coordinator.data["accueil"].get(idx, 0) == 1

    async def async_turn_on(self, **kwargs):
        if not self.is_on:
            await self.coordinator.api.set_light(True)
            await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        if self.is_on:
            await self.coordinator.api.set_light(False)
            await self.coordinator.async_request_refresh()
