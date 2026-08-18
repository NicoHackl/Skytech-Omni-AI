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

from config_loader import apply_options_to_env, load_options, read_addon_version
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.factory import DEFAULT_PROVIDER, ProviderFactory
from providers.gemini_provider import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from providers.gemini_provider import GEMINI_MODELS

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    # Datum TT.MM.JJJJ, Uhrzeit ohne Zonenzusatz. Die Zone kommt über TZ aus
    # der Umgebung und wird nicht mitgeschrieben.
    datefmt="%d.%m.%Y %H:%M:%S",
)
log = logging.getLogger("omniai")

# Die Add-on-Optionen (/data/options.json) werden einmal beim Start gelesen und
# als Umgebungsvariablen abgelegt, bevor die erste Anfrage eintrifft.
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
FEHLER_OHNE_OBERFLAECHE = (
    "Die Oberfläche wurde nicht mit ausgeliefert. Die Schnittstelle des Add-ons "
    "ist davon nicht betroffen und funktioniert weiter."
)

app = Flask(__name__)


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
                "gemini": {
                    "models": GEMINI_MODELS,
                    "default": GEMINI_DEFAULT_MODEL,
                },
            },
        }
    )


@app.route("/status", methods=["GET"])
def status():
    """Zustand des Add-ons für die Oberfläche.

    Zu den Zugängen wird ausschließlich gemeldet, **ob** einer hinterlegt ist —
    nie der Wert selbst und auch nicht, wie lang er ist.
    """
    return jsonify(
        {
            "provider": os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER),
            "version": read_addon_version(),
            "default_model": os.environ.get("OMNIAI_MODEL") or None,
            "credentials": {
                "claude_sub": bool(
                    os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", "").strip()
                    or os.environ.get("ANTHROPIC_API_KEY", "").strip()
                ),
                "gemini": bool(
                    os.environ.get("GEMINI_API_KEY", "").strip()
                    or os.environ.get("GOOGLE_API_KEY", "").strip()
                ),
            },
        }
    )


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
    port = int(os.environ.get("PORT", 8000))
    log.info("Skytech OmniAI startet auf Port %s", port)
    serve(app, host="0.0.0.0", port=port, threads=8)
