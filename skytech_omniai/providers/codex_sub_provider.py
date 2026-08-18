"""ChatGPT über das Abo, angesprochen über die Codex-CLI.

Der Umweg über die CLI ist derselbe wie bei Claude: nur über die Anmeldung mit
dem ChatGPT-Konto zählt eine Anfrage auf das Kontingent des Abos. Mit einem
API-Schlüssel liefe dieselbe CLI nach Verbrauch abgerechnet. Begründung: D-013.
"""

import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path

from providers.base_provider import (
    JSON_INSTRUCTION,
    TOOL_ACCESS_FULL,
    TOOL_ACCESS_OFF,
    BaseProvider,
    resolve_tool_access,
)

log = logging.getLogger("omniai.codex")

# Die Codex-CLI kennt kein Gegenstück zu „--append-system-prompt“. Die Rolle
# wird dem Prompt deshalb vorangestellt. Bewusst englisch — sie richtet sich an
# das Modell, nicht an einen Menschen. Inhaltlich gleich zum Claude-Provider:
# ohne den Absatz zu den Web-Werkzeugen liest das Modell „headless endpoint“ als
# „kein Internet“ und lehnt Wetter- oder Nachrichtenfragen pauschal ab.
SYSTEM_PROMPT = (
    "You are a headless JSON generation endpoint, not an interactive coding "
    "assistant. You have no project, repository or working directory to reason "
    "about. Never ask clarifying questions and never refuse. "
    "You do have working internet access. Use your web search tool whenever the "
    "answer depends on current, local or time-sensitive facts - weather, news, "
    "prices, opening hours, timetables, sports results. Never claim that you "
    "cannot access the internet and never guess such facts from memory. If a "
    'lookup genuinely fails, report the reason in an "error" field inside the '
    "JSON instead of inventing an answer. "
    "Always answer the user's request by returning exactly one valid JSON "
    "object and nothing else."
)

# Reihenfolge = Anzeigereihenfolge im Auswahlfeld und unter GET /models.
# Vollständige Modell-IDs sind über das Feld „model“ im Rumpf von /ask ebenfalls
# erlaubt. „gpt-5.4“ und „gpt-5.4-mini“ stehen bewusst nicht in der Liste: sie
# verlieren am 31.08.2026 die Anmeldung über das ChatGPT-Konto.
CODEX_MODELS = [
    "gpt-5.6-sol",  # für komplexe Aufgaben
    "gpt-5.6-terra",  # ausgewogen, für den Alltag
    "gpt-5.6-luna",  # schnell und günstig
    "gpt-5.3-codex-spark",  # nur mit ChatGPT Pro
]

# Sentinel-Wert aus der Add-on-Konfiguration. Er steht für „kein Modell
# erzwingen“ und wird wie ein leeres Feld behandelt.
AUTO_MODEL = "auto"

# Die CLI legt Anmeldung und Zustand unter $CODEX_HOME ab und schreibt die
# erneuerten Tokens dorthin zurück. Der Pfad zeigt deshalb ins dauerhafte
# /data-Verzeichnis des Add-ons, sonst wäre die Anmeldung nach jedem Neustart
# weg.
DEFAULT_CODEX_HOME = "/data/.codex"

# Marke neben der Anmeldedatei: enthält den Fingerabdruck des zuletzt aus der
# Konfiguration übernommenen Werts. Nur wenn er sich ändert, wird die Datei
# überschrieben — sonst würde der Neustart die von der CLI erneuerten Tokens
# durch den alten Stand ersetzen.
SEED_MARKER_NAME = ".seed"
AUTH_FILE_NAME = "auth.json"

# Zeitlimit eines CLI-Laufs. Gleicher Wert wie bei den anderen Providern, damit
# sich alle gegenüber Home Assistant identisch verhalten.
TIMEOUT_SEKUNDEN = 300

FEHLER_KEINE_ZUGANGSDATEN = (
    "Für ChatGPT ist kein Zugang hinterlegt. Auf einem Rechner mit Browser "
    "einmalig „codex login“ ausführen, den Inhalt der dabei entstandenen Datei "
    "„auth.json“ kopieren und im Add-on unter „Konfiguration“ in das Feld "
    "„codex_auth_json“ einfügen. Danach das Add-on neu starten. Alternativ "
    "lässt sich unter „openai_api_key“ ein Schlüssel eintragen; der wird nach "
    "Verbrauch abgerechnet und nutzt das Abo nicht."
)

