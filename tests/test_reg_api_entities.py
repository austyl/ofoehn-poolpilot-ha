import importlib.util
import pathlib
import types
import sys
import asyncio
import pytest


@pytest.fixture
def modules():
    """Load integration modules with stubbed dependencies."""
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

        def async_write_ha_state(self):
            pass

    fake_uc.DataUpdateCoordinator = _DUC
    fake_uc.CoordinatorEntity = _CE
    sys.modules["homeassistant.helpers.update_coordinator"] = fake_uc

    fake_climate_const = types.ModuleType("homeassistant.components.climate.const")
    fake_climate_const.HVACMode = types.SimpleNamespace(OFF="off", HEAT="heat", COOL="cool", AUTO="auto")
    fake_climate_const.ClimateEntityFeature = types.SimpleNamespace(TARGET_TEMPERATURE=1)
    sys.modules["homeassistant.components.climate.const"] = fake_climate_const

    fake_climate_mod = types.ModuleType("homeassistant.components.climate")
    fake_climate_mod.ClimateEntity = object
    sys.modules["homeassistant.components.climate"] = fake_climate_mod

    fake_switch_mod = types.ModuleType("homeassistant.components.switch")
    fake_switch_mod.SwitchEntity = object
    sys.modules["homeassistant.components.switch"] = fake_switch_mod

    fake_bs_mod = types.ModuleType("homeassistant.components.binary_sensor")
    fake_bs_mod.BinarySensorEntity = object
    sys.modules["homeassistant.components.binary_sensor"] = fake_bs_mod

    fake_const = types.ModuleType("homeassistant.const")
    fake_const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C")
    sys.modules["homeassistant.const"] = fake_const

    base_path = pathlib.Path(__file__).resolve().parents[1]
    custom_components_path = base_path / "custom_components"
    package_cc = types.ModuleType("custom_components")
    package_cc.__path__ = [str(custom_components_path)]
    sys.modules["custom_components"] = package_cc
    package_pp = types.ModuleType("custom_components.ofoehn_poolpilot")
    package_pp.__path__ = [str(custom_components_path / "ofoehn_poolpilot")]
    sys.modules["custom_components.ofoehn_poolpilot"] = package_pp

    const_path = custom_components_path / "ofoehn_poolpilot" / "const.py"
    const_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.const", const_path)
    const_module = importlib.util.module_from_spec(const_spec)
    const_spec.loader.exec_module(const_module)
    sys.modules["custom_components.ofoehn_poolpilot.const"] = const_module

    coord_path = custom_components_path / "ofoehn_poolpilot" / "coordinator.py"
    coord_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.coordinator", coord_path)
    coord_module = importlib.util.module_from_spec(coord_spec)
    coord_spec.loader.exec_module(coord_module)
    sys.modules["custom_components.ofoehn_poolpilot.coordinator"] = coord_module

    climate_path = custom_components_path / "ofoehn_poolpilot" / "climate.py"
    climate_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.climate", climate_path)
    climate_module = importlib.util.module_from_spec(climate_spec)
    climate_spec.loader.exec_module(climate_module)

    switch_path = custom_components_path / "ofoehn_poolpilot" / "switch.py"
    switch_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.switch", switch_path)
    switch_module = importlib.util.module_from_spec(switch_spec)
    switch_spec.loader.exec_module(switch_module)

    bs_path = custom_components_path / "ofoehn_poolpilot" / "binary_sensor.py"
    bs_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.binary_sensor", bs_path)
    bs_module = importlib.util.module_from_spec(bs_spec)
    bs_spec.loader.exec_module(bs_module)

    return types.SimpleNamespace(
        parse_reg=coord_module.parse_reg,
        OFoehnApi=coord_module.OFoehnApi,
        OFoehnClimate=climate_module.OFoehnClimate,
        HVACMode=climate_module.HVACMode,
        PowerSwitch=switch_module.PowerSwitch,
        PoolLightSwitch=switch_module.PoolLightSwitch,
        ConnectivityBinarySensor=bs_module.ConnectivityBinarySensor,
        PumpBinarySensor=bs_module.PumpBinarySensor,
        HeatingBinarySensor=bs_module.HeatingBinarySensor,
    )


