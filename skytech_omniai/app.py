import os

from flask import Flask, jsonify, request

from config_loader import apply_options_to_env, load_options
from providers.factory import ProviderFactory

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

    try:
        provider = ProviderFactory.create(provider_name)
        result = provider.execute(prompt)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
