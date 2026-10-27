"""Tests der Embeddings für Skytech X (``POST /v1/embeddings``, D-023).

Google wird nicht angesprochen: ``urlopen`` liefert eine vorbereitete Antwort und
schreibt die Anfrage mit.
"""

import io
import json
import urllib.error

import pytest

import embeddings
from app import app as flask_app

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def google(monkeypatch):
    calls = []

    def urlopen(request, timeout=None):
        body = json.loads(request.data.decode("utf-8"))
        calls.append(
            {"url": request.full_url, "body": body, "key": request.get_header("X-goog-api-key")}
        )
        if calls[-1]["body"]["requests"][0]["content"]["parts"][0]["text"] == "kaputt":
            raise urllib.error.HTTPError(
                request.full_url, 400, "bad", {}, io.BytesIO(b'{"error":{"message":"x"}}')
            )
        answer = {
            "embeddings": [{"values": [0.1 * (i + 1)] * 3} for i, _ in enumerate(body["requests"])],
            "usageMetadata": {"promptTokenCount": 12},
        }
        return FakeResponse(json.dumps(answer).encode("utf-8"))

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", urlopen)
    return calls


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OMNIAI_API_TOKEN", TOKEN)
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-schluessel")
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_embeddings_use_only_gemini_embedding_001(client, google):
    antwort = client.post(
        "/v1/embeddings",
        headers=AUTH,
        json={"input": ["Grafana", "PV"], "taskType": "RETRIEVAL_QUERY"},
    )

    assert antwort.status_code == 200
    daten = antwort.get_json()
    assert daten["model"] == "gemini-embedding-001"
    assert daten["dimensions"] == 768
    assert len(daten["embeddings"]) == 2
    assert daten["usage"] == {"inputTokens": 12}
    call = google[0]
    assert call["url"].endswith("/models/gemini-embedding-001:batchEmbedContents")
    assert call["key"] == "gemini-schluessel"
    assert call["body"]["requests"][1] == {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": "PV"}]},
        "taskType": "RETRIEVAL_QUERY",
        "outputDimensionality": 768,
    }
    assert "gemini-schluessel" not in json.dumps(daten)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"input": []},
        {"input": [""]},
        {"input": ["x"] * 101},
        {"input": ["x" * 8001]},
        {"input": ["x"], "taskType": "CLUSTERING"},
        {"input": ["x"], "dimensions": 100},
        {"input": ["x"], "dimensions": True},
        {"input": "x"},
    ],
)
def test_malformed_requests(client, google, body):
    antwort = client.post("/v1/embeddings", headers=AUTH, json=body)

    assert antwort.status_code == 400
    assert google == []


def test_without_key_or_with_google_error(client, google, monkeypatch):
    fehler = client.post("/v1/embeddings", headers=AUTH, json={"input": ["kaputt"]})
    monkeypatch.delenv("GEMINI_API_KEY")
    ohne = client.post("/v1/embeddings", headers=AUTH, json={"input": ["x"]})

    assert fehler.status_code == 503
    assert fehler.get_json()["code"] == "PROVIDER_UNAVAILABLE"
    assert ohne.status_code == 503
    assert ohne.get_json()["error"] == embeddings.FEHLER_KEIN_SCHLUESSEL


def test_capabilities_report_embeddings(client):
    daten = client.get("/v1/capabilities", headers=AUTH).get_json()

    assert daten["embeddings"] == {
        "available": True,
        "model": "gemini-embedding-001",
        "dimensions": 768,
    }


def test_embeddings_need_the_token(client):
    assert client.post("/v1/embeddings", json={"input": ["x"]}).status_code == 401
