"""Claude über das Pro/Max-Abo, angesprochen über die Claude-Code-CLI.

Der Umweg über die CLI ist der Kern des Add-ons: er nutzt das rollierende
Limit des Web-Abos statt eines metered abgerechneten API-Schlüssels.
"""

import json
import logging
import os
import subprocess

from providers.base_provider import (
    JSON_INSTRUCTION,
    TOOL_ACCESS_FULL,
    TOOL_ACCESS_OFF,
    TOOL_ACCESS_WEB,
    Attachment,
    BaseProvider,
    ProviderTimeout,
    resolve_tool_access,
)

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

# Die Stufen selbst und ihre Auflösung stehen in ``base_provider`` — sie gelten
# für beide Befehlszeilen. Hier steht nur, wie eine Stufe für „claude -p“
# aussieht.

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

    def _tool_access_args(self) -> list:
        """Übersetzt die Werkzeugstufe in Argumente für die CLI."""
        level = resolve_tool_access()
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
        if resolve_tool_access() == TOOL_ACCESS_FULL:
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
        if resolve_tool_access() == TOOL_ACCESS_FULL and wie_root_verweigerung:
            return FEHLER_WERKZEUGE_UNTER_ROOT
        return FEHLER_CLI_ABGEBROCHEN

    def _resolve_model(self, model: str | None) -> str:
        """Wählt das Modell: erst die Anfrage, dann das add-on-weite Standardmodell."""
        chosen = (model or "").strip()
        if not chosen:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        return chosen

    def execute(
        self,
        prompt: str,
        model: str | None = None,
        timeout: int | None = None,
        attachments: list[Attachment] | None = None,
        effort: str | None = None,
    ) -> dict:
        self.reject_attachments(attachments)
        env = self._build_env()
        full_prompt = prompt + JSON_INSTRUCTION

        # Ereignisstrom statt Textausgabe: nur darin meldet die CLI das
        # rate_limit_event mit dem Stand des Abos (D-032, D-034). Die Antwort
        # steht im abschließenden result-Ereignis.
        command = [
            "claude",
            "-p",
            full_prompt,
            "--output-format",
            "stream-json",
            "--verbose",
            "--append-system-prompt",
            SYSTEM_PROMPT,
        ]
        chosen_model = self._resolve_model(model)
        if chosen_model:
            # Die CLI nimmt sowohl Kurzaliasse (sonnet/opus/haiku) als auch
            # vollständige Modell-IDs entgegen.
            command += ["--model", chosen_model]
        if effort:
            command += ["--effort", effort]
        command += self._tool_access_args()

        log.info(
            "Anfrage an Claude, Modell: %s, Stufe: %s, Werkzeuge: %s",
            chosen_model or "Vorgabe der CLI",
            effort or "Vorgabe",
            resolve_tool_access(),
        )

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout or TIMEOUT_SEKUNDEN,
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
            log.error("Claude-CLI nach %s s abgebrochen", timeout or TIMEOUT_SEKUNDEN)
            raise ProviderTimeout(FEHLER_ZEITUEBERSCHREITUNG) from fehler

        # Vor der Prüfung des Rückgabecodes: auch eine wegen des Limits
        # abgelehnte Anfrage meldet den Stand, und genau der ist dann gefragt.
        answer, failed, used_model = self._read_stream_with_model(result.stdout)
        self.last_model = used_model or chosen_model or None

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

        if failed:
            log.error("Claude-CLI meldet einen Fehler im Ergebnis: %s", answer)
            raise RuntimeError(self._cli_fehler(answer))

        return self.parse_json(answer)

    @classmethod
    def _read_stream_with_model(cls, stdout: str) -> tuple[str, bool, str | None]:
        """Wie ``_read_stream``, dazu das Modell aus dem Init-Ereignis (Vertrag 1.4.0)."""
        import model_catalog

        used = None
        for line in (stdout or "").splitlines():
            line = line.strip()
            if '"init"' not in line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("subtype") == "init":
                used = message.get("model") if isinstance(message.get("model"), str) else None
                model_catalog.remember_claude_model(used)
                break
        answer, failed = cls._read_stream(stdout)
        return answer, failed, used

    @staticmethod
    def _read_stream(stdout: str) -> tuple[str, bool]:
        """Antworttext und Fehlerkennung aus dem Ereignisstrom der CLI.

        Ein ``rate_limit_event`` wird nebenbei als Limitstand gespeichert.
        Fehlt das ``result``-Ereignis (ältere CLI, reine Textausgabe), gilt die
        Ausgabe als Ganzes wie bisher.
        """
        # Import hier: limits zieht die Google-Konten nach, die der Provider
        # sonst nicht braucht.
        import limits

        final = None
        for line in (stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if not isinstance(message, dict):
                continue
            kind = message.get("type")
            if kind == "rate_limit_event":
                limits.record_claude(message.get("rate_limit_info"))
            elif kind == "result":
                final = message
        if final is None:
            return (stdout or "").strip(), False
        text = final.get("result")
        text = text.strip() if isinstance(text, str) else ""
        return text, bool(final.get("is_error")) or final.get("subtype") not in (None, "success")