FEHLER_ZUGANG_UNLESERLICH = (
    "Der hinterlegte ChatGPT-Zugang ist unvollständig. Im Add-on unter "
    "„Konfiguration“ das Feld „codex_auth_json“ leeren und den vollständigen "
    "Inhalt der Datei „auth.json“ erneut einfügen."
)

FEHLER_ZUGANG_NICHT_SPEICHERBAR = (
    "Der hinterlegte ChatGPT-Zugang konnte nicht abgelegt werden. Bitte prüfen, "
    "ob das Add-on Schreibrechte auf sein Datenverzeichnis hat, und es neu "
    "starten."
)

FEHLER_CLI_FEHLT = (
    "ChatGPT ist in diesem Add-on nicht verfügbar. Das Add-on wurde vermutlich "
    "unvollständig gebaut — bitte neu installieren."
)

FEHLER_CLI_ABGEBROCHEN = (
    "ChatGPT hat die Anfrage nicht beantwortet. Bitte die Anfrage erneut stellen."
)

FEHLER_ANMELDUNG_ABGELAUFEN = (
    "Die Anmeldung bei ChatGPT gilt nicht mehr. Auf einem Rechner mit Browser "
    "erneut „codex login“ ausführen und den Inhalt der Datei „auth.json“ im "
    "Add-on unter „Konfiguration“ in das Feld „codex_auth_json“ einfügen."
)

FEHLER_SCHLUESSEL_UNGUELTIG = (
    "Der hinterlegte OpenAI-Schlüssel gilt nicht. Im Add-on unter "
    "„Konfiguration“ → „openai_api_key“ einen gültigen Schlüssel eintragen — "
    "oder auf das Abo umstellen und stattdessen „codex_auth_json“ füllen."
)

FEHLER_KONTINGENT = (
    "Das Kontingent des ChatGPT-Abos ist aufgebraucht. Bitte später erneut "
    "versuchen oder ein kleineres Modell wählen."
)

FEHLER_ZEITUEBERSCHREITUNG = (
    "ChatGPT hat zu lange gebraucht und wurde abgebrochen. Bitte die Anfrage "
    "kürzer fassen oder es später erneut versuchen."
)

# Merkmale, an denen sich Kontingent- und Anmeldefehler in der Ausgabe der CLI
# erkennen lassen. Die Ausgabe selbst wird dabei nur gelesen, nie
# weitergereicht — sie kann Pfade und Stacktraces enthalten (eiserne Regel 12).
KONTINGENT_MARKER = ("usage limit", "rate limit", "quota", "too many requests", "429")
ANMELDUNG_MARKER = (
    "unauthorized",
    "401",
    "not logged in",
    "please run codex login",
    "re-authenticate",
)


