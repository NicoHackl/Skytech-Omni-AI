"""Claude über das Pro/Max-Abo, angesprochen über die Claude-Code-CLI.

Der Umweg über die CLI ist der Kern des Add-ons: er nutzt das rollierende
Limit des Web-Abos statt eines metered abgerechneten API-Schlüssels.
"""

import logging
import os
import subprocess

from providers.base_provider import JSON_INSTRUCTION, BaseProvider

log = logging.getLogger("omniai.claude")

# Die Claude-Code-CLI verhält sich von Haus aus wie ein interaktiver
# Programmierassistent: sie liest Projektkontext aus dem Arbeitsverzeichnis und
# stellt Rückfragen. In dieser Rolle lehnt sie reine JSON-Aufträge ab. Der
# folgende Systemprompt schiebt sie in die Rolle eines Endpunkts. Bewusst
# englisch — er richtet sich an das Modell, nicht an einen Menschen.
#
# Der Absatz zu den Web-Werkzeugen ist nicht schmückend: ohne ihn liest das
# Modell „headless endpoint, kein Arbeitsverzeichnis“ als „kein Internet“ und
# lehnt Wetter- oder Nachrichtenfragen pauschal ab, statt die freigegebenen
# Werkzeuge zu benutzen.
SYSTEM_PROMPT = (
    "You are a headless JSON generation endpoint, not an interactive coding "
    "assistant. You have no project, repository or working directory to reason "
    "about. Never ask clarifying questions and never refuse. "
    "You do have working internet access. Use the WebSearch and WebFetch "
    "tools whenever the answer depends on current, local or time-sensitive "
    "facts - weather, news, prices, opening hours, timetables, sports "
    "results. Never claim that you cannot access the internet and never guess "
    "such facts from memory. If a lookup genuinely fails, report the reason in "
    'an "error" field inside the JSON instead of inventing an answer. '
    "Always answer the user's request by returning exactly one valid JSON "
    "object and nothing else."
)

# Kurzaliasse, die die CLI versteht, in der Reihenfolge des Auswahlfelds im
# Add-on. Vollständige Modell-IDs sind über das Feld „model“ im Rumpf von /ask
# ebenfalls erlaubt.
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]

# Freigabestufen für die Werkzeuge der CLI. Im Headless-Modus („claude -p“) gibt
# es keine interaktive Rückfrage — und ohne ausdrückliche Freigabe lehnt die CLI
# deshalb jedes genehmigungspflichtige Werkzeug automatisch ab, auch WebSearch
# und WebFetch. Es ist also nie etwas blockiert, es war nur nie freigegeben.
TOOL_ACCESS_OFF = "off"  # keine Werkzeuge, Antwort allein aus dem Trainingswissen
TOOL_ACCESS_WEB = "web"  # nur Websuche und Seitenabruf
TOOL_ACCESS_FULL = "full"  # alle Werkzeuge, inklusive Shell- und Dateizugriff

# Vorgabe ist bewusst „web“ und nicht „full“: „full“ erlaubt der CLI auch Shell-
# und Dateizugriff im Container, und dort liegt unter /data das Token des Abos.
# Für Recherchefragen genügt die Websuche. Begründung: D-012.
DEFAULT_TOOL_ACCESS = TOOL_ACCESS_WEB

# Die beiden Werkzeuge, die für eine Recherche nötig sind: WebSearch findet die
# Quelle, WebFetch liest sie aus.
WEB_TOOLS = ["WebSearch", "WebFetch"]

# Zeitlimit eines CLI-Laufs. Gleicher Wert wie beim Gemini-Provider, damit sich
# beide gegenüber Home Assistant identisch verhalten.
TIMEOUT_SEKUNDEN = 300

