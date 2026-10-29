"""Anmeldung des Google-Kontos für ``gemini_agy`` — im Add-on selbst.

Die Antigravity-CLI kennt keinen Befehl zum Anmelden: wer ohne gültige Anmeldung
einen Auftrag erteilt, bekommt eine Google-Adresse gedruckt und 60 Sekunden Zeit,
den Code von der Zielseite einzufügen. Im Add-on sitzt niemand am Terminal, also
hält dieses Modul den Prozess offen, reicht die Adresse an die Oberfläche weiter
und schreibt den dort eingefügten Code in seine Eingabe.

Entsteht die Anmeldung im Add-on, schreibt und liest dieselbe Umgebung die Datei
— das umgeht die Berichte, nach denen eine in einem anderen Container erzeugte
Anmeldung nicht angenommen wird.

Jede Anmeldung legt ein **neues Konto** an (D-024): eigenes Heimatverzeichnis,
eigene Anmeldung. Erst wenn sie gelungen und in einem frischen Prozess bestätigt
ist, kommt das Konto in die Liste; scheitert sie, verschwinden seine Dateien wieder.

Ablauf: ``start`` → Nutzer meldet sich bei Google an und kopiert den Code →
``submit`` → die CLI tauscht den Code, beantwortet einen Probeauftrag → ein
frischer Prozess prüft, dass die Anmeldung die Datei überdauert hat. Alle Zustände
liest die Oberfläche über ``status``.
"""

import contextlib
import logging
import os
import pty
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

from providers import gemini_agy_accounts as accounts
from providers import gemini_agy_provider as cli
from providers.gemini_agy_accounts import Account, AccountError
from providers.gemini_agy_provider import RUN_LOCK, AgyResult

log = logging.getLogger("omniai.gemini_agy.login")

# Die CLI druckt die Adresse in eine eigene Zeile; erst mit dem Zeilenende ist
# sie vollständig.
URL_PATTERN = re.compile(r"(https://accounts\.google\.com/\S+)\s*\n")
CODE_PATTERN = re.compile(r"^[A-Za-z0-9_\-./~%+]{8,2048}$")

# Die CLI wartet auf den Code genau so lange; was länger dauert, scheitert dort.
CODE_WINDOW_SEKUNDEN = 60
# Die Oberfläche zeigt etwas weniger, damit nicht der letzte Atemzug zählt.
CODE_SAFETY_SEKUNDEN = 4
# Nachfrist, bevor die Sitzung ohne Code als abgelaufen gilt: die CLI gibt selbst
# auf, sobald ihre Minute um ist, und ihr Ausgang ist die genauere Auskunft.
WATCH_GRACE_SEKUNDEN = 2
WATCH_INTERVAL_SEKUNDEN = 0.1
URL_WAIT_SEKUNDEN = 20
# Nach dem Code: Tausch bei Google und ein kurzer Probeauftrag.
FINISH_WAIT_SEKUNDEN = 150
VERIFY_TIMEOUT_SEKUNDEN = 30
START_LOCK_WAIT_SEKUNDEN = 5

# Der Probeauftrag zeigt, dass die Anmeldung samt Konto und Tarif trägt.
PING_PROMPT = 'Reply with the JSON object {"ok": true} and nothing else.'

FEHLER_CLI_FEHLT = cli.FEHLER_CLI_FEHLT
FEHLER_BESETZT = (
    "Gerade läuft eine Anfrage an Google Gemini (AGY). Bitte in einem Moment erneut versuchen."
)
FEHLER_KONTO_UNBEKANNT = "Dieses Konto gibt es nicht (mehr)."
FEHLER_KEIN_START = "Die Adresse von Google ließ sich nicht abrufen. Bitte erneut versuchen."
FEHLER_KEINE_ANMELDUNG = "Es läuft keine Anmeldung. Bitte neu starten."
FEHLER_CODE_FORMAT = "Das sieht nicht nach dem Code von Google aus. Bitte ihn vollständig kopieren."
FEHLER_CODE_ABGELEHNT = (
    "Google hat den Code nicht angenommen. Er gilt nur kurz und nur einmal. Bitte die "
    "Anmeldung neu starten."
)
FEHLER_ZEIT = (
    "Die Anmeldung hat zu lange gedauert; Google gibt dafür etwa eine Minute. Bitte neu "
    "starten und den Code gleich einfügen."
)
FEHLER_PRUEFUNG_ZEIT = "Google hat zu lange gebraucht. Bitte die Anmeldung erneut versuchen."
FEHLER_NICHT_GESPEICHERT = (
    "Google hat die Anmeldung angenommen, sie ließ sich aber nicht dauerhaft speichern. "
    "Google Gemini (AGY) ist damit derzeit nicht nutzbar. Ursache steht im Protokoll des Add-ons."
)
FEHLER_ALLGEMEIN = "Die Anmeldung hat nicht geklappt. Bitte erneut versuchen."


