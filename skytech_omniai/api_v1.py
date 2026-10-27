"""Schnittstelle v1 für Skytech X (D-019).

Vertrag: ``docs/contracts/omniai-api-v1.yaml`` (Kopie; Masterkopie im Repo
Skytech-X-Backend). Anders als ``/ask`` ist jeder Aufruf hier mit einem Token
geschützt, Fehler tragen zusätzlich einen stabilen Code, und Antworten lassen
sich gegen ein JSON-Schema prüfen.

Umgesetzt sind Gesundheit, Fähigkeiten und Einmal-Antworten. Agent-Läufe
(``/v1/runs``) folgen in einem späteren Schritt (Roadmap M5).
"""

import hmac
import json
import logging
import os

from flask import Blueprint, jsonify, request
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from config_loader import read_addon_version
from providers.base_provider import NotJson, ProviderTimeout, UnknownModel
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.factory import DEFAULT_PROVIDER, ProviderFactory
from providers.gemini_provider import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from providers.gemini_provider import GEMINI_MODELS

log = logging.getLogger("omniai.v1")

api_v1 = Blueprint("api_v1", __name__, url_prefix="/v1")

MAX_INPUT_LENGTH = 100_000
MAX_INSTRUCTIONS_LENGTH = 20_000
DEFAULT_TIMEOUT_SECONDS = 120
MIN_TIMEOUT_SECONDS = 5
MAX_TIMEOUT_SECONDS = 600

# Anzeigenamen und Modelllisten je Anbieter. Neue Anbieter erscheinen hier und
# in der Factory; Skytech X liest die Liste über /v1/capabilities.
PROVIDERS = {
    "claude_sub": {"name": "Claude (Abo)", "models": CLAUDE_MODELS, "default": None},
    "codex_sub": {"name": "ChatGPT (Abo)", "models": CODEX_MODELS, "default": None},
    "gemini": {"name": "Google Gemini", "models": GEMINI_MODELS, "default": GEMINI_DEFAULT_MODEL},
}

# Anweisung an das Modell, englisch wie die übrigen Modell-Anweisungen.
SCHEMA_INSTRUCTION = (
    "\n\nThe JSON you return MUST validate against this JSON Schema (2020-12):\n{schema}"
)
RETRY_INSTRUCTION = (
    "\n\nYour previous answer did not match the required JSON Schema. Problem: {problem}. "
    "Answer again, strictly following the schema."
)

FEHLER_KEIN_TOKEN = "Für die Schnittstelle ist kein Token eingerichtet."
FEHLER_TOKEN = "Das Token fehlt oder ist falsch."
FEHLER_EINGABE = "Die Anfrage ist unvollständig oder hat ein falsches Format."
FEHLER_SCHEMA_UNGUELTIG = "Das mitgeschickte JSON-Schema ist ungültig."
FEHLER_SCHEMA_PASST_NICHT = (
    "Die Antwort des Modells passte auch nach einem zweiten Versuch nicht zum verlangten Schema."
)
FEHLER_UNBEKANNT = "Die Anfrage konnte nicht bearbeitet werden. Bitte später erneut versuchen."


def credentials_present() -> dict[str, bool]:
    """Ob für einen Anbieter Zugangsdaten hinterlegt sind — nie die Werte."""
    return {
        "claude_sub": bool(
            os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        ),
        "codex_sub": bool(
            os.environ.get("CODEX_AUTH_JSON", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        ),
        "gemini": bool(
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        ),
    }


def _error(status: int, code: str, message: str):
    return jsonify({"error": message, "code": code}), status


@api_v1.before_request
def require_token():
    """Jeder Aufruf von /v1 braucht ``Authorization: Bearer <api_token>``.

    Vergleich in konstanter Zeit, damit sich das Token nicht Zeichen für
    Zeichen erraten lässt. Ohne eingerichtetes Token ist /v1 geschlossen.
    """
    expected = os.environ.get("OMNIAI_API_TOKEN", "").strip()
    if not expected:
        log.warning("Aufruf von %s abgelehnt: kein Token eingerichtet", request.path)
        return _error(401, "UNAUTHORIZED", FEHLER_KEIN_TOKEN)
    header = request.headers.get("Authorization", "")
    supplied = header[7:].strip() if header.startswith("Bearer ") else ""
    if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        log.warning("Aufruf von %s mit falschem oder fehlendem Token abgelehnt", request.path)
        return _error(401, "UNAUTHORIZED", FEHLER_TOKEN)
    return None


@api_v1.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP", "version": read_addon_version()})


@api_v1.route("/capabilities", methods=["GET"])
def capabilities():
    """Anbieter, Modelle und Fähigkeiten für die Auswahl in Skytech X.

    Werkzeuge (MCP) gibt es erst mit den Agent-Läufen; bis dahin meldet jeder
    Anbieter ``tools: false``. Nutzungsdaten werden noch nicht erhoben.
    """
    present = credentials_present()
    providers = [
        {
            "id": key,
            "name": meta["name"],
            "available": present[key],
            "models": meta["models"],
            "defaultModel": meta["default"],
            "features": {"tools": False, "structuredOutput": True, "usage": False},
        }
        for key, meta in PROVIDERS.items()
    ]
    return jsonify(
        {
            "providers": providers,
            "limits": {"maxPromptLength": MAX_INPUT_LENGTH},
            "mcp": {"protocolVersions": [], "transports": []},
        }
    )


def _validate_request(payload) -> tuple[dict | None, str | None]:
    """Prüft den Rumpf von /v1/completions. Liefert die bereinigten Werte oder
    den Fehlercode für die Antwort."""
    if not isinstance(payload, dict):
        return None, "VALIDATION_ERROR"
    text = payload.get("input")
    instructions = payload.get("instructions")
    schema = payload.get("outputSchema")
    timeout = payload.get("timeoutSeconds", DEFAULT_TIMEOUT_SECONDS)
    provider = payload.get("provider")
    model = payload.get("model")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_INPUT_LENGTH:
        return None, "VALIDATION_ERROR"
    if instructions is not None and (
        not isinstance(instructions, str) or len(instructions) > MAX_INSTRUCTIONS_LENGTH
    ):
        return None, "VALIDATION_ERROR"
    if schema is not None and not isinstance(schema, dict):
        return None, "VALIDATION_ERROR"
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, int)
        or not MIN_TIMEOUT_SECONDS <= timeout <= MAX_TIMEOUT_SECONDS
    ):
        return None, "VALIDATION_ERROR"
    for value in (provider, model):
        if value is not None and not isinstance(value, str):
            return None, "VALIDATION_ERROR"
    return {
        "input": text,
        "instructions": instructions or "",
        "schema": schema,
        "timeout": timeout,
        "provider": provider or None,
        "model": model or None,
    }, None


