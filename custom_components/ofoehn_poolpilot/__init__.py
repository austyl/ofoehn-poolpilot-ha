from __future__ import annotations

import logging
from datetime import timedelta

from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, PLATFORMS, SCAN_INTERVAL
from .coordinator import OFoehnApi, OFoehnCoordinator

_LOGGER = logging.getLogger(__name__)


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
    )

    coordinator = OFoehnCoordinator(
        hass=hass,
        logger=_LOGGER,
        name="ofoehn_poolpilot",
        api=api,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
        options=entry.options,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "host": entry.data["host"],
        "port": entry.data.get("port", 80),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)