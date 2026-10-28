"""Tests der HTTP-Schnittstelle über den Testclient von Flask."""

import json
from typing import ClassVar

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

    assert set(daten["providers"]) == {"claude_sub", "codex_sub", "gemini", "gemini_sub"}
    # Die Modelle kennt die Google-Befehlszeile erst nach der Anmeldung.
    assert daten["providers"]["gemini_sub"] == {"models": [], "default": None}
    assert daten["providers"]["gemini"]["default"] == "gemini-flash-latest"
    assert daten["providers"]["claude_sub"]["default"] is None
    # Ohne Angabe entscheidet die Codex-CLI selbst.
    assert daten["providers"]["codex_sub"]["default"] is None
    assert "gpt-5.6-sol" in daten["providers"]["codex_sub"]["models"]


def test_status_reports_credentials_as_yes_or_no(client, monkeypatch):
    """Zum Zugang kommt nur ja/nein zurück — nie der Wert selbst."""
    monkeypatch.setenv("GEMINI_API_KEY", "geheim")

    daten = client.get("/status").get_json()

    assert daten["credentials"] == {
        "claude_sub": False,
        "codex_sub": False,
        "gemini": True,
        "gemini_sub": False,
    }
    # Der Wert selbst taucht nirgends in der Antwort auf.
    assert "geheim" not in json.dumps(daten, ensure_ascii=False)


def test_status_without_credentials(client):
    """Leerzustand: frisch installiert ist noch nichts hinterlegt."""
    daten = client.get("/status").get_json()

    assert daten["credentials"] == {
        "claude_sub": False,
        "codex_sub": False,
        "gemini": False,
        "gemini_sub": False,
    }
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


# --- Einstellungen ---------------------------------------------------------

INGRESS = {"REMOTE_ADDR": app_module.INGRESS_PROXY_ADDR}


class FakeSupervisor:
    """Steht für den Supervisor: hält Optionen und merkt sich, was gespeichert wurde."""

    stored: ClassVar[dict] = {}
    saved: ClassVar[list] = []
    valid = True

    def __init__(self):
        self.available = True

    def get_self_options(self):
        return dict(FakeSupervisor.stored)

    def validate_options(self, options):
        return FakeSupervisor.valid, "" if FakeSupervisor.valid else "unknown key"

    def save_options(self, options):
        FakeSupervisor.saved.append(options)
        FakeSupervisor.stored = dict(options)


@pytest.fixture
def supervisor(monkeypatch):
    FakeSupervisor.stored = {
        "provider": "claude_sub",
        "model": "auto",
        "tool_access": "web",
        "claude_oauth_token": "geheim-claude",
        "gemini_api_key": "",
    }
    FakeSupervisor.saved = []
    FakeSupervisor.valid = True
    monkeypatch.setattr(app_module, "SupervisorClient", FakeSupervisor)
    return FakeSupervisor


def _revision(client):
    return client.get("/settings", environ_base=INGRESS).get_json()["stored_revision"]


def test_settings_show_no_credential_value(client, supervisor):
    """Die Seite bekommt nur ja/nein zu den Zugängen und darf über den Ingress speichern."""
    daten = client.get("/settings", environ_base=INGRESS).get_json()

    assert daten["can_save"] is True
    assert daten["read_only_reason"] is None
    assert daten["secrets_set"]["claude_oauth_token"] is True
    assert "geheim" not in json.dumps(daten)


def test_settings_from_the_open_port_are_read_only(client, supervisor):
    """Über Port 8000 lässt sich nichts ändern — auch nicht mit gefälschtem Ingress-Kopf."""
    daten = client.get("/settings").get_json()
    assert daten["can_save"] is False
    assert daten["read_only_reason"] == "ingress"

    antwort = client.put(
        "/settings",
        json={"options": {"tool_access": "full"}, "stored_revision": "x"},
        headers={"X-Ingress-Path": "/api/hassio_ingress/abc"},
    )

    assert antwort.status_code == 403
    assert supervisor.saved == []


