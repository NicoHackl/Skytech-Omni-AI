"""HTTP-Schnittstelle des Add-ons.

Nimmt Prompts entgegen, reicht sie an den gewählten KI-Provider weiter und
liefert dessen Antwort als JSON zurück. Aus demselben Prozess wird zusätzlich
die gebaute Weboberfläche ausgeliefert, damit Home Assistant sie über seinen
Ingress einblenden kann.

Grundsatz für alle Antworten: technische Ursachen gehen ins Log, der
Antwortrumpf enthält einen deutschen Satz ohne Statuscode, Klassennamen,
Pfad oder Rohausgabe des Modells.
"""

import logging
import os
import re
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory
from waitress import serve
from werkzeug.exceptions import NotFound

from api_v1 import api_v1
from config_loader import OPTIONS_PATH, apply_options_to_env, load_options, read_addon_version
from providers.base_provider import resolve_tool_access
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.factory import DEFAULT_PROVIDER, ProviderFactory
from providers.gemini_agy_login import LoginError
from providers.gemini_agy_login import login as gemini_login
from providers.gemini_agy_provider import available_models as gemini_agy_models
from providers.gemini_agy_provider import is_signed_in as gemini_agy_signed_in
from providers.gemini_agy_provider import refresh_models as gemini_agy_refresh_models
from providers.gemini_provider import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from providers.gemini_provider import GEMINI_MODELS
from settings import merge_update, public_view, revision
from supervisor_client import SupervisorClient, SupervisorRejected, SupervisorUnavailable

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    # Datum TT.MM.JJJJ, Uhrzeit ohne Zonenzusatz. Die Zone kommt über TZ aus
    # der Umgebung und wird nicht mitgeschrieben.
    datefmt="%d.%m.%Y %H:%M:%S",
)
log = logging.getLogger("omniai")

# Die Add-on-Optionen (/data/options.json) werden beim Start gelesen und als
# Umgebungsvariablen abgelegt, bevor die erste Anfrage eintrifft. Speichert die
# Seite „Einstellungen“ neu, setzt PUT /settings die Umgebung erneut.
apply_options_to_env(load_options())

# Verzeichnis mit dem gebauten Bündel der Oberfläche. Fehlt es, läuft das
# Add-on trotzdem — dann gibt es eben nur die Schnittstelle.
WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"

# Home Assistant hängt das Add-on unter einem Pfad mit Sitzungs-Token ein, der
# bei jedem Aufruf ein anderer ist. Erlaubt sind nur die Zeichen, die in einem
# solchen Pfad vorkommen können — der Wert landet im Markup und wird deshalb
# nicht ungeprüft übernommen.
INGRESS_PFAD_MUSTER = re.compile(r"^/[A-Za-z0-9._~/-]*$")

FEHLER_UNBEKANNT = "Die Anfrage konnte nicht bearbeitet werden. Bitte später erneut versuchen."
FEHLER_NUR_INGRESS = "Einstellungen lassen sich nur in Home Assistant über die Seitenleiste ändern."
FEHLER_NUR_LESEN = (
    "Die Einstellungen lassen sich nur ändern, wenn das Add-on in Home Assistant läuft."
)
FEHLER_KONFLIKT = (
    "Die Einstellungen wurden inzwischen anderswo geändert. Bitte neu laden und erneut speichern."
)
FEHLER_UNGUELTIG = "Bitte die markierten Felder prüfen."
FEHLER_EINSTELLUNGEN = "Die Einstellungen konnten nicht gespeichert werden."
FEHLER_ANMELDUNG_NUR_INGRESS = (
    "Die Anmeldung bei Google geht nur in Home Assistant über die Seitenleiste."
)
FEHLER_ANMELDUNG_EINGABE = "Bitte den Code von Google einfügen."

# Über diese Adresse reicht der Supervisor die Aufrufe aus der Seitenleiste von
# Home Assistant herein — erst nachdem Home Assistant den Nutzer angemeldet
# hat. Port 8000 ist dagegen unauthentifiziert; wer dort die Einstellungen
# ändern könnte, könnte die Werkzeugstufe „full“ setzen und damit an die
# Zugänge unter /data gelangen. Der Kopf X-Ingress-Path taugt nicht als Beleg,
# den kann jeder Aufrufer selbst mitschicken.
INGRESS_PROXY_ADDR = "172.30.32.2"

FEHLER_OHNE_OBERFLAECHE = (
    "Die Oberfläche wurde nicht mit ausgeliefert. Die Schnittstelle des Add-ons "
    "ist davon nicht betroffen und funktioniert weiter."
)

