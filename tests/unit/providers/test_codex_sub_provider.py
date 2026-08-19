"""Tests für den ChatGPT-Provider. Die CLI selbst wird dabei nie aufgerufen."""

import json
import subprocess
from types import SimpleNamespace

import pytest

from providers import codex_sub_provider
from providers.codex_sub_provider import AUTH_FILE_NAME, CODEX_MODELS, CodexSubProvider

AUTH_JSON = '{"tokens": {"access_token": "geheim", "refresh_token": "auch-geheim"}}'


def _result(returncode=0, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


@pytest.fixture
def codex_home(tmp_path, monkeypatch):
    """Datenverzeichnis der CLI — im Container /data/.codex."""
    home = tmp_path / ".codex"
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


@pytest.fixture
def provider(codex_home, monkeypatch):
    monkeypatch.setenv("CODEX_AUTH_JSON", AUTH_JSON)
    return CodexSubProvider()


def _captured(provider, monkeypatch):
    """Führt execute aus und gibt Argumentliste, Umgebung und Eingabe zurück."""
    aufrufe = []

    def fake_run(command, **kwargs):
        aufrufe.append((command, kwargs.get("env", {}), kwargs.get("input", "")))
        return _result(stdout="{}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider.execute("Test")
    return aufrufe[0]


def test_returns_the_parsed_answer(provider, monkeypatch):
    """Normalfall: die Ausgabe der CLI wird als JSON zurückgegeben."""
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: _result(stdout='{"status": "ok"}')
    )

    assert provider.execute("Test") == {"status": "ok"}


def test_the_prompt_goes_through_the_standard_input(provider, monkeypatch):
    """Als Argument stünde der Prompt in der Prozessliste."""
    command, _, eingabe = _captured(provider, monkeypatch)

    assert command[-1] == "-"
    assert "Test" in eingabe
    assert not any("Test" in teil for teil in command)


def test_the_call_stays_outside_the_source_tree(provider, monkeypatch):
    """Ohne --cd läse die CLI eine AGENTS.md und deutete die Anfrage um."""
    command, _, _ = _captured(provider, monkeypatch)

    assert command[command.index("--cd") + 1] == "/data"
    assert "--skip-git-repo-check" in command
    assert "--ephemeral" in command
    assert "--ignore-user-config" in command


def test_passes_the_requested_model(provider, monkeypatch):
    """Ein Modell aus der Anfrage landet als Aufrufparameter bei der CLI."""
    aufrufe = []

    def fake_run(command, **kwargs):
        aufrufe.append(command)
        return _result(stdout="{}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    provider.execute("Test", model="gpt-5.6-luna")

    assert aufrufe[0][aufrufe[0].index("--model") + 1] == "gpt-5.6-luna"


def test_falls_back_to_the_configured_model(provider, monkeypatch):
    """Ohne Angabe in der Anfrage gilt das add-on-weite Standardmodell."""
    monkeypatch.setenv("OMNIAI_MODEL", "gpt-5.6-terra")

    assert provider._resolve_model(None) == "gpt-5.6-terra"


def test_without_a_model_the_cli_decides(provider, monkeypatch):
    """Leerzustand: ohne Vorgabe wird kein Modell erzwungen."""
    command, _, _ = _captured(provider, monkeypatch)

    assert "--model" not in command


def test_a_model_of_another_provider_is_rejected(provider):
    """Das Auswahlfeld ist für alle Anbieter dasselbe — ein Claude-Alias passt nicht."""
    with pytest.raises(ValueError) as fehler:
        provider.execute("Test", model="sonnet")

    text = str(fehler.value)
    assert "sonnet" in text
    for name in CODEX_MODELS:
        assert name in text


def test_without_credentials_it_refuses(codex_home, monkeypatch):
    """Fehlerfall: ohne Zugang wird gar nicht erst aufgerufen."""
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("Es darf kein Aufruf erfolgen.")
    )

    with pytest.raises(RuntimeError) as fehler:
        CodexSubProvider().execute("Test")

    assert "codex_auth_json" in str(fehler.value)


def test_an_api_key_works_as_a_fallback(codex_home, monkeypatch):
    """Ohne Abo-Zugang trägt der Schlüssel — nach Verbrauch abgerechnet."""
    monkeypatch.setenv("OPENAI_API_KEY", "schluessel")
    provider = CodexSubProvider()
    _, env, _ = _captured(provider, monkeypatch)

    assert env["OPENAI_API_KEY"] == "schluessel"
    assert not (codex_home / AUTH_FILE_NAME).exists()


def test_the_subscription_wins_over_the_key(provider, codex_home, monkeypatch):
    """Sonst verschöbe ein vergessener Schlüssel still die Abrechnung."""
    monkeypatch.setenv("OPENAI_API_KEY", "schluessel")
    _, env, _ = _captured(provider, monkeypatch)

    assert "OPENAI_API_KEY" not in env
    assert (codex_home / AUTH_FILE_NAME).read_text(encoding="utf-8") == AUTH_JSON


def test_a_failed_run_hides_the_cli_output(provider, monkeypatch):
    """Eiserne Regel 12: die Ausgabe der CLI kann Pfade enthalten und bleibt im Log."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(
            returncode=1, stderr="thread panicked at /usr/lib/codex/main.rs:42"
        ),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    text = str(fehler.value)
    assert "/usr/lib" not in text
    assert "panicked" not in text


def test_an_exhausted_quota_gets_its_own_sentence(provider, monkeypatch):
    """Ein aufgebrauchtes Kontingent ist kein Fehler des Nutzers."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(returncode=1, stderr="You've hit your usage limit."),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "Kontingent" in str(fehler.value)


def test_an_expired_login_names_the_way_out(provider, monkeypatch):
    """Die Meldung sagt, welches Feld neu zu befüllen ist."""
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(returncode=1, stderr="401 Unauthorized"),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    text = str(fehler.value)
    assert "codex_auth_json" in text
    assert "401" not in text


def test_a_rejected_key_names_the_key_field(codex_home, monkeypatch):
    """Wer den Schlüssel benutzt, soll nicht auf das Abo-Feld verwiesen werden."""
    monkeypatch.setenv("OPENAI_API_KEY", "schluessel")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: _result(returncode=1, stderr="401 Unauthorized"),
    )

    with pytest.raises(RuntimeError) as fehler:
        CodexSubProvider().execute("Test")

    text = str(fehler.value)
    assert "openai_api_key" in text
    assert "401" not in text