FEHLER_KEINE_ZUGANGSDATEN = (
    "Für Claude ist kein Zugang hinterlegt. Im Add-on unter „Konfiguration“ das "
    "Feld „claude_oauth_token“ ausfüllen und das Add-on neu starten. Das Token "
    "wird einmalig auf einem Rechner mit Browser erzeugt, indem dort "
    "„claude setup-token“ ausgeführt wird. Alternativ lässt sich unter "
    "„anthropic_api_key“ ein Anthropic-Schlüssel eintragen; der wird nach "
    "Verbrauch abgerechnet und nutzt das Abo nicht."
)

FEHLER_CLI_FEHLT = (
    "Claude ist in diesem Add-on nicht verfügbar. Das Add-on wurde vermutlich "
    "unvollständig gebaut — bitte neu installieren."
)

FEHLER_CLI_ABGEBROCHEN = (
    "Claude hat die Anfrage nicht beantwortet. Bitte prüfen, ob das hinterlegte "
    "Token noch gültig ist, und die Anfrage erneut stellen."
)

FEHLER_ZEITUEBERSCHREITUNG = (
    "Claude hat zu lange gebraucht und wurde abgebrochen. Bitte die Anfrage "
    "kürzer fassen oder es später erneut versuchen."
)

FEHLER_WERKZEUGE_UNTER_ROOT = (
    "Claude verweigert die Werkzeugstufe „Alle Werkzeuge“, weil das Add-on als "
    "Systembenutzer läuft. Im Add-on unter „Konfiguration“ das Feld "
    "„tool_access“ auf „web“ stellen und das Add-on neu starten — Websuche und "
    "Seitenabruf bleiben damit verfügbar."
)

# Merkmale, an denen sich die Verweigerung unter root in der Ausgabe der CLI
# erkennen lässt. Beide Gruppen müssen zutreffen, damit eine beliebige andere
# Fehlermeldung mit dem Wort „permission“ nicht falsch gedeutet wird.
ROOT_MARKER = ("root", "sudo")
PERMISSION_MARKER = ("permission", "bypasspermissions", "skip-permissions")


