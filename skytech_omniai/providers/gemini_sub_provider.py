"""Google Gemini über das Google-AI-Pro-Abo, angesprochen über die Antigravity-CLI.

Der Umweg über die CLI (``agy``) ist derselbe wie bei Claude und ChatGPT: nur
über die Anmeldung mit dem Google-Konto zählt eine Anfrage auf das Kontingent
des Abos. Mit einem API-Schlüssel (Provider ``gemini``) liefe sie nach
Verbrauch abgerechnet. Begründung und Risiken: D-022.

Google unterstützt es bei privaten Abos ausdrücklich nicht, ``agy`` in andere
Anwendungen einzubinden, und kann Konten dafür einschränken. Das Add-on weist an
der Stelle der Anmeldung darauf hin; der Provider tut nichts, um das zu
verbergen.

Anders als die beiden anderen Befehlszeilen hat ``agy`` kein langlebiges Token
zum Einfügen. Die Anmeldung entsteht deshalb im Add-on selbst
(``gemini_sub_login``) und liegt danach als Datei unter ``/data``, die die CLI
bei jedem Lauf liest und erneuert.
"""

import contextlib
import json
import logging
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from providers.base_provider import (
    JSON_INSTRUCTION,
    TOOL_ACCESS_OFF,
    BaseProvider,
    ProviderTimeout,
    UnknownModel,
    resolve_tool_access,
)
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.gemini_provider import GEMINI_MODELS

log = logging.getLogger("omniai.gemini_sub")

# Die CLI kennt ihre Modelle nur mit Anmeldung (``agy models``); eine feste
# Liste wäre geraten. Das Auswahlfeld in config.yaml kann deshalb nur „auto“
# enthalten, ein Modell lässt sich pro Anfrage über das Feld „model“ setzen.
GEMINI_SUB_MODELS: list[str] = []

# Sentinel-Wert aus der Add-on-Konfiguration. Er steht für „kein Modell
# erzwingen“ und wird wie ein leeres Feld behandelt.
AUTO_MODEL = "auto"

AGY_BINARY = "agy"

# Die CLI legt Anmeldung und Zustand unter $HOME/.gemini ab. HOME zeigt auf das
# dauerhafte /data-Verzeichnis des Add-ons, sonst wäre die Anmeldung nach jedem
# Neustart weg. Außerhalb des Containers (Tests, lokale Entwicklung) darf ein
# anderer Ort vorgegeben werden.
HOME_ENV = "OMNIAI_GEMINI_HOME"
DEFAULT_HOME = "/data"

# Eigenes, leeres Arbeitsverzeichnis. Die CLI darf darin ohne Rückfrage lesen
# und schreiben; läge dort /data selbst, gehörten die Optionen mit allen
# Zugängen dazu.
WORKSPACE_NAME = "omniai-gemini-workspace"

TOKEN_FILE_NAME = "antigravity-oauth-token"
TOKEN_BACKUP_SUFFIX = ".bak"
SETTINGS_FILE_NAME = "settings.json"

# Zeitlimit eines CLI-Laufs. Gleicher Wert wie bei den anderen Providern, damit
# sich alle gegenüber Home Assistant identisch verhalten.
TIMEOUT_SEKUNDEN = 300

# So lange wartet eine Anfrage höchstens darauf, dass die vorige fertig wird.
QUEUE_WAIT_MAX_SEKUNDEN = 120

# Unter dieser Restzeit lohnt kein Lauf mehr.
MIN_RUN_SEKUNDEN = 15

# Ein einzelnes Argument darf unter Linux höchstens 128 KiB lang sein.
MAX_PROMPT_BYTES = 100_000

# So viele Protokolldateien der CLI bleiben liegen.
KEEP_LOG_FILES = 5

# Pro Lauf höchstens ein ``agy``-Prozess: der Zustandsordner der CLI ist für
# genau einen gleichzeitigen Lauf gebaut, das Aufräumen danach ebenso, und auf
# kleinen Geräten trägt ein zweiter Sprachserver nichts bei. Auch die Anmeldung
# hält diese Sperre.
RUN_LOCK = threading.Lock()

