from __future__ import annotations

import re
from typing import Any, Dict

from aiohttp import ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from .const import ENDPOINTS, DEFAULT_INDEX

class OFoehnApi:
    def __init__(self, host: str, port: int, session: ClientSession) -> None:
        self._base = f"http://{host}:{port}"
        self._session = session

    async def _get(self, path: str) -> str:
        async with self._session.get(self._base + path, timeout=10) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def _post(self, path: str, data: Any | None = None) -> str:
        async with self._session.post(self._base + path, data=data or {}, timeout=10) as resp:
            resp.raise_for_status()
            return await resp.text()

    # Reads
    async def read_super(self) -> str:
        return await self._get(ENDPOINTS["super"])

    async def read_accueil(self) -> str:
        return await self._get(ENDPOINTS["accueil"])

    async def read_reg(self) -> str:
        return await self._get(ENDPOINTS["reg_get"])

    # Writes
    async def set_mode(self, mode: str) -> None:
        await self._post(ENDPOINTS["reg_set"], {"mode": mode})

    async def set_setpoint(self, temp: float) -> None:
        t = f"{temp:.1f}"
        data = {"consigneFroid": t, "consigneChaud": t, "consigneAuto": t}
        await self._post(ENDPOINTS["reg_set"], data)

    async def toggle_power(self) -> None:
        await self._get(ENDPOINTS["toggle"])

    async def set_light(self, on: bool) -> None:
        payload = "1" if on else "0"
        await self._post(ENDPOINTS["light"], payload)


def parse_donnees(raw: str) -> Dict[int, float]:
    # Extract DONNEE<idx>=<number> from raw text
    out: Dict[int, float] = {}
    for m in re.finditer(r"DONNEE(\d+)=([0-9.]+)", raw):
        try:
            out[int(m.group(1))] = float(m.group(2))
        except Exception:
            continue
    return out


def parse_reg(raw: str) -> Dict[str, Any]:
    # Heuristic: first line, first comma-separated value is setpoint
    # Mode appears as CHAUD/FROID/AUTO in line
    line = raw.split("\n", 1)[0]
    setpoint = None
    try:
        setpoint = float(line.split(",", 1)[0])
    except Exception:
        pass
    mode = "AUTO"
    if "CHAUD" in line.upper():
        mode = "CHAUD"
    elif "FROID" in line.upper():
        mode = "FROID"
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
        return {
            "super_raw": sup,
            "accueil_raw": acc,
            "reg_raw": reg,
            "super": parse_donnees(sup),
            "accueil": parse_donnees(acc),
            "reg": parse_reg(reg),
            "indices": {
                "water_in_idx": self.options.get("water_in_idx", DEFAULT_INDEX["water_in_idx"]),
                "water_out_idx": self.options.get("water_out_idx", DEFAULT_INDEX["water_out_idx"]),
                "air_idx": self.options.get("air_idx", DEFAULT_INDEX["air_idx"]),
                "light_idx": self.options.get("light_idx", DEFAULT_INDEX["light_idx"]),
                "power_idx": self.options.get("power_idx", DEFAULT_INDEX["power_idx"]),
            }
        }