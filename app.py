import os

from flask import Flask, jsonify, request

from providers.factory import ProviderFactory

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