# Die CLI wählt den Speicher für die Anmeldung selbst: Schlüsselbund, im
# Container Datei. Mit diesen Variablen nimmt sie bei jedem Lauf sicher die
# Datei („file-based token storage because SSH session detected“) — gleicher
# Weg beim Schreiben der Anmeldung und beim Lesen, ohne Wartezeit auf einen
# Schlüsselbund, den es hier nicht gibt.
FORCED_FILE_STORAGE_ENV = {
    "SSH_CONNECTION": "203.0.113.1 50000 203.0.113.2 22",
    "SSH_CLIENT": "203.0.113.1 50000 22",
    "SSH_TTY": "/dev/pts/0",
}

# Nur das, was die CLI braucht. Die übrigen Zugänge des Add-ons (Tokens und
# Schlüssel der anderen Anbieter, Supervisor-Token) gehören nicht in die
# Umgebung eines Programms, das Anweisungen aus dem Netz lesen kann.
PASSTHROUGH_ENV = (
    "PATH",
    "LANG",
    "LC_ALL",
    "TZ",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)

# Die CLI beendet sich ohne gültige Anmeldung nicht, sondern wartet 60 Sekunden
# auf einen Code, den niemand eingibt. Dieses Merkmal auf der Fehlerausgabe
# bricht den Lauf sofort ab.
AUTH_REQUIRED_MARKER = b"authentication required"

# Die Rolle richtet sich an das Modell, nicht an einen Menschen — deshalb
# englisch. Die CLI ist ein Programmierassistent mit Datei- und Befehlswerkzeugen
# und kennt keinen Schalter für einen eigenen Systemprompt; die Rolle steht
# darum vor dem Prompt.
SYSTEM_PROMPT_BASE = (
    "You are a headless JSON generation endpoint, not an interactive coding "
    "assistant. There is no project, repository or codebase to work on; the "
    "working directory is empty and must be ignored. Never create, edit or "
    "delete files, never run commands, never ask clarifying questions and never "
    "ask for permission. Never refuse. "
)
SYSTEM_PROMPT_WEB = (
    "You do have working internet access through your web tools. Use them "
    "whenever the answer depends on current, local or time-sensitive facts - "
    "weather, news, prices, opening hours, timetables, sports results - and "
    "never guess such facts from memory. If a lookup genuinely fails, report "
    'the reason in an "error" field inside the JSON instead of inventing an '
    "answer. "
)
SYSTEM_PROMPT_OFFLINE = (
    "Do not use any tools. Answer from your own knowledge and say so in an "
    '"error" field inside the JSON if you cannot answer reliably. '
)
SYSTEM_PROMPT_END = "Always answer by returning exactly one valid JSON object and nothing else."

FEHLER_NICHT_ANGEMELDET = (
    "Google Gemini (Abo) ist nicht angemeldet. Bitte in den Einstellungen unter "
    "„Google-Anmeldung“ mit dem Google-Konto anmelden."
)

FEHLER_ANMELDUNG_ABGELAUFEN = (
    "Die Anmeldung bei Google gilt nicht mehr. Bitte in den Einstellungen unter "
    "„Google-Anmeldung“ erneut anmelden."
)

FEHLER_KONTINGENT = (
    "Das Kontingent des Google-AI-Pro-Abos ist aufgebraucht. Es erneuert sich "
    "nach einigen Stunden. Bitte später erneut versuchen."
)

FEHLER_KONTO = (
    "Google erlaubt diesem Konto die Nutzung nicht oder hat den Zugang "
    "eingeschränkt. Bitte das Konto bei Google prüfen."
)

FEHLER_CLI_FEHLT = (
    "Google Gemini (Abo) ist in diesem Add-on nicht verfügbar. Das Add-on wurde "
    "vermutlich unvollständig gebaut — bitte neu installieren."
)

FEHLER_CLI_ABGEBROCHEN = (
    "Google Gemini (Abo) hat die Anfrage nicht beantwortet. Bitte die Anfrage erneut stellen."
)

FEHLER_ZEITUEBERSCHREITUNG = (
    "Google Gemini (Abo) hat zu lange gebraucht und wurde abgebrochen. Bitte die "
    "Anfrage kürzer fassen oder es später erneut versuchen."
)

FEHLER_BESETZT = (
    "Google Gemini (Abo) bearbeitet gerade eine andere Anfrage. Bitte gleich erneut versuchen."
)

