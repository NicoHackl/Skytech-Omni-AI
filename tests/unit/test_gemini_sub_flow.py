"""Ablauf von der Anmeldung bis zur Antwort — über die HTTP-Schnittstelle.

Zusammen getestet wird, was die Einzeltests nur getrennt prüfen: Endpunkte, die
echte Anmeldung (mit Pty und Prozess), der Provider mit seinen Einstellungen und
das Aufräumen. Statt der Google-CLI läuft ein Skript, das ihren Ablauf nachspielt.
"""

import json
import stat
import sys
import textwrap
import time

import pytest

import app as app_module
from app import app as flask_app
from providers import gemini_sub_login
from providers import gemini_sub_provider as cli

CODE = "4/0AFLOW-CODE-12345"
INGRESS = {"REMOTE_ADDR": app_module.INGRESS_PROXY_ADDR}

SCRIPT = f"""
import json, os, sys, time
home = os.environ["HOME"]
token = os.path.join(home, ".gemini", "antigravity-cli", "antigravity-oauth-token")
if sys.argv[1] == "models":
    sys.exit(0 if os.path.exists(token) else 1)
if not os.path.exists(token):
    print("Authentication required. Please visit the URL to log in:", file=sys.stderr)
    print("  https://accounts.google.com/o/oauth2/auth?state=x", file=sys.stderr)
    print("", file=sys.stderr, flush=True)
    if sys.stdin.readline().strip() != "{CODE}":
        print(json.dumps({{"conversation_id": "", "status": "ERROR", "error": "invalid_grant"}}))
        sys.exit(1)
    os.makedirs(os.path.dirname(token), exist_ok=True)
    open(token, "w").write(json.dumps({{"token": {{"refresh_token": "x"}}}}))
    print(json.dumps({{"conversation_id": "k1", "status": "SUCCESS", "response": "{{}}"}}))
    sys.exit(0)
answer = json.dumps({{"antwort": "Hallo aus dem Ablauf"}})
print(json.dumps({{"conversation_id": "k2", "status": "SUCCESS", "response": answer}}))
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    script = tmp_path / "fake-agy"
    script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(SCRIPT), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(cli, "AGY_BINARY", str(script))
    # Eine frische Anmeldung statt der gemeinsamen des Add-ons.
    monkeypatch.setattr(app_module, "gemini_login", gemini_sub_login.GeminiLogin())
    flask_app.config["TESTING"] = True
    yield flask_app.test_client()
    app_module.gemini_login.cancel()


def _status(client):
    return client.get("/auth/gemini", environ_base=INGRESS).get_json()


def _wait_idle(client):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        status = _status(client)
        if status["state"] == "idle":
            return status
        time.sleep(0.05)
    pytest.fail(f"Anmeldung wurde nicht fertig: {_status(client)}")


def test_from_login_to_answer_and_back(client):
    # Vor der Anmeldung: erreichbar, aber ohne Zugang.
    status = _status(client)
    assert status["available"] is True
    assert status["signed_in"] is False
    assert client.get("/status").get_json()["credentials"]["gemini_sub"] is False
    antwort = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_sub"})
    assert antwort.status_code == 500
    assert "Google-Anmeldung" in antwort.get_json()["error"]

    # Anmelden: Adresse holen, Code einfügen, warten.
    gestartet = client.post("/auth/gemini/start", environ_base=INGRESS).get_json()
    assert gestartet["state"] == "waiting"
    assert gestartet["url"].startswith("https://accounts.google.com/")
    client.post("/auth/gemini/code", json={"code": CODE}, environ_base=INGRESS)
    fertig = _wait_idle(client)
    assert fertig["signed_in"] is True
    assert fertig["error"] is None
    assert client.get("/status").get_json()["credentials"]["gemini_sub"] is True

    # Anfragen laufen jetzt durch — mit Einstellungen und ohne Reste.
    antwort = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_sub"})
    assert antwort.status_code == 200
    assert antwort.get_json() == {"antwort": "Hallo aus dem Ablauf"}
    settings = json.loads((cli.state_dir() / "settings.json").read_text())
    assert "command(*)" in settings["permissions"]["deny"]
    assert list(cli.workspace_dir().iterdir()) == []

    # Abmelden: wieder ohne Zugang.
    assert client.delete("/auth/gemini", environ_base=INGRESS).get_json()["signed_in"] is False
    assert client.get("/status").get_json()["credentials"]["gemini_sub"] is False
    assert (
        client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_sub"}).status_code == 500
    )


def test_a_wrong_code_leaves_the_account_signed_out(client):
    client.post("/auth/gemini/start", environ_base=INGRESS)

    client.post("/auth/gemini/code", json={"code": "4/0AFALSCH-99999"}, environ_base=INGRESS)
    status = _wait_idle(client)

    assert status["signed_in"] is False
    assert "neu starten" in status["error"]
    # Und danach geht ein neuer Versuch.
    assert client.post("/auth/gemini/start", environ_base=INGRESS).get_json()["state"] == "waiting"


def test_the_open_port_neither_shows_the_address_nor_starts_a_login(client):
    assert client.post("/auth/gemini/start").status_code == 403
    client.post("/auth/gemini/start", environ_base=INGRESS)

    assert client.get("/auth/gemini").get_json()["url"] is None
