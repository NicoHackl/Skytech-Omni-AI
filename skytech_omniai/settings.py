"""Fachlogik der Seite „Einstellungen“ — ohne Flask und ohne Netz.

Hier steht, was die Oberfläche von den Add-on-Optionen zu sehen bekommt, wie
ein Entwurf aus der Oberfläche mit dem gespeicherten Stand verschmilzt und was
daran geprüft wird. Gespeichert wird über ``supervisor_client``; ``app.py``
verbindet beides.
"""

import hashlib
import json

from config_loader import MODEL_AUTO, OPTION_ENV_MAP, SECRET_OPTIONS
from providers.base_provider import DEFAULT_TOOL_ACCESS, TOOL_ACCESS_LEVELS
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.factory import DEFAULT_PROVIDER
from providers.gemini_provider import GEMINI_MODELS
from providers.gemini_sub_provider import GEMINI_SUB_MODELS

# Welche Modelle zu welchem Anbieter gehören. Das Auswahlfeld in config.yaml
# ist eine gemeinsame Liste für alle; auf der Seite „Einstellungen“ wird
# dagegen geprüft, ob das Modell zum gewählten Anbieter passt.
PROVIDER_MODELS = {
    "claude_sub": CLAUDE_MODELS,
    "codex_sub": CODEX_MODELS,
    "gemini": GEMINI_MODELS,
    "gemini_sub": GEMINI_SUB_MODELS,
}

# Felder, die die Oberfläche bearbeiten darf. Alles andere in den Optionen
# bleibt beim Speichern unangetastet.
EDITABLE_OPTIONS = tuple(OPTION_ENV_MAP)

FEHLER_ANBIETER = "Bitte einen der angebotenen Anbieter wählen."
FEHLER_MODELL = "Dieses Modell gehört nicht zum gewählten Anbieter."
FEHLER_WERKZEUGE = "Bitte eine der angebotenen Stufen wählen."
FEHLER_TEXT = "Hier wird ein Text erwartet."
FEHLER_API_TOKEN = "Das Token braucht mindestens 32 Zeichen."
API_TOKEN_MIN_LENGTH = 32
FEHLER_CHATGPT_ZUGANG = (
    "Das ist nicht der Inhalt der Datei „auth.json“. Bitte die Datei vollständig kopieren."
)


def revision(options: dict) -> str:
    """Fingerabdruck des gespeicherten Stands.

    Damit erkennt das Speichern, ob die Optionen inzwischen anderswo geändert
    wurden — etwa im Reiter „Konfiguration“ von Home Assistant. Ohne diese
    Prüfung überschriebe ein alter Browser-Tab den neueren Stand stillschweigend.
    """
    canonical = json.dumps(options, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def public_view(options: dict) -> dict:
    """Was die Oberfläche von den Optionen sieht.

    Zugänge kommen nie als Wert zurück, auch nicht gekürzt — nur, ob einer
    hinterlegt ist. Das Feld selbst ist leer, damit das Formular einen leeren
    Wert als „unverändert“ zurückschicken kann.
    """
    visible = {key: _text(options.get(key)) for key in EDITABLE_OPTIONS}
    for key in SECRET_OPTIONS:
        visible[key] = ""
    # Leere Felder zeigen, was tatsächlich gilt: ein leeres Modell meint
    # dasselbe wie der Sentinel, und Anbieter und Werkzeugstufe fallen in den
    # Providern auf ihre Vorgabe zurück.
    visible["model"] = visible["model"] or MODEL_AUTO
    visible["provider"] = visible["provider"] or DEFAULT_PROVIDER
    visible["tool_access"] = visible["tool_access"] or DEFAULT_TOOL_ACCESS
    return {
        "options": visible,
        "secrets_set": {key: bool(_text(options.get(key))) for key in SECRET_OPTIONS},
        "stored_revision": revision(options),
    }


def merge_update(current: dict, draft: dict) -> tuple[dict, dict[str, str]]:
    """Verschmilzt einen Entwurf der Oberfläche mit dem gespeicherten Stand.

    Regeln für Zugänge: fehlt das Feld oder ist es leer, bleibt der
    gespeicherte Wert; ``None`` entfernt ihn; jeder andere Text ersetzt ihn.
    Unbekannte Felder im Entwurf werden ignoriert, unbekannte Felder im
    gespeicherten Stand bleiben erhalten.

    :returns: die neuen Optionen und je Feld ein deutscher Satz, falls etwas
        nicht passt. Bei Fehlern sind die neuen Optionen nicht zu speichern.
    """
    merged = dict(current)
    errors: dict[str, str] = {}

    for key in EDITABLE_OPTIONS:
        if key not in draft:
            continue
        value = draft[key]
        if key in SECRET_OPTIONS:
            if value is None:
                merged[key] = ""
                continue
            if not isinstance(value, str):
                errors[key] = FEHLER_TEXT
                continue
            if value.strip():
                merged[key] = value.strip()
            continue
        if not isinstance(value, str):
            errors[key] = FEHLER_TEXT
            continue
        merged[key] = value.strip()

    provider = _text(merged.get("provider"))
    if provider not in PROVIDER_MODELS:
        errors.setdefault("provider", FEHLER_ANBIETER)

    model = _text(merged.get("model")) or MODEL_AUTO
    merged["model"] = model
    if "provider" not in errors and model != MODEL_AUTO and model not in PROVIDER_MODELS[provider]:
        errors.setdefault("model", FEHLER_MODELL)

    if _text(merged.get("tool_access")) not in TOOL_ACCESS_LEVELS:
        errors.setdefault("tool_access", FEHLER_WERKZEUGE)

    # Nur ein neu eingetragener Zugang wird geprüft. Ein bereits gespeicherter
    # Wert hat seinen Weg schon hinter sich; ihn hier abzulehnen, würde jedes
    # Speichern blockieren, ohne dass der Nutzer ihn sehen könnte.
    codex = draft.get("codex_auth_json")
    if isinstance(codex, str) and codex.strip():
        try:
            parsed = json.loads(codex)
        except ValueError:
            parsed = None
        if not isinstance(parsed, dict):
            errors.setdefault("codex_auth_json", FEHLER_CHATGPT_ZUGANG)

    token = draft.get("api_token")
    if isinstance(token, str) and token.strip() and len(token.strip()) < API_TOKEN_MIN_LENGTH:
        errors.setdefault("api_token", FEHLER_API_TOKEN)

    return merged, errors