class LoginError(Exception):
    """Die Anmeldung lässt sich nicht fortsetzen; der Satz ist für Nutzer geschrieben."""

    def __init__(
        self,
        message: str,
        *,
        busy: bool = False,
        invalid: bool = False,
        missing: bool = False,
        field: str = "code",
    ):
        super().__init__(message)
        self.busy = busy
        # Die Eingabe taugt nicht; ``field`` nennt das Feld, das die Oberfläche markiert.
        self.invalid = invalid
        self.field = field
        self.missing = missing


@dataclass
class _Session:
    process: subprocess.Popen
    master_fd: int
    account: Account
    url: str
    deadline: float
    out_chunks: list = field(default_factory=list)
    err_chunks: list = field(default_factory=list)
    pumps: list = field(default_factory=list)
    state: str = "waiting"  # waiting | checking
    finish_deadline: float = 0.0
    before: dict = field(default_factory=dict)
    # Erst die bestätigte Anmeldung macht das Konto zu einem der Liste.
    registered: bool = False
    # ``_finish`` hat begonnen; ein zweiter Aufruf darf nichts mehr tun.
    finished: bool = False


def extract_code(raw: str) -> str:
    """Holt den Code aus dem, was der Nutzer eingefügt hat.

    Die Zielseite zeigt den Code selbst; wer stattdessen die ganze Adresse mit
    ``code=…`` kopiert, soll trotzdem zum Ziel kommen.

    :raises LoginError: wenn das Ergebnis nicht wie ein Code aussieht.
    """
    text = (raw or "").strip()
    if "code=" in text:
        query = urlparse(text).query if text.startswith("http") else text
        values = parse_qs(query).get("code")
        if values:
            text = values[0].strip()
    if not CODE_PATTERN.match(text):
        raise LoginError(FEHLER_CODE_FORMAT, invalid=True)
    return text


