"""Tests der Schnittstelle v1 für Skytech X (D-019).

Die Anbieter werden durch einen Platzhalter ersetzt, der vorgegebene Antworten
oder Fehler liefert — geprüft wird das Verhalten der Schnittstelle, nicht das
der Befehlszeilen.
"""

import json
from typing import ClassVar

import pytest

import api_v1 as api_module
from app import app as flask_app
from providers.base_provider import NotJson, ProviderTimeout, UnknownModel

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeProvider:
    """Liefert der Reihe nach die vorgegebenen Antworten bzw. wirft Fehler."""

    answers: ClassVar[list] = []
    prompts: ClassVar[list] = []
    timeouts: ClassVar[list] = []

    def execute(self, prompt, model=None, timeout=None):
        FakeProvider.prompts.append(prompt)
        FakeProvider.timeouts.append(timeout)
        answer = FakeProvider.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def effective_model(self, model=None):
        if model == "falsch":
            raise UnknownModel("„falsch“ gehört nicht zu diesem Anbieter.")
        return model or "auto"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OMNIAI_API_TOKEN", TOKEN)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture
def fake(monkeypatch):
    FakeProvider.answers = []
    FakeProvider.prompts = []
    FakeProvider.timeouts = []

    def create(name=None):
        if name == "unbekannt":
            raise ValueError("Der Anbieter „unbekannt“ ist nicht verfügbar.")
        return FakeProvider()

    monkeypatch.setattr(api_module.ProviderFactory, "create", staticmethod(create))
    return FakeProvider


# --- Token -----------------------------------------------------------------


def test_without_configured_token_everything_is_closed(client, monkeypatch):
    monkeypatch.delenv("OMNIAI_API_TOKEN")

    antwort = client.get("/v1/health", headers=AUTH)

    assert antwort.status_code == 401
    assert antwort.get_json()["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    "headers", [{}, {"Authorization": "Bearer falsch"}, {"Authorization": TOKEN}]
)
def test_wrong_or_missing_token_is_rejected(client, headers):
    antwort = client.get("/v1/capabilities", headers=headers)

    assert antwort.status_code == 401
    assert antwort.get_json() == {
        "error": "Das Token fehlt oder ist falsch.",
        "code": "UNAUTHORIZED",
    }


def test_old_endpoints_stay_open(client):
    """Die bisherigen Endpunkte bleiben ohne Token erreichbar (D-010 unverändert)."""
    assert client.get("/health").status_code == 200


# --- Gesundheit und Fähigkeiten ---------------------------------------------


def test_health(client):
    antwort = client.get("/v1/health", headers=AUTH)

    assert antwort.status_code == 200
    assert antwort.get_json()["status"] == "UP"


def test_capabilities_report_availability_without_secrets(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "geheimer-schluessel")

    daten = client.get("/v1/capabilities", headers=AUTH).get_json()

    by_id = {p["id"]: p for p in daten["providers"]}
    assert set(by_id) == {"claude_sub", "codex_sub", "gemini", "gemini_agy", "gemini_web"}
    assert by_id["gemini"]["available"] is True
    assert by_id["claude_sub"]["available"] is False
    assert by_id["gemini"]["defaultModel"] == "gemini-flash-latest"
    assert by_id["gemini"]["features"] == {"tools": False, "structuredOutput": True, "usage": False}
    assert by_id["claude_sub"]["features"]["tools"] is True
    assert daten["mcp"]["protocolVersions"] == ["2025-11-25"]
    assert daten["limits"]["maxPromptLength"] == 100_000
    assert "geheimer-schluessel" not in json.dumps(daten)
    assert TOKEN not in json.dumps(daten)


def test_the_google_subscription_is_available_only_with_a_login(client):
    """Zugang ist hier keine Umgebungsvariable, sondern die Anmeldung im Add-on."""
    from providers import gemini_agy_provider

    def available():
        daten = client.get("/v1/capabilities", headers=AUTH).get_json()
        return {p["id"]: p for p in daten["providers"]}["gemini_agy"]

    assert available()["available"] is False

    gemini_agy_provider.token_path().parent.mkdir(parents=True, exist_ok=True)
    gemini_agy_provider.token_path().write_text('{"token": {"refresh_token": "x"}}')

    eintrag = available()
    assert eintrag["available"] is True
    assert eintrag["features"] == {"tools": False, "structuredOutput": True, "usage": False}
    assert eintrag["models"] == []

    gemini_agy_provider.store_models([gemini_agy_provider.ModelInfo("Gemini 4 Argon (High)")])
    assert available()["models"] == ["Gemini 4 Argon (High)"]


