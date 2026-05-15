from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import timedelta
from typing import Any, Optional

from aiohttp import BasicAuth, ClientError, ClientResponseError, ClientSession
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
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
FIRMWARE_RE = re.compile(r"Version\s+V?([0-9.]+)", re.IGNORECASE)
ACCUEIL_COMPACT_RE = re.compile(
    r"(?P<mode>Chaud|Froid|Auto|OFF)\s+"
    r"(?P<water_in>-?\d+(?:[.,]\d+)?)°C\s*\(\s*(?P<setpoint>-?\d+(?:[.,]\d+)?)°C\s*\)\s+"
    r"(?P<regulation>.+?)\s+"
    r"(?P<season_stop>Non\s*\(Automne\)|Oui\s*\(Automne\)|\S+\s*\([^)]+\)|\S+)\s+"
    r"(?P<pump_state>Non|Oui|OFF|ON)\s+"
    r"(?P<power_state>OFF|ON)\s+"
    r"(?P<stopped_state>Arrêtée|Arretee|Marche|En marche|Stopped|\S+)\s+"
    r"(?P<next_action>Aucune|Aucun|\S+)\s+"
    r"(?P<general_state>Normal|Défaut|Defaut|Alarme|Alarm|\S+)\s+"
    r"(?P<delta>-?\d+(?:[.,]\d+)?)°C\s+"
    r"(?P<air_temp>-?\d+(?:[.,]\d+)?)°C\s+"
    r"(?P<pressure_1>-?\d+(?:[.,]\d+)?)\s+"
    r"(?P<pressure_2>-?\d+(?:[.,]\d+)?)\s+"
    r"(?P<serial_number>\d{8,})\s+"
    r"(?P<module_name>[A-Za-z][\w-]+)\s+"
    r"(?P<timer_count>\d+)\s+TIMER\(s\)\s*:\s*(?P<timer_status>[A-Za-zéû]+)\s+"
    r"(?P<device_date>\d{2}/\d{2}/\d{4})\s+(?P<device_time>\d{2}:\d{2}:\d{2})\s+"
    r"(?P<mac_address>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s+"
    r"(?P<module_build>\S+)\s+"
    r"(?P<module_version>[0-9]+(?:[.,][0-9]+)?)\s+"
    r"(?P<option_1>En option|\S+)\s+"
    r"(?P<option_2>En option|\S+)\s+"
    r"(?P<signal_level>-?\d+)\s+"
    r"(?P<voltage>-?\d+(?:[.,]\d+)?)V\s+"
    r"(?P<internal_temp>-?\d+(?:[.,]\d+)?)°C\s+"
    r"(?P<config_code>\S+)\s+"
    r"(?P<hardware_code>\S+)",
    re.IGNORECASE,
)
TEMP_PAIR_RE = re.compile(
    r"(-?\d+(?:[.,]\d+)?)\s*(?:°|&deg;)\s*C\s*\(\s*(-?\d+(?:[.,]\d+)?)\s*(?:°|&deg;)?\s*C?\s*\)",
    re.IGNORECASE,
)

READ_RETRIES = 0
READ_RETRY_DELAY = 0.75
INTER_REQUEST_DELAY = 0.25
RETRYABLE_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}