class GeminiLogin:
    """Hält höchstens eine laufende Anmeldung."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session: _Session | None = None
        self._error: str | None = None

    # --- Auskunft ---------------------------------------------------------

    def status(self, *, include_url: bool = False) -> dict:
        """Zustand für die Oberfläche. Die Adresse nur, wenn der Aufrufer sie sehen darf."""
        session = self._session
        state = session.state if session else "idle"
        seconds_left = None
        if session and session.state == "waiting":
            seconds_left = max(0, int(session.deadline - time.monotonic()))
        return {
            "available": cli.cli_available(),
            "signed_in": cli.is_signed_in(),
            "accounts": [accounts.describe(a) for a in accounts.list_accounts()],
            # Wer sich gerade anmeldet, steht noch nicht in der Liste.
            "pending_label": session.account.label if session else None,
            "state": state,
            "url": session.url if (session and include_url and state == "waiting") else None,
            "seconds_left": seconds_left,
            "error": self._error if state == "idle" else None,
        }

    # --- Ablauf -----------------------------------------------------------

    def start(self, label: str = "") -> dict:
        """Startet die CLI für ein **neues Konto** und liefert die Adresse bei Google.

        ``label`` ist der Name, unter dem das Konto in der Oberfläche steht; leer
        heißt „Konto N“.

        :raises LoginError: wenn sich keine Anmeldung starten lässt.
        """
        with self._lock:
            if self._session is not None:
                self._finish(self._session, error=None)
            self._error = None
            if not cli.cli_available():
                raise LoginError(FEHLER_CLI_FEHLT)
            try:
                account = accounts.new_account(label)
            except AccountError as error:
                raise LoginError(str(error), invalid=True, field="label") from error
            if not RUN_LOCK.acquire(timeout=START_LOCK_WAIT_SEKUNDEN):
                raise LoginError(FEHLER_BESETZT, busy=True)
            try:
                try:
                    session = self._spawn(account)
                except RuntimeError as error:
                    raise LoginError(str(error)) from error
            except BaseException:
                RUN_LOCK.release()
                # Ein Konto, das nie entstand, soll auch keinen Ordner hinterlassen.
                accounts.discard_files(account)
                raise
            self._session = session
        threading.Thread(target=self._watch, args=(session,), daemon=True).start()
        log.info("Anmeldung bei Google gestartet")
        return self.status(include_url=True)

    def submit(self, raw_code: str) -> dict:
        """Gibt den eingefügten Code an die CLI weiter. Das Ergebnis liefert ``status``.

        :raises LoginError: wenn keine Anmeldung wartet oder der Code unbrauchbar ist.
        """
        code = extract_code(raw_code)
        with self._lock:
            session = self._session
            if session is None or session.state != "waiting":
                raise LoginError(FEHLER_KEINE_ANMELDUNG)
            if time.monotonic() > session.deadline + CODE_SAFETY_SEKUNDEN:
                raise LoginError(FEHLER_ZEIT)
            try:
                os.write(session.master_fd, (code + "\n").encode("utf-8"))
            except OSError as error:
                log.error("Code ließ sich nicht an die Google-CLI übergeben: %s", error)
                self._finish(session, error=FEHLER_ALLGEMEIN)
                raise LoginError(FEHLER_ALLGEMEIN) from error
            session.state = "checking"
            session.finish_deadline = time.monotonic() + FINISH_WAIT_SEKUNDEN
        log.info("Code von Google an die CLI übergeben, Prüfung läuft")
        return self.status()

    def cancel(self) -> dict:
        with self._lock:
            if self._session is not None:
                self._finish(self._session, error=None)
            self._error = None
        return self.status()

    def logout(self, account_id: str) -> dict:
        """Entfernt ein Konto samt Anmeldung. Widerrufen lässt sie sich nur im Google-Konto.

        :raises LoginError: wenn es das Konto nicht gibt oder gerade eine Anfrage läuft.
        """
        with self._lock:
            if self._session is not None:
                self._finish(self._session, error=None)
            self._error = None
            # Mitten in einer Anfrage dieses Kontos die Dateien zu löschen, brächte der
            # Anfrage einen unverständlichen Fehler.
            if not RUN_LOCK.acquire(timeout=START_LOCK_WAIT_SEKUNDEN):
                raise LoginError(FEHLER_BESETZT, busy=True)
            try:
                removed = accounts.remove_account(account_id)
                if removed is None:
                    raise LoginError(FEHLER_KONTO_UNBEKANNT, missing=True)
                if not accounts.list_accounts():
                    # Die Liste der Modelle gehört zu den Konten, die sich abgemeldet haben.
                    cli.clear_models()
            finally:
                RUN_LOCK.release()
        log.info("Google-Konto „%s“ entfernt", removed.label)
        return self.status()

    # --- Innenleben -------------------------------------------------------

    def _spawn(self, account: Account) -> _Session:
        workspace = cli.prepare_state("off", account.home)
        command = [
            cli.AGY_BINARY,
            "-p",
            PING_PROMPT,
            "--output-format",
            "json",
            "--print-timeout",
            f"{FINISH_WAIT_SEKUNDEN - 10}s",
            "--disable-slash-commands",
        ]
        before = cli.snapshot_state(account.home)
        # Eine Pty als Eingabe: mit /dev/null druckt die CLI die Adresse und
        # wartet, aber liest nichts; mit einer Pipe gibt sie sofort auf. Nur ein
        # Terminal zeigt ihr, dass jemand den Code eintippt.
        master_fd, slave_fd = pty.openpty()
        try:
            process = subprocess.Popen(
                command,
                stdin=slave_fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=cli.agy_env(account.home),
                cwd=workspace,
                start_new_session=True,
                close_fds=True,
            )
        except FileNotFoundError as error:
            os.close(master_fd)
            raise RuntimeError(FEHLER_CLI_FEHLT) from error
        except OSError as error:
            os.close(master_fd)
            log.error("Google-CLI ließ sich nicht starten: %s", error)
            raise RuntimeError(FEHLER_ALLGEMEIN) from error
        finally:
            os.close(slave_fd)

        session = _Session(
            process=process,
            master_fd=master_fd,
            account=account,
            url="",
            deadline=0.0,
            before=before,
        )
        for stream, sink in (
            (process.stdout, session.out_chunks),
            (process.stderr, session.err_chunks),
        ):
            thread = threading.Thread(target=cli.pump, args=(stream, sink, None, b""), daemon=True)
            thread.start()
            session.pumps.append(thread)

        started = time.monotonic()
        while time.monotonic() - started < URL_WAIT_SEKUNDEN:
            text = b"".join(session.err_chunks).decode("utf-8", errors="replace")
            match = URL_PATTERN.search(text)
            if match and urlparse(match.group(1)).hostname == "accounts.google.com":
                session.url = match.group(1)
                session.deadline = time.monotonic() + CODE_WINDOW_SEKUNDEN - CODE_SAFETY_SEKUNDEN
                return session
            if process.poll() is not None:
                break
            time.sleep(0.1)

        output = b"".join(session.err_chunks).decode("utf-8", errors="replace")
        log.error("Keine Anmeldeadresse von der Google-CLI. Ausgabe: %s", output.strip())
        self._release(session)
        raise RuntimeError(FEHLER_KEIN_START)

    def _release(self, session: _Session) -> None:
        """Beendet den Prozess, schließt die Eingabe und räumt die Gesprächsdaten auf."""
        cli.terminate(session.process)
        with contextlib.suppress(OSError):
            os.close(session.master_fd)
        cli.cleanup_state(session.before, home=session.account.home)
        if not session.registered:
            # Eine Anmeldung, die nicht zum Konto wurde, hinterlässt nichts.
            accounts.discard_files(session.account)

    def _finish(self, session: _Session, *, error: str | None) -> None:
        """Beendet die Sitzung genau einmal und gibt die Sperre frei. Unter ``_lock`` aufrufen.

        Erst wenn die Sperre frei ist, gilt die Sitzung als beendet: wer den Zustand
        „idle“ liest, darf gleich danach eine Anfrage stellen, ohne auf eine Sperre zu
        stoßen, die niemand mehr hält.
        """
        if self._session is not session or session.finished:
            return
        session.finished = True
        try:
            self._release(session)
        finally:
            # Die Sperre muss auch dann frei werden, wenn das Aufräumen scheitert —
            # sonst liefe nie wieder eine Anfrage.
            RUN_LOCK.release()
            self._error = error
            self._session = None

    def _watch(self, session: _Session) -> None:
        """Beobachtet Zeitlimits und den Ausgang des Prozesses, bis die Sitzung endet."""
        try:
            while True:
                time.sleep(WATCH_INTERVAL_SEKUNDEN)
                if self._session is not session:
                    return
                if session.process.poll() is not None:
                    break
                now = time.monotonic()
                if (
                    session.state == "waiting"
                    and now > session.deadline + CODE_SAFETY_SEKUNDEN + WATCH_GRACE_SEKUNDEN
                ):
                    with self._lock:
                        self._finish(session, error=FEHLER_ZEIT)
                    log.info("Anmeldung bei Google abgelaufen: kein Code eingefügt")
                    return
                if session.state == "checking" and now > session.finish_deadline:
                    with self._lock:
                        self._finish(session, error=FEHLER_PRUEFUNG_ZEIT)
                    log.error("Anmeldung bei Google: Prüfung dauerte zu lange")
                    return
            error = self._evaluate(session)
            with self._lock:
                self._finish(session, error=error)
        except Exception:
            log.exception("Unerwarteter Fehler bei der Anmeldung")
            with self._lock:
                self._finish(session, error=FEHLER_ALLGEMEIN)

    def _evaluate(self, session: _Session) -> str | None:
        """Wertet den Lauf aus, der die Anmeldung beendet hat.

        :returns: einen Satz für den Nutzer bei Misserfolg, sonst ``None``.
        """
        cli.kill_group(session.process.pid)
        for thread in session.pumps:
            thread.join(timeout=5)
        result = AgyResult(
            returncode=session.process.returncode,
            stdout=b"".join(session.out_chunks).decode("utf-8", errors="replace"),
            stderr=b"".join(session.err_chunks).decode("utf-8", errors="replace"),
        )
        envelope = cli.parse_envelope(result.stdout)
        status = str((envelope or {}).get("status", "")).upper()
        quota_only = False
        if status != "SUCCESS":
            output = f"{(envelope or {}).get('error', '')}\n{result.stderr}"
            # Die Anmeldung kann gelungen sein und nur der Probeauftrag am Kontingent
            # scheitern (ein Konto, das gerade leer ist). Dann gehört das Konto trotzdem
            # in die Liste — mit Wartezeit.
            token_written = cli.read_token_file(cli.token_path(session.account.home)) is not None
            if cli.classify_failure(output) == "quota" and token_written:
                quota_only = True
                log.warning("Anmeldung gelungen, der Probeauftrag fand aber kein Kontingent")
            else:
                log.error(
                    "Anmeldung bei Google fehlgeschlagen, Rückgabecode %s. Ausgabe: %s",
                    result.returncode,
                    _without_urls(output).strip(),
                )
                return self._login_failure(output)

        # Der Probeauftrag hat geklappt. Ob die Anmeldung auch einen neuen
        # Prozess überlebt, zeigt erst ein neuer Prozess — das ist der Fall,
        # an dem andere Container gescheitert sind.
        try:
            verify = cli.run_agy(
                [cli.AGY_BINARY, "models"],
                env=cli.agy_env(session.account.home),
                cwd=cli.workspace_dir(session.account.home),
                timeout=VERIFY_TIMEOUT_SEKUNDEN,
            )
        except OSError as error:
            log.error("Prüfung der Anmeldung nicht möglich: %s", error)
            return FEHLER_NICHT_GESPEICHERT
        if verify.returncode != 0 or verify.auth_required or verify.timed_out:
            log.error(
                "Anmeldung nicht dauerhaft: Prüfung in neuem Prozess endete mit %s. Ausgabe: %s",
                verify.returncode,
                _without_urls(f"{verify.stderr}\n{verify.stdout}").strip(),
            )
            return FEHLER_NICHT_GESPEICHERT

        cli.backup_token(session.account.home)
        accounts.add_account(session.account)
        session.registered = True
        models = cli.parse_models(verify.stdout)
        if models:
            cli.store_models(models)
        else:
            log.warning("Aus der Ausgabe der Google-CLI ließen sich keine Modelle lesen")
        # Die Modellnamen stehen nur hier im Log: sie sind die Grundlage für
        # eine spätere feste Liste und enthalten nichts Persönliches.
        log.info(
            "Anmeldung bei Google erfolgreich, Konto „%s“. Verfügbare Modelle:\n%s",
            session.account.label,
            verify.stdout.strip()[:2000],
        )
        if quota_only:
            accounts.mark_exhausted(session.account.id)
            return cli.FEHLER_KONTINGENT
        return None

    @staticmethod
    def _login_failure(output: str) -> str:
        lowered = output.lower()
        if "invalid_grant" in lowered or "token exchange failed" in lowered:
            return FEHLER_CODE_ABGELEHNT
        if "timed out" in lowered:
            return FEHLER_ZEIT
        kind = cli.classify_failure(output)
        if kind == "account":
            return cli.FEHLER_KONTO
        if kind == "quota":
            # Die Anmeldung selbst hat geklappt; nur der Probeauftrag fand kein Kontingent.
            return cli.FEHLER_KONTINGENT
        return FEHLER_ALLGEMEIN


def _without_urls(text: str) -> str:
    """Anmeldeadressen tragen Zufallswerte der laufenden Sitzung; ins Log gehören sie nicht."""
    return re.sub(r"https://accounts\.google\.com/\S+", "<Anmeldeadresse>", text)


# Eine Anmeldung je Add-on.
login = GeminiLogin()
