from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator
from .helpers import device_info_for_host

SUPPORTED_HVAC = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    host = data["host"]
    async_add_entities([OFoehnClimate(coord, host, entry.entry_id)], True)


class OFoehnClimate(CoordinatorEntity, ClimateEntity):
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = SUPPORTED_HVAC
    _attr_target_temperature_step = 0.5
    _attr_min_temp = 10
    _attr_max_temp = 35

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str):
        super().__init__(coordinator)
        self._host = host
        self._entry_id = entry_id
        self._attr_name = "O'Foehn – PAC Piscine"
        self._attr_unique_id = f"ofoehn_climate_{host}"

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    def _is_power_on(self):
        idx = self.coordinator.data["indices"].get("power_idx")
        if idx is None:
            return True
        try:
            return float(self.coordinator.data["super"].get(idx, 1)) > 0
        except Exception:
            return True

    async def _power_on(self):
        if not self._is_power_on():
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()

    async def _power_off(self):
        if self._is_power_on():
            await self.coordinator.api.toggle_power()
            await self.coordinator.async_request_refresh()

    @property
    def current_temperature(self):
        idx = self.coordinator.data["indices"]["water_in_idx"]
        return self.coordinator.data["super"].get(idx)

    @property
    def target_temperature(self):
        return self.coordinator.data["reg"].get("setpoint")

    @property
    def hvac_mode(self):
        if not self._is_power_on():
            return HVACMode.OFF
        mode = self.coordinator.data["reg"].get("mode", "AUTO")
        if mode == "CHAUD":
            return HVACMode.HEAT
        if mode == "FROID":
            return HVACMode.COOL
        return HVACMode.AUTO

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get("temperature")
        if temp is not None:
            await self.coordinator.api.set_setpoint(float(temp))
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self._power_off()
            return
        await self._power_on()
        mapping = {
            HVACMode.HEAT: "CHAUD",
            HVACMode.COOL: "FROID",
            HVACMode.AUTO: "AUTO",
        }
        await self.coordinator.api.set_mode(mapping.get(hvac_mode, "AUTO"))
        await self.coordinator.async_request_refresh()
