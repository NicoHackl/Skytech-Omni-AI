"""Liest die Add-on-Optionen und legt sie als Umgebungsvariablen ab.

Alles, was der Betreiber auf der Seite „Einstellungen“ der Oberfläche oder im
Reiter „Konfiguration“ von Home Assistant einträgt, verwaltet der Supervisor
und legt es in einer Datei im Container ab. Von dort wandert es in die
Umgebung, weil Provider und die beiden Befehlszeilen ihre Werte dort erwarten.
Geschrieben wird diese Datei hier nie — das übernimmt ``supervisor_client``.
"""

import json
import logging
import os
import re
from pathlib import Path

log = logging.getLogger("omniai.config")

# Der Supervisor legt die Optionen hier ab.
OPTIONS_PATH = "/data/options.json"

# Die Versionsnummer wird in config.yaml gepflegt und von dort gelesen, damit
# sie nur an einer Stelle steht. Für eine einzelne Zeile lohnt keine
# YAML-Abhängigkeit im Add-on-Image.
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
VERSION_MUSTER = re.compile(r'^version:\s*"?([^"\s]+)"?\s*$', re.MULTILINE)


def load_options() -> dict:
    """Liest die Add-on-Optionen.

    Fehlt die Datei, kommt ein leeres Wörterbuch zurück: so lässt sich das
    Add-on auch außerhalb von Home Assistant starten, etwa zum Entwickeln.

    :raises RuntimeError: wenn die Datei zwar da, aber nicht lesbar oder kein
        gültiges JSON ist. Ein stiller Fallback wäre hier falsch — der
        Betreiber hat etwas eingetragen, das nicht ankommt.
    """
    try:
        with open(OPTIONS_PATH, encoding="utf-8") as datei:
            return json.load(datei)
    except FileNotFoundError:
        log.info(
            "Keine Add-on-Optionen unter %s gefunden — es gelten die Vorgabewerte.",
            OPTIONS_PATH,
        )
        return {}
    except (json.JSONDecodeError, OSError) as fehler:
        # Betreibermeldung: Pfad und Ursache gehören hier ausdrücklich dazu,
        # weil genau er es reparieren soll.
        raise RuntimeError(
            f"Die Add-on-Optionen in {OPTIONS_PATH} konnten nicht gelesen werden: {fehler}"
        ) from fehler


def read_addon_version() -> str | None:
    """Liest die Versionsnummer aus ``config.yaml``.

    Gibt ``None`` zurück, wenn die Datei fehlt oder keine Version enthält —
    die Oberfläche zeigt dann einen Platzhalter statt einer erfundenen Nummer.
    """
    try:
        treffer = VERSION_MUSTER.search(CONFIG_PATH.read_text(encoding="utf-8"))
    except OSError as fehler:
        log.warning("Versionsnummer nicht lesbar: %s", fehler)
        return None
    return treffer.group(1) if treffer else None


