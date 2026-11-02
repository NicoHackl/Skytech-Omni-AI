"""Geschützte, direkte Claude-Verbrauchsabfrage ohne Modellaufruf (D-037).

Die interne Schnittstelle ist keine zugesicherte API. Nur normalisierte Fenster
werden gespeichert, niemals Zugangsdaten oder die rohe Antwort. Auch Pausen
bleiben nach einem Neustart erhalten; sie sind keine Kontingent-Wartezeiten.
"""

import hashlib
import http.client
import json
import logging
import math
import threading
import urllib.error
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from providers.google_accounts import write_json

log = logging.getLogger("omniai.claude_usage")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
CACHE_SECONDS = 300
MAX_BACKOFF_SECONDS = 3600
REQUEST_TIMEOUT = 8
MAX_RESPONSE_BYTES = 65536
_LOCK = threading.Lock()
_memory: dict = {}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Der Bearer-Zugang darf niemals an ein Umleitungsziel gelangen.
        return None


def _fetch_usage(token: str) -> object:
    request = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
            "User-Agent": "Skytech-OmniAI",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError("Verbrauchsantwort zu groß")
    return json.loads(body)


def _finite(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _windows(payload: object, names: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("Verbrauchsantwort ist kein Objekt")
    windows = []
    for name in names:
        item = payload.get(name)
        if not isinstance(item, dict):
            continue
        used = _finite(item.get("utilization"))
        reset = item.get("resets_at")
        if used is None or not 0 <= used <= 100:
            continue
        if reset is None:
            windows.append({"id": name, "usedPercent": used, "resetsAtEpoch": None})
            continue
        if not isinstance(reset, str):
            continue
        try:
            parsed = datetime.fromisoformat(reset.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                continue
            epoch = parsed.timestamp()
        except (ValueError, OverflowError):
            continue
        if math.isfinite(epoch) and epoch > 0:
            windows.append({"id": name, "usedPercent": used, "resetsAtEpoch": epoch})
    if not windows:
        raise ValueError("Keine gültigen Verbrauchsfenster")
    return windows


def _retry_delay(value: str | None, now: float) -> float:
    if not value:
        return 0
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - now
        except (ValueError, TypeError, OverflowError):
            return 0
    return max(0, seconds) if math.isfinite(seconds) else 0


def _save(path: Path, state: dict) -> None:
    _memory[str(path)] = state
    try:
        write_json(path, state)
    except OSError:
        log.warning("Claude-Verbrauch und Abfragepause nur im Arbeitsspeicher gesichert")


def query_usage(token: str, directory: Path, names: dict, now: float) -> dict | None:
    """Liefert den letzten Messstand; fragt frühestens nach Ablauf der Pause neu ab.

    ``token`` kommt ausschließlich aus der Umgebung des Aufrufers. Ein Wechsel
    verwirft den alten Cache. ``names`` begrenzt die übernommenen Fenster.
    Netzfehler lassen den bisherigen Messzeitpunkt unverändert.
    """
    if not token:
        return None
    fingerprint = hashlib.sha256(token.encode()).hexdigest()
    path = directory / "claude_usage.json"
    with _LOCK:
        state = _memory.get(str(path))
        if state is None:
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                state = {}
            except (OSError, ValueError):
                log.warning("Gespeicherte Claude-Verbrauchsabfrage unlesbar")
                state = {}
        if not isinstance(state, dict) or state.get("fingerprint") != fingerprint:
            state = {"fingerprint": fingerprint}
        measurement = state.get("measurement")
        if measurement is not None:
            # Die Ablage kann beschädigt oder von einer anderen Fassung sein.
            # Nur bekannte, vollständig normalisierte Werte wiederverwenden.
            valid = isinstance(measurement, dict) and _finite(measurement.get("at")) is not None
            items = measurement.get("windows") if valid else None
            valid = valid and isinstance(items, list) and bool(items)
            if valid:
                valid = all(
                    isinstance(w, dict)
                    and isinstance(w.get("id"), str)
                    and w["id"] in names
                    and _finite(w.get("usedPercent")) is not None
                    and 0 <= w["usedPercent"] <= 100
                    and (
                        w.get("resetsAtEpoch") is None
                        or (_finite(w.get("resetsAtEpoch")) is not None and w["resetsAtEpoch"] > 0)
                    )
                    for w in items
                )
            if not valid:
                state.pop("measurement", None)
                log.warning("Gespeicherter Claude-Messstand ungültig; verwende CLI-Beobachtung")
        next_attempt = _finite(state.get("nextAttempt")) or 0
        if now < next_attempt:
            return state.get("measurement")

        # Vor dem Netzaufruf sichern: auch ein Prozessabbruch darf keine Serie
        # sofortiger Wiederholungen beim Neustart erzeugen.
        state["nextAttempt"] = now + CACHE_SECONDS
        _save(path, state)
        failures = _finite(state.get("failures")) or 0
        failures = min(max(int(failures), 0) + 1, 5)
        delay = min(CACHE_SECONDS * 2 ** (failures - 1), MAX_BACKOFF_SECONDS)
        try:
            windows = _windows(_fetch_usage(token), names)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403):
                delay = MAX_BACKOFF_SECONDS
            delay = max(delay, _retry_delay((error.headers or {}).get("Retry-After"), now))
            # Keine Ausnahme-Rohtexte: Header und Antwort können Zugangsdaten
            # oder Kontodaten enthalten. Der Status genügt zur Diagnose.
            log.warning("Claude-Verbrauchsabfrage abgelehnt (Status %s)", error.code)
            error.close()
        except (OSError, ValueError, urllib.error.URLError, http.client.HTTPException):
            log.warning("Claude-Verbrauchsabfrage fehlgeschlagen; letzter Stand bleibt erhalten")
        else:
            state.update(measurement={"at": now, "windows": windows}, failures=0)
            _save(path, state)
            return state["measurement"]
        state.update(failures=failures, nextAttempt=now + delay)
        _save(path, state)
        return state.get("measurement")