def test_settings_outside_home_assistant_cannot_be_saved(client):
    """Ohne Supervisor zeigt die Seite den Stand nur an."""
    daten = client.get("/settings", environ_base=INGRESS).get_json()
    assert daten["can_save"] is False
    # Ohne Supervisor-Zugang ist der Ingress nicht schuld — die Seite muss den
    # richtigen Grund nennen.
    assert daten["read_only_reason"] == "supervisor"

    antwort = client.put(
        "/settings", json={"options": {}, "stored_revision": "x"}, environ_base=INGRESS
    )

    assert antwort.status_code == 503


def test_saving_takes_effect_without_restart(client, supervisor):
    """Normalfall: gespeichert, und die nächste Anfrage sieht den neuen Anbieter."""
    antwort = client.put(
        "/settings",
        json={
            "options": {"provider": "gemini", "model": "auto", "gemini_api_key": "neu"},
            "stored_revision": _revision(client),
        },
        environ_base=INGRESS,
    )

    assert antwort.status_code == 200
    assert supervisor.saved[0]["claude_oauth_token"] == "geheim-claude"
    status = client.get("/status").get_json()
    assert status["provider"] == "gemini"
    assert status["credentials"]["gemini"] is True
    assert "neu" not in json.dumps(antwort.get_json())


def test_saving_an_outdated_state_is_refused(client, supervisor):
    """Wurde inzwischen anderswo gespeichert, überschreibt ein alter Tab nichts."""
    antwort = client.put(
        "/settings",
        json={"options": {"provider": "gemini"}, "stored_revision": "veraltet"},
        environ_base=INGRESS,
    )

    assert antwort.status_code == 409
    assert supervisor.saved == []


def test_invalid_fields_are_marked(client, supervisor):
    """Fehlerfall: das betroffene Feld bekommt einen eigenen Satz."""
    antwort = client.put(
        "/settings",
        json={"options": {"tool_access": "alles"}, "stored_revision": _revision(client)},
        environ_base=INGRESS,
    )

    assert antwort.status_code == 422
    assert set(antwort.get_json()["field_errors"]) == {"tool_access"}
    assert supervisor.saved == []


def test_a_refusal_of_the_supervisor_stays_readable(client, supervisor):
    """Fehlerfall: die englische Meldung des Supervisors landet nicht auf dem Bildschirm."""
    supervisor.valid = False

    antwort = client.put(
        "/settings",
        json={"options": {"provider": "gemini"}, "stored_revision": _revision(client)},
        environ_base=INGRESS,
    )

    assert antwort.status_code == 422
    assert "unknown" not in antwort.get_json()["error"]
    assert supervisor.saved == []


# --- Sidebar-Fuß (D-018) ---------------------------------------------------


class InfoSupervisor:
    """Liefert ``/addons/self/info``; zählt die Aufrufe über alle Instanzen."""

    info: ClassVar[dict] = {}
    fehler: ClassVar[Exception | None] = None
    calls: ClassVar[int] = 0

    def __init__(self, available: bool = True):
        self.available = available

    def get_self_info(self):
        InfoSupervisor.calls += 1
        if InfoSupervisor.fehler:
            raise InfoSupervisor.fehler
        return dict(InfoSupervisor.info)


@pytest.fixture
def info_supervisor(monkeypatch):
    InfoSupervisor.info = {"slug": "b80e8355_skytech_omniai", "name": "Skytech OmniAI"}
    InfoSupervisor.fehler = None
    InfoSupervisor.calls = 0
    monkeypatch.setattr(app_module, "SupervisorClient", InfoSupervisor)
    monkeypatch.setattr(app_module, "_addon_link", {})
    return InfoSupervisor


def test_addon_links_to_the_config_page_with_repository_prefix(client, info_supervisor):
    """Der Slug kommt vom Supervisor, samt Präfix des Add-on-Repositorys."""
    assert client.get("/addon").get_json() == {
        "name": "Skytech OmniAI",
        "config_path": "/config/app/b80e8355_skytech_omniai/config",
    }