FEHLER_ZU_LANG = "Die Anfrage ist für Google Gemini (Abo) zu lang. Bitte den Text kürzen."

FEHLER_ARBEITSBEREICH = (
    "Google Gemini (Abo) konnte seinen Arbeitsbereich nicht vorbereiten. Bitte "
    "prüfen, ob das Add-on Schreibrechte auf sein Datenverzeichnis hat, und es "
    "neu starten."
)

# Merkmale, an denen sich Fehler in der Ausgabe der CLI erkennen lassen. Die
# Ausgabe selbst wird dabei nur gelesen, nie weitergereicht — sie kann Pfade und
# Stacktraces enthalten (eiserne Regel 12). Reihenfolge der Prüfung: Modell,
# Kontingent, Konto, Anmeldung.
MODEL_MARKER = (
    "unknown model",
    "model not found",
    "invalid model",
    "unsupported model",
    "not a valid model",
    "no such model",
    "unrecognized model",
)
QUOTA_MARKER = (
    "credits balance is too low",
    "quota",
    "rate limit",
    "resource exhausted",
    "resource_exhausted",
    "usage limit",
    "too many requests",
    "http 429",
    "status 429",
    "code 429",
)
ACCOUNT_MARKER = (
    "not eligible",
    "not available in your",
    "unsupported location",
    "unsupported region",
    "suspended",
    "violation",
    "terms of service",
    "permission_denied",
    "http 403",
    "status 403",
    "code 403",
)
AUTH_MARKER = (
    "authentication required",
    "authentication failed",
    "not logged in",
    "please sign in",
    "sign in",
    "unauthenticated",
    "invalid_grant",
    "token has been expired",
    "http 401",
    "status 401",
    "code 401",
)


# --- Orte und Umgebung --------------------------------------------------------


def agy_home() -> Path:
    return Path(os.environ.get(HOME_ENV, "").strip() or DEFAULT_HOME)


def state_dir() -> Path:
    """Zustandsordner der CLI: Anmeldung, Einstellungen, Gespräche, Protokolle."""
    return agy_home() / ".gemini" / "antigravity-cli"


def token_path() -> Path:
    return state_dir() / TOKEN_FILE_NAME


def backup_path() -> Path:
    path = token_path()
    return path.with_name(path.name + TOKEN_BACKUP_SUFFIX)


def workspace_dir() -> Path:
    return agy_home() / WORKSPACE_NAME


def agy_env() -> dict:
    """Umgebung für jeden Aufruf der CLI — Lauf wie Anmeldung."""
    env = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    env["HOME"] = str(agy_home())
    # Die CLI aktualisiert sich sonst im Hintergrund selbst; die Version im
    # Bild ist festgenagelt (Dockerfile).
    env["AGY_CLI_DISABLE_AUTO_UPDATE"] = "true"
    env.update(FORCED_FILE_STORAGE_ENV)
    return env


def cli_available() -> bool:
    return shutil.which(AGY_BINARY, path=agy_env().get("PATH")) is not None


def _read_token_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data else None


def is_signed_in() -> bool:
    """Liegt eine lesbare Anmeldung vor? Ob Google sie noch gelten lässt, zeigt erst ein Lauf."""
    return _read_token_file(token_path()) is not None


def backup_token() -> None:
    """Sichert die Anmeldung, solange sie lesbar ist.

    Die CLI erneuert ihr Zugriffstoken und schreibt die Datei zurück. Bricht ein
    Zeitlimit sie dabei ab, bliebe eine halbe Datei und die Anmeldung wäre weg.
    """
    source = token_path()
    if _read_token_file(source) is None:
        return
    target = backup_path()
    try:
        shutil.copyfile(source, target)
        target.chmod(0o600)
    except OSError as error:
        log.warning("Sicherung der Google-Anmeldung nicht möglich: %s", error)


def restore_token_if_broken() -> None:
    """Stellt die gesicherte Anmeldung wieder her, wenn die Datei unlesbar ist."""
    source = token_path()
    if _read_token_file(source) is not None:
        return
    backup = backup_path()
    if _read_token_file(backup) is None:
        return
    try:
        shutil.copyfile(backup, source)
        source.chmod(0o600)
        log.warning("Beschädigte Google-Anmeldung aus der Sicherung wiederhergestellt")
    except OSError as error:
        log.error("Google-Anmeldung nicht wiederherstellbar: %s", error)