def test_missing_cli_is_reported_understandably(provider, monkeypatch):
    """Fehlerfall: ein unvollständig gebautes Bild bekommt einen eigenen Satz."""

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("codex")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "nicht verfügbar" in str(fehler.value)


def test_a_timeout_is_reported_understandably(provider, monkeypatch):
    """Fehlerfall: das Zeitlimit endet in einer Meldung, nicht in einem Absturz."""

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="codex", timeout=codex_sub_provider.TIMEOUT_SEKUNDEN)

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "zu lange" in str(fehler.value)


# --- Werkzeug-Freigabe ------------------------------------------------------
# Anders als bei Claude gibt es keine Liste einzelner Werkzeuge, sondern eine
# Sandbox-Stufe und einen Schalter für die Websuche.


def test_web_level_allows_the_search_without_write_access(provider, monkeypatch):
    """Normalfall: nachschlagen ja, schreiben nein."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "web")
    command, _, _ = _captured(provider, monkeypatch)

    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--search" in command


def test_the_tool_arguments_stand_before_the_subcommand(provider, monkeypatch):
    """„--search“ kennt nur der Hauptbefehl — dahinter bricht die CLI ab."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "web")
    command, _, _ = _captured(provider, monkeypatch)

    assert command.index("--search") < command.index("exec")
    assert command.index("--sandbox") < command.index("exec")


def test_full_level_opens_the_sandbox(provider, monkeypatch):
    """Stufe full erlaubt Befehle und Dateizugriff im Container."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "full")
    command, _, _ = _captured(provider, monkeypatch)

    assert command[command.index("--sandbox") + 1] == "danger-full-access"
    assert "--search" in command


def test_off_level_switches_the_search_off(provider, monkeypatch):
    """Stufe off beantwortet allein aus dem Trainingswissen."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "off")
    command, _, _ = _captured(provider, monkeypatch)

    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--search" not in command
    assert 'web_search="disabled"' in command


def test_the_system_prompt_names_the_search(provider, monkeypatch):
    """Ohne diesen Hinweis behauptet das Modell, es habe kein Internet."""
    _, _, eingabe = _captured(provider, monkeypatch)

    assert "web search tool" in eingabe
    assert "cannot access the internet" in eingabe


# --- Anmeldung --------------------------------------------------------------
# Die CLI erneuert ihre Tokens selbst und schreibt sie in dieselbe Datei zurück.
# Der Wert aus der Konfiguration darf sie deshalb nur bei einer Änderung
# überschreiben.


def test_the_access_is_written_to_the_data_directory(provider, codex_home, monkeypatch):
    """Erster Start: der eingetragene Zugang landet dort, wo die CLI ihn sucht."""
    _captured(provider, monkeypatch)

    datei = codex_home / AUTH_FILE_NAME
    assert json.loads(datei.read_text(encoding="utf-8")) == json.loads(AUTH_JSON)
    # Nur der Add-on-Prozess selbst darf die Datei lesen.
    assert datei.stat().st_mode & 0o077 == 0


def test_a_renewed_login_survives_a_restart(provider, codex_home, monkeypatch):
    """Der von der CLI aufgefrischte Stand wird nicht durch den alten ersetzt."""
    _captured(provider, monkeypatch)
    erneuert = '{"tokens": {"access_token": "frisch"}}'
    (codex_home / AUTH_FILE_NAME).write_text(erneuert, encoding="utf-8")

    _captured(CodexSubProvider(), monkeypatch)

    assert (codex_home / AUTH_FILE_NAME).read_text(encoding="utf-8") == erneuert


def test_a_newly_entered_access_replaces_the_old_one(provider, codex_home, monkeypatch):
    """Wer einen neuen Zugang einträgt, erwartet, dass er auch gilt."""
    _captured(provider, monkeypatch)
    neu = '{"tokens": {"access_token": "neu"}}'
    monkeypatch.setenv("CODEX_AUTH_JSON", neu)

    _captured(CodexSubProvider(), monkeypatch)

    assert (codex_home / AUTH_FILE_NAME).read_text(encoding="utf-8") == neu


def test_an_incomplete_access_is_reported_without_its_value(codex_home, monkeypatch):
    """Fehlerfall: die Meldung nennt das Feld, nie den eingefügten Inhalt."""
    monkeypatch.setenv("CODEX_AUTH_JSON", "nur die halbe Datei")
    monkeypatch.setattr(
        subprocess, "run", lambda *args, **kwargs: pytest.fail("Es darf kein Aufruf erfolgen.")
    )

    with pytest.raises(RuntimeError) as fehler:
        CodexSubProvider().execute("Test")

    text = str(fehler.value)
    assert "codex_auth_json" in text
    assert "halbe Datei" not in text