class ClaudeSubProvider(BaseProvider):
    """Führt Prompts über die Claude-Code-CLI aus und nutzt dabei das Abo des
    Nutzers statt eines metered abgerechneten API-Schlüssels."""

    def __init__(self):
        # Die CLI legt Konfiguration und Anmeldedaten unter $HOME/.claude ab.
        # HOME zeigt deshalb auf das dauerhafte /data-Verzeichnis des Add-ons,
        # damit die Anmeldung einen Neustart übersteht. (Der frühere Weg über
        # XDG_CONFIG_HOME wirkte nicht: die CLI hängt ihren Zustand an HOME.)
        os.environ.setdefault("HOME", "/data")

    @staticmethod
    def resolve_tool_access() -> str:
        """Liest die Werkzeugstufe aus der Umgebung.

        Ein unbekannter oder leerer Wert fällt auf die Vorgabe zurück: ein
        Tippfehler in der Konfiguration soll den Provider nicht lahmlegen.

        Ist bewusst öffentlich — ``app.py`` meldet denselben Wert über
        ``GET /status``, damit Oberfläche und Provider nicht auseinanderlaufen.
        """
        level = os.environ.get("OMNIAI_TOOL_ACCESS", "").strip().lower()
        if level in (TOOL_ACCESS_OFF, TOOL_ACCESS_WEB, TOOL_ACCESS_FULL):
            return level
        if level:
            log.warning(
                "Unbekannte Werkzeugstufe %r, es gilt die Vorgabe %r",
                level,
                DEFAULT_TOOL_ACCESS,
            )
        return DEFAULT_TOOL_ACCESS

    def _tool_access_args(self) -> list:
        """Übersetzt die Werkzeugstufe in Argumente für die CLI."""
        level = self.resolve_tool_access()
        if level == TOOL_ACCESS_OFF:
            return []
        if level == TOOL_ACCESS_WEB:
            # --allowedTools erwartet eine Liste von Namen. Der Aufruf läuft
            # ohne Shell, also ist jeder Name ein eigenes Element.
            return ["--allowedTools", *WEB_TOOLS]
        return ["--permission-mode", "bypassPermissions"]

    def _build_env(self) -> dict:
        """Stellt die Umgebung für den CLI-Aufruf zusammen.

        :raises RuntimeError: wenn weder Abo-Token noch API-Schlüssel gesetzt ist.
        """
        env = os.environ.copy()
        token = env.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
        api_key = env.get("ANTHROPIC_API_KEY", "").strip()
        if not token and not api_key:
            log.error("Aufruf ohne hinterlegte Claude-Zugangsdaten abgelehnt")
            raise RuntimeError(FEHLER_KEINE_ZUGANGSDATEN)
        if self.resolve_tool_access() == TOOL_ACCESS_FULL:
            # Das Add-on läuft als root in einem abgeschotteten Container. Ohne
            # diese Markierung lehnen manche CLI-Fassungen das Umgehen der
            # Berechtigungsabfrage unter root grundsätzlich ab.
            env["IS_SANDBOX"] = "1"
        return env

    def _cli_fehler(self, ausgabe: str) -> str:
        """Wählt die Meldung für einen abgebrochenen CLI-Lauf.

        Die Ausgabe der CLI selbst wird dabei nur **gelesen**, nie
        weitergereicht — sie kann Pfade und Stacktraces enthalten
        (eiserne Regel 12).
        """
        klein = ausgabe.lower()
        wie_root_verweigerung = any(m in klein for m in ROOT_MARKER) and any(
            m in klein for m in PERMISSION_MARKER
        )
        if self.resolve_tool_access() == TOOL_ACCESS_FULL and wie_root_verweigerung:
            return FEHLER_WERKZEUGE_UNTER_ROOT
        return FEHLER_CLI_ABGEBROCHEN

    def _resolve_model(self, model: str | None) -> str:
        """Wählt das Modell: erst die Anfrage, dann das add-on-weite Standardmodell."""
        chosen = (model or "").strip()
        if not chosen:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        return chosen

    def execute(self, prompt: str, model: str | None = None) -> dict:
        env = self._build_env()
        full_prompt = prompt + JSON_INSTRUCTION

        command = ["claude", "-p", full_prompt, "--append-system-prompt", SYSTEM_PROMPT]
        chosen_model = self._resolve_model(model)
        if chosen_model:
            # Die CLI nimmt sowohl Kurzaliasse (sonnet/opus/haiku) als auch
            # vollständige Modell-IDs entgegen.
            command += ["--model", chosen_model]
        command += self._tool_access_args()

        log.info(
            "Anfrage an Claude, Modell: %s, Werkzeuge: %s",
            chosen_model or "Vorgabe der CLI",
            self.resolve_tool_access(),
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEKUNDEN,
                env=env,
                # Aus dem dauerhaften Datenverzeichnis heraus starten, nicht aus
                # dem Quellbaum des Add-ons: sonst liest die CLI eine CLAUDE.md
                # ein und deutet die Anfrage als Programmieraufgabe um.
                cwd="/data",
            )
        except FileNotFoundError as fehler:
            log.error("Die Claude-CLI wurde im Container nicht gefunden: %s", fehler)
            raise RuntimeError(FEHLER_CLI_FEHLT) from fehler
        except subprocess.TimeoutExpired as fehler:
            log.error("Claude-CLI nach %s s abgebrochen", TIMEOUT_SEKUNDEN)
            raise RuntimeError(FEHLER_ZEITUEBERSCHREITUNG) from fehler

        if result.returncode != 0:
            # Die Ausgabe der CLI kann Pfade und Stacktraces enthalten und geht
            # deshalb vollständig ins Log, nicht an den Aufrufer.
            ausgabe = result.stderr.strip() or result.stdout.strip()
            log.error(
                "Claude-CLI beendet mit Rückgabecode %s. Ausgabe: %s",
                result.returncode,
                ausgabe,
            )
            raise RuntimeError(self._cli_fehler(ausgabe))

        return self.parse_json(result.stdout.strip())
