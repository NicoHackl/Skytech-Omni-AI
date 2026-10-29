"""Anmeldung für Gemini Web; Schreiben ausschließlich über den Home-Assistant-Ingress."""

import logging

from flask import Blueprint, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from providers import gemini_web_accounts as accounts
from providers import gemini_web_provider as provider

log = logging.getLogger("omniai.gemini_web.routes")
FEHLER_EINGABE = "Bitte den Namen und beide Anmeldewerte prüfen."
FEHLER_AKTION = "Die Google-Anmeldung konnte nicht geändert werden. Bitte erneut versuchen."


def create_blueprint(from_ingress) -> Blueprint:
    """Nutzt dieselbe Herkunftsprüfung wie die bestehenden Einstellungen."""
    blueprint = Blueprint("gemini_web_auth", __name__, url_prefix="/auth/gemini-web")

    @blueprint.before_request
    def protect():
        if request.method != "GET" and not from_ingress():
            return jsonify(
                {"error": "Die Anmeldung geht nur in Home Assistant über die Seitenleiste."}
            ), 403
        request.max_content_length = 24 * 1024
        return None

    @blueprint.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        return jsonify(
            {"error": "Die Anmeldewerte sind zu lang. Bitte die Werte erneut kopieren."}
        ), 413

    @blueprint.errorhandler(ValueError)
    def invalid(error):
        # Nur eigene Eingabefehler sind für den Nutzer formuliert.
        message = str(error) if isinstance(error, accounts.AccountError) else FEHLER_EINGABE
        return jsonify({"error": message}), 400

    @blueprint.errorhandler(RuntimeError)
    def failed(error):
        return jsonify({"error": str(error)}), 503

    @blueprint.errorhandler(OSError)
    def storage_failed(error):
        log.error("Private Google-Anmeldung konnte nicht gespeichert oder entfernt werden")
        return jsonify({"error": FEHLER_AKTION}), 500

    @blueprint.route("", methods=["GET"])
    def status():
        return jsonify(accounts.public_status())

    @blueprint.route("", methods=["POST"])
    def add():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": FEHLER_EINGABE}), 400
        return jsonify(
            provider.add_account(
                payload.get("label", ""),
                payload.get("psid"),
                payload.get("psidts"),
            )
        )

    @blueprint.route("/<account_id>", methods=["DELETE"])
    def remove(account_id):
        return jsonify(provider.remove_account(account_id))

    @blueprint.route("/models", methods=["POST"])
    def models():
        return jsonify({"models": provider.refresh_models()})

    return blueprint
