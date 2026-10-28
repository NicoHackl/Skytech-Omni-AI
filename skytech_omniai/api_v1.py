"""Schnittstelle v1 für Skytech X (D-019).

Vertrag: ``docs/contracts/omniai-api-v1.yaml`` (Kopie; Masterkopie im Repo
Skytech-X-Backend). Anders als ``/ask`` ist jeder Aufruf hier mit einem Token
geschützt, Fehler tragen zusätzlich einen stabilen Code, und Antworten lassen
sich gegen ein JSON-Schema prüfen.

Umgesetzt sind Gesundheit, Fähigkeiten, Einmal-Antworten und Agent-Läufe
(``/v1/runs``, Ausführung in ``runs.py``, D-021).
"""

import hmac
import json
import logging
import os
import re

from flask import Blueprint, Response, jsonify, request, stream_with_context
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

import embeddings
from config_loader import read_addon_version
from providers.base_provider import NotJson, ProviderTimeout, UnknownModel
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.factory import DEFAULT_PROVIDER, ProviderFactory
from providers.gemini_provider import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from providers.gemini_provider import GEMINI_MODELS
from providers.gemini_sub_provider import available_models as gemini_sub_models
from providers.gemini_sub_provider import is_signed_in as gemini_sub_signed_in
from runs import MAX_CONCURRENT_RUNS, MAX_RUN_MINUTES, RunConflict, RunManager

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
    # Die Modelle kennt die Google-Befehlszeile erst nach der Anmeldung; die Liste
    # wird beim Abruf geholt (Funktion statt Liste).
    "gemini_sub": {"name": "Google Gemini (Abo)", "models": gemini_sub_models, "default": None},
}

# Anbieter, die in Läufen Werkzeuge (MCP) aufrufen können.
TOOL_PROVIDERS = {"claude_sub"}
MCP_PROTOCOL_VERSIONS = ["2025-11-25"]
MAX_CONTEXT_LENGTH = 40_000
SSE_PING_SECONDS = 15

_RUN_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")
_PROVIDER_ID = re.compile(r"^[a-z0-9_-]{1,32}$")
_SERVER_NAME = re.compile(r"^[a-z0-9_-]{1,32}$")

runs = RunManager()

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
FEHLER_KEINE_WERKZEUGE = "Dieser Anbieter kann in Läufen keine Werkzeuge benutzen."
FEHLER_LAUF_UNBEKANNT = "Diesen Lauf gibt es nicht."


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
        # Kein Wert in der Umgebung, sondern die Anmeldung, die im Add-on selbst
        # entstanden ist (Einstellungen → Google-Anmeldung).
        "gemini_sub": gemini_sub_signed_in(),
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

    Werkzeuge (MCP) in Läufen kann bisher nur Claude; Nutzungsdaten liefert
    ebenfalls nur Claude, und zwar in Läufen.
    """
    present = credentials_present()
    providers = [
        {
            "id": key,
            "name": meta["name"],
            "available": present[key],
            "models": meta["models"]() if callable(meta["models"]) else meta["models"],
            "defaultModel": meta["default"],
            "features": {
                "tools": key in TOOL_PROVIDERS,
                "structuredOutput": True,
                "usage": key in TOOL_PROVIDERS,
            },
        }
        for key, meta in PROVIDERS.items()
    ]
    return jsonify(
        {
            "providers": providers,
            "limits": {
                "maxPromptLength": MAX_INPUT_LENGTH,
                "maxConcurrentRuns": MAX_CONCURRENT_RUNS,
                "maxRunMinutes": MAX_RUN_MINUTES,
            },
            "mcp": {"protocolVersions": MCP_PROTOCOL_VERSIONS, "transports": ["streamable-http"]},
            "embeddings": {
                "available": embeddings.available(),
                "model": embeddings.MODEL,
                "dimensions": embeddings.DEFAULT_DIMENSIONS,
            },
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


# --- Embeddings ---------------------------------------------------------------


@api_v1.route("/embeddings", methods=["POST"])
def create_embeddings():
    """Vektoren für Texte, ausschließlich mit ``gemini-embedding-001`` (D-023)."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _error(400, "VALIDATION_ERROR", FEHLER_EINGABE)
    texts = payload.get("input")
    task_type = payload.get("taskType", "RETRIEVAL_DOCUMENT")
    dimensions = payload.get("dimensions", embeddings.DEFAULT_DIMENSIONS)
    if (
        not isinstance(texts, list)
        or not 1 <= len(texts) <= embeddings.MAX_INPUTS
        or not all(
            isinstance(t, str) and t.strip() and len(t) <= embeddings.MAX_INPUT_LENGTH
            for t in texts
        )
        or task_type not in embeddings.TASK_TYPES
        or isinstance(dimensions, bool)
        or dimensions not in embeddings.DIMENSIONS
    ):
        return _error(400, "VALIDATION_ERROR", FEHLER_EINGABE)
    try:
        vectors, tokens = embeddings.embed(texts, task_type, dimensions)
    except embeddings.EmbeddingTimeout as fehler:
        return _error(504, "TIMEOUT", str(fehler))
    except RuntimeError as fehler:
        return _error(503, "PROVIDER_UNAVAILABLE", str(fehler))
    log.info(
        "Embeddings für Skytech X geliefert: %s Text(e), %s Dimensionen", len(texts), dimensions
    )
    answer = {"model": embeddings.MODEL, "dimensions": dimensions, "embeddings": vectors}
    if tokens is not None:
        answer["usage"] = {"inputTokens": tokens}
    return jsonify(answer)


