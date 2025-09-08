from __future__ import annotations

import logging
import re
import html
from typing import Any, Dict, Optional

from aiohttp import BasicAuth, ClientResponseError, ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import (
    AUTH_BASIC,
    AUTH_COOKIE,
    AUTH_NONE,
    AUTH_QUERY,
    DEFAULT_INDEX,
    DEFAULT_TIMEOUT,
    ENDPOINTS,
)

_LOGGER = logging.getLogger(__name__)

class OFoehnApi:
    def __init__(
        self,
        host: str,
        port: int,
        session: ClientSession,
        auth_mode: str = AUTH_NONE,
        username: Optional[str] = None,
        password: Optional[str] = None,
        login_path: str = "/login.cgi",
        login_method: str = "POST",
        user_field: str = "user",
        pass_field: str = "pass",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._base = f"http://{host}:{port}"
        self._session = session
        self._auth_mode = auth_mode
        self._username = username
        self._password = password
        self._login_path = login_path
        self._login_method = login_method.upper()
        self._user_field = user_field
        self._pass_field = pass_field
        self._basic_auth = BasicAuth(username, password) if (auth_mode == AUTH_BASIC and username) else None
        self._timeout = timeout

    def _url(self, path: str, query: Dict[str, Any] | None = None) -> str:
        url = self._base + path
        if self._auth_mode == AUTH_QUERY and self._username and self._password:
            q = query.copy() if query else {}
            q[self._user_field] = self._username
            q[self._pass_field] = self._password
            from urllib.parse import urlencode
            sep = "&" if "?" in url else "?"
            url = url + sep + urlencode(q)
        elif query:
            from urllib.parse import urlencode
            sep = "&" if "?" in url else "?"
            url = url + sep + urlencode(query)
        return url

    async def _maybe_login(self) -> None:
        if self._auth_mode != AUTH_COOKIE:
            return
        data = {self._user_field: self._username or "", self._pass_field: self._password or ""}
        url = self._base + self._login_path
        if self._login_method == "GET":
            async with self._session.get(url, params=data, timeout=self._timeout) as resp:
                resp.raise_for_status()
        else:
            async with self._session.post(url, data=data, timeout=self._timeout) as resp:
                resp.raise_for_status()

    async def _fetch(self, method: str, path: str, *, data: Any | None = None, query: Dict[str, Any] | None = None) -> str:
        url = self._url(path, query=query)
        try:
            if method == "GET":
                async with self._session.get(url, timeout=self._timeout, auth=self._basic_auth) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            else:
                if self._auth_mode == AUTH_QUERY and self._username and self._password:
                    if isinstance(data, dict) or data is None:
                        data = data.copy() if data else {}
                        data[self._user_field] = self._username
                        data[self._pass_field] = self._password
                async with self._session.post(url, data=data or {}, timeout=self._timeout, auth=self._basic_auth) as resp:
                    resp.raise_for_status()
                    return await resp.text()
        except ClientResponseError as e:
            if e.status in (401, 403) and self._auth_mode == AUTH_COOKIE:
                await self._maybe_login()
                if method == "GET":
                    async with self._session.get(url, timeout=self._timeout) as resp2:
                        resp2.raise_for_status()
                        return await resp2.text()
                else:
                    async with self._session.post(url, data=data or {}, timeout=self._timeout) as resp2:
                        resp2.raise_for_status()
                        return await resp2.text()
            raise

    # Reads
    async def read_super(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["super"])

    async def read_accueil(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["accueil"])

    async def read_reg(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["reg_get"])

    # Writes
    async def set_mode(self, mode: str) -> None:
        await self._fetch("POST", ENDPOINTS["reg_set"], data={"mode": mode})

    async def set_setpoint(self, temp: float) -> None:
        t = f"{temp:.1f}"
        data = {"consigneFroid": t, "consigneChaud": t, "consigneAuto": t}
        await self._fetch("POST", ENDPOINTS["reg_set"], data=data)

    async def toggle_power(self) -> None:
        await self._fetch("GET", ENDPOINTS["toggle"])

    async def set_light(self, on: bool) -> None:
        payload = "1" if on else "0"
        await self._fetch("POST", ENDPOINTS["light"], data=payload)

    async def check_connection(self) -> bool:
        """Perform a lightweight request to verify connectivity."""
        try:
            await self.read_super()
            return True
        except Exception:
            return False


def parse_accueil_html(raw: str) -> Dict[str, Any]:
    raw = html.unescape(raw)
    result: Dict[str, Any] = {}

    patterns = {
        "mode": r"Mode\s*:\s*([^<]+)",
        "reg_mode": r"Mode de régulation\s*:\s*([^<]+)",
        "pump": r"Pompe\s*:\s*([^<]+)",
        "heat": r"Chauffage\s*:\s*([^<]+)",
        "next_action": r"Prochaine action\s*:\s*([^<]+)",
        "general_state": r"État général\s*:\s*([^<]+)",
        "delta_setpoint": r"Écart consigne\s*:\s*([0-9.,]+)",
        "air_temp": r"Température air\s*:\s*([0-9.,]+)",
        "voltage": r"Tension\s*:\s*([0-9.,]+)",
        "internal_temp": r"Température interne\s*:\s*([0-9.,]+)",
        "clock": r"Horloge\s*:\s*([^<]+)",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, raw, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip()
        if key in {"delta_setpoint", "air_temp", "voltage", "internal_temp"}:
            try:
                result[key] = float(value.replace(',', '.'))
            except Exception:
                _LOGGER.debug("Error parsing %s from accueil HTML: %s", key, value)
        else:
            result[key] = value

    match = re.search(r"Chaud\s+([\d.,]+)°C.*?\(([\d.,]+)°C\)", raw, re.IGNORECASE)
    if match:
        try:
            result["water_in"] = float(match.group(1).replace(',', '.'))
            result["setpoint"] = float(match.group(2).replace(',', '.'))
        except Exception:
            _LOGGER.debug("Error parsing water values from accueil HTML: %s", raw)

    if not result:
        _LOGGER.debug("Failed to parse accueil HTML: %s", raw)
    return result


def parse_donnees(raw: str) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for m in re.finditer(r"DONNEE(\d+)=([0-9.]+)", raw):
        try:
            out[int(m.group(1))] = float(m.group(2))
        except Exception:
            _LOGGER.debug("Error parsing donnees entry: %s", m.group(0))
            continue
    if not out:
        _LOGGER.debug("No donnees parsed from: %s", raw)
    return out


def parse_reg(raw: str) -> Dict[str, Any]:
    line = raw.split("\n", 1)[0]
    setpoint = None
    try:
        setpoint = float(line.split(",", 1)[0])
    except Exception:
        _LOGGER.debug("Failed to parse setpoint from reg: %s", raw)
    mode = "AUTO"
    if "CHAUD" in line.upper():
        mode = "CHAUD"
    elif "FROID" in line.upper():
        mode = "FROID"
    else:
        _LOGGER.debug("Failed to determine mode from reg: %s", raw)
    return {"setpoint": setpoint, "mode": mode, "raw": raw}


class OFoehnCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, logger, name: str, api: OFoehnApi, update_interval, options) -> None:
        super().__init__(hass, logger, name=name, update_interval=update_interval)
        self.api = api
        self.options = options or {}

    async def _async_update_data(self) -> dict:
        sup = await self.api.read_super()
        acc = await self.api.read_accueil()
        reg = await self.api.read_reg()
        self.logger.debug("super_raw: %s", sup)
        self.logger.debug("accueil_raw: %s", acc)
        self.logger.debug("reg_raw: %s", reg)
        parsed_accueil = parse_accueil_html(acc)
        return {
            "super_raw": sup,
            "accueil_raw": acc,
            "reg_raw": reg,
            "super": parse_donnees(sup),
            "accueil": parse_donnees(acc),
            "reg": parse_reg(reg),
            "water_in": parsed_accueil.get("water_in"),
            "setpoint": parsed_accueil.get("setpoint"),
            "indices": {
                "water_in_idx": self.options.get("water_in_idx", DEFAULT_INDEX["water_in_idx"]),
                "water_out_idx": self.options.get("water_out_idx", DEFAULT_INDEX["water_out_idx"]),
                "air_idx": self.options.get("air_idx", DEFAULT_INDEX["air_idx"]),
                "light_idx": self.options.get("light_idx", DEFAULT_INDEX["light_idx"]),
                "power_idx": self.options.get("power_idx", DEFAULT_INDEX["power_idx"]),
            }
        }
