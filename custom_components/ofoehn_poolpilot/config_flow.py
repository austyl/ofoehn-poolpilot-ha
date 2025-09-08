from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

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
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)

        oi = self.config_entry.options or {}
        schema = vol.Schema(
            {
                vol.Optional("water_in_idx", default=oi.get("water_in_idx", DEFAULT_INDEX["water_in_idx"])): int,
                vol.Optional(
                    "water_out_idx", default=oi.get("water_out_idx", DEFAULT_INDEX["water_out_idx"])
                ): int,
                vol.Optional("air_idx", default=oi.get("air_idx", DEFAULT_INDEX["air_idx"])): int,
                vol.Optional(
                    "voltage_idx", default=oi.get("voltage_idx", DEFAULT_INDEX["voltage_idx"])
                ): int,
                vol.Optional(
                    "internal_idx", default=oi.get("internal_idx", DEFAULT_INDEX["internal_idx"])
                ): int,
                vol.Optional("pump_idx", default=oi.get("pump_idx", DEFAULT_INDEX["pump_idx"])): int,
                vol.Optional(
                    "heating_idx", default=oi.get("heating_idx", DEFAULT_INDEX["heating_idx"])
                ): int,
                vol.Optional("light_idx", default=oi.get("light_idx", DEFAULT_INDEX["light_idx"])): int,
                vol.Optional("power_idx", default=oi.get("power_idx", DEFAULT_INDEX["power_idx"])): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