app = Flask(__name__)
# Schnittstelle v1 für Skytech X mit Token-Pflicht (D-019), eigenes Modul.
app.register_blueprint(api_v1)


# --- Schnittstelle ---------------------------------------------------------


@app.route("/ask", methods=["POST"])
def ask():
    """Führt einen Prompt gegen den gewählten Provider aus.

    Erwartet ``prompt`` und optional ``provider`` und ``model``. Antwortet mit
    dem geparsten JSON des Modells oder mit ``{"error": "<deutscher Satz>"}``.
    """
    payload = request.get_json(silent=True) or {}
    prompt = payload.get("prompt")
    if not prompt:
        return jsonify({"error": "Es wurde kein Prompt übergeben."}), 400

    try:
        provider = ProviderFactory.create(payload.get("provider"))
        result = provider.execute(prompt, model=payload.get("model"))
        return jsonify(result)
    except ValueError as fehler:
        # Falscher Provider- oder Modellname. Der Text ist bereits so
        # formuliert, dass ihn ein Mensch lesen kann.
        log.warning("Anfrage abgelehnt: %s", fehler)
        return jsonify({"error": str(fehler)}), 400
    except RuntimeError as fehler:
        # Der Provider hat abgelehnt oder war nicht erreichbar. Auch diese
        # Meldungen sind in den Providern bereits übersetzt.
        log.error("Anfrage fehlgeschlagen: %s", fehler)
        return jsonify({"error": str(fehler)}), 500
    except Exception:
        log.exception("Unerwarteter Fehler bei der Anfrage")
        return jsonify({"error": FEHLER_UNBEKANNT}), 500


@app.route("/models", methods=["GET"])
def models():
    """Listet Provider und Modelle auf, damit Skripte und Oberfläche die
    gültigen Werte abfragen können, statt sie fest zu verdrahten.

    ``default`` ist das Modell, das der Provider ohne explizite Angabe nutzt;
    ``null`` bedeutet, dass der Provider selbst entscheidet.
    """
    return jsonify(
        {
            "active_provider": os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER),
            "providers": {
                "claude_sub": {"models": CLAUDE_MODELS, "default": None},
                "codex_sub": {"models": CODEX_MODELS, "default": None},
                "gemini": {
                    "models": GEMINI_MODELS,
                    "default": GEMINI_DEFAULT_MODEL,
                },
                # Die Liste kommt von der Google-Befehlszeile (nach der Anmeldung), nicht
                # aus dem Code; ``default`` ist die Option „gemini_agy_model“.
                "gemini_agy": {
                    "models": gemini_agy_models(),
                    "default": os.environ.get("GEMINI_AGY_MODEL", "").strip() or None,
                },
            },
        }
    )


def _default_model() -> str | None:
    """Standardmodell des aktiven Anbieters. Google Gemini (AGY) hat eine eigene
    Option, weil sein Auswahlfeld keine feste Liste haben kann."""
    if os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER) == "gemini_agy":
        return os.environ.get("GEMINI_AGY_MODEL", "").strip() or None
    return os.environ.get("OMNIAI_MODEL") or None


@app.route("/status", methods=["GET"])
def status():
    """Zustand des Add-ons für die Oberfläche.

    Zu den Zugängen wird ausschließlich gemeldet, **ob** einer hinterlegt ist —
    nie der Wert selbst und auch nicht, wie lang er ist.

    ``tool_access`` kommt aus derselben Auflösung wie im Provider, damit die
    Oberfläche nicht die rohe Option zeigt, sondern die Stufe, die tatsächlich
    gilt — ein vertippter Wert fällt dort auf die Vorgabe zurück.
    """
    return jsonify(
        {
            "provider": os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER),
            "version": read_addon_version(),
            "default_model": _default_model(),
            "tool_access": resolve_tool_access(),
            "credentials": {
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
                # Die Anmeldung entsteht im Add-on selbst (Seite „Einstellungen“)
                # und liegt als Datei unter /data, nicht in der Umgebung.
                "gemini_agy": gemini_agy_signed_in(),
            },
        }
    )


def _from_ingress() -> bool:
    """Kommt die Anfrage über den Ingress von Home Assistant?"""
    return request.remote_addr == INGRESS_PROXY_ADDR


