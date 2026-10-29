"""Ingress-Schutz und Geheimhaltung der Cookie-Anmeldung."""

from types import SimpleNamespace

import pytest

import app
from providers import gemini_web_accounts as accounts
from providers import gemini_web_provider as web
from providers.gemini_web_client import WebClientError

INGRESS = {"REMOTE_ADDR": "172.30.32.2"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        web, "client", SimpleNamespace(call=lambda *a, **kw: {"models": ["gemini-pro"]})
    )
    return app.app.test_client()


@pytest.mark.parametrize(
    "method,path",
    [
        ("post", "/auth/gemini-web"),
        ("delete", "/auth/gemini-web/konto-1"),
        ("post", "/auth/gemini-web/models"),
    ],
)
def test_writing_requires_real_ingress(client, method, path):
    response = getattr(client, method)(path, headers={"X-Ingress-Path": "/fake"})
    assert response.status_code == 403
    assert not accounts.list_accounts()


def test_login_and_models_never_echo_the_credentials(client, caplog, monkeypatch):
    values = {
        "label": "Heizung",
        "psid": "synthetisch-wert-eins",
        "psidts": "synthetisch-wert-zwei",
    }
    response = client.post("/auth/gemini-web", json=values, environ_base=INGRESS)
    assert response.status_code == 200
    assert response.get_json()["accounts"][0]["label"] == "Heizung"
    assert response.headers["Cache-Control"] == "no-store"
    assert "synthetisch" not in response.text + caplog.text
    assert "synthetisch" not in client.get("/auth/gemini-web").text
    monkeypatch.setenv("AI_PROVIDER", "gemini_web")
    monkeypatch.setenv("OMNIAI_GEMINI_WEB_MODEL", "gemini-pro")
    assert client.get("/status").get_json()["credentials"]["gemini_web"] is True
    assert client.get("/status").get_json()["default_model"] == "gemini-pro"
    assert client.post("/auth/gemini-web/models", environ_base=INGRESS).get_json() == {
        "models": ["gemini-pro"]
    }
    assert (
        client.delete("/auth/gemini-web/konto-1", environ_base=INGRESS).get_json()["accounts"] == []
    )


def test_rejected_login_has_no_side_effects(client, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise WebClientError("auth")

    monkeypatch.setattr(web, "client", SimpleNamespace(call=fail))
    response = client.post(
        "/auth/gemini-web",
        json={"psid": "synthetisch-a", "psidts": "synthetisch-b"},
        environ_base=INGRESS,
    )
    assert response.status_code == 503
    assert client.get("/auth/gemini-web").get_json()["accounts"] == []
    assert "synthetisch" not in caplog.text + response.text


@pytest.mark.parametrize(
    "payload", [[], "text", None, {"psid": {}}, {"label": 5, "psid": "a", "psidts": "b"}]
)
def test_invalid_login_payload(client, payload):
    assert client.post("/auth/gemini-web", json=payload, environ_base=INGRESS).status_code == 400


def test_empty_models_and_capabilities_are_available_without_a_library(client, monkeypatch):
    assert client.get("/models").get_json()["providers"]["gemini_web"]["models"] == []
    monkeypatch.setenv("OMNIAI_API_TOKEN", "test-api-token")
    response = client.get("/v1/capabilities", headers={"Authorization": "Bearer test-api-token"})
    item = next(p for p in response.get_json()["providers"] if p["id"] == "gemini_web")
    assert item["models"] == [] and item["available"] is False
    assert "attachments" not in item["features"]


def test_attachments_are_explicitly_rejected_until_http_support_is_ready(client, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Keine Anfrage darf mit stillschweigend weggelassenem Anhang laufen")

    monkeypatch.setattr(app.ProviderFactory, "create", forbidden)
    response = client.post(
        "/ask",
        json={
            "prompt": "Bild prüfen",
            "provider": "gemini_web",
            "attachments": [{"name": "bild.png"}],
        },
    )
    assert response.status_code == 400
    assert "Anhänge" in response.get_json()["error"]


def test_too_large_login_body_has_a_german_error(client):
    response = client.post(
        "/auth/gemini-web", json={"psid": "a" * 25000, "psidts": "b"}, environ_base=INGRESS
    )
    assert response.status_code == 413
    assert response.is_json
    assert "zu lang" in response.get_json()["error"]
