from __future__ import annotations

import voluptuous as vol
from aiohttp import ClientError, ClientResponseError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import aiohttp_client

from .const import (
    AUTH_BASIC,
    AUTH_COOKIE,
    AUTH_NONE,
    AUTH_QUERY,
    CONF_SCAN_INTERVAL,
    DEFAULT_INDEX,
    DEFAULT_PORT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL,
)
from .coordinator import OFoehnApi

AUTH_OPTIONS = [AUTH_NONE, AUTH_BASIC, AUTH_QUERY, AUTH_COOKIE]


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the provided auth is invalid."""


async def validate_input(hass, data: dict) -> str:
    """Validate the user input allows us to connect."""
    session = aiohttp_client.async_get_clientsession(hass)
    api = OFoehnApi(
        host=data["host"],
        port=data["port"],
        session=session,
        auth_mode=data["auth_mode"],
        username=data.get("username"),
        password=data.get("password"),
        login_path=data.get("login_path", "/login.cgi"),
        login_method=data.get("login_method", "POST"),
        user_field=data.get("user_field", "user"),
        pass_field=data.get("pass_field", "pass"),
    )

    try:
        await api.read_super()
    except ClientResponseError as err:
        if err.status in (401, 403):
            raise InvalidAuth from err
        raise CannotConnect from err
    except TimeoutError as err:
        raise CannotConnect from err
    except ClientError as err:
        raise CannotConnect from err

    return f"O'Foehn ({data['host']})"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = {
                **user_input,
                "host": user_input["host"].strip(),
                "login_path": f"/{user_input['login_path'].lstrip('/')}",
            }

            if user_input["auth_mode"] != AUTH_NONE and (
                not user_input.get("username") or not user_input.get("password")
            ):
                errors["base"] = "missing_auth"
            else:
                try:
                    title = await validate_input(self.hass, user_input)
                    self._async_abort_entries_match({"host": user_input["host"]})
                    await self.async_set_unique_id(user_input["host"].lower())
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=title, data=user_input)
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except Exception:
                    errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required("host"): str,
            vol.Optional("port", default=DEFAULT_PORT): int,
            vol.Optional("auth_mode", default=AUTH_NONE): vol.In(AUTH_OPTIONS),
            vol.Optional("username"): str,
            vol.Optional("password"): str,
            vol.Optional("login_path", default="/login.cgi"): str,
            vol.Optional("login_method", default="POST"): vol.In(["GET", "POST"]),
            vol.Optional("user_field", default="user"): str,
            vol.Optional("pass_field", default="pass"): str,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    @callback
    def async_get_options_flow(self, config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Options", data=user_input)

        oi = self.config_entry.options or {}
        schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=oi.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
            ),
            vol.Optional("water_in_idx", default=oi.get("water_in_idx", DEFAULT_INDEX["water_in_idx"])): int,
            vol.Optional("water_out_idx", default=oi.get("water_out_idx", DEFAULT_INDEX["water_out_idx"])): int,
            vol.Optional("air_idx", default=oi.get("air_idx", DEFAULT_INDEX["air_idx"])): int,
            vol.Optional("light_idx", default=oi.get("light_idx", DEFAULT_INDEX["light_idx"])): int,
            vol.Optional("power_idx", default=oi.get("power_idx", DEFAULT_INDEX["power_idx"])): int,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
