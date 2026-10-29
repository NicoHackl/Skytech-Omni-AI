"""Gemini Web: eigenständige temporäre Chats und offener Wechsel zwischen Google-Konten."""

import json
import logging
import os
import shutil
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from providers import gemini_web_accounts as accounts
from providers import google_accounts
from providers.base_provider import (
    JSON_INSTRUCTION,
    Attachment,
    BaseProvider,
    ProviderTimeout,
    UnknownModel,
)
from providers.gemini_web_client import WebClientError, client

log = logging.getLogger("omniai.gemini_web")
RUN_LOCK = threading.Lock()
TIMEOUT_SECONDS = 120
FEHLER_ANMELDUNG = (
    "Bitte in den Einstellungen von Gemini Web ein Google-Konto anmelden "
    "oder die abgelaufene Anmeldung entfernen und erneut einfügen."
)
FEHLER_ANFRAGE = "Gemini Web hat die Anfrage nicht beantwortet. Bitte später erneut versuchen."
FEHLER_TIMEOUT = "Gemini Web hat zu lange gebraucht. Bitte später erneut versuchen."


def available_models() -> list[str]:
    return accounts.load_models()


def is_signed_in() -> bool:
    return bool(accounts.ready_accounts())


def _pause_path():
    return accounts.base_home() / "omniai-gemini-web-pause.json"