def build_prompt(instructions: str, text: str, schema: dict | None) -> str:
    """Setzt Anweisungen, Aufgabe und ggf. das Schema zu einem Prompt zusammen."""
    parts = []
    if instructions.strip():
        parts.append(instructions.strip())
    parts.append(text.strip())
    prompt = "\n\n".join(parts)
    if schema is not None:
        prompt += SCHEMA_INSTRUCTION.format(schema=json.dumps(schema, ensure_ascii=False))
    return prompt


def first_schema_problem(validator: Draft202012Validator, output) -> str | None:
    """Erste Abweichung vom Schema als kurzer Satz fürs Modell (englisch), sonst None."""
    error = next(iter(validator.iter_errors(output)), None)
    if error is None:
        return None
    location = "/".join(str(p) for p in error.absolute_path) or "root"
    return f"at {location}: {error.message}"[:500]


@api_v1.route("/completions", methods=["POST"])
def completions():
    """Eine Antwort ohne Werkzeuge, optional gegen ein JSON-Schema geprüft.

    Passt die Antwort nicht zum Schema, wird das Modell einmal mit dem
    gefundenen Fehler erneut gefragt; passt sie dann immer noch nicht, kommt
    ``SCHEMA_MISMATCH``.
    """
    values, code = _validate_request(request.get_json(silent=True))
    if values is None:
        return _error(400, code or "VALIDATION_ERROR", FEHLER_EINGABE)

    validator = None
    if values["schema"] is not None:
        try:
            Draft202012Validator.check_schema(values["schema"])
        except SchemaError as fehler:
            log.warning("Ungültiges Schema in /v1/completions: %s", fehler.message)
            return _error(400, "VALIDATION_ERROR", FEHLER_SCHEMA_UNGUELTIG)
        validator = Draft202012Validator(values["schema"])

    try:
        provider = ProviderFactory.create(values["provider"])
    except ValueError as fehler:
        return _error(422, "UNKNOWN_PROVIDER", str(fehler))
    provider_name = values["provider"] or os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER)

    prompt = build_prompt(values["instructions"], values["input"], values["schema"])
    try:
        model_name = provider.effective_model(values["model"])
        output = None
        for attempt in (1, 2):
            try:
                output = provider.execute(prompt, model=values["model"], timeout=values["timeout"])
            except NotJson:
                problem = "the answer was not valid JSON"
            else:
                problem = first_schema_problem(validator, output) if validator else None
                if problem is None:
                    break
            log.warning("Antwort passt nicht (Versuch %s): %s", attempt, problem)
            if attempt == 2:
                return _error(422, "SCHEMA_MISMATCH", FEHLER_SCHEMA_PASST_NICHT)
            prompt += RETRY_INSTRUCTION.format(problem=problem)
    except UnknownModel as fehler:
        return _error(422, "UNKNOWN_MODEL", str(fehler))
    except ProviderTimeout as fehler:
        log.error("Zeitüberschreitung in /v1/completions: %s", fehler)
        return _error(504, "TIMEOUT", str(fehler))
    except RuntimeError as fehler:
        # Die Sätze sind in den Providern bereits übersetzt, Ursache im Log.
        log.error("Anbieter nicht verfügbar in /v1/completions: %s", fehler)
        return _error(503, "PROVIDER_UNAVAILABLE", str(fehler))
    except Exception:
        log.exception("Unerwarteter Fehler in /v1/completions")
        return _error(500, "INTERNAL", FEHLER_UNBEKANNT)

    log.info("Antwort für Skytech X geliefert, Anbieter %s, Modell %s", provider_name, model_name)
    # Nutzungsdaten liefern die Anbieter hier noch nicht; das Feld fehlt dann
    # ganz, statt mit einem Leerwert zu erscheinen.
    return jsonify({"output": output, "provider": provider_name, "model": model_name})


@api_v1.route("/<path:rest>", methods=["GET", "POST", "PUT", "DELETE"])
def not_found(rest: str):
    """Unbekannte /v1-Pfade antworten im Fehlerformat des Vertrags, statt auf
    die Oberfläche zu fallen. Betrifft bis M5 auch /v1/runs."""
    log.info("Unbekannter Endpunkt /v1/%s angefragt", rest)
    return _error(404, "NOT_FOUND", "Diesen Endpunkt gibt es in dieser Version noch nicht.")
