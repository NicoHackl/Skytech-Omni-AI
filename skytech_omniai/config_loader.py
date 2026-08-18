"""Liest die Add-on-Optionen und legt sie als Umgebungsvariablen ab.

Alles, was der Betreiber im Reiter „Konfiguration“ von Home Assistant einträgt,
schreibt der Supervisor in eine Datei im Container. Von dort wandert es in die
Umgebung, weil Provider und die Claude-CLI ihre Werte dort erwarten.
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


def apply_options_to_env(options: dict) -> None:
    """Bildet die Add-on-Optionen auf die erwarteten Umgebungsvariablen ab.

    Damit ist das ganze Add-on aus der Oberfläche von Home Assistant heraus
    konfigurierbar; im Code steht kein einziger Zugangsdatenwert.
    """
    provider = (options.get("provider") or "").strip()
    if provider:
        os.environ["AI_PROVIDER"] = provider

    # Add-on-weites Standardmodell. Ein „model“ im Rumpf von /ask schlägt es;
    # dieser Wert greift nur, wenn die Anfrage selbst keines nennt.
    # „auto“ ist der Sentinel des Auswahlfelds und bedeutet „kein Modell
    # erzwingen" — er wird deshalb wie ein leeres Feld behandelt.
    model = (options.get("model") or "").strip()
    if model and model != "auto":
        os.environ["OMNIAI_MODEL"] = model

    # Langlebiges Token des Claude-Pro/Max-Abos. Wird einmal auf einem Rechner
    # mit Browser über `claude setup-token` erzeugt und hier eingetragen.
    token = (options.get("claude_oauth_token") or "").strip()
    if token:
        os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token

    # Alternative zum Abo: metered abgerechneter Anthropic-API-Schlüssel.
    api_key = (options.get("anthropic_api_key") or "").strip()
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    # Google-AI-Studio-Schlüssel für den Gemini-Provider. Wird unter
    # https://aistudio.google.com/apikey erzeugt und metered abgerechnet.
    gemini_api_key = (options.get("gemini_api_key") or "").strip()
    if gemini_api_key:
        os.environ["GEMINI_API_KEY"] = gemini_api_key

    # Bewusst ohne die Werte selbst: im Log steht nur, was gesetzt wurde.
    log.info(
        "Optionen übernommen — Provider: %s, Standardmodell: %s, Zugänge: %s",
        os.environ.get("AI_PROVIDER", "Vorgabe"),
        os.environ.get("OMNIAI_MODEL", "keine Vorgabe"),
        ", ".join(
            name
            for name, gesetzt in (
                ("Claude-Abo", bool(token)),
                ("Anthropic-API", bool(api_key)),
                ("Gemini", bool(gemini_api_key)),
            )
            if gesetzt
        )
        or "keine",
    )
