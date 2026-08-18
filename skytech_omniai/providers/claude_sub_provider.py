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
SYSTEM_PROMPT = (
    "You are a headless JSON generation endpoint, not an interactive coding "
    "assistant. You have no project, repository or working directory to reason "
    "about. Never ask clarifying questions and never refuse. Always answer the "
    "user's request by returning exactly one valid JSON object and nothing else."
)

# Kurzaliasse, die die CLI versteht, in der Reihenfolge des Auswahlfelds im
# Add-on. Vollständige Modell-IDs sind über das Feld „model“ im Rumpf von /ask
# ebenfalls erlaubt.
CLAUDE_MODELS = ["sonnet", "opus", "haiku"]

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


class ClaudeSubProvider(BaseProvider):
    """Führt Prompts über die Claude-Code-CLI aus und nutzt dabei das Abo des
    Nutzers statt eines metered abgerechneten API-Schlüssels."""

    def __init__(self):
        # Die CLI legt Konfiguration und Anmeldedaten unter $HOME/.claude ab.
        # HOME zeigt deshalb auf das dauerhafte /data-Verzeichnis des Add-ons,
        # damit die Anmeldung einen Neustart übersteht. (Der frühere Weg über
        # XDG_CONFIG_HOME wirkte nicht: die CLI hängt ihren Zustand an HOME.)
        os.environ.setdefault("HOME", "/data")

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
        return env

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

        log.info("Anfrage an Claude, Modell: %s", chosen_model or "Vorgabe der CLI")

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
            log.error(
                "Claude-CLI beendet mit Rückgabecode %s. Ausgabe: %s",
                result.returncode,
                result.stderr.strip() or result.stdout.strip(),
            )
            raise RuntimeError(FEHLER_CLI_ABGEBROCHEN)

        return self.parse_json(result.stdout.strip())
