import os

from flask import Flask, jsonify, request

from config_loader import apply_options_to_env, load_options
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.factory import DEFAULT_PROVIDER, ProviderFactory
from providers.gemini_provider import DEFAULT_MODEL as GEMINI_DEFAULT_MODEL
from providers.gemini_provider import GEMINI_MODELS

# Load the Home Assistant add-on options (/data/options.json) and expose the
# relevant values as environment variables before the first request arrives.
apply_options_to_env(load_options())

app = Flask(__name__)


@app.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json(silent=True) or {}
    prompt = payload.get("prompt")
    if not prompt:
        return jsonify({"error": "Missing 'prompt' in request body"}), 400

    provider_name = payload.get("provider")
    model = payload.get("model")

    try:
        provider = ProviderFactory.create(provider_name)
        result = provider.execute(prompt, model=model)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/models", methods=["GET"])
def models():
    """Listet Provider und Modelle auf, damit Home-Assistant-Skripte die
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