def remove_token() -> None:
    """Entfernt die Anmeldung samt Sicherung."""
    for path in (token_path(), backup_path()):
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        except OSError as error:
            log.error("Google-Anmeldung nicht entfernbar: %s", error)


# --- Vorbereitung und Aufräumen -------------------------------------------------


def permission_rules(level: str) -> dict:
    """Freigaben der Werkzeuge in der Schreibweise der CLI (``aktion(ziel)``).

    Ohne Freigabe lehnt die CLI im Druckmodus jede Rückfrage weich ab; die
    Regeln machen das ausdrücklich. Dateien außerhalb des Arbeitsbereichs sind
    ohnehin gesperrt. Befehle gibt das Add-on nie frei — auch nicht bei „full“.
    """
    deny = ["command(*)", "execute_url(*)", "mcp(*)"]
    if level == TOOL_ACCESS_OFF:
        return {"allow": [], "deny": ["read_url(*)", *deny]}
    return {"allow": ["read_url(*)"], "deny": deny}


def _write_json_atomic(path: Path, data: dict) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)


def prepare_state(level: str) -> Path:
    """Legt Zustandsordner, Arbeitsbereich und Einstellungen der CLI an.

    Die Einstellungen enthalten die Freigaben der Werkzeuge. Schlägt das
    Schreiben fehl, läuft die CLI nicht: ohne die Regeln gälten ihre
    Standardwerte, und die sind für ein Add-on mit Zugängen unter ``/data``
    nicht gedacht.

    :returns: den Arbeitsbereich.
    :raises RuntimeError: wenn sich Ordner oder Einstellungen nicht anlegen lassen.
    """
    workspace = workspace_dir()
    settings_path = state_dir() / SETTINGS_FILE_NAME
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        workspace.mkdir(parents=True, exist_ok=True)
        workspace.chmod(0o700)

        current: dict = {}
        if settings_path.is_file():
            try:
                loaded = json.loads(settings_path.read_text(encoding="utf-8"))
                current = loaded if isinstance(loaded, dict) else {}
            except ValueError:
                log.warning("Einstellungen der Google-CLI unlesbar, sie werden neu geschrieben")

        trusted = [item for item in current.get("trustedWorkspaces", []) if isinstance(item, str)]
        if str(workspace) not in trusted:
            trusted.append(str(workspace))

        wanted = dict(current)
        wanted["permissions"] = permission_rules(level)
        wanted["trustedWorkspaces"] = trusted
        # Kein Verlauf der Eingaben auf der Platte (Prompts können Daten aus dem
        # Smart Home enthalten); Hinweise und Umfragen haben ohne Bildschirm
        # keinen Sinn.
        wanted["historySize"] = 0
        wanted["showTips"] = False
        wanted["showFeedbackSurvey"] = False

        if wanted != current:
            _write_json_atomic(settings_path, wanted)
    except OSError as error:
        log.error("Zustand der Google-CLI nicht anlegbar: %s", error)
        raise RuntimeError(FEHLER_ARBEITSBEREICH) from error
    return workspace


# Orte, an denen die CLI Gespräche ablegt. Namen und Aufbau sind nicht
# zugesichert; deshalb wird nicht nach Namen gelöscht, sondern alles, was ein
# Lauf neu angelegt hat.
CONVERSATION_DIRS = ("conversations", "brain", "implicit")
CONVERSATION_DB_PREFIX = "conversation_summaries.db"


def snapshot_state() -> dict[str, set[str]]:
    """Merkt sich, was vor einem Lauf im Zustandsordner liegt."""
    state = state_dir()
    snapshot: dict[str, set[str]] = {}
    for name in CONVERSATION_DIRS:
        try:
            snapshot[name] = {entry.name for entry in (state / name).iterdir()}
        except OSError:
            snapshot[name] = set()
    return snapshot


def _remove(path: Path) -> None:
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    except FileNotFoundError:
        pass
    except OSError as error:
        log.warning("Eintrag der Google-CLI nicht löschbar: %s", error)