def test_addon_remembers_only_success(client, info_supervisor):
    """Ein Ausfall wird erneut versucht, ein Erfolg nicht mehr."""
    info_supervisor.fehler = app_module.SupervisorUnavailable("weg")
    assert client.get("/addon").get_json() == {"name": "Skytech OmniAI", "config_path": None}

    info_supervisor.fehler = None
    assert client.get("/addon").get_json()["config_path"] is not None
    client.get("/addon")
    assert info_supervisor.calls == 2


def test_addon_without_supervisor_has_no_link(client, monkeypatch):
    """Außerhalb von Home Assistant bleibt der Fuß ein Namensschild."""
    monkeypatch.setattr(app_module, "_addon_link", {})
    assert client.get("/addon").get_json() == {"name": "Skytech OmniAI", "config_path": None}


def test_addon_rejects_an_invalid_slug(client, info_supervisor):
    """Ein unerwarteter Slug wird nicht zu einem Pfad zusammengesetzt."""
    info_supervisor.info = {"slug": "../../evil", "name": "Skytech OmniAI"}
    assert client.get("/addon").get_json()["config_path"] is None


# --- Anmeldung bei Google (gemini_sub) ---------------------------------------


class FakeLogin:
    """Steht für die Anmeldung: merkt sich Aufrufe, wirft auf Wunsch einen Fehler."""

    def __init__(self):
        self.calls = []
        self.error = None

    def _answer(self, name, *args):
        self.calls.append((name, *args))
        if self.error:
            raise self.error
        return {"state": "waiting", "url": "https://accounts.google.com/x", "signed_in": False}

    def status(self, include_url=False):
        self.calls.append(("status", include_url))
        return {"state": "idle", "url": "https://accounts.google.com/x" if include_url else None}

    def start(self):
        return self._answer("start")

    def submit(self, code):
        return self._answer("submit", code)

    def cancel(self):
        return self._answer("cancel")

    def logout(self):
        return self._answer("logout")


@pytest.fixture
def login(monkeypatch):
    fake = FakeLogin()
    monkeypatch.setattr(app_module, "gemini_login", fake)
    return fake


def test_the_login_status_hides_the_address_from_the_open_port(client, login):
    assert client.get("/auth/gemini").get_json()["url"] is None
    assert client.get("/auth/gemini", environ_base=INGRESS).get_json()["url"].startswith("https://")


@pytest.mark.parametrize(
    ("methode", "pfad"),
    [
        ("post", "/auth/gemini/start"),
        ("post", "/auth/gemini/code"),
        ("post", "/auth/gemini/cancel"),
        ("delete", "/auth/gemini"),
    ],
)
def test_the_login_cannot_be_changed_from_the_open_port(client, login, methode, pfad):
    """Wer Port 8000 erreicht, soll weder anmelden noch abmelden können."""
    antwort = getattr(client, methode)(pfad, json={"code": "4/0Acode-12345"})

    assert antwort.status_code == 403
    assert "Seitenleiste" in antwort.get_json()["error"]
    assert login.calls == []


def test_the_login_can_be_started_and_ended_through_the_ingress(client, login):
    assert client.post("/auth/gemini/start", environ_base=INGRESS).get_json()["state"] == "waiting"
    assert client.post("/auth/gemini/cancel", environ_base=INGRESS).status_code == 200
    assert client.delete("/auth/gemini", environ_base=INGRESS).status_code == 200
    assert [aufruf[0] for aufruf in login.calls] == ["start", "cancel", "logout"]


def test_the_code_is_handed_over(client, login):
    antwort = client.post(
        "/auth/gemini/code", json={"code": "4/0Acode-12345"}, environ_base=INGRESS
    )

    assert antwort.status_code == 200
    assert ("submit", "4/0Acode-12345") in login.calls


@pytest.mark.parametrize("rumpf", [{}, {"code": ""}, {"code": "   "}, {"code": 5}, None])
def test_a_missing_code_is_marked_at_the_field(client, login, rumpf):
    antwort = client.post("/auth/gemini/code", json=rumpf, environ_base=INGRESS)

    assert antwort.status_code == 422
    assert "code" in antwort.get_json()["field_errors"]
    assert login.calls == []


