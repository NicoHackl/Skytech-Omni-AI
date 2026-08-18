"""Tests für den Claude-Provider. Die CLI selbst wird dabei nie aufgerufen."""

import subprocess
from types import SimpleNamespace

import pytest

from providers import claude_sub_provider
from providers.claude_sub_provider import ClaudeSubProvider


def _result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "token")
    return ClaudeSubProvider()


def test_returns_the_parsed_answer(provider, monkeypatch):
    """Normalfall: die Ausgabe der CLI wird als JSON zurückgegeben."""
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: _result(stdout='{"status": "ok"}')
    )

    assert provider.execute("Test") == {"status": "ok"}


def test_passes_the_requested_model(provider, monkeypatch):
    """Ein Modell aus der Anfrage landet als Aufrufparameter bei der CLI."""
    aufrufe = []

    def fake_run(command, **kwargs):
        aufrufe.append(command)
        return _result(stdout="{}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider.execute("Test", model="opus")

    assert "--model" in aufrufe[0]
    assert aufrufe[0][aufrufe[0].index("--model") + 1] == "opus"


def test_falls_back_to_the_configured_model(provider, monkeypatch):
    """Ohne Angabe in der Anfrage gilt das add-on-weite Standardmodell."""
    monkeypatch.setenv("OMNIAI_MODEL", "haiku")

    assert provider._resolve_model(None) == "haiku"


def test_without_credentials_it_refuses(monkeypatch):
    """Fehlerfall: ohne Zugang wird gar nicht erst aufgerufen."""
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("Es darf kein Aufruf erfolgen.")
    )

    with pytest.raises(RuntimeError) as fehler:
        ClaudeSubProvider().execute("Test")

    assert "claude_oauth_token" in str(fehler.value)


def test_a_failed_run_hides_the_cli_output(provider, monkeypatch):
    """Eiserne Regel 12: die Ausgabe der CLI kann Pfade enthalten und bleibt im Log."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(
            returncode=1, stderr="Traceback: /usr/local/lib/claude/index.js:42"
        ),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    text = str(fehler.value)
    assert "/usr/local" not in text
    assert "Traceback" not in text


def test_missing_cli_is_reported_understandably(provider, monkeypatch):
    """Fehlerfall: ein unvollständig gebautes Bild bekommt einen eigenen Satz."""

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("claude")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "nicht verfügbar" in str(fehler.value)


def test_a_timeout_is_reported_understandably(provider, monkeypatch):
    """Fehlerfall: das Zeitlimit endet in einer Meldung, nicht in einem Absturz."""

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=claude_sub_provider.TIMEOUT_SEKUNDEN)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "zu lange" in str(fehler.value)
