from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, Optional

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AUTH_BASIC, AUTH_COOKIE, AUTH_NONE, AUTH_QUERY, DEFAULT_INDEX, ENDPOINTS

DONNEE_RE = re.compile(r"DONNEE(\d+)=(-?\d+(?:[.,]\d+)?)")
REG_VALUE_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


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
        self._basic_auth = (
            BasicAuth(username, password)
            if auth_mode == AUTH_BASIC and username and password
            else None
        )
        self._cookie_authenticated = auth_mode != AUTH_COOKIE
        self._auth_lock = asyncio.Lock()

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

    async def _perform_request(
        self, method: str, url: str, *, data: Any | None = None
    ) -> str:
        if method == "GET":
            async with self._session.get(
                url, timeout=10, auth=self._basic_auth
            ) as resp:
                resp.raise_for_status()
                return await resp.text()

        async with self._session.post(
            url, data=data or {}, timeout=10, auth=self._basic_auth
        ) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _maybe_login(self, *, force: bool = False) -> None:
        if self._auth_mode != AUTH_COOKIE:
            return
        if self._cookie_authenticated and not force:
            return

        async with self._auth_lock:
            if self._cookie_authenticated and not force:
                return

            data = {
                self._user_field: self._username or "",
                self._pass_field: self._password or "",
            }
            url = self._base + self._login_path
            if self._login_method == "GET":
                async with self._session.get(url, params=data, timeout=10) as resp:
                    resp.raise_for_status()
            else:
                async with self._session.post(url, data=data, timeout=10) as resp:
                    resp.raise_for_status()
            self._cookie_authenticated = True

    async def _fetch(
        self,
        method: str,
        path: str,
        *,
        data: Any | None = None,
        query: Dict[str, Any] | None = None,
    ) -> str:
        url = self._url(path, query=query)
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()

        try:
            if self._auth_mode == AUTH_QUERY and self._username and self._password:
                if isinstance(data, dict) or data is None:
                    data = data.copy() if data else {}
                    data[self._user_field] = self._username
                    data[self._pass_field] = self._password

            return await self._perform_request(method, url, data=data)
        except ClientResponseError as err:
            if err.status in (401, 403) and self._auth_mode == AUTH_COOKIE:
                self._cookie_authenticated = False
                await self._maybe_login(force=True)
                return await self._perform_request(method, url, data=data)
            raise

    # Reads
    async def read_super(self) -> str:
        return await self._fetch("GET", ENDPOINTS["super"])

    async def read_accueil(self) -> str:
        return await self._fetch("GET", ENDPOINTS["accueil"])

    async def read_reg(self) -> str:
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


def parse_donnees(raw: str) -> Dict[int, float]:
    out: Dict[int, float] = {}
    for match in DONNEE_RE.finditer(raw):
        try:
            out[int(match.group(1))] = float(match.group(2).replace(",", "."))
        except (TypeError, ValueError):
            continue
    return out


def parse_reg(raw: str) -> Dict[str, Any]:
    line = raw.strip().split("\n", 1)[0] if raw else ""
    setpoint = None
    value_match = REG_VALUE_RE.search(line)
    if value_match:
        try:
            setpoint = float(value_match.group(0).replace(",", "."))
        except (TypeError, ValueError):
            setpoint = None

    mode = "AUTO"
    upper_line = line.upper()
    if "OFF" in upper_line or "ARRET" in upper_line or "ARRÊT" in upper_line:
        mode = "OFF"
    elif "CHAUD" in upper_line:
        mode = "CHAUD"
    elif "FROID" in upper_line:
        mode = "FROID"
    return {"setpoint": setpoint, "mode": mode, "raw": raw}


class OFoehnCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, logger, name: str, api: OFoehnApi, update_interval, options) -> None:
        super().__init__(hass, logger, name=name, update_interval=update_interval)
        self.api = api
        self.options = options or {}

    async def _async_update_data(self) -> dict:
        try:
            sup, acc, reg = await asyncio.gather(
                self.api.read_super(),
                self.api.read_accueil(),
                self.api.read_reg(),
            )
        except (ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error while updating device: {err}") from err

        return {
            "super_raw": sup,
            "accueil_raw": acc,
            "reg_raw": reg,
            "super": parse_donnees(sup),
            "accueil": parse_donnees(acc),
            "reg": parse_reg(reg),
            "indices": {
                "water_in_idx": int(
                    self.options.get("water_in_idx", DEFAULT_INDEX["water_in_idx"])
                ),
                "water_out_idx": int(
                    self.options.get("water_out_idx", DEFAULT_INDEX["water_out_idx"])
                ),
                "air_idx": int(self.options.get("air_idx", DEFAULT_INDEX["air_idx"])),
                "light_idx": int(
                    self.options.get("light_idx", DEFAULT_INDEX["light_idx"])
                ),
                "power_idx": int(
                    self.options.get("power_idx", DEFAULT_INDEX["power_idx"])
                ),
            },
        }