def _stored_options(supervisor: SupervisorClient) -> tuple[dict, bool]:
    """Gespeicherte Optionen und ob sie aus dem Supervisor stammen.

    Ohne Supervisor (außerhalb von Home Assistant) oder wenn er gerade nicht
    antwortet, gilt die Datei, die beim Start gelesen wurde — die Seite zeigt
    dann den Stand an, lässt aber nichts speichern.
    """
    if supervisor.available:
        try:
            return supervisor.get_self_options(), True
        except (SupervisorUnavailable, SupervisorRejected) as fehler:
            log.warning("Optionen nicht vom Supervisor lesbar, es gilt die Datei: %s", fehler)
    return load_options(), False


@app.route("/settings", methods=["GET"])
def settings_read():
    """Einstellungen für die gleichnamige Seite der Oberfläche.

    Zugänge kommen nur als „hinterlegt ja/nein“ zurück — dieselbe Auskunft,
    die ``/status`` ohnehin gibt. ``can_save`` sagt der Oberfläche, ob sie ein
    Formular oder nur eine Anzeige rendert; ``read_only_reason`` warum nicht:
    ``supervisor`` (kein Zugang zu den Optionen) oder ``ingress`` (Aufruf über
    den offenen Port). Die Oberfläche übersetzt das in einen Satz.
    """
    supervisor = SupervisorClient()
    options, from_supervisor = _stored_options(supervisor)
    if not from_supervisor:
        reason = "supervisor"
    elif not _from_ingress():
        reason = "ingress"
    else:
        reason = None
    return jsonify({**public_view(options), "can_save": reason is None, "read_only_reason": reason})


@app.route("/settings", methods=["PUT"])
def settings_save():
    """Speichert die Einstellungen und übernimmt sie ohne Neustart.

    Erwartet ``options`` (Entwurf der Oberfläche) und ``stored_revision`` (der
    Stand, auf dem der Entwurf beruht). Die Provider lesen ihre Werte bei
    jeder Anfrage aus der Umgebung; nach dem Speichern genügt es deshalb, sie
    neu zu setzen.
    """
    if not _from_ingress():
        log.warning("Speichern der Einstellungen von %s abgelehnt", request.remote_addr)
        return jsonify({"error": FEHLER_NUR_INGRESS}), 403

    supervisor = SupervisorClient()
    if not supervisor.available:
        return jsonify({"error": FEHLER_NUR_LESEN}), 503

    payload = request.get_json(silent=True)
    draft = payload.get("options") if isinstance(payload, dict) else None
    if not isinstance(draft, dict):
        return jsonify({"error": FEHLER_EINSTELLUNGEN}), 400

    try:
        current = supervisor.get_self_options()
        if payload.get("stored_revision") != revision(current):
            return jsonify({"error": FEHLER_KONFLIKT}), 409

        merged, field_errors = merge_update(current, draft)
        if field_errors:
            return jsonify({"error": FEHLER_UNGUELTIG, "field_errors": field_errors}), 422

        valid, message = supervisor.validate_options(merged)
        if not valid:
            # Die Meldung des Supervisors ist englisch und nennt Schemafelder —
            # sie gehört ins Log, nicht auf den Bildschirm.
            log.warning("Supervisor lehnt die Einstellungen ab: %s", message)
            return jsonify({"error": FEHLER_EINSTELLUNGEN}), 422

        supervisor.save_options(merged)
    except (SupervisorUnavailable, SupervisorRejected) as fehler:
        # Die Sätze sind im Client bereits übersetzt, die Ursache steht im Log.
        return jsonify({"error": str(fehler)}), 502

    apply_options_to_env(merged, clear_missing=True)
    log.info("Einstellungen über die Oberfläche gespeichert")
    return jsonify({**public_view(merged), "can_save": True, "read_only_reason": None})


# --- Anmeldung bei Google (gemini_agy) -------------------------------------


def _login_refused():
    """Antwort, wenn die Anfrage nicht über den Ingress kam — sonst ``None``.

    Wer den offenen Port erreicht, soll weder eine Anmeldung starten noch
    entfernen können, und die Anmeldeadresse bekommt er auch nicht zu sehen.
    """
    if _from_ingress():
        return None
    log.warning("Anmeldung bei Google von %s abgelehnt", request.remote_addr)
    return jsonify({"error": FEHLER_ANMELDUNG_NUR_INGRESS}), 403


