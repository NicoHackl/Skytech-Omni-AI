"""Diagnosejournal des Add-ons (D-039): Format, Korrelation, Abruf, keine Fremdtexte."""

import json

import pytest

import diagnostics
from app import app as flask_app

TOKEN = "t" * 40
AUTH = {"Authorization": f"Bearer {TOKEN}"}

TRACE = "5d3c2b1a-0f9e-4d8c-b7a6-123456789abc"


def test_events_have_increasing_seq_and_no_free_text(tmp_path):
    journal = diagnostics.Journal(str(tmp_path / "d"))
    journal.record(
        "OPERATION_END",
        "provider.codex_sub.execute",
        "ERROR",
        1500,
        error_code="TOOLS_NOT_SUPPORTED",
        error=RuntimeError("geheimer Text mit Token xyz"),
    )
    journal.record("OPERATION_END", "x y z; rm -rf", "SUCCESS", error_code="kein code")
    page = journal.read(0, 10)
    first, second = page["events"]
    assert (first["seq"], second["seq"], page["head"], page["next"]) == (1, 2, 2, 2)
    assert first["errorCode"] == "TOOLS_NOT_SUPPORTED"
    assert first["failures"][0]["type"] == "RuntimeError"
    assert "geheimer" not in json.dumps(page) and "xyz" not in json.dumps(page)
    assert second["errorCode"] is None and ";" not in second["operation"]
    assert journal.read(1, 10)["events"][0]["seq"] == 2


def test_seq_survives_a_restart(tmp_path):
    first = diagnostics.Journal(str(tmp_path / "d"))
    first.record("OPERATION_START", "run.claude_sub", "STARTED")
    again = diagnostics.Journal(str(tmp_path / "d"))
    again.record("OPERATION_START", "run.claude_sub", "STARTED")
    assert [e["seq"] for e in again.read(0, 10)["events"]] == [1, 2]
    assert again.read(0, 10)["instanceId"] != first.instance_id


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OMNIAI_API_TOKEN", TOKEN)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_requests_are_correlated_and_codes_journaled(client):
    auth = AUTH

    antwort = client.post(
        "/v1/runs",
        headers={**auth, "X-Correlation-Id": TRACE},
        json={"runId": "r", "provider": "mistral", "prompt": "x"},
    )
    assert antwort.headers["X-Correlation-Id"] == TRACE
    page = client.get("/v1/diagnostics/events?after=0&limit=50", headers=auth).get_json()
    ende = [e for e in page["events"] if e["kind"] == "HTTP_END"]
    assert ende[-1]["traceId"] == TRACE
    assert ende[-1]["operation"] == "POST /v1/runs"
    assert ende[-1]["outcome"] == "REJECTED"
    assert ende[-1]["errorCode"] in ("UNKNOWN_PROVIDER", "VALIDATION_ERROR")
    # Der Abruf selbst erzeugt keine Ereignisse.
    again = client.get(f"/v1/diagnostics/events?after={page['next']}", headers=auth).get_json()
    assert again["events"] == []
    assert client.get("/v1/diagnostics/events?limit=0", headers=auth).status_code == 400
    capabilities = client.get("/v1/capabilities", headers=auth).get_json()
    assert capabilities["diagnostics"] == {"available": True, "schemaVersion": 1}
