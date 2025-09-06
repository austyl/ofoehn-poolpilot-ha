import importlib.util
import pathlib
import types
import sys

fake_aiohttp = types.ModuleType("aiohttp")
fake_aiohttp.ClientSession = object
fake_aiohttp.BasicAuth = object
fake_aiohttp.ClientResponseError = Exception
sys.modules.setdefault("aiohttp", fake_aiohttp)

fake_ha = types.ModuleType("homeassistant")
sys.modules.setdefault("homeassistant", fake_ha)
fake_ha_core = types.ModuleType("homeassistant.core")
fake_ha_core.HomeAssistant = object
sys.modules.setdefault("homeassistant.core", fake_ha_core)
fake_ha_helpers = types.ModuleType("homeassistant.helpers")
sys.modules.setdefault("homeassistant.helpers", fake_ha_helpers)
fake_ha_uc = types.ModuleType("homeassistant.helpers.update_coordinator")

class _DUC:
    def __init__(self, *args, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

fake_ha_uc.DataUpdateCoordinator = _DUC
sys.modules.setdefault("homeassistant.helpers.update_coordinator", fake_ha_uc)

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

coord_path = custom_components_path / "ofoehn_poolpilot" / "coordinator.py"
coord_spec = importlib.util.spec_from_file_location("custom_components.ofoehn_poolpilot.coordinator", coord_path)
coordinator = importlib.util.module_from_spec(coord_spec)
coord_spec.loader.exec_module(coordinator)

parse_accueil_html = coordinator.parse_accueil_html


def test_parse_accueil_html_parses_values():
    raw = "Chaud 28,1°C quelque chose (30°C)"
    result = parse_accueil_html(raw)
    assert result["water_in"] == 28.1
    assert result["setpoint"] == 30.0


def test_parse_accueil_html_no_match():
    assert parse_accueil_html("foobar") == {}