def _login_failed(fehler: LoginError):
    """Übersetzt eine abgelehnte Anmeldung in eine Antwort mit fertigem Satz."""
    log.warning("Anmeldung bei Google nicht fortgesetzt: %s", fehler)
    if fehler.invalid:
        return jsonify({"error": str(fehler), "field_errors": {fehler.field: str(fehler)}}), 422
    if fehler.missing:
        return jsonify({"error": str(fehler)}), 404
    return jsonify({"error": str(fehler)}), 409 if fehler.busy else 400


@app.route("/auth/gemini-agy", methods=["GET"])
def gemini_login_status():
    """Zustand der Anmeldung für die Seite „Einstellungen“.

    Die Adresse, unter der sich der Nutzer anmeldet, kommt nur über den Ingress
    zurück; ``signed_in`` ist dieselbe Auskunft wie in ``/status``.
    """
    return jsonify(gemini_login.status(include_url=_from_ingress()))


@app.route("/auth/gemini-agy/start", methods=["POST"])
def gemini_login_start():
    """Startet die Anmeldung eines **neuen Kontos** und liefert die Adresse bei Google.

    Der Rumpf darf ``label`` tragen, den Namen des Kontos in der Oberfläche.
    """
    refused = _login_refused()
    if refused:
        return refused
    payload = request.get_json(silent=True)
    label = payload.get("label") if isinstance(payload, dict) else ""
    try:
        return jsonify(gemini_login.start(label if isinstance(label, str) else ""))
    except LoginError as fehler:
        return _login_failed(fehler)
    except Exception:
        log.exception("Unerwarteter Fehler beim Start der Anmeldung bei Google")
        return jsonify({"error": FEHLER_UNBEKANNT}), 500


@app.route("/auth/gemini-agy/code", methods=["POST"])
def gemini_login_code():
    """Nimmt den Code entgegen, den Google nach der Anmeldung anzeigt."""
    refused = _login_refused()
    if refused:
        return refused
    payload = request.get_json(silent=True)
    code = payload.get("code") if isinstance(payload, dict) else None
    if not isinstance(code, str) or not code.strip():
        return jsonify(
            {"error": FEHLER_ANMELDUNG_EINGABE, "field_errors": {"code": FEHLER_ANMELDUNG_EINGABE}}
        ), 422
    try:
        return jsonify(gemini_login.submit(code))
    except LoginError as fehler:
        return _login_failed(fehler)
    except Exception:
        log.exception("Unerwarteter Fehler bei der Anmeldung bei Google")
        return jsonify({"error": FEHLER_UNBEKANNT}), 500


@app.route("/auth/gemini-agy/cancel", methods=["POST"])
def gemini_login_cancel():
    """Bricht eine laufende Anmeldung ab."""
    refused = _login_refused()
    if refused:
        return refused
    return jsonify(gemini_login.cancel())


@app.route("/auth/gemini-agy/models", methods=["POST"])
def gemini_login_models():
    """Holt die Modelle der Google-Befehlszeile neu, etwa nach einem Wechsel des Tarifs.

    Läuft gerade eine Anfrage, bleibt die bisherige Liste; auf die Sperre wird nicht
    gewartet.
    """
    refused = _login_refused()
    if refused:
        return refused
    return jsonify({"models": [model.label for model in gemini_agy_refresh_models(force=True)]})


@app.route("/auth/gemini-agy/<account_id>", methods=["DELETE"])
def gemini_login_remove(account_id: str):
    """Entfernt ein Konto samt Anmeldung. Widerrufen lässt sie sich nur im Google-Konto."""
    refused = _login_refused()
    if refused:
        return refused
    try:
        return jsonify(gemini_login.logout(account_id))
    except LoginError as fehler:
        return _login_failed(fehler)
    except Exception:
        log.exception("Unerwarteter Fehler beim Entfernen eines Google-Kontos")
        return jsonify({"error": FEHLER_UNBEKANNT}), 500


# Name im Sidebar-Fuß, solange der Supervisor den echten nicht liefert.
ADDON_FALLBACK_NAME = "Skytech OmniAI"

# Supervisor-Slugs bestehen aus Kleinbuchstaben, Ziffern und Unterstrichen. Was
# anders aussieht, wird nicht zu einem Pfad im Frontend von Home Assistant.
SLUG_MUSTER = re.compile(r"[a-z0-9_]+")

# Name und Konfigurationsseite ändern sich zur Laufzeit nicht; gemerkt wird
# nur ein Erfolg, ein Ausfall wird beim nächsten Aufruf erneut versucht.
_addon_link: dict = {}


