"""Tests des Zugriffs auf die eigenen Add-on-Optionen über den Supervisor."""

import io
import json
import urllib.error

import pytest

import supervisor_client
from supervisor_client import SupervisorClient, SupervisorRejected, SupervisorUnavailable


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _answer(monkeypatch, body: dict, calls: list):
    def fake_urlopen(request, timeout):
        calls.append(request)
        return FakeResponse(json.dumps(body).encode("utf-8"))

    monkeypatch.setattr(supervisor_client, "_open", fake_urlopen)


def test_without_token_there_is_no_supervisor():
    """Leerzustand: außerhalb von Home Assistant gibt es nichts zu schreiben."""
    client = SupervisorClient()

    assert client.available is False
    with pytest.raises(SupervisorUnavailable):
        client.get_self_options()


def test_reads_the_stored_options(monkeypatch):
    """Normalfall: die Optionen kommen aus dem Info-Endpunkt des Add-ons."""
    calls = []
    _answer(monkeypatch, {"result": "ok", "data": {"options": {"provider": "gemini"}}}, calls)

    options = SupervisorClient(token="tok").get_self_options()

    assert options == {"provider": "gemini"}
    assert calls[0].full_url == "http://supervisor/addons/self/info"
    assert calls[0].get_header("Authorization") == "Bearer tok"


def test_save_wraps_the_options(monkeypatch):
    """Der Speicher-Endpunkt erwartet die Optionen unter „options“."""
    calls = []
    _answer(monkeypatch, {"result": "ok", "data": {}}, calls)

    SupervisorClient(token="tok").save_options({"provider": "gemini"})

    assert calls[0].get_method() == "POST"
    assert json.loads(calls[0].data) == {"options": {"provider": "gemini"}}


def test_a_refusal_stays_free_of_token_and_values(monkeypatch):
    """Fehlerfall: weder Token noch Optionswert landen in der Meldung."""

    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b'{"message": "denied"}')
        )

    monkeypatch.setattr(supervisor_client, "_open", fake_urlopen)

    with pytest.raises(SupervisorRejected) as fehler:
        SupervisorClient(token="geheim-token").save_options({"gemini_api_key": "geheim-wert"})

    assert "geheim" not in str(fehler.value)
    assert "403" not in str(fehler.value)


def test_an_unreachable_supervisor(monkeypatch):
    """Fehlerfall: keine Verbindung wird als „nicht erreichbar“ gemeldet."""

    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("Verbindung abgelehnt")

    monkeypatch.setattr(supervisor_client, "_open", fake_urlopen)

    with pytest.raises(SupervisorUnavailable):
        SupervisorClient(token="tok").validate_options({})
