import importlib.util
import pathlib
import types
import sys

fake_aiohttp = types.ModuleType("aiohttp")
fake_aiohttp.ClientSession = object
fake_aiohttp.BasicAuth = object
fake_aiohttp.ClientResponseError = Exception
sys.modules["aiohttp"] = fake_aiohttp

fake_ha = types.ModuleType("homeassistant")
sys.modules["homeassistant"] = fake_ha

fake_core = types.ModuleType("homeassistant.core")
fake_core.HomeAssistant = object
sys.modules["homeassistant.core"] = fake_core

fake_helpers = types.ModuleType("homeassistant.helpers")
sys.modules["homeassistant.helpers"] = fake_helpers

fake_uc = types.ModuleType("homeassistant.helpers.update_coordinator")

class _DUC:
    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

class _CE:
    def __init__(self, coordinator):
        self.coordinator = coordinator

fake_uc.DataUpdateCoordinator = _DUC
fake_uc.CoordinatorEntity = _CE
sys.modules["homeassistant.helpers.update_coordinator"] = fake_uc

fake_sensor_mod = types.ModuleType("homeassistant.components.sensor")
fake_sensor_mod.SensorEntity = object
sys.modules["homeassistant.components.sensor"] = fake_sensor_mod

fake_const = types.ModuleType("homeassistant.const")
fake_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
fake_const.UnitOfElectricPotential = types.SimpleNamespace(VOLT="V")
sys.modules["homeassistant.const"] = fake_const

fake_entity = types.ModuleType("homeassistant.helpers.entity")

class _EC:
    DIAGNOSTIC = "diagnostic"

fake_entity.EntityCategory = _EC
sys.modules["homeassistant.helpers.entity"] = fake_entity

base_path = pathlib.Path(__file__).resolve().parents[1]
custom_components_path = base_path / "custom_components"
package_cc = types.ModuleType("custom_components")
package_cc.__path__ = [str(custom_components_path)]
sys.modules.setdefault("custom_components", package_cc)

package_pp = types.ModuleType("custom_components.ofoehn_poolpilot")
package_pp.__path__ = [str(custom_components_path / "ofoehn_poolpilot")]
sys.modules.setdefault("custom_components.ofoehn_poolpilot", package_pp)

const_path = custom_components_path / "ofoehn_poolpilot" / "const.py"
const_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.const", const_path)
const_module = importlib.util.module_from_spec(const_spec)
const_spec.loader.exec_module(const_module)
sys.modules["custom_components.ofoehn_poolpilot.const"] = const_module

sensor_path = custom_components_path / "ofoehn_poolpilot" / "sensor.py"
sensor_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.sensor", sensor_path)
sensor_module = importlib.util.module_from_spec(sensor_spec)
sensor_spec.loader.exec_module(sensor_module)

TempSensor = sensor_module.TempSensor
VoltageSensor = sensor_module.VoltageSensor


class DummyCoordinator:
    def __init__(self, data):
        self.data = data


def test_temp_sensor_fallback():
    coord = DummyCoordinator(
        {
            "indices": {"water_in_idx": 1},
            "super": {},
            "water_in": 28.6,
        }
    )
    sensor = TempSensor(coord, "host", "entry", key="water_in_idx", name="Eau In")
    assert sensor.native_value == 28.6


def test_voltage_sensor_fallback():
    coord = DummyCoordinator(
        {
            "indices": {"voltage_idx": 1},
            "super": {},
            "voltage": 230.0,
        }
    )
    sensor = VoltageSensor(coord, "host", "entry", key="voltage_idx", name="Tension")
    assert sensor.native_value == 230.0