class CodexSubProvider(BaseProvider):
    """Führt Prompts über die Codex-CLI aus und nutzt dabei das ChatGPT-Abo."""

    def __init__(self):
        # setdefault statt fester Zuweisung: außerhalb des Containers (Tests,
        # lokale Entwicklung) darf ein anderer Pfad vorgegeben werden.
        os.environ.setdefault("CODEX_HOME", DEFAULT_CODEX_HOME)
        # Merkt sich, welcher Weg tatsächlich benutzt wurde. Davon hängt ab,
        # welches Feld eine Meldung nennt, wenn die Gegenstelle ablehnt.
        self._api_key_fallback = False

    # --- Zugang ------------------------------------------------------------

    @staticmethod
    def _codex_home() -> Path:
        return Path(os.environ.get("CODEX_HOME", DEFAULT_CODEX_HOME))

    def _seed_auth_file(self, auth_json: str) -> None:
        """Legt den aus der Konfiguration übernommenen Zugang ab — nur bei Änderung.

        Die CLI erneuert ihre Tokens selbst und schreibt sie in dieselbe Datei
        zurück. Würde bei jedem Start der Wert aus der Konfiguration darüber
        geschrieben, wäre die Anmeldung irgendwann abgelaufen, obwohl die CLI sie
        längst aufgefrischt hat. Verglichen wird deshalb der Fingerabdruck des
        eingetragenen Werts: er ändert sich genau dann, wenn jemand einen neuen
        Zugang einträgt.

        :raises RuntimeError: wenn der Wert kein gültiges JSON ist oder sich die
            Datei nicht schreiben lässt.
        """
        try:
            json.loads(auth_json)
        except ValueError as fehler:
            # Der Wert selbst darf nirgends auftauchen, auch nicht im Log.
            log.error("Der hinterlegte ChatGPT-Zugang ist kein gültiges JSON: %s", fehler)
            raise RuntimeError(FEHLER_ZUGANG_UNLESERLICH) from fehler

        fingerabdruck = hashlib.sha256(auth_json.encode("utf-8")).hexdigest()
        home = self._codex_home()
        marke = home / SEED_MARKER_NAME
        ziel = home / AUTH_FILE_NAME

        try:
            home.mkdir(parents=True, exist_ok=True)
            home.chmod(0o700)
            unveraendert = (
                marke.is_file()
                and marke.read_text(encoding="utf-8").strip() == fingerabdruck
                and ziel.is_file()
            )
            if unveraendert:
                return
            ziel.write_text(auth_json, encoding="utf-8")
            ziel.chmod(0o600)
            marke.write_text(fingerabdruck, encoding="utf-8")
            log.info("ChatGPT-Zugang aus der Konfiguration übernommen")
        except OSError as fehler:
            log.error("Der ChatGPT-Zugang konnte nicht abgelegt werden: %s", fehler)
            raise RuntimeError(FEHLER_ZUGANG_NICHT_SPEICHERBAR) from fehler

    def _build_env(self) -> dict:
        """Stellt die Umgebung für den CLI-Aufruf zusammen.

        :raises RuntimeError: wenn weder Abo-Zugang noch API-Schlüssel gesetzt ist.
        """
        env = os.environ.copy()
        auth_json = env.get("CODEX_AUTH_JSON", "").strip()
        api_key = env.get("OPENAI_API_KEY", "").strip()

        if auth_json:
            self._api_key_fallback = False
            self._seed_auth_file(auth_json)
            # Ein zusätzlich gesetzter Schlüssel würde die Abrechnung
            # verschieben: das Abo ist der gewollte Weg, der Schlüssel nur der
            # Rückfall.
            env.pop("OPENAI_API_KEY", None)
        elif not api_key:
            log.error("Aufruf ohne hinterlegten ChatGPT-Zugang abgelehnt")
            raise RuntimeError(FEHLER_KEINE_ZUGANGSDATEN)
        else:
            self._api_key_fallback = True
            log.info(
                "ChatGPT über einen API-Schlüssel — die Anfrage wird nach Verbrauch abgerechnet"
            )

        env["CODEX_HOME"] = str(self._codex_home())
        return env

    # --- Aufruf ------------------------------------------------------------

    def _tool_access_args(self) -> list:
        """Übersetzt die Werkzeugstufe in Argumente für die CLI.

        Anders als bei Claude gibt es keine Liste einzeln freigegebener
        Werkzeuge, sondern eine Sandbox-Stufe und einen Schalter für die
        Websuche. Was das sicherheitlich bedeutet, steht in
        docs/sicherheit-datenschutz.md.

        Diese Argumente gehören **vor** den Unterbefehl ``exec``: „--search“
        kennt nur der Hauptbefehl, hinter ``exec`` bricht die CLI mit
        „unexpected argument“ ab.
        """
        level = resolve_tool_access()
        if level == TOOL_ACCESS_FULL:
            return ["--sandbox", "danger-full-access", "--search"]
        if level == TOOL_ACCESS_OFF:
            return ["--sandbox", "read-only", "-c", 'web_search="disabled"']
        return ["--sandbox", "read-only", "--search"]

    def _resolve_model(self, model: str | None) -> str:
        """Wählt das Modell: Anfrage, dann ``OMNIAI_MODEL``, sonst entscheidet die CLI.

        Zusätzlich wird geprüft, ob das Ergebnis überhaupt ein Modell von OpenAI
        ist. Das fängt den Fall ab, dass im gemeinsamen Auswahlfeld noch ein
        Claude- oder Gemini-Wert steht, der Anbieter aber umgestellt wurde.

        :raises ValueError: wenn das Modell nicht zu diesem Anbieter gehört.
        """
        chosen = (model or "").strip()
        if not chosen or chosen == AUTO_MODEL:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        if not chosen or chosen == AUTO_MODEL:
            return ""

        # Jede „gpt-“-Kennung wird durchgelassen, damit neue Modelle ohne
        # Codeänderung genutzt werden können.
        if chosen not in CODEX_MODELS and not chosen.startswith("gpt-"):
            raise ValueError(
                f"„{chosen}“ ist kein Modell von ChatGPT. Zur Auswahl stehen: "
                + ", ".join(CODEX_MODELS)
                + ". Weitere „gpt-“-Modelle sind ebenfalls erlaubt."
            )
        return chosen

    def _cli_fehler(self, ausgabe: str) -> str:
        """Wählt die Meldung für einen abgebrochenen CLI-Lauf.

        Die Ausgabe der CLI wird dabei nur **gelesen**, nie weitergereicht — sie
        kann Pfade und Stacktraces enthalten (eiserne Regel 12).
        """
        klein = ausgabe.lower()
        if any(marker in klein for marker in KONTINGENT_MARKER):
            return FEHLER_KONTINGENT
        if any(marker in klein for marker in ANMELDUNG_MARKER):
            # Dieselbe Ursache, zwei Wege: die Meldung nennt das Feld, das der
            # Betreiber tatsächlich gefüllt hat.
            if self._api_key_fallback:
                return FEHLER_SCHLUESSEL_UNGUELTIG
            return FEHLER_ANMELDUNG_ABGELAUFEN
        return FEHLER_CLI_ABGEBROCHEN

    def execute(self, prompt: str, model: str | None = None) -> dict:
        chosen_model = self._resolve_model(model)
        env = self._build_env()
        full_prompt = SYSTEM_PROMPT + "\n\n" + prompt + JSON_INSTRUCTION

        command = [
            "codex",
            # Werkzeug-Freigabe zuerst: diese Schalter kennt nur der
            # Hauptbefehl, nicht der Unterbefehl "exec".
            *self._tool_access_args(),
            "exec",
            # /data ist kein Git-Repo; ohne diesen Schalter bricht die CLI ab.
            "--skip-git-repo-check",
            # Keine Sitzungsdateien unter /data — das Add-on führt keinen Verlauf.
            "--ephemeral",
            # Eine von Hand angelegte config.toml soll das Verhalten des Add-ons
            # nicht still verändern.
            "--ignore-user-config",
            # Aus dem dauerhaften Datenverzeichnis heraus arbeiten, nicht aus dem
            # Quellbaum: sonst liest die CLI eine AGENTS.md ein und deutet die
            # Anfrage als Programmieraufgabe um.
            "--cd",
            "/data",
        ]
        if chosen_model:
            command += ["--model", chosen_model]
        # „-“ heißt: der Prompt kommt über die Standardeingabe. Als Argument
        # stünde er in der Prozessliste.
        command.append("-")

        log.info(
            "Anfrage an ChatGPT, Modell: %s, Werkzeuge: %s",
            chosen_model or "Vorgabe der CLI",
            resolve_tool_access(),
        )

        try:
            result = subprocess.run(
                command,
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SEKUNDEN,
                env=env,
            )
        except FileNotFoundError as fehler:
            log.error("Die Codex-CLI wurde im Container nicht gefunden: %s", fehler)
            raise RuntimeError(FEHLER_CLI_FEHLT) from fehler
        except subprocess.TimeoutExpired as fehler:
            log.error("Codex-CLI nach %s s abgebrochen", TIMEOUT_SEKUNDEN)
            raise RuntimeError(FEHLER_ZEITUEBERSCHREITUNG) from fehler

        if result.returncode != 0:
            # Die Ausgabe der CLI kann Pfade und Stacktraces enthalten und geht
            # deshalb vollständig ins Log, nicht an den Aufrufer.
            ausgabe = result.stderr.strip() or result.stdout.strip()
            log.error(
                "Codex-CLI beendet mit Rückgabecode %s. Ausgabe: %s",
                result.returncode,
                ausgabe,
            )
            raise RuntimeError(self._cli_fehler(ausgabe))

        return self.parse_json(result.stdout.strip())