# --- Agent-Läufe -------------------------------------------------------------


def _is_text(value, max_length: int, required: bool = False) -> bool:
    if value is None:
        return not required
    return isinstance(value, str) and (value.strip() or not required) and len(value) <= max_length


def _validate_run(payload) -> dict | None:
    """Prüft den Rumpf von POST /v1/runs gegen den Vertrag. None = ungültig."""
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("runId"), str) or not _RUN_ID.match(payload["runId"]):
        return None
    if not isinstance(payload.get("provider"), str) or not _PROVIDER_ID.match(payload["provider"]):
        return None
    if not _is_text(payload.get("prompt"), MAX_INPUT_LENGTH, required=True):
        return None
    if not _is_text(payload.get("instructions"), MAX_INSTRUCTIONS_LENGTH):
        return None
    if not _is_text(payload.get("context"), MAX_CONTEXT_LENGTH):
        return None
    if payload.get("model") is not None and not isinstance(payload["model"], str):
        return None
    schema = payload.get("outputSchema")
    if schema is not None:
        if not isinstance(schema, dict):
            return None
        try:
            Draft202012Validator.check_schema(schema)
        except SchemaError:
            return None
    tools = payload.get("tools") or {}
    if not isinstance(tools, dict):
        return None
    servers = tools.get("mcpServers") or []
    allowed = tools.get("allowedTools") or []
    if not isinstance(servers, list) or len(servers) > 8 or not isinstance(allowed, list):
        return None
    if not all(isinstance(t, str) and 0 < len(t) <= 128 for t in allowed):
        return None
    for server in servers:
        if not isinstance(server, dict) or not isinstance(server.get("name"), str):
            return None
        if not _SERVER_NAME.match(server["name"]):
            return None
        url = server.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            return None
        headers = server.get("headers") or {}
        if not isinstance(headers, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in headers.items()
        ):
            return None
    limits = payload.get("limits") or {}
    if not isinstance(limits, dict):
        return None
    for key in ("maxMinutes", "maxToolCalls"):
        value = limits.get(key)
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 0
        ):
            return None
    return {
        "runId": payload["runId"],
        "provider": payload["provider"],
        "model": payload.get("model") or None,
        "instructions": payload.get("instructions"),
        "context": payload.get("context"),
        "prompt": payload["prompt"],
        "outputSchema": schema,
        "tools": {"mcpServers": servers, "allowedTools": allowed},
        "limits": limits,
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


@api_v1.route("/runs", methods=["POST"])
def start_run():
    """Startet einen Agent-Lauf; dieselbe Anfrage noch einmal liefert den
    bestehenden Lauf (Idempotenz je ``runId``)."""
    values = _validate_run(request.get_json(silent=True))
    if values is None:
        return _error(400, "VALIDATION_ERROR", FEHLER_EINGABE)
    if values["provider"] not in PROVIDERS:
        return _error(
            422, "UNKNOWN_PROVIDER", f"Der Anbieter „{values['provider']}“ ist nicht verfügbar."
        )
    if values["tools"]["mcpServers"] and values["provider"] not in TOOL_PROVIDERS:
        return _error(422, "TOOLS_NOT_SUPPORTED", FEHLER_KEINE_WERKZEUGE)
    try:
        ProviderFactory.create(values["provider"]).effective_model(values["model"])
    except UnknownModel as fehler:
        return _error(422, "UNKNOWN_MODEL", str(fehler))
    except ValueError as fehler:
        return _error(422, "UNKNOWN_PROVIDER", str(fehler))
    if not credentials_present()[values["provider"]]:
        return _error(
            503, "PROVIDER_UNAVAILABLE", "Für diesen Anbieter sind keine Zugangsdaten hinterlegt."
        )
    try:
        run, created = runs.start(values["runId"], values)
    except RunConflict as konflikt:
        return _error(409, konflikt.code, konflikt.message)
    if created:
        log.info(
            "Lauf %s angenommen: Anbieter %s, %s Werkzeug-Server, Vorgang %s",
            run.run_id,
            values["provider"],
            len(values["tools"]["mcpServers"]),
            values["metadata"].get("workItemId") or "-",
        )
    return jsonify(run.state()), 202


@api_v1.route("/runs/<run_id>", methods=["GET"])
def run_state(run_id: str):
    run = runs.get(run_id)
    if run is None:
        return _error(404, "NOT_FOUND", FEHLER_LAUF_UNBEKANNT)
    return jsonify(run.state())


@api_v1.route("/runs/<run_id>/cancel", methods=["POST"])
def cancel_run(run_id: str):
    run = runs.cancel(run_id)
    if run is None:
        return _error(404, "NOT_FOUND", FEHLER_LAUF_UNBEKANNT)
    return jsonify(run.state()), 202


@api_v1.route("/runs/<run_id>/events", methods=["GET"])
def run_events(run_id: str):
    """Ereignisse eines Laufs als Server-Sent Events, fortsetzbar über
    ``Last-Event-ID``; endet nach dem abschließenden Status."""
    run = runs.get(run_id)
    if run is None:
        return _error(404, "NOT_FOUND", FEHLER_LAUF_UNBEKANNT)
    try:
        after = max(int(request.headers.get("Last-Event-ID", "0")), 0)
    except ValueError:
        after = 0

    def stream():
        seq = after
        while True:
            events = runs.events_after(run, seq, SSE_PING_SECONDS)
            if not events:
                if run.terminal and seq >= len(run.events):
                    return
                yield ": ping\n\n"
                continue
            for event in events:
                seq = event["seq"]
                payload = json.dumps(event, ensure_ascii=False)
                yield f"id: {event['seq']}\nevent: {event['type']}\ndata: {payload}\n\n"
            if run.terminal and seq >= len(run.events):
                return

    return Response(
        stream_with_context(stream()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@api_v1.route("/<path:rest>", methods=["GET", "POST", "PUT", "DELETE"])
def not_found(rest: str):
    """Unbekannte /v1-Pfade antworten im Fehlerformat des Vertrags, statt auf
    die Oberfläche zu fallen."""
    log.info("Unbekannter Endpunkt /v1/%s angefragt", rest)
    return _error(404, "NOT_FOUND", "Diesen Endpunkt gibt es in dieser Version noch nicht.")