def clean_html_text(raw: str | None) -> str:
    """Convert device HTML-ish payloads to readable plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = text.replace("\xa0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def clean_html_lines(raw: str | None) -> list[str]:
    """Return cleaned non-empty lines from a device payload."""
    if not raw:
        return []
    lines = [clean_html_text(line) for line in raw.splitlines()]
    return [line for line in lines if line]


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value.replace(",", "."))
    except (AttributeError, TypeError, ValueError):
        return None


def _extract_float(value: str | None) -> float | None:
    if not value:
        return None
    match = FLOAT_RE.search(value)
    if not match:
        return None
    return _to_float(match.group(0))


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
    return None


def _extract_anchor_texts(raw: str) -> list[str]:
    values: list[str] = []
    for match in HTML_LINK_RE.finditer(raw or ""):
        text = clean_html_text(match.group(1))
        if text:
            values.append(text)
    return values


def _is_enabled_text(value: str | None) -> bool | None:
    text = clean_html_text(value)
    if not text:
        return None
    upper = text.upper()
    if upper in {"ON", "OK", "1"}:
        return True
    if upper in {"OFF", "0"}:
        return False
    return None


def parse_page_metadata(raw: str) -> dict[str, Any]:
    """Extract metadata when a payload contains an HTML page."""
    if not raw or "<html" not in raw.lower():
        return {}

    result: dict[str, Any] = {}
    firmware_match = FIRMWARE_RE.search(raw)
    if firmware_match:
        result["firmware_version"] = f"V{firmware_match.group(1)}"
    return result


def parse_accueil_values(raw: str) -> dict[str, Any]:
    """Parse the line-oriented accueil.cgi payload."""
    lines = clean_html_lines(raw)
    if len(lines) < 10:
        return {}

    def text_at(index: int) -> str | None:
        return lines[index] if index < len(lines) else None

    result: dict[str, Any] = {}

    result["mode"] = _normalize_mode(text_at(0))

    temp_pair = text_at(1)
    if temp_pair:
        match = TEMP_PAIR_RE.search(temp_pair)
        if match:
            result["water_in"] = _to_float(match.group(1))
            result["setpoint"] = _to_float(match.group(2))

    result["reg_mode"] = text_at(2)
    result["season_stop"] = text_at(3)
    result["heat_state"] = text_at(4)
    result["pump_state"] = text_at(5)
    result["pump_on"] = _is_enabled_text(text_at(5))
    result["stopped_state"] = text_at(6)
    result["next_action"] = text_at(7)
    result["general_state"] = text_at(8)
    result["delta"] = _extract_float(text_at(9))
    result["air_temp"] = _extract_float(text_at(10))
    result["pressure_1"] = _extract_float(text_at(11))
    result["pressure_2"] = _extract_float(text_at(12))
    result["serial_number"] = text_at(13)
    result["module_name"] = text_at(14)

    timer_count = text_at(15)
    timer_status_line = text_at(16)
    timer_status = None
    if timer_status_line and ":" in timer_status_line:
        timer_status = timer_status_line.split(":", 1)[1].strip()
    result["timers_summary"] = (
        f"{timer_count} actifs ({timer_status})"
        if timer_count and timer_status
        else timer_status_line
    )

    device_date = text_at(17)
    device_time = text_at(18)
    if device_date and device_time:
        result["clock"] = f"{device_date} {device_time}"

    result["mac_address"] = text_at(19)
    result["module_build"] = text_at(20)
    result["module_version"] = text_at(21)
    result["option_1"] = text_at(22)
    result["option_2"] = text_at(23)
    result["signal_level"] = text_at(24)

    voltage_text = text_at(25)
    if voltage_text:
        result["voltage"] = _extract_float(voltage_text)

    result["internal_temp"] = _extract_float(text_at(26))
    result["config_code"] = text_at(27)
    result["hardware_code"] = text_at(28)
    result["ph_license"] = text_at(29)
    return {key: value for key, value in result.items() if value is not None}


def parse_super_values(raw: str) -> dict[str, Any]:
    """Parse the line-oriented payload used by the supervision page."""
    if not raw or "<html" in raw.lower():
        return {}

    lines = [clean_html_text(line) for line in raw.splitlines()]
    lines = [line for line in lines if line]
    if len(lines) < 24:
        return {}

    def text_at(index: int) -> str | None:
        return lines[index] if index < len(lines) else None

    def float_at(index: int) -> float | None:
        value = text_at(index)
        if not value:
            return None
        match = FLOAT_RE.search(value)
        if not match:
            return None
        return _to_float(match.group(0))

    webuser_type = text_at(22)
    ev_raw = text_at(24)

    return {
        "contact_bp1": text_at(0),
        "contact_bp2": text_at(1),
        "contact_hp1": text_at(2),
        "contact_hp2": text_at(3),
        "balneo_state": text_at(4),
        "water_in": float_at(5),
        "water_out": float_at(6),
        "air_temp": float_at(7),
        "compressor_1_temp": float_at(8),
        "battery_1_temp": float_at(9),
        "compressor_2_temp": float_at(10),
        "battery_2_temp": float_at(11),
        "pressure_1": float_at(12),
        "pressure_2": float_at(13),
        "chlorine_state": text_at(14),
        "ph_state": text_at(15),
        "pump_state": text_at(16),
        "pump_on": _is_enabled_text(text_at(16)),
        "fan_state": text_at(17),
        "valve_1_state": text_at(18),
        "compressor_1_state": text_at(19),
        "compressor_1_on": _is_enabled_text(text_at(19)),
        "valve_2_state": text_at(20),
        "compressor_2_state": text_at(21),
        "compressor_2_on": _is_enabled_text(text_at(21)),
        "webuser_type": webuser_type,
        "webuser_role": (
            "Utilisateur"
            if webuser_type == "0"
            else "Installateur/Admin"
            if webuser_type
            else None
        ),
        "power_state": text_at(23),
        "power_on": _is_enabled_text(text_at(23)),
        "ev_present": (
            "Oui" if ev_raw == "1" else "Non" if ev_raw is not None else None
        ),
        "ext2_temp": float_at(25),
        "superheat": float_at(26),
        "ev_position": text_at(27),
        "gas_temp": float_at(28),
        "delta": float_at(29),
        "ph_license": text_at(30),
    }

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
        self._cookie_logged_in = False

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

    async def _maybe_login(self, *, force: bool = False) -> None:
        if self._auth_mode != AUTH_COOKIE:
            return
        if self._cookie_logged_in and not force:
            return
        data = {self._user_field: self._username or "", self._pass_field: self._password or ""}
        url = self._base + self._login_path
        try:
            if self._login_method == "GET":
                async with self._session.get(url, params=data, timeout=self._timeout) as resp:
                    resp.raise_for_status()
            else:
                async with self._session.post(url, data=data, timeout=self._timeout) as resp:
                    resp.raise_for_status()
        except Exception:
            self._cookie_logged_in = False
            raise
        self._cookie_logged_in = True

    async def _fetch(
        self,
        method: str,
        path: str,
        *,
        data: Any | None = None,
        query: dict[str, Any] | None = None,
        retries: int = 0,
    ) -> str:
        url = self._url(path, query=query)
        auth_retry_done = False
        attempt = 0

        while attempt <= retries:
            try:
                if method == "GET":
                    async with self._session.get(url, timeout=self._timeout, auth=self._basic_auth) as resp:
                        resp.raise_for_status()
                        return await resp.text()

                payload = data
                if self._auth_mode == AUTH_QUERY and self._username and self._password:
                    if isinstance(payload, dict) or payload is None:
                        payload = payload.copy() if payload else {}
                        payload[self._user_field] = self._username
                        payload[self._pass_field] = self._password
                async with self._session.post(
                    url,
                    data=payload or {},
                    timeout=self._timeout,
                    auth=self._basic_auth,
                ) as resp:
                    resp.raise_for_status()
                    return await resp.text()
            except ClientResponseError as err:
                if err.status in (401, 403) and self._auth_mode == AUTH_COOKIE and not auth_retry_done:
                    self._cookie_logged_in = False
                    await self._maybe_login(force=True)
                    auth_retry_done = True
                    continue
                if method != "GET" or attempt >= retries or err.status not in RETRYABLE_HTTP_STATUSES:
                    raise
                attempt += 1
                delay = READ_RETRY_DELAY * attempt
                _LOGGER.warning(
                    "Read %s failed with HTTP %s, retrying in %.2fs (%s/%s)",
                    path,
                    err.status,
                    delay,
                    attempt,
                    retries,
                )
                await asyncio.sleep(delay)
            except (ClientError, asyncio.TimeoutError, OSError) as err:
                if method != "GET" or attempt >= retries:
                    raise
                attempt += 1
                delay = READ_RETRY_DELAY * attempt
                _LOGGER.warning(
                    "Read %s failed (%s), retrying in %.2fs (%s/%s)",
                    path,
                    err,
                    delay,
                    attempt,
                    retries,
                )
                await asyncio.sleep(delay)

        raise UpdateFailed(f"Unable to read {path}")

    # Reads
    async def read_super(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["super"], retries=READ_RETRIES)

    async def read_accueil(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["accueil"], retries=READ_RETRIES)

    async def read_reg(self) -> str:
        if self._auth_mode == AUTH_COOKIE:
            await self._maybe_login()
        return await self._fetch("GET", ENDPOINTS["reg_get"], retries=READ_RETRIES)

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
    result: dict[str, Any] = parse_accueil_values(raw)

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

    compact_match = ACCUEIL_COMPACT_RE.search(plain)
    if compact_match:
        compact = compact_match.groupdict()

        if not result.get("mode"):
            result["mode"] = _normalize_mode(compact.get("mode"))
        if result.get("water_in") is None:
            result["water_in"] = _to_float(compact.get("water_in"))
        if result.get("setpoint") is None:
            result["setpoint"] = _to_float(compact.get("setpoint"))
        if not result.get("reg_mode"):
            result["reg_mode"] = compact.get("regulation")
        if not result.get("next_action"):
            result["next_action"] = compact.get("next_action")
        if not result.get("general_state"):
            result["general_state"] = compact.get("general_state")

        for key in (
            "air_temp",
            "pressure_1",
            "pressure_2",
            "delta",
            "voltage",
            "internal_temp",
        ):
            if result.get(key) is None:
                result[key] = _to_float(compact.get(key))

        result.setdefault("pump_state", compact.get("pump_state"))
        result.setdefault("stopped_state", compact.get("stopped_state"))
        result.setdefault("season_stop", compact.get("season_stop"))
        result.setdefault("serial_number", compact.get("serial_number"))
        result.setdefault("module_name", compact.get("module_name"))
        result.setdefault(
            "timers_summary",
            f"{compact.get('timer_count')} actifs ({compact.get('timer_status')})"
            if compact.get("timer_count") and compact.get("timer_status")
            else None,
        )
        result.setdefault(
            "clock",
            f"{compact.get('device_date')} {compact.get('device_time')}"
            if compact.get("device_date") and compact.get("device_time")
            else None,
        )
        result.setdefault("mac_address", compact.get("mac_address"))
        result.setdefault("module_build", compact.get("module_build"))
        result.setdefault("module_version", compact.get("module_version"))
        result.setdefault("signal_level", compact.get("signal_level"))
        result.setdefault("config_code", compact.get("config_code"))
        result.setdefault("hardware_code", compact.get("hardware_code"))

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
    lines = clean_html_lines(raw)
    if len(lines) >= 6:
        numeric_values = [_to_float(value) for value in lines[1:5]]
        result = {
            "mode": _normalize_mode(lines[0]),
            "setpoint": numeric_values[1] if len(numeric_values) > 1 else None,
            "regulation": lines[5],
            "raw": raw,
            "values": lines,
        }
        for idx, value in enumerate(numeric_values, start=1):
            if value is not None:
                result[f"reg_value_{idx}"] = value

        if len(lines) > 6:
            result["reg_flag_1"] = lines[6]
        if len(lines) > 7:
            result["reg_flag_2"] = lines[7]
        if len(lines) > 8:
            result["reg_flag_3"] = lines[8]
        if len(lines) > 9:
            result["reg_flag_4"] = lines[9]
        if len(lines) > 10:
            result["reg_flag_5"] = lines[10]
        if len(lines) > 11:
            result["reg_flag_6"] = lines[11]
        return result

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
        "values": parts,
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

    def _build_indices(self) -> dict[str, int]:
        return {
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

    async def _read_with_fallback(
        self,
        *,
        name: str,
        reader,
        previous_raw: str | None,
        required: bool = False,
    ) -> tuple[str, bool, str | None]:
        try:
            return await reader(), False, None
        except Exception as err:
            if previous_raw:
                self.logger.warning(
                    "Read %s failed, reusing the last valid payload: %s",
                    name,
                    err,
                )
                return previous_raw, True, str(err)
            if required:
                raise UpdateFailed(f"Unable to refresh {name}: {err}") from err
            self.logger.warning(
                "Read %s failed with no cached payload available: %s",
                name,
                err,
            )
            return "", True, str(err)

    async def _async_update_data(self) -> dict:
        previous = self.data if isinstance(self.data, dict) else {}

        sup, sup_stale, sup_error = await self._read_with_fallback(
            name="super.cgi",
            reader=self.api.read_super,
            previous_raw=previous.get("super_raw"),
            required=True,
        )
        await asyncio.sleep(INTER_REQUEST_DELAY)
        acc, acc_stale, acc_error = await self._read_with_fallback(
            name="accueil.cgi",
            reader=self.api.read_accueil,
            previous_raw=previous.get("accueil_raw"),
        )
        await asyncio.sleep(INTER_REQUEST_DELAY)
        reg, reg_stale, reg_error = await self._read_with_fallback(
            name="getReg.cgi",
            reader=self.api.read_reg,
            previous_raw=previous.get("reg_raw"),
        )
        self.logger.debug("super_raw: %s", sup)
        self.logger.debug("accueil_raw: %s", acc)
        self.logger.debug("reg_raw: %s", reg)
        page_metadata: dict[str, Any] = {}
        for raw in (sup, acc, reg):
            if not page_metadata:
                page_metadata = parse_page_metadata(raw)
        parsed_super = parse_super_values(sup)
        parsed_accueil = parse_accueil_html(acc)
        return {
            **previous,
            "super_raw": sup,
            "accueil_raw": acc,
            "reg_raw": reg,
            "super": parse_donnees(sup),
            "accueil": parse_donnees(acc),
            "reg": parse_reg(reg),
            "super_stale": sup_stale,
            "accueil_stale": acc_stale,
            "reg_stale": reg_stale,
            "super_error": sup_error,
            "accueil_error": acc_error,
            "reg_error": reg_error,
            **page_metadata,
            **parsed_super,
            **parsed_accueil,
            "indices": self._build_indices(),
        }
