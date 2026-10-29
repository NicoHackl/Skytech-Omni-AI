"""Einzige Brücke zu gemini-webapi: eigene Ereignisschleife, private Ablage, bereinigte Fehler."""

import asyncio
import atexit
import contextlib
import importlib
import logging
import os
import tempfile
import threading
from concurrent.futures import TimeoutError as FutureTimeout
from contextvars import ContextVar
from importlib.metadata import version
from pathlib import Path

from providers import gemini_web_accounts as accounts
from providers.base_provider import Attachment
from providers.google_accounts import write_json

log = logging.getLogger("omniai.gemini_web.client")
_CACHE_HOME: ContextVar[Path] = ContextVar("gemini_web_cache_home")


class WebClientError(RuntimeError):
    """Nur eine interne Fehlerart, niemals Rohtext oder Zugangsdaten der Bibliothek."""

    def __init__(self, kind: str):
        self.kind = kind
        super().__init__("Die Verbindung zu Gemini Web konnte nicht abgeschlossen werden.")


def _cache_path(cookies, verbose: bool = False) -> Path:
    # Das Original benutzt den vollen Cookie-Wert im Dateinamen. Ein Kontext je
    # Konto gilt auch in dessen Hintergrundaufgaben, ohne globale Env-Wechsel.
    return _CACHE_HOME.get() / "session.json"


def _library():
    """Lädt nur die geprüfte Fassung und ersetzt deren unsichere Cache-Pfade."""
    if version("gemini-webapi") != "2.1.1":
        raise WebClientError("dependency")
    package = importlib.import_module("gemini_webapi")
    package.logger.disable("gemini_webapi")
    for name in ("rotate_1psidts", "get_access_token"):
        module = importlib.import_module(f"gemini_webapi.utils.{name}")
        module._get_cookies_cache_path = _cache_path
        module._get_cookie_cache_dir = _CACHE_HOME.get
    return package


def _error_kind(error: Exception) -> str:
    return {
        "UsageLimitExceededError": "quota",
        "AuthError": "auth",
        "TemporarilyBlockedError": "blocked",
        "ModelInvalidError": "model",
        "TimeoutError": "timeout",
    }.get(type(error).__name__, "failure")


class GeminiWebClient:
    """Ein synchroner Einstieg; Clients und deren Wartung leben nur im eigenen Thread."""

    def __init__(self):
        self._start_lock = threading.Lock()
        self._loop = None
        self._thread = None
        self._clients = {}
        self._serial = None

    def _start(self):
        with self._start_lock:
            if self._loop is not None:
                return self._loop
            ready = threading.Event()

            def serve():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._serial = asyncio.Lock()
                self._loop = loop
                ready.set()
                loop.run_forever()
                loop.close()

            self._thread = threading.Thread(target=serve, name="gemini-web", daemon=True)
            self._thread.start()
            ready.wait()
            return self._loop

    def call(
        self,
        account: accounts.Account,
        *,
        prompt: str | None = None,
        model: str = "",
        timeout: float = 120,
        attachments: list[Attachment] | None = None,
        close: bool = False,
    ) -> dict:
        """Wartet begrenzt, bricht bei Ablauf ab und räumt den laufenden Client auf."""
        loop = self._start()
        finished = threading.Event()

        async def invoke():
            try:
                async with self._serial:
                    return await self._request(account, prompt, model, attachments, close)
            finally:
                finished.set()

        future = asyncio.run_coroutine_threadsafe(invoke(), loop)
        try:
            return future.result(timeout=max(0.01, timeout))
        except FutureTimeout:
            future.cancel()
            # Das Future meldet schon beim Abbruch fertig; erst das Ereignis
            # bestätigt das Aufräumen der Dateien und des Clients im Thread.
            finished.wait(timeout=5)
            raise WebClientError("timeout") from None
        except WebClientError:
            raise
        except Exception as error:
            kind = _error_kind(error)
            log.warning("Gemini-Web-Verbindung abgebrochen: %s", kind)
            raise WebClientError(kind) from None

    async def _request(self, account, prompt, model, attachments, close):
        token = _CACHE_HOME.set(account.home)
        key = str(account.home)
        client = self._clients.get(key)
        try:
            if close:
                if client:
                    await client.close()
                    self._clients.pop(key, None)
                return {}
            package = _library()
            if client is None:
                cookies = accounts.read_cookies(account)
                if not cookies:
                    raise WebClientError("auth")
                client = package.GeminiClient(cookies["psid"], cookies["psidts"])
                self._clients[key] = client
            await client.init(timeout=120, auto_refresh=True, verbose=False)
            # init() kann auch als Gast erfolgreich sein. Das ist keine Anmeldung.
            status = importlib.import_module("gemini_webapi.constants").AccountStatus
            if client.account_status != status.AVAILABLE:
                raise WebClientError("auth")
            models = [m.model_name for m in client.list_models() or [] if m.is_available]
            if prompt is None:
                return {"models": models}
            chosen = None
            if model:
                try:
                    chosen = client.resolve_model(model)
                except ValueError:
                    raise WebClientError("model") from None
            with tempfile.TemporaryDirectory(prefix="omniai-gemini-web-") as directory:
                paths = []
                for index, attachment in enumerate(attachments or []):
                    # Der Dateiname ist geprüft; trotzdem bleibt die Ablage auch bei
                    # einem direkten Provider-Aufruf im temporären Verzeichnis.
                    name = Path(attachment.name.replace("\\", "/")).name
                    path = Path(directory) / f"{index}-{name}"
                    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(descriptor, "wb") as stream:
                        stream.write(attachment.data)
                    paths.append(path)
                output = await client.generate_content(
                    prompt,
                    model=chosen,
                    files=paths or None,
                    temporary=True,
                )
                return {"text": output.text, "models": models}
        except BaseException:
            # Auch Abbruch darf keinen halbfertigen oder weiterhin anfragenden
            # Client zurücklassen. Keine Ausnahme-Texte der Bibliothek ausgeben.
            if client:
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(client.close(), timeout=3)
            self._clients.pop(key, None)
            raise
        finally:
            if client and not close:
                self._persist_cookies(account, client)
            _CACHE_HOME.reset(token)

    @staticmethod
    def _persist_cookies(account, client):
        try:
            values = {cookie.name: cookie.value for cookie in client.cookies.jar}
            psid, psidts = values.get("__Secure-1PSID"), values.get("__Secure-1PSIDTS")
            if psid and psidts:
                write_json(account.home / "cookies.json", {"psid": psid, "psidts": psidts})
        except Exception:
            log.error("Erneuerte Google-Anmeldung konnte nicht gespeichert werden")

    def shutdown(self):
        """Schließt Clients beim Beenden, ohne beim nie genutzten Anbieter zu starten."""
        if self._loop is None:
            return

        async def close_all():
            async with self._serial:
                for home, client in list(self._clients.items()):
                    token = _CACHE_HOME.set(Path(home))
                    try:
                        await client.close()
                    except Exception:
                        log.warning("Gemini-Web-Verbindung beim Beenden nicht sauber geschlossen")
                    finally:
                        _CACHE_HOME.reset(token)
                self._clients.clear()

        try:
            asyncio.run_coroutine_threadsafe(close_all(), self._loop).result(timeout=5)
        except Exception:
            log.warning("Gemini-Web-Verbindungen beim Beenden nicht rechtzeitig geschlossen")
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)


client = GeminiWebClient()
atexit.register(client.shutdown)
