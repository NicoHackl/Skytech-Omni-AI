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
(``gemini_agy_login``) und liegt danach als Datei unter ``/data``, die die CLI
bei jedem Lauf liest und erneuert.
"""

import contextlib
import json
import logging
import os
import re
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
from providers.gemini_agy_accounts import (
    DEFAULT_HOME,  # noqa: F401  (hier wieder ausgegeben, siehe Tests)
    HOME_ENV,  # noqa: F401
    TOKEN_BACKUP_SUFFIX,  # noqa: F401
    TOKEN_FILE_NAME,  # noqa: F401
    WORKSPACE_NAME,  # noqa: F401
    Account,
    backup_path,
    base_home,
    list_accounts,
    mark_exhausted,
    mark_needs_login,
    mark_ok,
    next_try_time,
    read_token_file,
    ready_accounts,
    state_dir,
    token_path,
    workspace_dir,
)
from providers.gemini_provider import GEMINI_MODELS

log = logging.getLogger("omniai.gemini_agy")

# Die CLI kennt ihre Modelle nur mit Anmeldung (``agy models``); eine feste
# Liste wäre geraten. Das Auswahlfeld in config.yaml kann deshalb nur „auto“
# enthalten, ein Modell lässt sich pro Anfrage über das Feld „model“ setzen.
GEMINI_AGY_MODELS: list[str] = []

# Sentinel-Wert aus der Add-on-Konfiguration. Er steht für „kein Modell
# erzwingen“ und wird wie ein leeres Feld behandelt.
AUTO_MODEL = "auto"

AGY_BINARY = "agy"

# Orte und Konten (Anmeldung, Zustand, Arbeitsbereich je Konto) stehen in
# ``gemini_agy_accounts``.
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
    "Google Gemini (AGY) ist nicht angemeldet. Bitte in den Einstellungen unter "
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
    "Google Gemini (AGY) ist in diesem Add-on nicht verfügbar. Das Add-on wurde "
    "vermutlich unvollständig gebaut — bitte neu installieren."
)

FEHLER_CLI_ABGEBROCHEN = (
    "Google Gemini (AGY) hat die Anfrage nicht beantwortet. Bitte die Anfrage erneut stellen."
)

FEHLER_ZEITUEBERSCHREITUNG = (
    "Google Gemini (AGY) hat zu lange gebraucht und wurde abgebrochen. Bitte die "
    "Anfrage kürzer fassen oder es später erneut versuchen."
)

FEHLER_BESETZT = (
    "Google Gemini (AGY) bearbeitet gerade eine andere Anfrage. Bitte gleich erneut versuchen."
)

FEHLER_ZU_LANG = "Die Anfrage ist für Google Gemini (AGY) zu lang. Bitte den Text kürzen."

FEHLER_ARBEITSBEREICH = (
    "Google Gemini (AGY) konnte seinen Arbeitsbereich nicht vorbereiten. Bitte "
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
    """Basisverzeichnis; dort liegt das erste Konto, die weiteren in Unterordnern."""
    return base_home()


def agy_env(home: Path | None = None) -> dict:
    """Umgebung für jeden Aufruf der CLI — Lauf wie Anmeldung. ``home`` ist das Konto."""
    env = {key: os.environ[key] for key in PASSTHROUGH_ENV if key in os.environ}
    env["HOME"] = str(home or base_home())
    # Die CLI aktualisiert sich sonst im Hintergrund selbst; die Version im
    # Bild ist festgenagelt (Dockerfile).
    env["AGY_CLI_DISABLE_AUTO_UPDATE"] = "true"
    env.update(FORCED_FILE_STORAGE_ENV)
    return env


def cli_available() -> bool:
    return shutil.which(AGY_BINARY, path=agy_env().get("PATH")) is not None


_read_token_file = read_token_file


def is_signed_in() -> bool:
    """Ist mindestens ein Konto angemeldet? Ob Google sie gelten lässt, zeigt erst ein Lauf."""
    return any(account.signed_in() for account in list_accounts())


def backup_token(home: Path | None = None) -> None:
    """Sichert die Anmeldung eines Kontos, solange sie lesbar ist.

    Die CLI erneuert ihr Zugriffstoken und schreibt die Datei zurück. Bricht ein
    Zeitlimit sie dabei ab, bliebe eine halbe Datei und die Anmeldung wäre weg.
    """
    source = token_path(home)
    if _read_token_file(source) is None:
        return
    target = backup_path(home)
    try:
        shutil.copyfile(source, target)
        target.chmod(0o600)
    except OSError as error:
        log.warning("Sicherung der Google-Anmeldung nicht möglich: %s", error)


def restore_token_if_broken(home: Path | None = None) -> None:
    """Stellt die gesicherte Anmeldung wieder her, wenn die Datei unlesbar ist."""
    source = token_path(home)
    if _read_token_file(source) is not None:
        return
    backup = backup_path(home)
    if _read_token_file(backup) is None:
        return
    try:
        shutil.copyfile(backup, source)
        source.chmod(0o600)
        log.warning("Beschädigte Google-Anmeldung aus der Sicherung wiederhergestellt")
    except OSError as error:
        log.error("Google-Anmeldung nicht wiederherstellbar: %s", error)


def remove_token(home: Path | None = None) -> None:
    """Entfernt die Anmeldung eines Kontos samt Sicherung."""
    for path in (token_path(home), backup_path(home)):
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


def prepare_state(level: str, home: Path | None = None) -> Path:
    """Legt Zustandsordner, Arbeitsbereich und Einstellungen der CLI an.

    Die Einstellungen enthalten die Freigaben der Werkzeuge. Schlägt das
    Schreiben fehl, läuft die CLI nicht: ohne die Regeln gälten ihre
    Standardwerte, und die sind für ein Add-on mit Zugängen unter ``/data``
    nicht gedacht.

    :returns: den Arbeitsbereich.
    :raises RuntimeError: wenn sich Ordner oder Einstellungen nicht anlegen lassen.
    """
    workspace = workspace_dir(home)
    settings_path = state_dir(home) / SETTINGS_FILE_NAME
    try:
        state_dir(home).mkdir(parents=True, exist_ok=True)
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


def snapshot_state(home: Path | None = None) -> dict[str, set[str]]:
    """Merkt sich, was vor einem Lauf im Zustandsordner liegt."""
    state = state_dir(home)
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


def cleanup_state(
    before: dict[str, set[str]], conversation_id: str = "", home: Path | None = None
) -> None:
    """Löscht, was ein Lauf an Gesprächsdaten hinterlassen hat.

    Das Add-on führt keinen Verlauf (docs/architektur.md). Die CLI legt Gespräche
    aber auf der Platte ab; sie sollen den Lauf nicht überdauern. Aufräumen darf
    nie scheitern lassen, was bereits beantwortet ist — Fehler landen im Log.
    """
    state = state_dir(home)
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
        for entry in workspace_dir(home).iterdir():
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


# --- Modelle ------------------------------------------------------------------
# Die CLI nennt ihre Modelle erst nach der Anmeldung (``agy models``). Das Add-on
# merkt sich die Liste in einer Datei neben der Anmeldung, damit Oberfläche und
# Schnittstelle sie sofort zeigen können, auch direkt nach einem Neustart.

MODELS_FILE_NAME = "omniai-gemini-models.json"
# So alt darf die Liste werden, bevor sie beim nächsten Abruf neu geholt wird.
MODELS_MAX_AGE_SEKUNDEN = 6 * 3600
MODELS_TIMEOUT_SEKUNDEN = 30
MAX_MODEL_LABEL = 80
# Stufen eines Modells stehen in Klammern hinter dem Namen, etwa „(High)“. Nennt
# der Aufrufer ein Modell ohne Stufe, bekommt er die erste dieser Reihe, die es gibt.
EFFORT_PREFERENCE = ("medium", "high", "low", "max")
# Wie viele Namen eine Fehlermeldung höchstens aufzählt.
MAX_LISTED_MODELS = 8

_EFFORT_SUFFIX = re.compile(r"\s*\((low|medium|high|xhigh|max)\)\s*$", re.IGNORECASE)
_BULLET = re.compile(r"^(?:[-*•>]|\d+[.)])\s+")
_ANNOTATION = re.compile(
    r"\s*(?:\((?:default|current|selected|recommended)\)"
    r"|\[(?:default|current|selected|recommended)\]|[✓✔*←])\s*$",
    re.IGNORECASE,
)
_COLUMNS = re.compile(r"\s{2,}|\t|\s[|│]\s")
_SKIP_LINE_START = (
    "fetching",
    "available models",
    "error",
    "usage",
    "warning",
    "note",
    "use ",
    "run ",
    "to select",
    "tip",
    "no models",
    "loading",
    "please",
)
_MODEL_LABEL = re.compile(r"^[\w .()\-:/+]{2,80}$")


@dataclass(frozen=True)
class ModelInfo:
    """Ein Modell der CLI: die Bezeichnung für ``--model`` und weitere Namen dafür."""

    label: str
    aliases: tuple[str, ...] = ()


def parse_models(output: str) -> list[ModelInfo]:
    """Liest die Ausgabe von ``agy models``.

    Das Zeilenformat ist nicht zugesichert; deshalb wird tolerant gelesen:
    ab der Überschrift „Available models“ (falls vorhanden), Aufzählungszeichen
    und Vermerke wie „(default)“ entfernt, eine erste Spalte als Bezeichnung,
    weitere Spalten als Nebennamen. Zeilen, die nach einem Satz aussehen,
    zählen nicht. Die Bezeichnung geht später unverändert an ``--model``.
    """
    lines = (output or "").splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower().startswith("available models"):
            lines = lines[index + 1 :]
            break

    found: dict[str, ModelInfo] = {}
    for raw in lines:
        line = _BULLET.sub("", raw.strip())
        while (stripped := _ANNOTATION.sub("", line)) != line:
            line = stripped
        if not line or line.lower().startswith(_SKIP_LINE_START):
            continue
        columns = [column.strip() for column in _COLUMNS.split(line) if column.strip()]
        if not columns:
            continue
        label, aliases = columns[0], columns[1:]
        if (
            label.endswith((":", "."))
            or len(label.split()) > 8
            or not _MODEL_LABEL.match(label)
            or not re.search(r"[A-Za-z]", label)
        ):
            continue
        found.setdefault(
            label, ModelInfo(label, tuple(a for a in aliases if len(a) <= MAX_MODEL_LABEL))
        )
    return list(found.values())


def models_path() -> Path:
    # Eine Liste für alle Konten: sie gehören demselben Tarif (D-024).
    return base_home() / MODELS_FILE_NAME


def load_models() -> tuple[float, list[ModelInfo]]:
    """Die gemerkte Liste und der Zeitpunkt, an dem sie geholt wurde (``0.0`` ohne Liste)."""
    try:
        data = json.loads(models_path().read_text(encoding="utf-8"))
        models = [
            ModelInfo(str(entry["label"]), tuple(str(a) for a in entry.get("aliases", [])))
            for entry in data["models"]
        ]
        return float(data["fetched_at"]), models
    except (OSError, ValueError, KeyError, TypeError):
        return 0.0, []


def store_models(models: list[ModelInfo]) -> None:
    payload = {
        "fetched_at": time.time(),
        "models": [{"label": m.label, "aliases": list(m.aliases)} for m in models],
    }
    try:
        state_dir().mkdir(parents=True, exist_ok=True)
        _write_json_atomic(models_path(), payload)
    except OSError as error:
        log.warning("Modellliste der Google-CLI nicht speicherbar: %s", error)


def clear_models() -> None:
    with contextlib.suppress(OSError):
        models_path().unlink()


def fetch_models_locked(
    fallback: list[ModelInfo], account: Account | None = None
) -> list[ModelInfo]:
    """Fragt die CLI nach ihren Modellen. Nur mit gehaltener ``RUN_LOCK`` aufrufen.

    Gefragt wird ``account``, sonst das erste angemeldete Konto. Schlägt der Abruf
    fehl, bleibt die bisherige Liste (``fallback``): eine verwaiste Liste ist besser
    als gar keine, und die Ursache steht im Log.
    """
    if account is None:
        account = next((a for a in list_accounts() if a.signed_in() and not a.needs_login), None)
    if account is None:
        return fallback
    try:
        workspace = prepare_state(resolve_tool_access(), account.home)
    except RuntimeError:
        return fallback
    before = snapshot_state(account.home)
    try:
        result = run_agy(
            [AGY_BINARY, "models"],
            env=agy_env(account.home),
            cwd=workspace,
            timeout=MODELS_TIMEOUT_SEKUNDEN,
        )
    except OSError as error:
        log.warning("Modelle der Google-CLI nicht abrufbar: %s", error)
        return fallback
    finally:
        cleanup_state(before, home=account.home)

    models = parse_models(result.stdout) or parse_models(f"{result.stdout}\n{result.stderr}")
    if result.returncode == 0 and not result.timed_out and not result.auth_required and models:
        store_models(models)
        log.info("Modelle der Google-CLI: %s", ", ".join(m.label for m in models))
        return models
    log.warning(
        "Keine Modelle von der Google-CLI gelesen (Rückgabecode %s). Ausgabe: %s",
        result.returncode,
        f"{result.stdout}\n{result.stderr}".strip(),
    )
    return fallback


def refresh_models(*, force: bool = False) -> list[ModelInfo]:
    """Die Modelle der CLI — aus der Datei, bei fehlender oder alter Liste frisch geholt.

    Läuft die CLI gerade für eine Anfrage, bleibt die Liste, wie sie ist: auf
    die Sperre wird hier nicht gewartet, denn die Oberfläche fragt oft.
    """
    if not is_signed_in():
        return []
    fetched_at, models = load_models()
    fresh = bool(models) and time.time() - fetched_at < MODELS_MAX_AGE_SEKUNDEN
    if fresh and not force:
        return models
    if not RUN_LOCK.acquire(blocking=False):
        return models
    try:
        return fetch_models_locked(models)
    finally:
        RUN_LOCK.release()


def available_models() -> list[str]:
    """Bezeichnungen für ``GET /models`` und die Oberfläche; leer ohne Anmeldung."""
    return [model.label for model in refresh_models()]


def _unknown_model_message(query: str, models: list[ModelInfo], matches: list[ModelInfo]) -> str:
    families = {_EFFORT_SUFFIX.sub("", m.label).strip() for m in matches}
    if len(families) > 1:
        names = sorted(families)[:MAX_LISTED_MODELS]
        return f"„{query}“ passt auf mehrere Modelle: {', '.join(names)}. Bitte genauer angeben."
    labels = [m.label for m in models][:MAX_LISTED_MODELS]
    more = " …" if len(models) > MAX_LISTED_MODELS else ""
    return (
        f"„{query}“ kennt Google Gemini (AGY) nicht. Zur Auswahl stehen: {', '.join(labels)}{more}."
    )


def pick_model(query: str, models: list[ModelInfo]) -> str:
    """Findet zu einer Eingabe die Bezeichnung, die die CLI versteht.

    Genau wie genannt (Groß- und Kleinschreibung egal) gilt zuerst; sonst reicht
    eine Kurzform, deren Teile alle im Namen vorkommen — „flash-3.8“ findet
    „Gemini 3.8 Flash (Medium)“, „argon-4“ findet „Gemini 4 Argon (Medium)“.
    Gibt es das Modell in mehreren Stufen, gilt die erste aus ``EFFORT_PREFERENCE``,
    sofern die Eingabe keine nennt. Passt die Eingabe auf mehrere Modelle oder auf
    keines, bekommt der Aufrufer die Auswahl genannt.

    :raises UnknownModel: wenn kein eindeutiges Modell passt.
    """
    wanted = query.strip()
    lowered = wanted.lower()
    for model in models:
        if lowered == model.label.lower() or lowered in (a.lower() for a in model.aliases):
            return model.label

    tokens = [token for token in re.split(r"[\s_\-/]+", lowered) if token]

    def contains(model: ModelInfo, token: str) -> bool:
        haystack = " ".join((model.label, *model.aliases)).lower()
        return re.search(rf"(?<![a-z0-9.]){re.escape(token)}(?![a-z0-9.])", haystack) is not None

    matches = [m for m in models if tokens and all(contains(m, t) for t in tokens)]
    families: dict[str, list[ModelInfo]] = {}
    for model in matches:
        families.setdefault(_EFFORT_SUFFIX.sub("", model.label).strip().lower(), []).append(model)
    if len(families) != 1:
        raise UnknownModel(_unknown_model_message(wanted, models, matches))

    variants = next(iter(families.values()))
    for effort in EFFORT_PREFERENCE:
        for model in variants:
            if re.search(rf"\({effort}\)\s*$", model.label, re.IGNORECASE):
                return model.label
    return variants[0].label


class AccountQuotaExhausted(RuntimeError):
    """Das Kontingent dieses Kontos ist aufgebraucht — das nächste Konto ist an der Reihe."""


class AccountAuthExpired(RuntimeError):
    """Google lässt die Anmeldung dieses Kontos nicht mehr gelten."""


class AccountRestricted(RuntimeError):
    """Google erlaubt diesem Konto die Nutzung nicht oder hat den Zugang eingeschränkt."""


def format_retry_time(timestamp: float) -> str:
    """``21:03`` — am selben Tag nur die Uhrzeit, sonst mit Datum (``29.10., 01:15``).

    Die Zone kommt über ``TZ`` aus dem Bild (Berlin) und wird nicht mit angezeigt.
    """
    moment = time.localtime(timestamp)
    today = time.localtime()
    clock = time.strftime("%H:%M", moment)
    if (moment.tm_year, moment.tm_yday) == (today.tm_year, today.tm_yday):
        return clock
    return f"{time.strftime('%d.%m.', moment)}, {clock}"


class GeminiAgyProvider(BaseProvider):
    """Führt Prompts über die Antigravity-CLI aus und nutzt dabei das Google-AI-Pro-Abo."""

    @staticmethod
    def _requested_model(model: str | None) -> str:
        """Was verlangt wurde: die Anfrage, sonst die Option, sonst nichts („die CLI wählt“).

        Ein add-on-weites Standardmodell, das zu einem anderen Anbieter gehört
        (stehengeblieben nach dem Umstellen des Anbieters), wird übergangen.
        """
        chosen = (model or "").strip()
        if chosen and chosen != AUTO_MODEL:
            return chosen
        for name in ("GEMINI_AGY_MODEL", "OMNIAI_MODEL"):
            default = os.environ.get(name, "").strip()
            if not default or default == AUTO_MODEL:
                continue
            if default in {*CLAUDE_MODELS, *CODEX_MODELS, *GEMINI_MODELS}:
                log.warning(
                    "Das Standardmodell gehört zu einem anderen Anbieter und wird übergangen"
                )
                continue
            return default
        return ""

    def _resolve_model(self, model: str | None) -> str:
        """Die Bezeichnung für ``--model`` — aus der gemerkten Liste der CLI, falls es eine gibt.

        Ohne Liste (noch nicht abgerufen) geht die Eingabe unverändert an die CLI;
        sie kennt ihre Modelle und lehnt unbekannte ab.

        :raises UnknownModel: wenn die Liste bekannt ist und kein eindeutiges Modell passt.
        """
        requested = self._requested_model(model)
        if not requested:
            return ""
        _, models = load_models()
        return pick_model(requested, models) if models else requested

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
            _, models = load_models()
            if models:
                return UnknownModel(_unknown_model_message(chosen_model, models, []))
            return UnknownModel(
                f"„{chosen_model}“ kennt Google Gemini (AGY) nicht. Ohne Angabe wählt es selbst."
            )
        if kind == "quota":
            return AccountQuotaExhausted(FEHLER_KONTINGENT)
        if kind == "account":
            return AccountRestricted(FEHLER_KONTO)
        if kind == "auth":
            return AccountAuthExpired(FEHLER_ANMELDUNG_ABGELAUFEN)
        return RuntimeError(FEHLER_CLI_ABGEBROCHEN)

    def _evaluate(self, result: AgyResult, chosen_model: str) -> dict:
        if result.timed_out:
            raise ProviderTimeout(FEHLER_ZEITUEBERSCHREITUNG)
        if result.auth_required:
            log.error("Die Google-CLI verlangt eine neue Anmeldung")
            raise AccountAuthExpired(FEHLER_ANMELDUNG_ABGELAUFEN)

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
        # Kennt das Add-on die Modelle noch nicht (etwa nach einem Update), holt es
        # sie unter der Sperre, bevor es das gewünschte Modell auflöst.
        needs_models = bool(chosen_model) and not load_models()[1]
        full_prompt = self._system_prompt() + "\n\n" + prompt + JSON_INSTRUCTION
        if len(full_prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
            raise RuntimeError(FEHLER_ZU_LANG)

        # Ohne jede Anmeldedatei lohnt das Warten auf die Sperre nicht. Die
        # genaue Prüfung folgt unter der Sperre: ein laufender Lauf kann die
        # Datei gerade neu schreiben und sie nur für einen Augenblick unlesbar
        # machen.
        if not any(account.has_files() for account in list_accounts()):
            log.error("Aufruf ohne Google-Anmeldung abgelehnt")
            raise RuntimeError(FEHLER_NICHT_ANGEMELDET)

        total = float(timeout or TIMEOUT_SEKUNDEN)
        started = time.monotonic()
        if not RUN_LOCK.acquire(timeout=min(total, QUEUE_WAIT_MAX_SEKUNDEN)):
            log.warning("Anfrage wartete vergeblich auf die laufende Google-CLI")
            raise RuntimeError(FEHLER_BESETZT)
        try:
            for account in list_accounts():
                restore_token_if_broken(account.home)
            signed_in = [a for a in list_accounts() if a.signed_in()]
            if not signed_in:
                log.error("Aufruf ohne lesbare Google-Anmeldung abgelehnt")
                raise RuntimeError(FEHLER_NICHT_ANGEMELDET)
            usable = [a for a in signed_in if not a.needs_login]
            if not usable:
                raise AccountAuthExpired(FEHLER_ANMELDUNG_ABGELAUFEN)
            ready = ready_accounts()
            if not ready:
                # Alle Konten warten auf ihren nächsten Versuch: kein Lauf, der nur
                # einen schnellen Fehler brächte.
                raise RuntimeError(self._exhausted_message(len(usable)))
            if needs_models:
                models = fetch_models_locked([], ready[0])
                if models:
                    chosen_model = pick_model(chosen_model, models)
            return self._with_rotation(
                ready, len(usable), full_prompt, chosen_model, total, started
            )
        finally:
            RUN_LOCK.release()

    @staticmethod
    def _exhausted_message(account_count: int) -> str:
        """Satz, wenn kein Konto mehr Kontingent hat; bei mehreren mit dem nächsten Versuch."""
        retry = next_try_time()
        if account_count <= 1 or retry is None:
            return FEHLER_KONTINGENT
        return (
            "Bei allen angemeldeten Google-Konten ist das Kontingent aufgebraucht. "
            f"Der nächste Versuch ist um {format_retry_time(retry)} möglich."
        )

    def _with_rotation(
        self,
        accounts: list[Account],
        usable_count: int,
        full_prompt: str,
        chosen_model: str,
        total: float,
        started: float,
    ) -> dict:
        """Läuft mit dem ersten Konto, das Kontingent hat; ist es leer, mit dem nächsten.

        Gewechselt wird nur bei einem aufgebrauchten Kontingent, einer ungültigen
        Anmeldung oder einem eingeschränkten Konto — nie bei einer schlechten
        Antwort. Der Wechsel ist offen und im Log zu sehen; das Add-on verbirgt
        ihn vor Google nicht (D-024).
        """
        quota = restricted = False
        last: Exception | None = None
        for index, account in enumerate(accounts):
            remaining = total - (time.monotonic() - started)
            if remaining < MIN_RUN_SEKUNDEN:
                if index == 0:
                    raise RuntimeError(FEHLER_BESETZT)
                raise ProviderTimeout(FEHLER_ZEITUEBERSCHREITUNG)
            try:
                answer = self._run(account, full_prompt, chosen_model, remaining)
            except AccountQuotaExhausted as error:
                mark_exhausted(account.id)
                log.warning("Konto „%s“: Kontingent aufgebraucht", account.label)
                quota, last = True, error
            except AccountRestricted as error:
                mark_exhausted(account.id, kind="account")
                log.error("Konto „%s“: von Google eingeschränkt", account.label)
                restricted, last = True, error
            except AccountAuthExpired as error:
                mark_needs_login(account.id)
                log.error("Konto „%s“: Anmeldung gilt nicht mehr", account.label)
                last = error
            else:
                mark_ok(account.id)
                return answer
            if index + 1 < len(accounts):
                log.info("Wechsel auf das nächste Google-Konto")

        if quota and (usable_count > 1 or len(accounts) > 1):
            raise RuntimeError(self._exhausted_message(usable_count))
        if restricted and not quota:
            raise AccountRestricted(FEHLER_KONTO)
        assert last is not None
        raise last

    def _run(self, account: Account, full_prompt: str, chosen_model: str, remaining: float) -> dict:
        level = resolve_tool_access()
        workspace = prepare_state(level, account.home)
        before = snapshot_state(account.home)

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
            "Anfrage an Google Gemini (AGY), Konto: %s, Modell: %s, Werkzeuge: %s",
            account.label,
            chosen_model or "Vorgabe der CLI",
            level,
        )

        conversation_id = ""
        try:
            try:
                result = run_agy(
                    command,
                    env=agy_env(account.home),
                    cwd=workspace,
                    timeout=remaining,
                    watch_auth=True,
                )
            except FileNotFoundError as error:
                log.error("Die Google-CLI wurde im Container nicht gefunden: %s", error)
                raise RuntimeError(FEHLER_CLI_FEHLT) from error
            envelope = parse_envelope(result.stdout)
            if envelope is not None:
                conversation_id = str(envelope.get("conversation_id") or "")
            answer = self._evaluate(result, chosen_model)
            backup_token(account.home)
            return answer
        finally:
            cleanup_state(before, conversation_id, account.home)