def _pause() -> dict:
    try:
        data = json.loads(_pause_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def _retry_message(timestamp: float, blocked: bool = False) -> str:
    when = datetime.fromtimestamp(timestamp, ZoneInfo("Europe/Berlin")).strftime("%H:%M")
    if blocked:
        return f"Google hat die Verbindung vorübergehend gesperrt. Nächster Versuch um {when}."
    return f"Das Kontingent der Google-Konten ist aufgebraucht. Nächster Versuch um {when}."


def _check_pause():
    until = float(_pause().get("until", 0))
    if until > time.time():
        raise RuntimeError(_retry_message(until, blocked=True))


@contextmanager
def _operation(timeout: float):
    started = time.monotonic()
    if not RUN_LOCK.acquire(timeout=min(timeout, 10)):
        raise ProviderTimeout(
            "Gemini Web bearbeitet gerade eine Anfrage. Bitte später erneut versuchen."
        )
    try:
        _check_pause()

        def remaining():
            value = timeout - (time.monotonic() - started)
            if value <= 0:
                raise ProviderTimeout(FEHLER_TIMEOUT)
            return value

        yield remaining
    finally:
        RUN_LOCK.release()


def _translated(error: WebClientError) -> Exception:
    log.warning("Gemini Web meldet: %s", error.kind)
    if error.kind == "timeout":
        return ProviderTimeout(FEHLER_TIMEOUT)
    if error.kind == "model":
        choices = ", ".join(available_models()) or "Vorgabe des Anbieters"
        return UnknownModel(f"Dieses Modell kennt Gemini Web nicht. Zur Auswahl stehen: {choices}.")
    if error.kind == "auth":
        return RuntimeError(FEHLER_ANMELDUNG)
    if error.kind == "blocked":
        strikes = int(_pause().get("strikes", 0)) + 1
        until = time.time() + google_accounts.backoff_seconds(strikes)
        google_accounts.write_json(_pause_path(), {"strikes": strikes, "until": until})
        return RuntimeError(_retry_message(until, blocked=True))
    return RuntimeError(FEHLER_ANFRAGE)


def _with_accounts(remaining, **kwargs) -> dict:
    ready = accounts.ready_accounts()
    if not ready:
        retry = google_accounts.next_try_time(accounts.list_accounts())
        if retry:
            raise RuntimeError(_retry_message(retry))
        raise RuntimeError(FEHLER_ANMELDUNG)
    for account in ready:
        try:
            result = client.call(account, timeout=remaining(), **kwargs)
        except WebClientError as error:
            if error.kind == "quota":
                accounts.mark_exhausted(account)
                log.warning("Google-Konto „%s“: Kontingent aufgebraucht", account.label)
            elif error.kind == "auth":
                accounts.mark_needs_login(account)
                log.warning("Google-Konto „%s“: Anmeldung abgelaufen", account.label)
            else:
                raise _translated(error) from None
        else:
            accounts.mark_ok(account)
            accounts.store_models(result["models"])
            _pause_path().unlink(missing_ok=True)
            return result
    retry = google_accounts.next_try_time(accounts.list_accounts())
    if retry:
        raise RuntimeError(_retry_message(retry))
    raise RuntimeError(FEHLER_ANMELDUNG)


def refresh_models() -> list[str]:
    """Liest Modelle erneut vom ersten nutzbaren Konto, ohne eine Anfrage zu erzeugen."""
    with _operation(TIMEOUT_SECONDS) as remaining:
        return _with_accounts(remaining)["models"]


def add_account(label: str, psid: str, psidts: str) -> dict:
    """Prüft die Anmeldung vor Aufnahme in die Liste; Fehler hinterlassen keine Cookies."""
    with _operation(TIMEOUT_SECONDS) as remaining:
        account = accounts.prepare_account(label, psid, psidts)
        try:
            result = client.call(account, timeout=remaining())
            accounts.store_models(result["models"])
            accounts.add_account(account)
        except Exception as error:
            # Schließen vor Löschen: ein Hintergrundtask darf nichts wieder anlegen.
            try:
                client.call(account, close=True, timeout=5)
            except Exception:
                log.error("Fehlgeschlagene Google-Anmeldung konnte nicht sauber geschlossen werden")
            shutil.rmtree(account.home, ignore_errors=True)
            if not accounts.list_accounts():
                accounts.models_path().unlink(missing_ok=True)
            if isinstance(error, WebClientError):
                raise _translated(error) from None
            raise
        log.info("Google-Konto „%s“ bei Gemini Web angemeldet", account.label)
        return accounts.public_status()


def remove_account(account_id: str) -> dict:
    """Beendet die Sitzung und entfernt dann Konto und dessen gesamte private Ablage."""
    # Entfernen muss auch während einer Verbindungssperre möglich bleiben.
    if not RUN_LOCK.acquire(timeout=5):
        raise RuntimeError(
            "Gemini Web bearbeitet gerade eine Anfrage. Bitte danach erneut versuchen."
        )
    try:
        account = next((a for a in accounts.list_accounts() if a.id == account_id), None)
        if account is None:
            raise accounts.AccountError("Dieses Konto ist nicht mehr angemeldet. Bitte neu laden.")
        try:
            client.call(account, close=True, timeout=10)
        except WebClientError as error:
            raise _translated(error) from None
        accounts.remove_account(account_id)
        log.info("Google-Konto „%s“ aus Gemini Web entfernt", account.label)
        return accounts.public_status()
    finally:
        RUN_LOCK.release()


class GeminiWebProvider(BaseProvider):
    """Web-App ohne lokalen Gesprächsverlauf; die Werkzeugstufe steuert diesen Zugang nicht."""

    def _resolve_model(self, model: str | None) -> str:
        chosen = model if model is not None else os.environ.get("OMNIAI_GEMINI_WEB_MODEL", "")
        return "" if chosen == "auto" else chosen.strip()

    def execute(
        self,
        prompt: str,
        model: str | None = None,
        timeout: int | None = None,
        attachments: list[Attachment] | None = None,
    ) -> dict:
        with _operation(float(timeout or TIMEOUT_SECONDS)) as remaining:
            result = _with_accounts(
                remaining,
                prompt=prompt + JSON_INSTRUCTION,
                model=self._resolve_model(model),
                attachments=attachments,
            )
            # parse_json bleibt der zentrale Auswerter; keine eigene JSON-Heuristik.
            return self.parse_json(result["text"])