# Option → Umgebungsvariable. Provider und die beiden Befehlszeilen erwarten
# ihre Werte in der Umgebung; die Reihenfolge ist die der Konfigurationsseite.
#
# - provider: aktiver Anbieter.
# - model: add-on-weites Standardmodell. Ein „model“ im Rumpf von /ask schlägt
#   es; dieser Wert greift nur, wenn die Anfrage selbst keines nennt.
# - tool_access: Werkzeugstufe der Befehlszeilen („off“, „web“, „full“). Ohne
#   Freigabe lehnt die CLI im Headless-Modus jedes Werkzeug ab — Anfragen, die
#   eine Recherche brauchen (Wetter, Nachrichten, Preise), scheitern dann.
# - claude_oauth_token: langlebiges Token des Claude-Pro/Max-Abos, einmal auf
#   einem Rechner mit Browser über `claude setup-token` erzeugt.
# - anthropic_api_key: Alternative zum Abo, nach Verbrauch abgerechnet.
# - codex_auth_json: Anmeldung des ChatGPT-Abos, der vollständige Inhalt der
#   Datei „auth.json“, die „codex login“ anlegt. Der Provider legt ihn im
#   Datenverzeichnis ab — aber nur, wenn sich der Wert geändert hat, damit die
#   von der CLI erneuerten Tokens erhalten bleiben.
# - openai_api_key: Alternative zum Abo, nach Verbrauch abgerechnet.
# - gemini_api_key: Google-AI-Studio-Schlüssel, unter
#   https://aistudio.google.com/apikey erzeugt und nach Verbrauch abgerechnet.
# - gemini_agy_model: Standardmodell für „Google Gemini (AGY)“. Das Auswahlfeld
#   „model“ kann es nicht tragen: die Bezeichnungen kennt die Google-Befehlszeile
#   erst nach der Anmeldung, die feste Liste in config.yaml also nicht.
# - api_token: Token, das Skytech X bei jedem Aufruf der Schnittstelle v1
#   mitschickt (D-019). Ohne Token lehnt /v1 jede Anfrage ab.
OPTION_ENV_MAP = {
    "provider": "AI_PROVIDER",
    "model": "OMNIAI_MODEL",
    "tool_access": "OMNIAI_TOOL_ACCESS",
    "claude_oauth_token": "CLAUDE_CODE_OAUTH_TOKEN",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "codex_auth_json": "CODEX_AUTH_JSON",
    "openai_api_key": "OPENAI_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "gemini_agy_model": "GEMINI_AGY_MODEL",
    "gemini_web_model": "OMNIAI_GEMINI_WEB_MODEL",
    "api_token": "OMNIAI_API_TOKEN",
}

# Zugänge: werden nie angezeigt, nie geloggt und an der Oberfläche nur als
# „hinterlegt ja/nein“ gemeldet. Klarnamen stehen für die Log-Zeile dabei.
SECRET_OPTIONS = {
    "claude_oauth_token": "Claude-Abo",
    "anthropic_api_key": "Anthropic-API",
    "codex_auth_json": "ChatGPT-Abo",
    "openai_api_key": "OpenAI-API",
    "gemini_api_key": "Gemini",
    "api_token": "Schnittstelle v1",
}

# „auto“ ist der Sentinel des Auswahlfelds „model“ und bedeutet „kein Modell
# erzwingen“ — er wird deshalb wie ein leeres Feld behandelt.
MODEL_AUTO = "auto"


def _option_value(options: dict, key: str) -> str:
    """Bereinigter Wert einer Option; der Sentinel „auto“ zählt als leer."""
    value = options.get(key)
    value = value.strip() if isinstance(value, str) else ""
    if key == "model" and value == MODEL_AUTO:
        return ""
    return value


def apply_options_to_env(options: dict, *, clear_missing: bool = False) -> None:
    """Bildet die Add-on-Optionen auf die erwarteten Umgebungsvariablen ab.

    Damit ist das ganze Add-on aus der Oberfläche von Home Assistant heraus
    konfigurierbar; im Code steht kein einziger Zugangsdatenwert.

    Beim Start bleibt ein leeres Feld folgenlos: eine von außen gesetzte
    Variable (lokale Entwicklung) wird nicht überschrieben. Nach dem Speichern
    auf der Seite „Einstellungen“ dagegen muss ein geleertes Feld auch aus der
    Umgebung verschwinden, sonst gälte ein entfernter Zugang bis zum Neustart
    weiter — dafür ``clear_missing=True``.
    """
    for key, env_name in OPTION_ENV_MAP.items():
        value = _option_value(options, key)
        if value:
            os.environ[env_name] = value
        elif clear_missing:
            os.environ.pop(env_name, None)

    # Bewusst ohne die Werte selbst: im Log steht nur, was gesetzt wurde.
    log.info(
        "Optionen übernommen — Provider: %s, Standardmodell: %s, Werkzeuge: %s, Zugänge: %s",
        os.environ.get("AI_PROVIDER", "Vorgabe"),
        os.environ.get("OMNIAI_MODEL", "keine Vorgabe"),
        os.environ.get("OMNIAI_TOOL_ACCESS", "Vorgabe"),
        ", ".join(name for key, name in SECRET_OPTIONS.items() if _option_value(options, key))
        or "keine",
    )
