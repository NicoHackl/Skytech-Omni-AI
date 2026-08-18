"""Tests der HTTP-Schnittstelle über den Testclient von Flask."""

import json

import pytest

import app as app_module
from app import app as flask_app


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_health_answers(client):
    """Der Endpunkt, an dem der Watchdog hängt."""
    antwort = client.get("/health")

    assert antwort.status_code == 200
    assert antwort.get_json() == {"status": "ok"}


def test_models_lists_every_provider(client):
    """Normalfall: Automatisierungen können die gültigen Werte abfragen."""
    daten = client.get("/models").get_json()

    assert set(daten["providers"]) == {"claude_sub", "codex_sub", "gemini"}
    assert daten["providers"]["gemini"]["default"] == "gemini-flash-latest"
    assert daten["providers"]["claude_sub"]["default"] is None
    # Ohne Angabe entscheidet die Codex-CLI selbst.
    assert daten["providers"]["codex_sub"]["default"] is None
    assert "gpt-5.6-sol" in daten["providers"]["codex_sub"]["models"]


def test_status_reports_credentials_as_yes_or_no(client, monkeypatch):
    """Zum Zugang kommt nur ja/nein zurück — nie der Wert selbst."""
    monkeypatch.setenv("GEMINI_API_KEY", "geheim")

    daten = client.get("/status").get_json()

    assert daten["credentials"] == {"claude_sub": False, "codex_sub": False, "gemini": True}
    # Der Wert selbst taucht nirgends in der Antwort auf.
    assert "geheim" not in json.dumps(daten, ensure_ascii=False)


def test_status_without_credentials(client):
    """Leerzustand: frisch installiert ist noch nichts hinterlegt."""
    daten = client.get("/status").get_json()

    assert daten["credentials"] == {"claude_sub": False, "codex_sub": False, "gemini": False}
    assert daten["default_model"] is None


def test_status_reports_the_chatgpt_access(client, monkeypatch):
    """Auch zum ChatGPT-Zugang kommt nur ja/nein — der eingefügte Inhalt nie."""
    monkeypatch.setenv("CODEX_AUTH_JSON", '{"tokens": {"access_token": "geheim"}}')

    daten = client.get("/status").get_json()

    assert daten["credentials"]["codex_sub"] is True
    assert "geheim" not in json.dumps(daten, ensure_ascii=False)


def test_status_reports_the_tool_level(client):
    """Ohne Angabe gilt die Vorgabe — die Oberfläche zeigt sie an."""
    assert client.get("/status").get_json()["tool_access"] == "web"


def test_status_reports_the_effective_tool_level(client, monkeypatch):
    """Ein vertippter Wert erscheint nicht in der Oberfläche, sondern die Vorgabe."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "vollzugriff")

    assert client.get("/status").get_json()["tool_access"] == "web"


def test_ask_without_prompt_is_rejected(client):
    """Fehlerfall: eine unvollständige Anfrage ist ein Eingabefehler, kein Serverfehler."""
    antwort = client.post("/ask", json={})

    assert antwort.status_code == 400
    assert antwort.get_json()["error"] == "Es wurde kein Prompt übergeben."


def test_ask_with_an_unknown_provider_is_rejected(client):
    """Fehlerfall: ein falscher Anbietername ist ebenfalls ein Eingabefehler."""
    antwort = client.post("/ask", json={"prompt": "Test", "provider": "openai"})

    assert antwort.status_code == 400
    assert "openai" in antwort.get_json()["error"]


def test_a_provider_failure_stays_free_of_technical_detail(client, monkeypatch):
    """Eiserne Regel 12: kein Antwortcode, kein Klassenname, kein Pfad im Rumpf."""

    class KaputterProvider:
        def execute(self, prompt, model=None):
            raise RuntimeError("Claude hat die Anfrage nicht beantwortet.")

    monkeypatch.setattr(
        app_module.ProviderFactory, "create", staticmethod(lambda name=None: KaputterProvider())
    )

    antwort = client.post("/ask", json={"prompt": "Test"})

    assert antwort.status_code == 500
    text = antwort.get_json()["error"]
    assert "500" not in text
    assert "RuntimeError" not in text
    assert "Traceback" not in text


def test_an_unexpected_failure_gets_a_generic_sentence(client, monkeypatch):
    """Was nicht vorhergesehen war, wird geloggt und allgemein gemeldet."""

    class KaputterProvider:
        def execute(self, prompt, model=None):
            raise KeyError("interner_feldname")

    monkeypatch.setattr(
        app_module.ProviderFactory, "create", staticmethod(lambda name=None: KaputterProvider())
    )

    antwort = client.post("/ask", json={"prompt": "Test"})

    assert antwort.status_code == 500
    assert antwort.get_json()["error"] == app_module.FEHLER_UNBEKANNT
    assert "interner_feldname" not in antwort.get_json()["error"]


def test_ask_returns_the_answer_of_the_provider(client, monkeypatch):
    """Normalfall: das JSON des Modells geht unverändert zurück."""

    class GuterProvider:
        def execute(self, prompt, model=None):
            return {"status": "ok", "prompt": prompt, "model": model}

    monkeypatch.setattr(
        app_module.ProviderFactory, "create", staticmethod(lambda name=None: GuterProvider())
    )

    daten = client.post("/ask", json={"prompt": "Hallo", "model": "opus"}).get_json()

    assert daten == {"status": "ok", "prompt": "Hallo", "model": "opus"}


def test_the_ingress_path_ends_up_in_the_base_element(client, tmp_path, monkeypatch):
    """Die Oberfläche muss unter dem wechselnden Pfad von Home Assistant laden."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)

    antwort = client.get("/", headers={"X-Ingress-Path": "/api/hassio_ingress/abc123"})

    assert '<base href="/api/hassio_ingress/abc123/">' in antwort.get_data(as_text=True)
    # Der Pfad gilt nur für diese Sitzung und darf nicht zwischengespeichert werden.
    assert antwort.headers["Cache-Control"] == "no-store"


def test_a_manipulated_ingress_path_is_ignored(client, tmp_path, monkeypatch):
    """Der Wert landet im Markup und wird deshalb nicht ungeprüft übernommen."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head></head><body></body></html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)

    antwort = client.get("/", headers={"X-Ingress-Path": '/x"><script>alert(1)</script>'})

    assert "<script>" not in antwort.get_data(as_text=True)
    assert '<base href="/">' in antwort.get_data(as_text=True)


def test_an_unknown_route_gets_the_interface(client, tmp_path, monkeypatch):
    """Das Routing findet im Browser statt — jede Unterseite liefert die Hülle."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><head></head><body>ok</body></html>", encoding="utf-8")
    monkeypatch.setattr(app_module, "WEB_DIST", dist)

    assert client.get("/anfrage").status_code == 200


def test_without_a_built_interface_the_api_still_works(client, tmp_path, monkeypatch):
    """Leerzustand: fehlt das Bündel, bleibt die Schnittstelle benutzbar."""
    monkeypatch.setattr(app_module, "WEB_DIST", tmp_path / "gibt-es-nicht")

    assert client.get("/").status_code == 503
    assert client.get("/health").status_code == 200