@app.route("/addon", methods=["GET"])
def addon():
    """Name und Konfigurationsseite des Add-ons in Home Assistant (D-018).

    Speist den Fuß der Sidebar. Der Slug trägt das Präfix des
    Add-on-Repositorys (z. B. ``b80e8355_skytech_omniai``) und steht nur beim
    Supervisor. Ohne ihn fehlt nur der Link — die Antwort ist immer 200.
    """
    if not _addon_link:
        supervisor = SupervisorClient()
        if supervisor.available:
            try:
                info = supervisor.get_self_info()
            except (SupervisorUnavailable, SupervisorRejected) as fehler:
                log.warning("Add-on-Slug nicht abrufbar, Sidebar-Fuß ohne Link: %s", fehler)
                info = {}
            slug = str(info.get("slug") or "")
            if SLUG_MUSTER.fullmatch(slug):
                _addon_link.update(
                    name=str(info.get("name") or ADDON_FALLBACK_NAME),
                    config_path=f"/config/app/{slug}/config",
                )
            elif info:
                log.warning("Supervisor meldet keinen gültigen Add-on-Slug, Sidebar-Fuß ohne Link")
    return jsonify(dict(_addon_link) or {"name": ADDON_FALLBACK_NAME, "config_path": None})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# --- Oberfläche ------------------------------------------------------------


def _ingress_basis() -> str:
    """Pfad, unter dem Home Assistant das Add-on gerade einblendet.

    Steht im Kopf ``X-Ingress-Path`` und wechselt mit jeder Sitzung. Wird das
    Add-on direkt über seinen Port aufgerufen, fehlt der Kopf und die Wurzel
    ist die richtige Basis.
    """
    pfad = request.headers.get("X-Ingress-Path", "").rstrip("/")
    if not pfad:
        return "/"
    if not INGRESS_PFAD_MUSTER.match(pfad):
        log.warning("Unerwarteter Ingress-Pfad im Kopf, wird ignoriert: %r", pfad)
        return "/"
    return pfad + "/"


def _index_ausliefern() -> Response:
    """Liefert die ``index.html`` mit passend gesetztem ``<base>``-Element.

    Alle Verweise im Bündel sind relativ. Ohne ein ``<base>``, das auf den
    aktuellen Ingress-Pfad zeigt, würden sie beim Aufruf einer Unterseite ins
    Leere zeigen. Weil der Pfad je Sitzung wechselt, darf die Seite nicht
    zwischengespeichert werden.
    """
    index = WEB_DIST / "index.html"
    if not index.is_file():
        log.error("Oberfläche fehlt: %s wurde nicht gefunden", index)
        return Response(FEHLER_OHNE_OBERFLAECHE, status=503, mimetype="text/plain")

    html = index.read_text(encoding="utf-8").replace(
        "<head>", f'<head><base href="{_ingress_basis()}">', 1
    )
    antwort = Response(html, mimetype="text/html")
    antwort.headers["Cache-Control"] = "no-store"
    return antwort


@app.route("/", methods=["GET"])
def spa_wurzel() -> Response:
    return _index_ausliefern()


@app.route("/<path:datei>", methods=["GET"])
def spa_datei(datei: str) -> Response:
    """Liefert eine Datei des Bündels; jede unbekannte Route bekommt die
    ``index.html``, damit das Routing im Browser übernehmen kann.

    Die Prüfung, ob der Pfad überhaupt im Bündelverzeichnis liegt, übernimmt
    ``send_from_directory``: es weist Ausbruchsversuche mit ``..`` genauso ab
    wie eine schlicht nicht vorhandene Datei.
    """
    try:
        return send_from_directory(WEB_DIST, datei)
    except NotFound:
        return _index_ausliefern()


if __name__ == "__main__":
    # Liegt eine Optionsdatei vor, läuft das Add-on in Home Assistant — dann
    # muss der Supervisor-Token da sein. Fehlt er, kann die Seite
    # „Einstellungen“ nichts speichern; das soll im Log stehen, nicht erst
    # auffallen, wenn jemand vergeblich speichern will.
    if Path(OPTIONS_PATH).is_file() and not SupervisorClient().available:
        log.warning(
            "SUPERVISOR_TOKEN fehlt in der Umgebung — die Seite „Einstellungen“ "
            "kann nichts speichern. Startbefehl im Dockerfile prüfen (with-contenv)."
        )
    port = int(os.environ.get("PORT", 8000))
    log.info("Skytech OmniAI startet auf Port %s", port)
    serve(app, host="0.0.0.0", port=port, threads=8)
