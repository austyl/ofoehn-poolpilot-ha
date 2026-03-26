from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import OFoehnApi, parse_donnees

from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    AUTH_NONE,
    AUTH_BASIC,
    AUTH_QUERY,
    AUTH_COOKIE,
    DEFAULT_INDEX,
)

AUTH_OPTIONS = [AUTH_NONE, AUTH_BASIC, AUTH_QUERY, AUTH_COOKIE]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=f"O'Foehn ({user_input['host']})", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("port", default=DEFAULT_PORT): int,
                vol.Optional("auth_mode", default=AUTH_NONE): vol.In(AUTH_OPTIONS),
                vol.Optional("username"): str,
                vol.Optional("password"): str,
                vol.Optional("login_path", default="/login.cgi"): str,
                vol.Optional("login_method", default="POST"): vol.In(["GET", "POST"]),
                vol.Optional("user_field", default="user"): str,
                vol.Optional("pass_field", default="pass"): str,
                vol.Optional("timeout", default=DEFAULT_TIMEOUT): int,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        super().__init__()

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)

        oi = self.config_entry.options or {}
        errors = {}
        donnees = {}

        session = async_get_clientsession(self.hass)
        api = OFoehnApi(
            host=self.config_entry.data["host"],
            port=self.config_entry.data.get("port", DEFAULT_PORT),
            session=session,
            auth_mode=self.config_entry.data.get("auth_mode", AUTH_NONE),
            username=self.config_entry.data.get("username"),
            password=self.config_entry.data.get("password"),
            login_path=self.config_entry.data.get("login_path", "/login.cgi"),
            login_method=self.config_entry.data.get("login_method", "POST"),
            user_field=self.config_entry.data.get("user_field", "user"),
            pass_field=self.config_entry.data.get("pass_field", "pass"),
            timeout=self.config_entry.data.get("timeout", DEFAULT_TIMEOUT),
        )

        try:
            raw = await api.read_super()
            donnees = parse_donnees(raw)
        except Exception:
            errors["base"] = "cannot_connect"
            donnees = {}

        select = None
        if donnees:
            select = {
                "selector": {
                    "select": {
                        "options": [
                            {"value": i, "label": f"{i} ({v})"}
                            for i, v in sorted(donnees.items())
                        ]
                    }
                }
            }

        schema_dict = {}
        for idx_key in ["water_in_idx", "water_out_idx", "air_idx", "voltage_idx", 
                        "internal_idx", "pump_idx", "heating_idx", "light_idx", "power_idx"]:
            kwargs = {
                "default": oi.get(idx_key, DEFAULT_INDEX[idx_key]),
            }
            if select:
                kwargs["description"] = select
            schema_dict[vol.Optional(idx_key, **kwargs)] = int

        schema = vol.Schema(schema_dict)

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

