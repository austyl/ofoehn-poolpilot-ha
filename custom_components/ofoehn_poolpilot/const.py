DOMAIN = "ofoehn_poolpilot"
DEFAULT_PORT = 80
PLATFORMS = ["climate", "sensor", "switch"]
SCAN_INTERVAL = 30  # seconds

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
    "light_idx": 16,  # from accueil.cgi usually
    "power_idx": 24   # indicator for power state (super/accueil dependent)
}