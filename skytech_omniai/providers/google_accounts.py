"""Gemeinsame Ablage und Wartezeiten für Google-Konten, unabhängig vom Zugang."""

import json
import logging
import os
import tempfile
from pathlib import Path

log = logging.getLogger("omniai.google_accounts")

BACKOFF_START_SECONDS = 1800
BACKOFF_MAX_SECONDS = 5 * 3600


def write_json(path: Path, payload: object) -> None:
    """Schreibt atomar; auch die vorübergehende Datei ist nur für den Besitzer lesbar."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".omniai-")
    temp = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def read_records(path: Path) -> list[dict] | None:
    """Liest eine Kontenliste; fehlend ist ``None``, beschädigt ist leer."""
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))["accounts"]
        if not isinstance(entries, list):
            raise ValueError
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        log.error("Liste der Google-Konten unlesbar, sie gilt als leer")
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def backoff_seconds(strikes: int) -> int:
    """Wachsende Wartezeit, ohne bei beschädigten Zählern riesige Zahlen zu bilden."""
    return min(BACKOFF_START_SECONDS * 2 ** max(0, min(strikes - 1, 4)), BACKOFF_MAX_SECONDS)


def ready_accounts(accounts, now: float) -> list:
    """Erstes nutzbares Konto zuerst, kein Reihum und kein Warten im Aufrufer."""
    return [
        account
        for account in accounts
        if account.signed_in() and not account.needs_login and account.exhausted_until <= now
    ]


def next_try_time(accounts) -> float | None:
    """Frühester nächster Versuch unter den weiterhin angemeldeten Konten."""
    times = [
        account.exhausted_until
        for account in accounts
        if account.signed_in() and not account.needs_login and account.exhausted_until > 0
    ]
    return min(times) if times else None