def cleanup_state(before: dict[str, set[str]], conversation_id: str = "") -> None:
    """Löscht, was ein Lauf an Gesprächsdaten hinterlassen hat.

    Das Add-on führt keinen Verlauf (docs/architektur.md). Die CLI legt Gespräche
    aber auf der Platte ab; sie sollen den Lauf nicht überdauern. Aufräumen darf
    nie scheitern lassen, was bereits beantwortet ist — Fehler landen im Log.
    """
    state = state_dir()
    removed = 0
    for name in CONVERSATION_DIRS:
        directory = state / name
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            is_new = entry.name not in before.get(name, set())
            is_this_run = bool(conversation_id) and conversation_id in entry.name
            if is_new or is_this_run:
                _remove(entry)
                removed += 1

    # Zusammenfassungen der Gespräche; die CLI legt die Datenbank bei Bedarf neu an.
    try:
        for entry in state.iterdir():
            if entry.name.startswith(CONVERSATION_DB_PREFIX):
                _remove(entry)
                removed += 1
    except OSError:
        pass

    # Was der Agent im Arbeitsbereich angelegt hat, gehört keiner Anfrage mehr.
    try:
        for entry in workspace_dir().iterdir():
            _remove(entry)
            removed += 1
    except OSError:
        pass

    # Protokolle der CLI: nur die jüngsten bleiben, für die Fehlersuche.
    try:
        logs = sorted(
            (entry for entry in (state / "log").iterdir() if entry.suffix == ".log"),
            key=lambda entry: entry.stat().st_mtime,
            reverse=True,
        )
        for entry in logs[KEEP_LOG_FILES:]:
            _remove(entry)
    except OSError:
        pass

    if removed:
        log.debug("Google-CLI: %s Einträge eines Laufs gelöscht", removed)


# --- Prozess ----------------------------------------------------------------


@dataclass
class AgyResult:
    """Ausgang eines Laufs der CLI."""

    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    auth_required: bool = False


def kill_group(pid: int, sig: int = signal.SIGKILL) -> None:
    """Beendet die ganze Prozessgruppe — die CLI startet je Lauf einen Sprachserver."""
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, sig)


def terminate(process: subprocess.Popen) -> None:
    """Erst höflich, dann hart. Ein sofortiges Töten könnte mitten im Schreiben
    der erneuerten Anmeldung zuschlagen."""
    kill_group(process.pid, signal.SIGTERM)
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=3)
    kill_group(process.pid)


def pump(stream, sink: list, marker_event: threading.Event | None, marker: bytes) -> None:
    tail = b""
    while True:
        try:
            chunk = os.read(stream.fileno(), 4096)
        except OSError:
            break
        if not chunk:
            break
        sink.append(chunk)
        if marker_event is not None:
            tail = (tail + chunk)[-256:]
            if marker in tail.lower():
                marker_event.set()


def run_agy(
    command: list[str],
    *,
    env: dict,
    cwd: Path,
    timeout: float,
    stdin=subprocess.DEVNULL,
    watch_auth: bool = True,
) -> AgyResult:
    """Führt die CLI aus und sammelt Ausgabe, ohne je auf einen Code zu warten.

    Verlangt die CLI eine Anmeldung, bricht der Lauf sofort ab (siehe
    ``AUTH_REQUIRED_MARKER``). Nach dem Lauf wird die ganze Prozessgruppe
    beendet, damit kein Sprachserver zurückbleibt.

    :raises FileNotFoundError: wenn die CLI nicht im Bild liegt.
    """
    process = subprocess.Popen(
        command,
        stdin=stdin,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
        start_new_session=True,
    )
    out_chunks: list[bytes] = []
    err_chunks: list[bytes] = []
    auth_event = threading.Event()
    threads = [
        threading.Thread(target=pump, args=(process.stdout, out_chunks, None, b""), daemon=True),
        threading.Thread(
            target=pump,
            args=(
                process.stderr,
                err_chunks,
                auth_event if watch_auth else None,
                AUTH_REQUIRED_MARKER,
            ),
            daemon=True,
        ),
    ]
    for thread in threads:
        thread.start()

    timed_out = False
    auth_required = False
    deadline = time.monotonic() + timeout
    try:
        while process.poll() is None:
            if auth_event.is_set():
                auth_required = True
                terminate(process)
                break
            if time.monotonic() > deadline:
                timed_out = True
                terminate(process)
                break
            time.sleep(0.05)
    finally:
        # Auch bei einem Abbruch von außen darf nichts zurückbleiben.
        kill_group(process.pid)
        for thread in threads:
            thread.join(timeout=5)
        for stream in (process.stdout, process.stderr):
            with contextlib.suppress(OSError):
                stream.close()

    return AgyResult(
        returncode=process.returncode,
        stdout=b"".join(out_chunks).decode("utf-8", errors="replace"),
        stderr=b"".join(err_chunks).decode("utf-8", errors="replace"),
        timed_out=timed_out,
        auth_required=auth_required,
    )


