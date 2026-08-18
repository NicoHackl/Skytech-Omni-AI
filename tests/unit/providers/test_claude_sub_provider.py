"""Tests für den Claude-Provider. Die CLI selbst wird dabei nie aufgerufen."""

import subprocess
from types import SimpleNamespace

import pytest

from providers import claude_sub_provider
from providers.claude_sub_provider import (
    DEFAULT_TOOL_ACCESS,
    TOOL_ACCESS_WEB,
    WEB_TOOLS,
    ClaudeSubProvider,
)


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


# --- Werkzeug-Freigabe ------------------------------------------------------
# Im Headless-Modus lehnt die CLI ohne ausdrueckliche Freigabe jedes Werkzeug
# ab. Diese Tests halten fest, welche Argumente je Stufe herausgehen.


def _captured_command(provider, monkeypatch):
    """Fuehrt execute aus und gibt die Argumentliste des CLI-Aufrufs zurueck."""
    aufrufe = []

    def fake_run(command, **kwargs):
        aufrufe.append((command, kwargs.get("env", {})))
        return _result(stdout="{}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider.execute("Test")
    return aufrufe[0]


def test_web_level_allows_only_the_web_tools(provider, monkeypatch):
    """Normalfall: Websuche und Seitenabruf, sonst nichts."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "web")
    command, env = _captured_command(provider, monkeypatch)

    assert command[command.index("--allowedTools") + 1 :] == WEB_TOOLS
    assert "--permission-mode" not in command
    # Nur die Stufe "full" braucht die Sandbox-Markierung.
    assert "IS_SANDBOX" not in env


def test_full_level_bypasses_the_permission_prompt(provider, monkeypatch):
    """Stufe full gibt alle Werkzeuge frei und markiert den Lauf als Sandbox."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "full")
    command, env = _captured_command(provider, monkeypatch)

    assert command[command.index("--permission-mode") + 1] == "bypassPermissions"
    assert "--allowedTools" not in command
    # Add-ons laufen als root; ohne die Markierung lehnt die CLI das ab.
    assert env["IS_SANDBOX"] == "1"


def test_off_level_passes_no_tool_arguments(provider, monkeypatch):
    """Stufe off entspricht dem Verhalten vor der Freigabe."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "off")
    command, _ = _captured_command(provider, monkeypatch)

    assert "--allowedTools" not in command
    assert "--permission-mode" not in command


def test_the_default_level_is_web():
    """Leerzustand: ohne Angabe wird recherchiert, aber nicht mehr."""
    assert DEFAULT_TOOL_ACCESS == TOOL_ACCESS_WEB
    assert ClaudeSubProvider.resolve_tool_access() == TOOL_ACCESS_WEB


def test_an_unknown_level_falls_back_to_the_default(monkeypatch):
    """Fehlerfall: ein Tippfehler legt den Provider nicht lahm."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "vollzugriff")

    assert ClaudeSubProvider.resolve_tool_access() == DEFAULT_TOOL_ACCESS


def test_the_level_is_read_case_insensitively(monkeypatch):
    """Ein grossgeschriebener Wert ist kein Tippfehler."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "  FULL  ")

    assert ClaudeSubProvider.resolve_tool_access() == "full"


def test_a_refusal_under_root_points_to_the_web_level(provider, monkeypatch):
    """Fehlerfall: die CLI verweigert full unter root — die Meldung nennt den Ausweg."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "full")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(
            returncode=1,
            stderr="--permission-mode bypassPermissions cannot be used with root/sudo privileges",
        ),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    text = str(fehler.value)
    assert "tool_access" in text
    # Eiserne Regel 12: die Meldung der CLI selbst bleibt im Log.
    assert "bypassPermissions" not in text
    assert "sudo" not in text


def test_other_failures_keep_the_generic_message(provider, monkeypatch):
    """Nicht jeder Abbruch ist die Verweigerung unter root."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "full")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(returncode=1, stderr="invalid API key"),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "tool_access" not in str(fehler.value)


def test_the_system_prompt_names_the_web_tools():
    """Ohne diesen Hinweis behauptet das Modell, es habe kein Internet."""
    for werkzeug in WEB_TOOLS:
        assert werkzeug in claude_sub_provider.SYSTEM_PROMPT
    assert "cannot access the internet" in claude_sub_provider.SYSTEM_PROMPT
