DOMAIN = "ofoehn_poolpilot"
DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 10  # seconds
PLATFORMS = ["climate", "sensor", "switch", "binary_sensor"]
SCAN_INTERVAL = 30  # seconds

# Auth modes
AUTH_NONE = "none"
AUTH_BASIC = "basic"
AUTH_QUERY = "query"
AUTH_COOKIE = "cookie"

ENDPOINTS = {
    "accueil": "/accueil.cgi",
    "super": "/super.cgi",
    "reg_get": "/getReg.cgi",
    "reg_set": "/setReg.cgi",
    "toggle": "/changeOnOff.cgi",
    "light": "/toggleE.cgi",
}

# Defaults for DONNEE indices (may vary by firmware)
DEFAULT_INDEX = {
    "water_in_idx": 5,
    "water_out_idx": 6,
    "air_idx": 7,
    "voltage_idx": 8,
    "internal_idx": 9,
    "pump_idx": 10,
    "heating_idx": 11,
    "light_idx": 16,  # accueil.cgi souvent
    "power_idx": 24   # état alim (selon firmware)
}