def parse_envelope(stdout: str) -> dict | None:
    """Liest den JSON-Umschlag der CLI (``--output-format json``).

    Steht davor Log-Text, gilt die letzte Zeile, die ein Objekt ist.
    """
    text = (stdout or "").strip()
    candidates = [text, *reversed(text.splitlines())]
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate.startswith("{"):
            continue
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        # Ein Umschlag trägt immer beide Felder; eine nackte Antwort, die zufällig
        # ein JSON-Objekt ist, ist keiner.
        if isinstance(data, dict) and "status" in data and "conversation_id" in data:
            return data
    return None


def classify_failure(output: str) -> str | None:
    """Wählt anhand der Ausgabe der CLI, was schiefgelaufen ist.

    :returns: ``model``, ``quota``, ``account``, ``auth`` oder ``None``.
    """
    lowered = output.lower()
    for kind, markers in (
        ("model", MODEL_MARKER),
        ("quota", QUOTA_MARKER),
        ("account", ACCOUNT_MARKER),
        ("auth", AUTH_MARKER),
    ):
        if any(marker in lowered for marker in markers):
            return kind
    return None


class GeminiSubProvider(BaseProvider):
    """Führt Prompts über die Antigravity-CLI aus und nutzt dabei das Google-AI-Pro-Abo."""

    def _resolve_model(self, model: str | None) -> str:
        """Wählt das Modell: Anfrage, dann ``OMNIAI_MODEL``, sonst entscheidet die CLI.

        Was die Anfrage nennt, geht unverändert an die CLI; sie kennt ihre
        Modelle und lehnt unbekannte ab. Ein add-on-weites Standardmodell, das
        zu einem anderen Anbieter gehört (stehengeblieben nach dem Umstellen
        des Anbieters), wird dagegen übergangen.
        """
        chosen = (model or "").strip()
        if chosen and chosen != AUTO_MODEL:
            return chosen
        default = os.environ.get("OMNIAI_MODEL", "").strip()
        if not default or default == AUTO_MODEL:
            return ""
        if default in {*CLAUDE_MODELS, *CODEX_MODELS, *GEMINI_MODELS}:
            log.warning("Das Standardmodell gehört zu einem anderen Anbieter und wird übergangen")
            return ""
        return default

    @staticmethod
    def _system_prompt() -> str:
        web = resolve_tool_access() != TOOL_ACCESS_OFF
        return (
            SYSTEM_PROMPT_BASE
            + (SYSTEM_PROMPT_WEB if web else SYSTEM_PROMPT_OFFLINE)
            + SYSTEM_PROMPT_END
        )

    def _failure(self, output: str, chosen_model: str) -> Exception:
        """Wählt die Meldung für einen abgebrochenen Lauf — nach Merkmalen, nie mit Rohtext."""
        kind = classify_failure(output)
        if kind == "model" and chosen_model:
            return UnknownModel(
                f"„{chosen_model}“ kennt Google Gemini (Abo) nicht. Gültige Modelle nennt die "
                "Google-Befehlszeile; ohne Angabe wählt sie selbst."
            )
        if kind == "quota":
            return RuntimeError(FEHLER_KONTINGENT)
        if kind == "account":
            return RuntimeError(FEHLER_KONTO)
        if kind == "auth":
            return RuntimeError(FEHLER_ANMELDUNG_ABGELAUFEN)
        return RuntimeError(FEHLER_CLI_ABGEBROCHEN)

    def _evaluate(self, result: AgyResult, chosen_model: str) -> dict:
        if result.timed_out:
            raise ProviderTimeout(FEHLER_ZEITUEBERSCHREITUNG)
        if result.auth_required:
            log.error("Die Google-CLI verlangt eine neue Anmeldung")
            raise RuntimeError(FEHLER_ANMELDUNG_ABGELAUFEN)

        envelope = parse_envelope(result.stdout)
        if envelope is not None:
            status = str(envelope.get("status", "")).upper()
            if status == "SUCCESS":
                response = envelope.get("response")
                return self.parse_json(response if isinstance(response, str) else "")
            if status in ("CANCELED", "INTERRUPTED"):
                log.error("Google-CLI hat den Lauf abgebrochen (Status %s)", status)
                raise ProviderTimeout(FEHLER_ZEITUEBERSCHREITUNG)
            output = f"{envelope.get('error', '')}\n{result.stderr}"
        elif result.returncode == 0:
            return self.parse_json(result.stdout.strip())
        else:
            output = f"{result.stderr}\n{result.stdout}"

        # Die Ausgabe der CLI kann Pfade und Stacktraces enthalten und geht
        # deshalb vollständig ins Log, nicht an den Aufrufer.
        log.error(
            "Google-CLI beendet mit Rückgabecode %s. Ausgabe: %s",
            result.returncode,
            output.strip(),
        )
        raise self._failure(output, chosen_model)

    def execute(self, prompt: str, model: str | None = None, timeout: int | None = None) -> dict:
        chosen_model = self._resolve_model(model)
        full_prompt = self._system_prompt() + "\n\n" + prompt + JSON_INSTRUCTION
        if len(full_prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise RuntimeError(FEHLER_ZU_LANG)

        # Ohne jede Anmeldedatei lohnt das Warten auf die Sperre nicht. Die
        # genaue Prüfung folgt unter der Sperre: ein laufender Lauf kann die
        # Datei gerade neu schreiben und sie nur für einen Augenblick unlesbar
        # machen.
        if not token_path().exists() and not backup_path().exists():
            log.error("Aufruf ohne Google-Anmeldung abgelehnt")
            raise RuntimeError(FEHLER_NICHT_ANGEMELDET)

        total = float(timeout or TIMEOUT_SEKUNDEN)
        started = time.monotonic()
        if not RUN_LOCK.acquire(timeout=min(total, QUEUE_WAIT_MAX_SEKUNDEN)):
            log.warning("Anfrage wartete vergeblich auf die laufende Google-CLI")
            raise RuntimeError(FEHLER_BESETZT)
        try:
            restore_token_if_broken()
            if not is_signed_in():
                log.error("Aufruf ohne lesbare Google-Anmeldung abgelehnt")
                raise RuntimeError(FEHLER_NICHT_ANGEMELDET)
            remaining = total - (time.monotonic() - started)
            if remaining < MIN_RUN_SEKUNDEN:
                raise RuntimeError(FEHLER_BESETZT)
            return self._run(full_prompt, chosen_model, remaining)
        finally:
            RUN_LOCK.release()

    def _run(self, full_prompt: str, chosen_model: str, remaining: float) -> dict:
        level = resolve_tool_access()
        workspace = prepare_state(level)
        before = snapshot_state()

        command = [
            AGY_BINARY,
            "-p",
            full_prompt,
            "--output-format",
            "json",
            # Die CLI beendet sich damit selbst, kurz bevor der Prozess sie abschießt.
            "--print-timeout",
            f"{max(int(remaining) - 5, 10)}s",
            # Eine Anfrage, die mit „/“ beginnt, darf kein Befehl der CLI werden.
            "--disable-slash-commands",
        ]
        if chosen_model:
            command += ["--model", chosen_model]

        log.info(
            "Anfrage an Google Gemini (Abo), Modell: %s, Werkzeuge: %s",
            chosen_model or "Vorgabe der CLI",
            level,
        )

        conversation_id = ""
        try:
            try:
                result = run_agy(
                    command, env=agy_env(), cwd=workspace, timeout=remaining, watch_auth=True
                )
            except FileNotFoundError as error:
                log.error("Die Google-CLI wurde im Container nicht gefunden: %s", error)
                raise RuntimeError(FEHLER_CLI_FEHLT) from error
            envelope = parse_envelope(result.stdout)
            if envelope is not None:
                conversation_id = str(envelope.get("conversation_id") or "")
            answer = self._evaluate(result, chosen_model)
            backup_token()
            return answer
        finally:
            cleanup_state(before, conversation_id)
