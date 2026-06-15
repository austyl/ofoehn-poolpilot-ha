from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import asyncio
import voluptuous as vol
from aiohttp import ClientError, ClientResponseError
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import OFoehnApi, parse_accueil_html, parse_donnees

from .const import (
    CONF_ENABLE_RAW_SENSORS,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    AUTH_NONE,
    AUTH_BASIC,
    AUTH_QUERY,
    AUTH_COOKIE,
    DEFAULT_INDEX,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SCAN_INTERVAL,
)

AUTH_OPTIONS = [AUTH_NONE, AUTH_BASIC, AUTH_QUERY, AUTH_COOKIE]


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate the device rejected authentication."""


class InvalidHost(HomeAssistantError):
    """Error to indicate the provided host is invalid."""


class MissingAuth(HomeAssistantError):
    """Error to indicate credentials are required."""


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def _normalize_host(self, value: str) -> tuple[str, int | None]:
        raw = value.strip()
        if not raw:
            raise InvalidHost

        parsed = urlparse(raw if "://" in raw else f"//{raw}")
        host = parsed.hostname or parsed.path.split("/", 1)[0].split(":", 1)[0]
        if not host:
            raise InvalidHost
        try:
            port = parsed.port
        except ValueError as err:
            raise InvalidHost from err
        return host.strip().lower(), port

    def _normalize_path(self, value: str, default: str) -> str:
        path = value.strip()
        if not path:
            return default
        if "://" in path:
            path = urlparse(path).path or default
        if not path.startswith("/"):
            path = f"/{path}"
        return path

    def _prepare_user_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        data = dict(user_input)
        host, parsed_port = self._normalize_host(str(data.get(CONF_HOST, "")))
        data[CONF_HOST] = host
        if parsed_port and data.get(CONF_PORT, DEFAULT_PORT) == DEFAULT_PORT:
            data[CONF_PORT] = parsed_port
        data["auth_mode"] = str(data.get("auth_mode", AUTH_NONE)).strip().lower()
        data[CONF_USERNAME] = str(data.get(CONF_USERNAME, "")).strip()
        data[CONF_PASSWORD] = "" if data.get(CONF_PASSWORD) is None else str(data.get(CONF_PASSWORD))
        data["login_path"] = self._normalize_path(
            str(data.get("login_path", "/login.cgi")),
            "/login.cgi",
        )
        data["login_method"] = str(data.get("login_method", "POST")).strip().upper() or "POST"
        data["user_field"] = str(data.get("user_field", "user")).strip() or "user"
        data["pass_field"] = str(data.get("pass_field", "pass")).strip() or "pass"
        data["timeout"] = int(data.get("timeout", DEFAULT_TIMEOUT))

        if data["auth_mode"] != AUTH_NONE:
            if not data[CONF_USERNAME] or not data[CONF_PASSWORD].strip():
                raise MissingAuth

        return data

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        data = self._prepare_user_input(user_input)
        session = async_get_clientsession(self.hass)
        api = OFoehnApi(
            host=data[CONF_HOST],
            port=data.get(CONF_PORT, DEFAULT_PORT),
            session=session,
            auth_mode=data.get("auth_mode", AUTH_NONE),
            username=data.get(CONF_USERNAME),
            password=data.get(CONF_PASSWORD),
            login_path=data.get("login_path", "/login.cgi"),
            login_method=data.get("login_method", "POST"),
            user_field=data.get("user_field", "user"),
            pass_field=data.get("pass_field", "pass"),
            timeout=data.get("timeout", DEFAULT_TIMEOUT),
        )

        try:
            raw_super, raw_accueil = await asyncio.gather(
                api.read_super(),
                api.read_accueil(),
            )
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise InvalidAuth from err
            raise CannotConnect from err
        except (ClientError, OSError, TimeoutError) as err:
            raise CannotConnect from err

        parsed_super = parse_donnees(raw_super)
        parsed_accueil = parse_accueil_html(raw_accueil)
        if not parsed_super and not parsed_accueil:
            raise CannotConnect

        if (
            data.get("auth_mode") == AUTH_NONE
            and not parsed_super
            and not parsed_accueil.get("serial_number")
            and not parsed_accueil.get("mode")
        ):
            raise InvalidAuth

        if parsed_accueil.get("serial_number"):
            data["serial_number"] = parsed_accueil["serial_number"]
        if parsed_accueil.get("mac_address"):
            data["mac_address"] = parsed_accueil["mac_address"]
        return data

    def _build_user_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
                vol.Optional(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): int,
                vol.Optional("auth_mode", default=defaults.get("auth_mode", AUTH_NONE)): vol.In(AUTH_OPTIONS),
                vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
                vol.Optional(CONF_PASSWORD, default=defaults.get(CONF_PASSWORD, "")): str,
                vol.Optional("login_path", default=defaults.get("login_path", "/login.cgi")): str,
                vol.Optional("login_method", default=defaults.get("login_method", "POST")): vol.In(["GET", "POST"]),
                vol.Optional("user_field", default=defaults.get("user_field", "user")): str,
                vol.Optional("pass_field", default=defaults.get("pass_field", "pass")): str,
                vol.Optional("timeout", default=defaults.get("timeout", DEFAULT_TIMEOUT)): int,
            }
        )

    async def async_step_user(self, user_input=None):
        errors = {}
        existing_entries = self._async_current_entries()
        existing_entry = existing_entries[0] if existing_entries else None

        if user_input is not None:
            try:
                prepared_input = await self._async_validate_input(user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except MissingAuth:
                errors["base"] = "missing_auth"
            except InvalidHost:
                errors["base"] = "invalid_host"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:
                errors["base"] = "unknown"
            else:
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data=prepared_input,
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

                unique_id = str(
                    prepared_input.get("serial_number")
                    or prepared_input.get("mac_address")
                    or prepared_input[CONF_HOST]
                ).strip().lower()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"O'Foehn ({prepared_input[CONF_HOST]})",
                    data=prepared_input,
                )

        defaults = dict(existing_entry.data) if existing_entry else dict(user_input or {})
        if not defaults.get(CONF_HOST):
            defaults[CONF_HOST] = ""
        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(defaults),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
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
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=oi.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    vol.Optional(
                        CONF_ENABLE_RAW_SENSORS,
                        default=oi.get(CONF_ENABLE_RAW_SENSORS, False),
                    ): bool,
                    vol.Optional(
                        "water_in_idx",
                        default=oi.get("water_in_idx", DEFAULT_INDEX["water_in_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "water_out_idx",
                        default=oi.get("water_out_idx", DEFAULT_INDEX["water_out_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "air_idx",
                        default=oi.get("air_idx", DEFAULT_INDEX["air_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "voltage_idx",
                        default=oi.get("voltage_idx", DEFAULT_INDEX["voltage_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "internal_idx",
                        default=oi.get("internal_idx", DEFAULT_INDEX["internal_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "pump_idx",
                        default=oi.get("pump_idx", DEFAULT_INDEX["pump_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "heating_idx",
                        default=oi.get("heating_idx", DEFAULT_INDEX["heating_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "light_idx",
                        default=oi.get("light_idx", DEFAULT_INDEX["light_idx"]),
                        description=select,
                    ): int,
                    vol.Optional(
                        "power_idx",
                        default=oi.get("power_idx", DEFAULT_INDEX["power_idx"]),
                        description=select,
                    ): int,
                }
            )
        else:
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=oi.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL),
                    ): vol.All(int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)),
                    vol.Optional(
                        CONF_ENABLE_RAW_SENSORS,
                        default=oi.get(CONF_ENABLE_RAW_SENSORS, False),
                    ): bool,
                    vol.Optional(
                        "water_in_idx",
                        default=oi.get("water_in_idx", DEFAULT_INDEX["water_in_idx"]),
                    ): int,
                    vol.Optional(
                        "water_out_idx",
                        default=oi.get("water_out_idx", DEFAULT_INDEX["water_out_idx"]),
                    ): int,
                    vol.Optional(
                        "air_idx",
                        default=oi.get("air_idx", DEFAULT_INDEX["air_idx"]),
                    ): int,
                    vol.Optional(
                        "voltage_idx",
                        default=oi.get("voltage_idx", DEFAULT_INDEX["voltage_idx"]),
                    ): int,
                    vol.Optional(
                        "internal_idx",
                        default=oi.get("internal_idx", DEFAULT_INDEX["internal_idx"]),
                    ): int,
                    vol.Optional(
                        "pump_idx",
                        default=oi.get("pump_idx", DEFAULT_INDEX["pump_idx"]),
                    ): int,
                    vol.Optional(
                        "heating_idx",
                        default=oi.get("heating_idx", DEFAULT_INDEX["heating_idx"]),
                    ): int,
                    vol.Optional(
                        "light_idx",
                        default=oi.get("light_idx", DEFAULT_INDEX["light_idx"]),
                    ): int,
                    vol.Optional(
                        "power_idx",
                        default=oi.get("power_idx", DEFAULT_INDEX["power_idx"]),
                    ): int,
                }
            )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
