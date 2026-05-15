from __future__ import annotations

import asyncio
from ipaddress import ip_address
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import OFoehnApi, parse_accueil_html, parse_donnees, parse_super_values

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
DISCOVERY_TIMEOUT = 1


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._detected_hosts: list[str] = []

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

    async def _async_validate_input(self, user_input: dict[str, Any]) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        api = OFoehnApi(
            host=user_input[CONF_HOST],
            port=user_input.get(CONF_PORT, DEFAULT_PORT),
            session=session,
            auth_mode=user_input.get("auth_mode", AUTH_NONE),
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
            login_path=user_input.get("login_path", "/login.cgi"),
            login_method=user_input.get("login_method", "POST"),
            user_field=user_input.get("user_field", "user"),
            pass_field=user_input.get("pass_field", "pass"),
            timeout=user_input.get("timeout", DEFAULT_TIMEOUT),
        )

        raw_super = await api.read_super()
        raw_accueil = await api.read_accueil()

        parsed_super = parse_super_values(raw_super)
        parsed_accueil = parse_accueil_html(raw_accueil)
        if not parsed_super and not parsed_accueil:
            raise ValueError("Not an O'Foehn payload")

        return {
            "serial_number": parsed_accueil.get("serial_number"),
            "mac_address": parsed_accueil.get("mac_address"),
            "module_name": parsed_accueil.get("module_name"),
        }

    async def _async_probe_host(self, host: str, port: int) -> str | None:
        session = async_get_clientsession(self.hass)
        api = OFoehnApi(
            host=host,
            port=port,
            session=session,
            timeout=DISCOVERY_TIMEOUT,
        )
        try:
            raw_accueil = await api.read_accueil()
        except Exception:
            return None

        parsed = parse_accueil_html(raw_accueil)
        if parsed.get("serial_number") or parsed.get("module_name") or parsed.get("mode"):
            return host
        return None


    async def _async_get_local_ipv4(self) -> str | None:
        adapters = await network.async_get_adapters(self.hass)
        for adapter in adapters:
            for ipv4 in adapter.get("ipv4", []):
                local_ip = ip_address(ipv4["address"])
                if local_ip.is_loopback or local_ip.is_link_local or not local_ip.is_private:
                    continue
                return str(local_ip)
        return None

    async def _async_discover_hosts(self, port: int) -> list[str]:
        local_ip = await self._async_get_local_ipv4()
        if not local_ip:
            return []

        detected = await self._async_probe_host(local_ip, port)
        if detected:
            return [detected]
        return []


    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                info = await self._async_validate_input(user_input)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                unique_id = info.get("serial_number") or info.get("mac_address")
                if unique_id:
                    await self.async_set_unique_id(str(unique_id))
                    self._abort_if_unique_id_configured()

                data = dict(user_input)
                if info.get("serial_number"):
                    data["serial_number"] = info["serial_number"]
                if info.get("mac_address"):
                    data["mac_address"] = info["mac_address"]
                return self.async_create_entry(title=f"O'Foehn ({user_input[CONF_HOST]})", data=data)

        defaults = dict(user_input or {})
        if not defaults:
            local_ip = await self._async_get_local_ipv4()
            if local_ip and not defaults.get(CONF_HOST):
                defaults[CONF_HOST] = local_ip

            if not self._detected_hosts:
                try:
                    self._detected_hosts = await asyncio.wait_for(
                        self._async_discover_hosts(DEFAULT_PORT), timeout=2
                    )
                except TimeoutError:
                    self._detected_hosts = []
                except Exception:
                    self._detected_hosts = []

            if self._detected_hosts and not defaults.get(CONF_HOST):
                defaults[CONF_HOST] = self._detected_hosts[0]

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_user_schema(defaults),
            errors=errors,
            description_placeholders={
                "detected_hosts": ", ".join(self._detected_hosts) if self._detected_hosts else "-"
            },
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
