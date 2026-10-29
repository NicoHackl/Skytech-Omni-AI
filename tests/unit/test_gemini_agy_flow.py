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
from providers import gemini_agy_login
from providers import gemini_agy_provider as cli

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
if os.path.exists(os.path.join(home, "LEER")):
    error = "Your AI credits balance is too low"
    print(json.dumps({{"conversation_id": "k3", "status": "ERROR", "error": error}}))
    sys.exit(3)
answer = json.dumps({{"antwort": "Hallo aus dem Ablauf", "konto": os.path.basename(home)}})
print(json.dumps({{"conversation_id": "k2", "status": "SUCCESS", "response": answer}}))
"""


@pytest.fixture
def client(tmp_path, monkeypatch):
    script = tmp_path / "fake-agy"
    script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(SCRIPT), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(cli, "AGY_BINARY", str(script))
    # Eine frische Anmeldung statt der gemeinsamen des Add-ons.
    monkeypatch.setattr(app_module, "gemini_login", gemini_agy_login.GeminiLogin())
    flask_app.config["TESTING"] = True
    yield flask_app.test_client()
    app_module.gemini_login.cancel()


def _status(client):
    return client.get("/auth/gemini-agy", environ_base=INGRESS).get_json()


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
    assert client.get("/status").get_json()["credentials"]["gemini_agy"] is False
    antwort = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"})
    assert antwort.status_code == 500
    assert "Google-Anmeldung" in antwort.get_json()["error"]

    # Anmelden: Adresse holen, Code einfügen, warten.
    gestartet = client.post("/auth/gemini-agy/start", environ_base=INGRESS).get_json()
    assert gestartet["state"] == "waiting"
    assert gestartet["url"].startswith("https://accounts.google.com/")
    client.post("/auth/gemini-agy/code", json={"code": CODE}, environ_base=INGRESS)
    fertig = _wait_idle(client)
    assert fertig["signed_in"] is True
    assert fertig["error"] is None
    assert client.get("/status").get_json()["credentials"]["gemini_agy"] is True

    # Anfragen laufen jetzt durch — mit Einstellungen und ohne Reste.
    antwort = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"})
    assert antwort.status_code == 200
    assert antwort.get_json()["antwort"] == "Hallo aus dem Ablauf"
    settings = json.loads((cli.state_dir() / "settings.json").read_text())
    assert "command(*)" in settings["permissions"]["deny"]
    assert list(cli.workspace_dir().iterdir()) == []

    # Abmelden: wieder ohne Zugang.
    entfernt = client.delete("/auth/gemini-agy/konto-1", environ_base=INGRESS).get_json()
    assert entfernt["signed_in"] is False
    assert client.get("/status").get_json()["credentials"]["gemini_agy"] is False
    assert (
        client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"}).status_code == 500
    )


def test_a_wrong_code_leaves_the_account_signed_out(client):
    client.post("/auth/gemini-agy/start", environ_base=INGRESS)

    client.post("/auth/gemini-agy/code", json={"code": "4/0AFALSCH-99999"}, environ_base=INGRESS)
    status = _wait_idle(client)

    assert status["signed_in"] is False
    assert "neu starten" in status["error"]
    # Und danach geht ein neuer Versuch.
    assert (
        client.post("/auth/gemini-agy/start", environ_base=INGRESS).get_json()["state"] == "waiting"
    )


def test_the_open_port_neither_shows_the_address_nor_starts_a_login(client):
    assert client.post("/auth/gemini-agy/start").status_code == 403
    client.post("/auth/gemini-agy/start", environ_base=INGRESS)

    assert client.get("/auth/gemini-agy").get_json()["url"] is None


def _login(client, label=""):
    client.post("/auth/gemini-agy/start", json={"label": label}, environ_base=INGRESS)
    client.post("/auth/gemini-agy/code", json={"code": CODE}, environ_base=INGRESS)
    return _wait_idle(client)


def test_two_accounts_share_the_load_when_the_first_runs_empty(client):
    """Das Ziel von D-024: ist das erste Konto leer, antwortet das nächste — ohne dass
    der Aufrufer etwas merkt."""
    assert [a["label"] for a in _login(client, "Privat")["accounts"]] == ["Privat"]
    status = _login(client, "Arbeit")
    assert [(a["label"], a["state"]) for a in status["accounts"]] == [
        ("Privat", "ok"),
        ("Arbeit", "ok"),
    ]

    # Solange Kontingent da ist, antwortet das erste Konto ...
    erste = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"})
    assert erste.get_json()["konto"] == "gemini-home"
    # ... ist es leer, das zweite.
    (cli.agy_home() / "LEER").write_text("", encoding="utf-8")
    zweite = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"})
    assert zweite.status_code == 200
    assert zweite.get_json()["konto"] == "konto-2"
    status = _status(client)
    assert [(a["label"], a["state"]) for a in status["accounts"]] == [
        ("Privat", "exhausted"),
        ("Arbeit", "ok"),
    ]
    assert status["accounts"][0]["retry_at"].endswith("Z")

    # Nur das zweite Konto zu entfernen lässt das erste wieder an die Reihe kommen
    # — nach seiner Wartezeit; bis dahin sagt die Antwort es.
    (cli.agy_home() / "LEER").unlink()
    entfernt = client.delete("/auth/gemini-agy/konto-2", environ_base=INGRESS).get_json()
    assert [a["label"] for a in entfernt["accounts"]] == ["Privat"]
    gesperrt = client.post("/ask", json={"prompt": "Hallo", "provider": "gemini_agy"})
    assert gesperrt.status_code == 500
    assert "Kontingent" in gesperrt.get_json()["error"]


def test_a_new_account_name_that_is_not_a_name_is_marked_at_its_field(client):
    antwort = client.post("/auth/gemini-agy/start", json={"label": "a;b"}, environ_base=INGRESS)

    assert antwort.status_code == 422
    assert "label" in antwort.get_json()["field_errors"]
    assert _status(client)["state"] == "idle"


def test_removing_an_unknown_account_answers_not_found(client):
    antwort = client.delete("/auth/gemini-agy/konto-9", environ_base=INGRESS)

    assert antwort.status_code == 404
    assert "gibt es nicht" in antwort.get_json()["error"]
