"""Abo-Limits der Anbieter für ``GET /v1/limits`` (Vertrag 1.3.0, D-032).

Jeder Wert nennt seine Herkunft, damit Skytech X gemessene Prozentwerte,
beobachtete Erschöpfung und geschätzte Wartezeiten auseinanderhalten kann:

* **Claude** — die CLI meldet in jedem Lauf ein ``rate_limit_event`` mit
  Fünfstunden- und Wochenfenster. Der letzte Stand wird gespeichert
  (``source: observed``). Ohne Lauf gibt es keinen neuen Wert.
* **Codex** — der App-Server der CLI beantwortet ``account/rateLimits/read``
  ohne Modellaufruf (``source: measured``). Ergebnis kurz zwischengespeichert.
* **Gemini (Web, AGY)** — nur der Zustand der Konten (erschöpft, eingeschränkt,
  Anmeldung nötig) mit der lokal geschätzten Wartezeit
  (``retryAtSource: estimated``); einen Prozentwert liefert Google nicht.
* **Gemini (API-Schlüssel)** — keine Quelle; Verbrauch bleibt unbekannt.

Unbekannt heißt ``usedPercent: null``, nie 0.
"""

import json
import logging
import os
import queue
import subprocess
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from providers import gemini_agy_accounts, gemini_web_accounts
from providers.google_accounts import write_json

log = logging.getLogger("omniai.limits")

DEFAULT_ACCOUNT = "default"

# Fensterlängen der Claude-Fenster; unbekannte Namen bleiben ohne Länge.
CLAUDE_WINDOW_MINUTES = {
    "five_hour": 300,
    "seven_day": 7 * 24 * 60,
    "seven_day_opus": 7 * 24 * 60,
    "seven_day_sonnet": 7 * 24 * 60,
}
CLAUDE_FILE_NAME = "claude_sub.json"

CODEX_CACHE_SECONDS = 60
CODEX_TIMEOUT_SECONDS = 20

_CODEX_LOCK = threading.Lock()
_codex_cache: dict = {"at": 0.0, "entry": None}
_CLAUDE_LOCK = threading.Lock()


def limits_dir() -> Path:
    return Path(os.environ.get("OMNIAI_LIMITS_DIR", "").strip() or "/data/limits")


def iso(timestamp: float | None) -> str | None:
    if not timestamp or timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _account(
    provider: str,
    state: str,
    account_ref: str = DEFAULT_ACCOUNT,
    label: str | None = None,
    windows: list | None = None,
    retry_at: float | None = None,
    retry_source: str | None = None,
    observed_at: float | None = None,
) -> dict:
    return {
        "provider": provider,
        "accountRef": account_ref,
        "label": label or None,
        "state": state,
        "retryAt": iso(retry_at),
        "retryAtSource": retry_source if retry_at else None,
        "observedAt": iso(observed_at),
        "windows": windows or [],
    }


# --- Claude -------------------------------------------------------------------


def record_claude(info: dict | None, now: float | None = None) -> None:
    """Speichert den Stand aus einem ``rate_limit_event`` der Claude-CLI."""
    if not isinstance(info, dict):
        return
    now = time.time() if now is None else now
    windows = []
    for name, window in (info.get("unifiedWindows") or {}).items():
        if not isinstance(window, dict):
            continue
        utilization = _number(window.get("utilization"))
        windows.append(
            {
                "id": str(name)[:40],
                "limitId": None,
                "durationMinutes": CLAUDE_WINDOW_MINUTES.get(name),
                "usedPercent": None if utilization is None else round(utilization * 100, 1),
                "resetsAt": iso(_number(window.get("resetsAt"))),
                "source": "observed",
                "observedAt": iso(now),
            }
        )
    record = {
        "observedAt": now,
        "rejected": info.get("status") == "rejected",
        "resetsAt": _number(info.get("resetsAt")),
        "windows": windows,
    }
    try:
        with _CLAUDE_LOCK:
            write_json(limits_dir() / CLAUDE_FILE_NAME, record)
    except OSError as error:
        log.warning("Limitstand von Claude nicht gespeichert: %s", error)


