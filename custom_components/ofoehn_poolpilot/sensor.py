from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfElectricPotential, UnitOfPressure, UnitOfTemperature
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_ENABLE_RAW_SENSORS, DOMAIN
from .coordinator import OFoehnCoordinator, clean_html_lines, clean_html_text
from .helpers import OFoehnEntity, get_donnee_float


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    coord: OFoehnCoordinator = data["coordinator"]
    device_key = data["device_key"]
    device_info = data["device_info"]

    entities: list[SensorEntity] = [
        TempSensor(coord, device_key, device_info, key="water_in_idx", name="Eau In"),
        TempSensor(coord, device_key, device_info, key="water_out_idx", name="Eau Out"),
        TempSensor(coord, device_key, device_info, key="air_idx", name="Air"),
        VoltageSensor(coord, device_key, device_info, key="voltage_idx", name="Tension"),
        TempSensor(coord, device_key, device_info, key="internal_idx", name="Temp Interne"),
        SetpointDiffSensor(coord, device_key, device_info),
        RegTextSensor(coord, device_key, device_info, key="mode", name="Mode"),
        RegTextSensor(coord, device_key, device_info, key="regulation", name="Régulation"),
        RegTextSensor(coord, device_key, device_info, key="next_action", name="Prochaine action"),
        RegTextSensor(coord, device_key, device_info, key="status", name="État général"),
        DiagnosticValueSensor(coord, device_key, device_info, key="reg_value_1", name="Reg Valeur 1"),
        DiagnosticValueSensor(coord, device_key, device_info, key="reg_value_2", name="Reg Valeur 2"),
        DiagnosticValueSensor(coord, device_key, device_info, key="reg_value_3", name="Reg Valeur 3"),
        DiagnosticValueSensor(coord, device_key, device_info, key="reg_value_4", name="Reg Valeur 4"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_1", name="Reg Flag 1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_2", name="Reg Flag 2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_3", name="Reg Flag 3"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_4", name="Reg Flag 4"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_5", name="Reg Flag 5"),
        DiagnosticTextSensor(coord, device_key, device_info, key="reg_flag_6", name="Reg Flag 6"),
        DiagnosticTextSensor(coord, device_key, device_info, key="firmware_version", name="Firmware"),
        DiagnosticTextSensor(coord, device_key, device_info, key="module_version", name="Version Module"),
        DiagnosticTextSensor(coord, device_key, device_info, key="module_build", name="Build Module"),
        DiagnosticTextSensor(coord, device_key, device_info, key="module_name", name="Module"),
        DiagnosticTextSensor(coord, device_key, device_info, key="serial_number", name="Numéro de série"),
        DiagnosticTextSensor(coord, device_key, device_info, key="mac_address", name="Adresse MAC"),
        DiagnosticTextSensor(coord, device_key, device_info, key="clock", name="Horloge"),
        DiagnosticTextSensor(coord, device_key, device_info, key="timers_summary", name="Timers"),
        DiagnosticTextSensor(coord, device_key, device_info, key="season_stop", name="Mode Saison"),
        DiagnosticTextSensor(coord, device_key, device_info, key="stopped_state", name="État arrêt"),
        DiagnosticTextSensor(coord, device_key, device_info, key="heat_state", name="État chauffage"),
        DiagnosticTextSensor(coord, device_key, device_info, key="signal_level", name="Niveau signal"),
        DiagnosticTextSensor(coord, device_key, device_info, key="option_1", name="Option 1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="option_2", name="Option 2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="config_code", name="Code Config"),
        DiagnosticTextSensor(coord, device_key, device_info, key="hardware_code", name="Code Hardware"),
        DiagnosticTextSensor(coord, device_key, device_info, key="webuser_role", name="Rôle WebUser"),
        DiagnosticTextSensor(coord, device_key, device_info, key="ph_license", name="Licence pH"),
        DiagnosticTextSensor(coord, device_key, device_info, key="ev_present", name="Présence EV"),
        DiagnosticTextSensor(coord, device_key, device_info, key="ev_position", name="Position EV"),
        DiagnosticTextSensor(coord, device_key, device_info, key="balneo_state", name="Balnéo"),
        DiagnosticTextSensor(coord, device_key, device_info, key="contact_bp1", name="Contact BP1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="contact_bp2", name="Contact BP2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="contact_hp1", name="Contact HP1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="contact_hp2", name="Contact HP2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="power_state", name="État alimentation"),
        DiagnosticTextSensor(coord, device_key, device_info, key="pump_state", name="Relai pompe"),
        DiagnosticTextSensor(coord, device_key, device_info, key="fan_state", name="Relai ventilateur"),
        DiagnosticTextSensor(coord, device_key, device_info, key="valve_1_state", name="Relai vanne 1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="compressor_1_state", name="Relai compresseur 1"),
        DiagnosticTextSensor(coord, device_key, device_info, key="valve_2_state", name="Relai vanne 2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="compressor_2_state", name="Relai compresseur 2"),
        DiagnosticTextSensor(coord, device_key, device_info, key="chlorine_state", name="Chlore"),
        DiagnosticTextSensor(coord, device_key, device_info, key="ph_state", name="pH"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="compressor_1_temp", name="Temp Compresseur 1"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="battery_1_temp", name="Temp Batterie 1"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="compressor_2_temp", name="Temp Compresseur 2"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="battery_2_temp", name="Temp Batterie 2"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="ext2_temp", name="Temp Sortie Échangeur"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="gas_temp", name="Temp Gaz"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="superheat", name="Surchauffe"),
        DiagnosticTemperatureSensor(coord, device_key, device_info, key="delta", name="Delta Supervision"),
        DiagnosticPressureSensor(coord, device_key, device_info, key="pressure_1", name="Pression 1"),
        DiagnosticPressureSensor(coord, device_key, device_info, key="pressure_2", name="Pression 2"),
    ]

    if entry.options.get(CONF_ENABLE_RAW_SENSORS, False):
        entities.extend(
            [
                RawSensor(coord, device_key, device_info, key="super_raw", name="Super Raw"),
                RawSensor(coord, device_key, device_info, key="accueil_raw", name="Accueil Raw"),
                RawSensor(coord, device_key, device_info, key="reg_raw", name="Reg Raw"),
            ]
        )

    async_add_entities(entities, True)


class TempSensor(OFoehnEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{device_key}"

    @property
    def native_value(self):
        fallback_map = {
            "water_in_idx": "water_in",
            "water_out_idx": "water_out",
            "air_idx": "air_temp",
            "internal_idx": "internal_temp",
        }
        return get_donnee_float(
            self.coordinator.data,
            self._key,
            fallback_key=fallback_map.get(self._key),
        )


class VoltageSensor(OFoehnEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{device_key}"

    @property
    def native_value(self):
        return get_donnee_float(
            self.coordinator.data,
            self._key,
            fallback_key="voltage",
        )


class DiagnosticTemperatureSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{device_key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class DiagnosticValueSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{device_key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class DiagnosticPressureSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.KPA
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{device_key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class SetpointDiffSensor(OFoehnEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._attr_name = "O'Foehn Écart Consigne"
        self._attr_unique_id = f"ofoehn_setpoint_diff_{device_key}"

    @property
    def native_value(self):
        data = self.coordinator.data
        delta = data.get("delta")
        if delta is not None:
            return delta
        water_in = data.get("water_in")
        setpoint = data.get("setpoint")
        if water_in is None or setpoint is None:
            return None
        return round(setpoint - water_in, 2)


class RegTextSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{device_key}"

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

        if self._key == "status":
            stopped_state = self.coordinator.data.get("stopped_state")
            if stopped_state not in (None, "", "Inconnu"):
                normalized = clean_html_text(stopped_state).lower()
                if normalized not in {"normal", "marche", "en marche", "running"}:
                    return stopped_state

        if value not in (None, "", "Inconnu"):
            return value

        fallback_keys = {
            "regulation": ("reg_mode",),
            "next_action": ("next_action",),
            "status": ("stopped_state", "general_state"),
        }
        for fallback_key in fallback_keys.get(self._key, ()):
            fallback_value = self.coordinator.data.get(fallback_key)
            if fallback_value not in (None, "", "Inconnu"):
                return fallback_value
        return value


class DiagnosticTextSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_diag_{key}_{device_key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class RawSensor(OFoehnEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: OFoehnCoordinator,
        device_key: str,
        device_info: dict,
        key: str,
        name: str,
    ):
        super().__init__(coordinator, device_key, device_info)
        self._key = key
        self._attr_name = f"O'Foehn {name}"
        self._attr_unique_id = f"ofoehn_{key}_{device_key}"

    @property
    def native_value(self):
        value = self.coordinator.data.get(self._key)
        if value is None:
            return None
        preview = clean_html_text(value)
        return (preview or value)[:255]

    @property
    def extra_state_attributes(self):
        value = self.coordinator.data.get(self._key)
        if value is None:
            return {}
        preview = clean_html_text(value)
        return {
            "raw": value,
            "plain_text": preview,
            "lines": clean_html_lines(value),
        }
