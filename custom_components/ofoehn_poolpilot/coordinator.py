from __future__ import annotations

import html
import logging
import re
from datetime import timedelta
from typing import Any, Optional

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

HTML_TAG_RE = re.compile(r"<[^>]+>")
HTML_LINK_RE = re.compile(r"<a\b[^>]*>(.*?)</a>", re.IGNORECASE | re.DOTALL)
WHITESPACE_RE = re.compile(r"\s+")
DONNEE_RE = re.compile(r"DONNEE(\d+)=(-?\d+(?:[.,]\d+)?)")
FLOAT_RE = re.compile(r"-?\d+(?:[.,]\d+)?")
TEMP_PAIR_RE = re.compile(
    r"(-?\d+(?:[.,]\d+)?)\s*(?:°|&deg;)\s*C\s*\(\s*(-?\d+(?:[.,]\d+)?)\s*(?:°|&deg;)?\s*C?\s*\)",
    re.IGNORECASE,
)


def clean_html_text(raw: str | None) -> str:
    """Convert device HTML-ish payloads to readable plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except (AttributeError, TypeError, ValueError):
        return None


def _normalize_mode(value: str | None) -> str | None:
    text = clean_html_text(value)
    if not text:
        return None
    upper = text.upper()
    if "OFF" in upper:
        return "OFF"
    if "CHAUD" in upper:
        return "CHAUD"
    if "FROID" in upper:
        return "FROID"
    if "AUTO" in upper:
        return "AUTO"
    return text


def _extract_anchor_texts(raw: str) -> list[str]:
    values: list[str] = []
    for match in HTML_LINK_RE.finditer(raw or ""):
        text = clean_html_text(match.group(1))
        if text:
            values.append(text)
    return values

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

    def _url(self, path: str, query: dict[str, Any] | None = None) -> str:
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

    async def _fetch(self, method: str, path: str, *, data: Any | None = None, query: dict[str, Any] | None = None) -> str:
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


def parse_accueil_html(raw: str) -> dict[str, Any]:
    plain = clean_html_text(raw)
    result: dict[str, Any] = {}

    patterns = {
        "mode": r"\bMode\s*:\s*(.+?)(?=\s+Mode de régulation\s*:|\s+Pompe\s*:|\s+Prochaine action\s*:|\s+État général\s*:|\s+Etat général\s*:|$)",
        "reg_mode": r"\b(?:Mode de régulation|Régulation)\s*:\s*(.+?)(?=\s+Pompe\s*:|\s+Prochaine action\s*:|\s+État général\s*:|\s+Etat général\s*:|$)",
        "pump": r"\bPompe\s*:\s*(.+?)(?=\s+Chauffage\s*:|\s+Prochaine action\s*:|\s+État général\s*:|\s+Etat général\s*:|$)",
        "heat": r"\bChauffage\s*:\s*(.+?)(?=\s+Prochaine action\s*:|\s+État général\s*:|\s+Etat général\s*:|$)",
        "next_action": r"\bProchaine action\s*:\s*(.+?)(?=\s+État général\s*:|\s+Etat général\s*:|\s+Température air\s*:|\s+Tension\s*:|\s+Horloge\s*:|$)",
        "general_state": r"\b(?:État général|Etat général)\s*:\s*(.+?)(?=\s+Température air\s*:|\s+Tension\s*:|\s+Horloge\s*:|$)",
        "delta_setpoint": r"\bÉcart consigne\s*:\s*(-?[0-9.,]+)",
        "air_temp": r"\bTempérature air\s*:\s*(-?[0-9.,]+)",
        "voltage": r"\bTension\s*:\s*(-?[0-9.,]+)",
        "internal_temp": r"\bTempérature interne\s*:\s*(-?[0-9.,]+)",
        "clock": r"\bHorloge\s*:\s*(.+)$",
    }

    for key, pattern in patterns.items():
        m = re.search(pattern, plain, re.IGNORECASE)
        if not m:
            continue
        value = m.group(1).strip()
        if key in {"delta_setpoint", "air_temp", "voltage", "internal_temp"}:
            try:
                result[key] = float(value.replace(",", "."))
            except (TypeError, ValueError):
                _LOGGER.debug("Error parsing %s from accueil HTML: %s", key, value)
        else:
            result[key] = value

    if not result.get("mode"):
        result["mode"] = _normalize_mode(plain)

    anchor_texts = _extract_anchor_texts(raw)
    if anchor_texts:
        if not result.get("mode"):
            for value in anchor_texts:
                normalized_mode = _normalize_mode(value)
                if normalized_mode in {"CHAUD", "FROID", "AUTO", "OFF"}:
                    result["mode"] = normalized_mode
                    break
        if not result.get("reg_mode") and len(anchor_texts) > 1:
            result["reg_mode"] = anchor_texts[1]

    match = TEMP_PAIR_RE.search(raw) or TEMP_PAIR_RE.search(plain)
    if match:
        water_in = _to_float(match.group(1))
        setpoint = _to_float(match.group(2))
        if water_in is not None:
            result["water_in"] = water_in
        if setpoint is not None:
            result["setpoint"] = setpoint
        if water_in is None or setpoint is None:
            _LOGGER.debug("Error parsing water values from accueil HTML: %s", raw)

    if not result.get("general_state"):
        state_matches = re.findall(r"\b(ON|OFF)\b", plain, re.IGNORECASE)
        if state_matches:
            result["general_state"] = state_matches[-1].upper()

    if not result.get("next_action"):
        next_action_match = re.search(
            r"\b(Aucune|Aucun|Arrêté|Arrete|Arrêt|Arret|Non \(Automne\))\b",
            plain,
            re.IGNORECASE,
        )
        if next_action_match:
            result["next_action"] = next_action_match.group(1)

    if not result:
        _LOGGER.debug("Failed to parse accueil HTML: %s", raw)
    return result


def parse_donnees(raw: str) -> dict[int, float]:
    out: dict[int, float] = {}
    for m in DONNEE_RE.finditer(raw):
        try:
            out[int(m.group(1))] = float(m.group(2).replace(",", "."))
        except (TypeError, ValueError):
            _LOGGER.debug("Error parsing donnees entry: %s", m.group(0))
            continue
    if not out:
        _LOGGER.debug("No donnees parsed from: %s", raw)
    return out


def parse_reg(raw: str) -> dict[str, Any]:
    line = clean_html_text(raw).split("\n", 1)[0]
    parts = [p.strip() for p in re.split(r"[;,]", line) if p.strip()]
    setpoint = None
    if parts:
        setpoint = _to_float(parts[0])
        if setpoint is None and FLOAT_RE.match(parts[0]):
            _LOGGER.debug("Failed to parse setpoint from reg: %s", raw)

    mode = None
    if len(parts) > 1:
        mode = _normalize_mode(parts[1])
    if mode is None:
        mode = _normalize_mode(line)

    regulation = parts[2] if len(parts) > 2 else None
    next_action = parts[3] if len(parts) > 3 else None
    status = parts[4] if len(parts) > 4 else None
    return {
        "setpoint": setpoint,
        "mode": mode,
        "regulation": regulation,
        "next_action": next_action,
        "status": status,
        "raw": raw,
    }


class OFoehnCoordinator(DataUpdateCoordinator[dict]):
    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        name: str,
        api: OFoehnApi,
        update_interval: timedelta,
        options: dict[str, Any] | None,
    ) -> None:
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
            **parsed_accueil,
            "indices": {
                "water_in_idx": self.options.get("water_in_idx", DEFAULT_INDEX["water_in_idx"]),
                "water_out_idx": self.options.get("water_out_idx", DEFAULT_INDEX["water_out_idx"]),
                "air_idx": self.options.get("air_idx", DEFAULT_INDEX["air_idx"]),
                "voltage_idx": self.options.get("voltage_idx", DEFAULT_INDEX["voltage_idx"]),
                "internal_idx": self.options.get("internal_idx", DEFAULT_INDEX["internal_idx"]),
                "pump_idx": self.options.get("pump_idx", DEFAULT_INDEX["pump_idx"]),
                "heating_idx": self.options.get("heating_idx", DEFAULT_INDEX["heating_idx"]),
                "light_idx": self.options.get("light_idx", DEFAULT_INDEX["light_idx"]),
                "power_idx": self.options.get("power_idx", DEFAULT_INDEX["power_idx"]),
            }
        }