@pytest.fixture
def make_coordinator():
    class DummyApi:
        def __init__(self):
            self.toggled = False
            self.light = None
            self.mode = None
            self.setpoint = None
            self.conn_result = True

        async def toggle_power(self):
            self.toggled = True

        async def set_light(self, on: bool):
            self.light = on

        async def set_mode(self, mode: str):
            self.mode = mode

        async def set_setpoint(self, temp: float):
            self.setpoint = temp

        async def check_connection(self):
            return self.conn_result

    class DummyCoordinator:
        def __init__(self, data):
            self.data = data
            self.api = DummyApi()
            self.last_update_success = True
            self.refreshed = False

        async def async_request_refresh(self):
            self.refreshed = True

    return DummyCoordinator


def test_parse_reg_parses_values(modules):
    raw = "28.5, chaud, AUTO, action, OK"
    result = modules.parse_reg(raw)
    assert result["setpoint"] == 28.5
    assert result["mode"] == "CHAUD"
    assert result["regulation"] == "AUTO"
    assert result["next_action"] == "action"
    assert result["status"] == "OK"


def test_parse_reg_defaults(modules):
    result = modules.parse_reg("invalid")
    assert result["setpoint"] is None
    assert result["mode"] == "AUTO"


def test_check_connection(modules):
    class OkApi(modules.OFoehnApi):
        def __init__(self):
            pass

        async def read_super(self):
            return "ok"

    class FailApi(modules.OFoehnApi):
        def __init__(self):
            pass

        async def read_super(self):
            raise Exception("nope")

    ok = OkApi()
    fail = FailApi()
    assert asyncio.run(ok.check_connection()) is True
    assert asyncio.run(fail.check_connection()) is False


def test_climate_hvac_mode(modules, make_coordinator):
    data = {
        "indices": {"water_in_idx": 1, "power_idx": 2},
        "super": {1: 26.0, 2: 1.0},
        "accueil": {},
        "reg": {"mode": "CHAUD", "setpoint": 30.0},
    }
    coord = make_coordinator(data)
    climate = modules.OFoehnClimate(coord, "host", "entry")
    assert climate.hvac_mode == modules.HVACMode.HEAT
    coord.data["reg"]["mode"] = "FROID"
    assert climate.hvac_mode == modules.HVACMode.COOL
    coord.data["reg"]["mode"] = "AUTO"
    assert climate.hvac_mode == modules.HVACMode.AUTO
    coord.data["super"][2] = 0.0
    assert climate.hvac_mode == modules.HVACMode.OFF


def test_power_switch(modules, make_coordinator):
    data = {
        "indices": {"power_idx": 1},
        "super": {1: 0.0},
        "accueil": {},
        "reg": {},
    }
    coord = make_coordinator(data)
    sw = modules.PowerSwitch(coord, "host")
    assert sw.is_on is False
    asyncio.run(sw.async_turn_on())
    assert coord.api.toggled is True
    coord.api.toggled = False
    coord.data["super"][1] = 1.0
    asyncio.run(sw.async_turn_off())
    assert coord.api.toggled is True


def test_pool_light_switch(modules, make_coordinator):
    data = {
        "indices": {"light_idx": 3},
        "super": {},
        "accueil": {3: 0},
        "reg": {},
    }
    coord = make_coordinator(data)
    light = modules.PoolLightSwitch(coord, "host")
    assert light.is_on is False
    asyncio.run(light.async_turn_on())
    assert coord.api.light is True
    asyncio.run(light.async_turn_off())
    assert coord.api.light is False


def test_pump_binary_sensor(modules, make_coordinator):
    data = {
        "indices": {"pump_idx": 5},
        "super": {5: 1},
        "accueil": {},
        "reg": {},
    }
    coord = make_coordinator(data)
    sensor = modules.PumpBinarySensor(coord, "host")
    assert sensor.is_on is True
    coord.data["super"][5] = 0
    assert sensor.is_on is False


def test_heating_binary_sensor(modules, make_coordinator):
    data = {
        "indices": {"heating_idx": 6},
        "super": {6: 0},
        "accueil": {},
        "reg": {},
    }
    coord = make_coordinator(data)
    sensor = modules.HeatingBinarySensor(coord, "host")
    assert sensor.is_on is False
    coord.data["super"][6] = 1
    assert sensor.is_on is True


def test_connectivity_binary_sensor(modules, make_coordinator):
    data = {"indices": {}, "super": {}, "accueil": {}, "reg": {}}
    coord = make_coordinator(data)
    sensor = modules.ConnectivityBinarySensor(coord, "host")
    assert sensor.is_on is True
    coord.api.conn_result = False
    res = asyncio.run(sensor.async_check_connection())
    assert res is False
    assert sensor.is_on is False
    coord.api.conn_result = True
    res = asyncio.run(sensor.async_check_connection())
    assert res is True
    assert sensor.is_on is True

