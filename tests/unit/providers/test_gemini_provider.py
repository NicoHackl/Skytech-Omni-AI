"""Tests für den Gemini-Provider. Es geht dabei nie eine echte Anfrage raus."""

import urllib.error

import pytest

from providers.gemini_provider import DEFAULT_MODEL, GeminiProvider


@pytest.fixture
def provider():
    return GeminiProvider()


def test_without_a_key_it_refuses(provider):
    """Fehlerfall: ohne Schlüssel gibt es einen Satz mit Handlungsanweisung."""
    with pytest.raises(RuntimeError) as fehler:
        provider._build_api_key()

    assert "gemini_api_key" in str(fehler.value)


def test_google_api_key_is_accepted_too(provider, monkeypatch):
    """Der zweite gängige Name funktioniert ebenfalls."""
    monkeypatch.setenv("GOOGLE_API_KEY", "schluessel")

    assert provider._build_api_key() == "schluessel"


def test_resolves_to_the_default_model(provider):
    """Leerzustand: ohne Angabe entscheidet der Provider selbst."""
    assert provider._resolve_model(None) == DEFAULT_MODEL
    assert provider._resolve_model("auto") == DEFAULT_MODEL


def test_the_request_beats_the_configuration(provider, monkeypatch):
    """Normalfall: das Modell aus der Anfrage hat Vorrang."""
    monkeypatch.setenv("OMNIAI_MODEL", "gemini-2.5-flash")

    assert provider._resolve_model("gemini-2.5-pro") == "gemini-2.5-pro"


def test_unknown_gemini_models_are_allowed(provider):
    """Neue Modelle von Google sollen ohne Codeänderung nutzbar sein."""
    assert provider._resolve_model("gemini-9.9-flash") == "gemini-9.9-flash"


def test_a_leftover_claude_alias_is_rejected(provider):
    """Fehlerfall: das gemeinsame Auswahlfeld kann einen fremden Alias enthalten."""
    with pytest.raises(ValueError) as fehler:
        provider._resolve_model("sonnet")

    assert "sonnet" in str(fehler.value)
    assert "gemini-flash-latest" in str(fehler.value)


def test_extracts_the_answer_from_the_steps(provider):
    """Normalfall: der Text steht in den Schritten vom Typ „model_output“."""
    payload = {
        "steps": [
            {"type": "reasoning", "content": [{"text": "denkt nach"}]},
            {"type": "model_output", "content": [{"text": '{"status": '}, {"text": '"ok"}'}]},
        ]
    }

    assert provider._extract_text(payload, "gemini-3.6-flash") == '{"status": "ok"}'


def test_falls_back_when_the_step_type_changes(provider):
    """Benennt Google die Schritttypen um, wird eingesammelt statt gescheitert."""
    payload = {"steps": [{"type": "etwas_neues", "content": [{"text": "Inhalt"}]}]}

    assert provider._extract_text(payload, "gemini-3.6-flash") == "Inhalt"


def test_an_empty_answer_is_reported_without_the_raw_payload(provider):
    """Eiserne Regel 12: die Rohantwort gehört ins Log, nicht in die Meldung."""
    payload = {"steps": [], "status": "FILTERED", "debug": "/tmp/interner/pfad"}

    with pytest.raises(RuntimeError) as fehler:
        provider._extract_text(payload, "gemini-3.6-flash")

    text = str(fehler.value)
    assert "FILTERED" not in text
    assert "/tmp" not in text


def test_http_errors_carry_no_status_code(provider):
    """Eiserne Regel 12: kein Antwortcode im sichtbaren Text."""
    for code in (401, 404, 429, 503, 418):
        fehler = urllib.error.HTTPError(
            url="https://example.invalid", code=code, msg="", hdrs=None, fp=None
        )
        text = str(GeminiProvider._http_fehler(fehler))

        assert str(code) not in text
        assert "HTTP" not in text
        assert text.endswith(".")