def claude_entry(available: bool, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not available:
        return _account("claude_sub", "unavailable")
    try:
        record = json.loads((limits_dir() / CLAUDE_FILE_NAME).read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError
    except FileNotFoundError:
        return _account("claude_sub", "unknown")
    except (OSError, ValueError):
        log.warning("Gespeicherter Limitstand von Claude unlesbar")
        return _account("claude_sub", "unknown")
    resets_at = _number(record.get("resetsAt"))
    state = "ok"
    retry_at = None
    if record.get("rejected"):
        # Nach der Rücksetzzeit ist der alte Ablehnungsgrund überholt, ein
        # neuer Wert kommt aber erst mit dem nächsten Lauf.
        if resets_at and resets_at > now:
            state, retry_at = "exhausted", resets_at
        else:
            state = "unknown"
    return _account(
        "claude_sub",
        state,
        windows=[w for w in record.get("windows", []) if isinstance(w, dict)],
        retry_at=retry_at,
        retry_source="provider",
        observed_at=_number(record.get("observedAt")),
    )


# --- Codex --------------------------------------------------------------------


def _codex_rpc(env: dict, timeout: float) -> dict:
    """Fragt den App-Server der Codex-CLI einmal ab; liefert ``result`` oder ``error``."""
    process = subprocess.Popen(
        ["codex", "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=env,
        cwd=env.get("CODEX_HOME") or None,
    )

    def send(message: dict) -> None:
        process.stdin.write(json.dumps(message) + "\n")
        process.stdin.flush()

    try:
        send(
            {
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": {"name": "skytech-omniai", "version": "1"}},
            }
        )
        # Eigener Lesethread: select() auf der gepufferten Pipe übersieht Zeilen, die schon
        # im Puffer liegen, und hängt dann trotz fertiger Antwort.
        lines: queue.Queue = queue.Queue()

        def pump() -> None:
            for item in process.stdout:
                lines.put(item)
            lines.put("")  # Ende der Ausgabe

        threading.Thread(target=pump, daemon=True).start()
        deadline = time.monotonic() + timeout
        while (remaining := deadline - time.monotonic()) > 0:
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty:
                break
            if not line:
                break
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if message.get("id") == 1:
                if "error" in message:
                    return {"error": message["error"]}
                send({"method": "initialized"})
                send({"id": 2, "method": "account/rateLimits/read"})
            elif message.get("id") == 2:
                return message
        raise TimeoutError("App-Server hat nicht rechtzeitig geantwortet")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def _codex_windows(result: dict, now: float) -> tuple[list, bool, float | None]:
    """Fenster aller Buckets, ob eines erschöpft ist und wann es frei wird."""
    buckets = result.get("rateLimitsByLimitId") or {}
    if not isinstance(buckets, dict) or not buckets:
        single = result.get("rateLimits")
        buckets = (
            {(single or {}).get("limitId") or "codex": single} if isinstance(single, dict) else {}
        )
    windows, exhausted, retry_at = [], False, None
    for limit_id, snapshot in buckets.items():
        if not isinstance(snapshot, dict):
            continue
        reached = bool(snapshot.get("rateLimitReachedType"))
        for slot in ("primary", "secondary"):
            window = snapshot.get(slot)
            if not isinstance(window, dict):
                continue
            used = _number(window.get("usedPercent"))
            resets = _number(window.get("resetsAt"))
            duration = _number(window.get("windowDurationMins"))
            windows.append(
                {
                    "id": slot,
                    "limitId": str(limit_id)[:40],
                    "durationMinutes": int(duration) if duration is not None else None,
                    "usedPercent": used,
                    "resetsAt": iso(resets),
                    "source": "measured",
                    "observedAt": iso(now),
                }
            )
            if (reached or (used is not None and used >= 100)) and resets:
                exhausted = True
                retry_at = max(retry_at or 0, resets)
        exhausted = exhausted or reached
    return windows, exhausted, retry_at


def codex_entry(available: bool, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    if not available:
        return _account("codex_sub", "unavailable")
    with _CODEX_LOCK:
        cached = _codex_cache["entry"]
        if cached is not None and now - _codex_cache["at"] < CODEX_CACHE_SECONDS:
            return cached
        entry = _query_codex(now)
        _codex_cache.update(at=now, entry=entry)
        return entry


def _query_codex(now: float) -> dict:
    # Import hier: der Provider setzt beim Erzeugen CODEX_HOME und legt den
    # Zugang aus der Konfiguration ab, genau wie vor einem normalen Aufruf.
    from providers.codex_sub_provider import CodexSubProvider

    provider = CodexSubProvider()
    try:
        env = provider._build_env()
    except RuntimeError:
        return _account("codex_sub", "unavailable")
    if provider._api_key_fallback:
        # Mit API-Schlüssel wird nach Verbrauch abgerechnet; ein Abo-Fenster gibt es nicht.
        return _account("codex_sub", "ok")
    try:
        answer = _codex_rpc(env, CODEX_TIMEOUT_SECONDS)
    except FileNotFoundError:
        log.error("Codex-CLI fehlt, Limits nicht abfragbar")
        return _account("codex_sub", "unavailable")
    except (OSError, TimeoutError) as error:
        log.warning("Limits von Codex nicht abfragbar: %s", error)
        return _account("codex_sub", "unknown")
    if "error" in answer:
        message = json.dumps(answer.get("error"))[:300].lower()
        log.warning("Codex lehnt die Limitabfrage ab: %s", message)
        if any(marker in message for marker in ("auth", "login", "401", "unauthorized", "token")):
            return _account("codex_sub", "login_required")
        return _account("codex_sub", "unknown")
    windows, exhausted, retry_at = _codex_windows(answer.get("result") or {}, now)
    return _account(
        "codex_sub",
        "exhausted" if exhausted else "ok",
        windows=windows,
        retry_at=retry_at,
        retry_source="provider",
        observed_at=now,
    )


# --- Gemini -------------------------------------------------------------------


def gemini_web_entries(now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    entries = []
    for account in gemini_web_accounts.list_accounts():
        retry_at = None
        if account.needs_login or not account.signed_in():
            state = "login_required"
        elif account.exhausted_until > now:
            state, retry_at = "exhausted", account.exhausted_until
        else:
            state = "ok"
        entries.append(
            _account(
                "gemini_web",
                state,
                account.id,
                account.label,
                retry_at=retry_at,
                retry_source="estimated",
            )
        )
    return entries


AGY_STATES = {
    "signed_out": "login_required",
    "login_expired": "login_required",
    "restricted": "restricted",
    "exhausted": "exhausted",
    "ok": "ok",
}


def gemini_agy_entries(now: float | None = None) -> list[dict]:
    now = time.time() if now is None else now
    entries = []
    for account in gemini_agy_accounts.list_accounts():
        state = AGY_STATES.get(account.state(now), "unknown")
        retry_at = account.exhausted_until if state in ("exhausted", "restricted") else None
        entries.append(
            _account(
                "gemini_agy",
                state,
                account.id,
                account.label,
                retry_at=retry_at,
                retry_source="estimated",
            )
        )
    return entries


# --- Gesamt -------------------------------------------------------------------


def report(present: dict[str, bool], now: float | None = None) -> dict:
    """Alle Konten aller bekannten Anbieter; ``present`` aus ``credentials_present``."""
    now = time.time() if now is None else now
    accounts = [
        claude_entry(present.get("claude_sub", False), now),
        codex_entry(present.get("codex_sub", False), now),
        _account("gemini", "ok" if present.get("gemini") else "unavailable"),
    ]
    for collect in (gemini_agy_entries, gemini_web_entries):
        try:
            accounts += collect(now)
        except Exception:  # Kontoliste beschädigt: Anbieter fehlt, Rest bleibt nutzbar
            log.exception("Kontenzustand für die Limits nicht lesbar")
    return {"measuredAt": iso(now), "accounts": accounts}
