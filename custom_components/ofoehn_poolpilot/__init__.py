from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ENABLE_RAW_SENSORS,
    CONF_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    PLATFORMS,
    SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
)
from .coordinator import OFoehnApi, OFoehnCoordinator
from .helpers import build_device_info

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _scan_interval_from_options(options: dict) -> timedelta:
    raw = options.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        seconds = SCAN_INTERVAL
    seconds = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, seconds))
    return timedelta(seconds=seconds)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session: ClientSession = async_get_clientsession(hass)

    api = OFoehnApi(
        host=entry.data["host"],
        port=entry.data.get("port", 80),
        session=session,
        auth_mode=entry.data.get("auth_mode", "none"),
        username=entry.data.get("username"),
        password=entry.data.get("password"),
        login_path=entry.data.get("login_path", "/login.cgi"),
        login_method=entry.data.get("login_method", "POST"),
        user_field=entry.data.get("user_field", "user"),
        pass_field=entry.data.get("pass_field", "pass"),
        timeout=entry.data.get("timeout", DEFAULT_TIMEOUT),
    )

    coordinator = OFoehnCoordinator(
        hass=hass,
        logger=_LOGGER,
        name="ofoehn_poolpilot",
        api=api,
        update_interval=_scan_interval_from_options(entry.options),
        options=entry.options,
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        _LOGGER.warning(
            "Initial poll failed for %s — integration stays configurable: %s",
            entry.data["host"],
            err,
        )

    entry_updates = dict(entry.data)
    changed = False
    for key in ("mac_address", "serial_number"):
        value = coordinator.data.get(key)
        if value and entry_updates.get(key) != value:
            entry_updates[key] = value
            changed = True
    if changed:
        hass.config_entries.async_update_entry(entry, data=entry_updates)

    device_key = entry.unique_id or entry.entry_id
    device_info = build_device_info(device_key, entry.data["host"], coordinator.data)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "host": entry.data["host"],
        "port": entry.data.get("port", 80),
        "device_key": device_key,
        "device_info": device_info,
    }

    async def _async_check_connection_service(call: ServiceCall) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for eid, info in hass.data.get(DOMAIN, {}).items():
            sensor = info.get("connectivity_sensor")
            if sensor is not None:
                res = await sensor.async_check_connection()
            else:
                res = await info["api"].check_connection()
            results[info["host"]] = res
            _LOGGER.info("Connectivity check for %s: %s", info["host"], res)
        return results

    if not hass.services.has_service(DOMAIN, "check_connection"):
        hass.services.async_register(
            DOMAIN, "check_connection", _async_check_connection_service, supports_response=True
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN] and hass.services.has_service(DOMAIN, "check_connection"):
            hass.services.async_remove(DOMAIN, "check_connection")
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data is None:
        return

    previous_options = dict(data["coordinator"].options)
    new_options = dict(entry.options)
    coordinator: OFoehnCoordinator = data["coordinator"]

    reload_needed = previous_options.get(CONF_ENABLE_RAW_SENSORS) != new_options.get(
        CONF_ENABLE_RAW_SENSORS
    )

    coordinator.set_options(new_options)
    coordinator.update_interval = _scan_interval_from_options(new_options)

    if reload_needed:
        await hass.config_entries.async_reload(entry.entry_id)
        return

    await coordinator.async_request_refresh()


def update_device_info(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Refresh stored device info after coordinator data changes."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if data is None:
        return
    data["device_info"] = build_device_info(
        data["device_key"],
        entry.data["host"],
        data["coordinator"].data or {},
    )