def test_an_unusable_code_is_marked_at_the_field(client, login):
    from providers.gemini_sub_login import LoginError

    login.error = LoginError("Das sieht nicht nach dem Code aus.", invalid=True)

    antwort = client.post("/auth/gemini/code", json={"code": "kurz"}, environ_base=INGRESS)

    assert antwort.status_code == 422
    assert antwort.get_json()["field_errors"]["code"] == "Das sieht nicht nach dem Code aus."


def test_a_busy_cli_answers_with_a_conflict(client, login):
    from providers.gemini_sub_login import LoginError

    login.error = LoginError("Gerade läuft eine Anfrage.", busy=True)

    antwort = client.post("/auth/gemini/start", environ_base=INGRESS)

    assert antwort.status_code == 409
    assert antwort.get_json() == {"error": "Gerade läuft eine Anfrage."}


def test_an_unexpected_failure_of_the_login_gets_a_generic_sentence(client, login):
    login.error = RuntimeError("/data/.gemini/x kaputt, Traceback")

    antwort = client.post("/auth/gemini/start", environ_base=INGRESS)

    assert antwort.status_code == 500
    text = antwort.get_json()["error"]
    assert "/data" not in text
    assert "Traceback" not in text


# --- Modelle von Google Gemini (Abo) -------------------------------------------


def _sign_in_and_store_models(*labels):
    from providers import gemini_sub_provider as cli

    cli.token_path().parent.mkdir(parents=True, exist_ok=True)
    cli.token_path().write_text('{"token": {"refresh_token": "x"}}')
    cli.store_models([cli.ModelInfo(label) for label in labels])


def test_models_lists_the_models_of_the_google_cli_after_the_login(client, monkeypatch):
    _sign_in_and_store_models("Gemini 4 Argon (High)", "Gemini 3.8 Flash (Medium)")
    monkeypatch.setenv("GEMINI_SUB_MODEL", "Gemini 4 Argon (High)")

    eintrag = client.get("/models").get_json()["providers"]["gemini_sub"]

    assert eintrag["models"] == ["Gemini 4 Argon (High)", "Gemini 3.8 Flash (Medium)"]
    assert eintrag["default"] == "Gemini 4 Argon (High)"


def test_models_of_the_google_cli_are_empty_before_the_login(client):
    eintrag = client.get("/models").get_json()["providers"]["gemini_sub"]

    assert eintrag == {"models": [], "default": None}


def test_the_model_refresh_needs_the_ingress(client, login):
    antwort = client.post("/auth/gemini/models")

    assert antwort.status_code == 403


def test_the_model_refresh_returns_the_new_list(client, monkeypatch):
    from providers import gemini_sub_provider as cli

    _sign_in_and_store_models("Alt (High)")
    monkeypatch.setattr(
        cli, "run_agy", lambda *a, **k: cli.AgyResult(0, "Gemini 4 Argon (High)\n", "")
    )

    antwort = client.post("/auth/gemini/models", environ_base=INGRESS)

    assert antwort.status_code == 200
    assert antwort.get_json() == {"models": ["Gemini 4 Argon (High)"]}


def test_status_shows_the_default_model_of_the_active_provider(client, monkeypatch):
    """Google Gemini (Abo) hat eine eigene Option; das gemeinsame Feld gehört den anderen."""
    monkeypatch.setenv("OMNIAI_MODEL", "sonnet")
    monkeypatch.setenv("GEMINI_SUB_MODEL", "Gemini 4 Argon (High)")

    assert client.get("/status").get_json()["default_model"] == "sonnet"

    monkeypatch.setenv("AI_PROVIDER", "gemini_sub")
    assert client.get("/status").get_json()["default_model"] == "Gemini 4 Argon (High)"

    monkeypatch.delenv("GEMINI_SUB_MODEL")
    assert client.get("/status").get_json()["default_model"] is None