def test_unknown_v1_path_answers_in_contract_format(client):
    antwort = client.post("/v1/gibt-es-nicht", headers=AUTH, json={})

    assert antwort.status_code == 404
    assert antwort.get_json()["code"] == "NOT_FOUND"


# --- Einmal-Antworten -------------------------------------------------------


def test_completion_without_schema(client, fake):
    fake.answers = [{"kategorie": "rechnung"}]

    antwort = client.post(
        "/v1/completions",
        headers=AUTH,
        json={"provider": "gemini", "instructions": "Ordne zu.", "input": "Eine Rechnung"},
    )

    assert antwort.status_code == 200
    assert antwort.get_json() == {
        "output": {"kategorie": "rechnung"},
        "provider": "gemini",
        "model": "auto",
    }
    assert fake.prompts[0].startswith("Ordne zu.\n\nEine Rechnung")
    assert fake.timeouts == [120]


SCHEMA = {
    "type": "object",
    "required": ["prio"],
    "properties": {"prio": {"type": "integer", "minimum": 1, "maximum": 3}},
}


def test_schema_is_given_to_the_model_and_checked(client, fake):
    fake.answers = [{"prio": 2}]

    antwort = client.post(
        "/v1/completions", headers=AUTH, json={"input": "Wie dringend?", "outputSchema": SCHEMA}
    )

    assert antwort.status_code == 200
    assert antwort.get_json()["output"] == {"prio": 2}
    assert '"maximum": 3' in fake.prompts[0]


def test_schema_mismatch_gets_one_retry(client, fake):
    fake.answers = [{"prio": 7}, {"prio": 3}]

    antwort = client.post(
        "/v1/completions", headers=AUTH, json={"input": "Wie dringend?", "outputSchema": SCHEMA}
    )

    assert antwort.status_code == 200
    assert antwort.get_json()["output"] == {"prio": 3}
    assert "did not match" in fake.prompts[1]


def test_schema_mismatch_twice_is_422(client, fake):
    fake.answers = [{"prio": 7}, NotJson("kein JSON")]

    antwort = client.post(
        "/v1/completions", headers=AUTH, json={"input": "Wie dringend?", "outputSchema": SCHEMA}
    )

    assert antwort.status_code == 422
    assert antwort.get_json()["code"] == "SCHEMA_MISMATCH"


def test_invalid_schema_is_rejected_before_asking(client, fake):
    antwort = client.post(
        "/v1/completions",
        headers=AUTH,
        json={"input": "x", "outputSchema": {"type": "kein-typ"}},
    )

    assert antwort.status_code == 400
    assert antwort.get_json()["code"] == "VALIDATION_ERROR"
    assert fake.prompts == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"input": ""},
        {"input": "x" * 100_001},
        {"input": "x", "timeoutSeconds": 1},
        {"input": "x", "timeoutSeconds": "60"},
        {"input": "x", "outputSchema": [1]},
        {"input": "x", "provider": 5},
    ],
)
def test_malformed_requests(client, fake, body):
    antwort = client.post("/v1/completions", headers=AUTH, json=body)

    assert antwort.status_code == 400
    assert antwort.get_json()["code"] == "VALIDATION_ERROR"


def test_unknown_provider_and_model(client, fake):
    unknown_provider = client.post(
        "/v1/completions", headers=AUTH, json={"input": "x", "provider": "unbekannt"}
    )
    unknown_model = client.post(
        "/v1/completions", headers=AUTH, json={"input": "x", "model": "falsch"}
    )

    assert unknown_provider.status_code == 422
    assert unknown_provider.get_json()["code"] == "UNKNOWN_PROVIDER"
    assert unknown_model.status_code == 422
    assert unknown_model.get_json()["code"] == "UNKNOWN_MODEL"


def test_timeout_and_unavailable_provider(client, fake):
    fake.answers = [ProviderTimeout("Keine Antwort in der vorgegebenen Zeit.")]
    timeout = client.post("/v1/completions", headers=AUTH, json={"input": "x"})
    fake.answers = [RuntimeError("Für Claude ist kein Zugang hinterlegt.")]
    unavailable = client.post("/v1/completions", headers=AUTH, json={"input": "x"})

    assert timeout.status_code == 504
    assert timeout.get_json()["code"] == "TIMEOUT"
    assert unavailable.status_code == 503
    assert unavailable.get_json() == {
        "error": "Für Claude ist kein Zugang hinterlegt.",
        "code": "PROVIDER_UNAVAILABLE",
    }


def test_timeout_seconds_reach_the_provider(client, fake):
    fake.answers = [{"ok": True}]

    client.post("/v1/completions", headers=AUTH, json={"input": "x", "timeoutSeconds": 30})

    assert fake.timeouts == [30]
