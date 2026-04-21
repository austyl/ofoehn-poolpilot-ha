from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfPressure, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OFoehnCoordinator, clean_html_text
from .helpers import device_info_for_host


async def async_setup_entry(hass, entry, async_add_entities):
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
            DiagnosticTextSensor(coord, host, entry.entry_id, key="firmware_version", name="Firmware"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="webuser_role", name="Rôle WebUser"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="ph_license", name="Licence pH"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="ev_present", name="Présence EV"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="ev_position", name="Position EV"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="balneo_state", name="Balnéo"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="contact_bp1", name="Contact BP1"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="contact_bp2", name="Contact BP2"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="contact_hp1", name="Contact HP1"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="contact_hp2", name="Contact HP2"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="power_state", name="État alimentation"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="pump_state", name="Relai pompe"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="fan_state", name="Relai ventilateur"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="valve_1_state", name="Relai vanne 1"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="compressor_1_state", name="Relai compresseur 1"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="valve_2_state", name="Relai vanne 2"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="compressor_2_state", name="Relai compresseur 2"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="chlorine_state", name="Chlore"),
            DiagnosticTextSensor(coord, host, entry.entry_id, key="ph_state", name="pH"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="compressor_1_temp", name="Temp Compresseur 1"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="battery_1_temp", name="Temp Batterie 1"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="compressor_2_temp", name="Temp Compresseur 2"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="battery_2_temp", name="Temp Batterie 2"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="ext2_temp", name="Temp Sortie Échangeur"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="gas_temp", name="Temp Gaz"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="superheat", name="Surchauffe"),
            DiagnosticTemperatureSensor(coord, host, entry.entry_id, key="delta", name="Delta Supervision"),
            DiagnosticPressureSensor(coord, host, entry.entry_id, key="pressure_1", name="Pression 1"),
            DiagnosticPressureSensor(coord, host, entry.entry_id, key="pressure_2", name="Pression 2"),
            RawSensor(coord, host, entry.entry_id, key="super_raw", name="Super Raw"),
            RawSensor(coord, host, entry.entry_id, key="accueil_raw", name="Accueil Raw"),
            RawSensor(coord, host, entry.entry_id, key="reg_raw", name="Reg Raw"),
        ],
        True,
    )


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
        return device_info_for_host(self._host)

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
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

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


class DiagnosticTemperatureSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class DiagnosticPressureSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class SetpointDiffSensor(CoordinatorEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str):
        super().__init__(coordinator)
        self._host = host
        self._attr_name = "O'Foehn Écart Consigne"
        self._attr_unique_id = f"ofoehn_setpoint_diff_{host}"

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        water_in = self.coordinator.data.get("water_in")
        setpoint = self.coordinator.data.get("setpoint")
        if water_in is None or setpoint is None:
            return None
        return round(setpoint - water_in, 2)


class RegTextSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        reg_data = self.coordinator.data.get("reg", {})
        value = reg_data.get(self._key)
        if self._key == "mode":
            fallback_mode = self.coordinator.data.get("mode")
            reg_raw = clean_html_text(self.coordinator.data.get("reg_raw"))
            if fallback_mode and (value is None or (value == "AUTO" and "AUTO" not in reg_raw.upper())):
                return fallback_mode
            return value or fallback_mode

        if value not in (None, "", "Inconnu"):
            return value

        fallback_keys = {
            "regulation": ("reg_mode",),
            "next_action": ("next_action",),
            "status": ("general_state",),
        }
        for fallback_key in fallback_keys.get(self._key, ()):
            fallback_value = self.coordinator.data.get(fallback_key)
            if fallback_value not in (None, "", "Inconnu"):
                return fallback_value
        return value


class DiagnosticTextSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class RawSensor(CoordinatorEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OFoehnCoordinator, host: str, entry_id: str, key: str, name: str):
        super().__init__(coordinator)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{host}"
        self._host = host

    @property
    def device_info(self):
        return device_info_for_host(self._host)

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        preview = clean_html_text(value)
        self._attr_extra_state_attributes = {"raw": value, "plain_text": preview}
        if value is None:
            return None
        return (preview or value)[:255]
