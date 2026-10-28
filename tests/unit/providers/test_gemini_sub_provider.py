"""Tests für den Provider „Google Gemini (Abo)“. Die CLI selbst wird nie aufgerufen.

Für den Prozessteil (``run_agy``) steht ein kleines Python-Skript an der Stelle
der CLI — es braucht weder Netz noch Anmeldung.
"""

import json
import os
import re
import sys
import textwrap
import time

import pytest

from providers import gemini_sub_accounts as accounts
from providers import gemini_sub_provider as modul
from providers.base_provider import NotJson, ProviderTimeout, UnknownModel
from providers.gemini_sub_provider import (
    GEMINI_SUB_MODELS,
    AgyResult,
    GeminiSubProvider,
    ModelInfo,
    agy_env,
    available_models,
    backup_path,
    backup_token,
    cleanup_state,
    is_signed_in,
    load_models,
    parse_envelope,
    parse_models,
    pick_model,
    prepare_state,
    refresh_models,
    remove_token,
    restore_token_if_broken,
    run_agy,
    snapshot_state,
    state_dir,
    token_path,
    workspace_dir,
)

TOKEN_JSON = '{"auth_method": "x", "token": {"refresh_token": "geheim-refresh"}}'

# Wörter, die in einer Meldung an den Nutzer nichts verloren haben (Regel 12).
TECHNIK = (
    "agy",
    "antigravity",
    "oauth",
    "token",
    "exit",
    "traceback",
    "/data",
    "401",
    "403",
    "429",
)


def _envelope(status="SUCCESS", response='{"ok": true}', error="", conversation_id="konv-1"):
    return json.dumps(
        {
            "conversation_id": conversation_id,
            "status": status,
            "response": response,
            "error": error,
        }
    )


def _result(stdout="", stderr="", returncode=0, **kwargs):
    return AgyResult(returncode=returncode, stdout=stdout, stderr=stderr, **kwargs)


class FakeAgy:
    """Ersatz für ``run_agy``: merkt sich die Aufrufe und liefert ein festes Ergebnis."""

    def __init__(self, result):
        self.result = result
        self.calls = []

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _sign_in():
    token_path().parent.mkdir(parents=True, exist_ok=True)
    token_path().write_text(TOKEN_JSON, encoding="utf-8")


@pytest.fixture
def signed_in():
    _sign_in()


@pytest.fixture
def fake(monkeypatch):
    agy = FakeAgy(_result(stdout=_envelope()))
    monkeypatch.setattr(modul, "run_agy", agy)
    return agy


@pytest.fixture
def provider():
    return GeminiSubProvider()


def _assert_no_tech(text):
    klein = text.lower()
    for wort in TECHNIK:
        assert wort not in klein, f"{wort!r} in {text!r}"


# --- Normalfall ---------------------------------------------------------------


def test_returns_the_parsed_answer(signed_in, fake, provider):
    """Normalfall: die Antwort steht im Umschlag der CLI und wird als JSON gelesen."""
    fake.result = _result(stdout=_envelope(response='{"status": "ok"}'))

    assert provider.execute("Test") == {"status": "ok"}


def test_the_answer_may_come_wrapped_in_a_code_block(signed_in, fake, provider):
    """Modelle verpacken JSON gern in Markdown — die gemeinsame Auswertung verzeiht das."""
    fake.result = _result(stdout=_envelope(response='```json\n{"a": 1}\n```'))

    assert provider.execute("Test") == {"a": 1}


def test_the_call_asks_for_json_without_slash_commands(signed_in, fake, provider):
    provider.execute("Wie spät ist es?")
    command, _ = fake.calls[0]

    assert command[0] == "agy"
    assert command[command.index("--output-format") + 1] == "json"
    # Ein Prompt, der mit „/“ beginnt, darf kein Befehl der CLI werden.
    assert "--disable-slash-commands" in command
    # Gefährliche Schalter gibt es nie.
    assert "--dangerously-skip-permissions" not in command
    assert "--continue" not in command
    prompt = command[command.index("-p") + 1]
    assert "Wie spät ist es?" in prompt
    assert "raw JSON only" in prompt


def test_the_cli_ends_itself_shortly_before_the_process_is_killed(signed_in, fake, provider):
    provider.execute("Test", timeout=100)
    command, kwargs = fake.calls[0]

    limit = command[command.index("--print-timeout") + 1]
    assert limit.endswith("s")
    assert 0 < int(limit[:-1]) < 100
    assert kwargs["timeout"] <= 100


def test_the_call_runs_in_the_empty_workspace_not_in_data(signed_in, fake, provider):
    """Im Arbeitsbereich darf die CLI ohne Rückfrage lesen — dort liegen keine Zugänge."""
    provider.execute("Test")
    _, kwargs = fake.calls[0]

    assert kwargs["cwd"] == workspace_dir()
    assert kwargs["cwd"] != modul.agy_home()
    assert workspace_dir().is_dir()


def test_the_environment_carries_no_foreign_secrets(signed_in, fake, provider, monkeypatch):
    """Ein Programm, das Anweisungen aus dem Netz liest, bekommt nur, was es braucht."""
    for name in (
        "CLAUDE_CODE_OAUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "CODEX_AUTH_JSON",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OMNIAI_API_TOKEN",
        "SUPERVISOR_TOKEN",
    ):
        monkeypatch.setenv(name, "geheim")

    provider.execute("Test")
    _, kwargs = fake.calls[0]
    env = kwargs["env"]

    assert "geheim" not in json.dumps(env)
    assert env["HOME"] == str(modul.agy_home())
    # Dateispeicher für die Anmeldung und keine Selbstaktualisierung.
    assert env["SSH_CONNECTION"]
    assert env["AGY_CLI_DISABLE_AUTO_UPDATE"] == "true"
    assert env == agy_env()


# --- Anmeldung -----------------------------------------------------------------


def test_without_login_the_cli_is_never_started(fake, provider):
    """Fehlerfall: ohne Anmeldung würde die CLI 60 Sekunden auf einen Code warten."""
    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "Google-Anmeldung" in str(fehler.value)
    _assert_no_tech(str(fehler.value))
    assert fake.calls == []


def test_an_unreadable_login_file_is_restored_from_the_backup(fake, provider):
    """Bricht ein Zeitlimit das Zurückschreiben der erneuerten Anmeldung ab, bleibt sie erhalten."""
    _sign_in()
    backup_token()
    token_path().write_text('{"token": {"refr', encoding="utf-8")

    assert provider.execute("Test") == {"ok": True}
    assert json.loads(token_path().read_text(encoding="utf-8"))["token"]["refresh_token"]


def test_a_successful_run_backs_up_the_login(signed_in, fake, provider):
    assert not backup_path().exists()

    provider.execute("Test")

    assert backup_path().is_file()
    assert oct(backup_path().stat().st_mode & 0o777) == "0o600"


def test_a_broken_login_without_backup_counts_as_signed_out(fake, provider):
    token_path().parent.mkdir(parents=True, exist_ok=True)
    token_path().write_text("kein json", encoding="utf-8")

    with pytest.raises(RuntimeError):
        provider.execute("Test")
    assert fake.calls == []


def test_remove_token_removes_the_backup_too(signed_in):
    backup_token()
    assert is_signed_in()

    remove_token()

    assert not token_path().exists()
    assert not backup_path().exists()
    assert not is_signed_in()


def test_restore_does_nothing_for_a_readable_login(signed_in):
    backup_token()
    token_path().write_text('{"token": {"refresh_token": "neuer"}}', encoding="utf-8")

    restore_token_if_broken()

    assert "neuer" in token_path().read_text(encoding="utf-8")


# --- Werkzeugstufen und Einstellungen der CLI ------------------------------------


def _settings():
    return json.loads((state_dir() / "settings.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("level", ["off", "web", "full"])
def test_commands_are_never_allowed(level, signed_in, fake, provider, monkeypatch):
    """Auch bei „Alle Werkzeuge“ gibt das Add-on der CLI keine Befehle frei."""
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", level)

    provider.execute("Test")
    rules = _settings()["permissions"]

    assert "command(*)" in rules["deny"]
    assert "execute_url(*)" in rules["deny"]
    assert not any(rule.startswith(("command", "write_file", "mcp")) for rule in rules["allow"])


def test_web_level_allows_reading_pages(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "web")

    provider.execute("Test")

    rules = _settings()["permissions"]
    assert rules["allow"] == ["read_url(*)"]
    assert "read_url(*)" not in rules["deny"]


def test_full_level_equals_web_level(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "web")
    provider.execute("Test")
    web = _settings()["permissions"]

    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "full")
    provider.execute("Test")

    assert _settings()["permissions"] == web


def test_off_level_forbids_reading_pages_and_says_so_in_the_prompt(
    signed_in, fake, provider, monkeypatch
):
    monkeypatch.setenv("OMNIAI_TOOL_ACCESS", "off")

    provider.execute("Test")
    prompt = fake.calls[0][0][fake.calls[0][0].index("-p") + 1]

    rules = _settings()["permissions"]
    assert rules["allow"] == []
    assert "read_url(*)" in rules["deny"]
    assert "Do not use any tools" in prompt
    assert "web tools" not in prompt


def test_web_level_tells_the_model_it_may_look_things_up(signed_in, fake, provider):
    provider.execute("Test")
    prompt = fake.calls[0][0][fake.calls[0][0].index("-p") + 1]

    assert "web tools" in prompt
    assert "Do not use any tools" not in prompt


def test_the_settings_keep_foreign_keys_and_trusted_folders(signed_in, fake, provider):
    """Die CLI legt eigene Schlüssel an (etwa vertraute Ordner); sie bleiben erhalten."""
    state_dir().mkdir(parents=True, exist_ok=True)
    (state_dir() / "settings.json").write_text(
        json.dumps({"theme": "dark", "trustedWorkspaces": ["/anderswo"]}), encoding="utf-8"
    )

    provider.execute("Test")
    settings = _settings()

    assert settings["theme"] == "dark"
    assert settings["trustedWorkspaces"] == ["/anderswo", str(workspace_dir())]
    assert settings["historySize"] == 0


def test_unreadable_settings_are_rewritten_not_trusted(signed_in, fake, provider):
    state_dir().mkdir(parents=True, exist_ok=True)
    (state_dir() / "settings.json").write_text("{kaputt", encoding="utf-8")

    provider.execute("Test")

    assert "command(*)" in _settings()["permissions"]["deny"]


def test_the_settings_file_is_only_rewritten_on_change(signed_in, fake, provider):
    provider.execute("Test")
    path = state_dir() / "settings.json"
    os.utime(path, (1_000_000, 1_000_000))

    provider.execute("Test")

    assert path.stat().st_mtime == 1_000_000
    assert oct(path.stat().st_mode & 0o777) == "0o600"


def test_without_settings_the_cli_does_not_run(signed_in, fake, provider, monkeypatch):
    """Fehlen die Freigabe-Regeln, gälten die Standardwerte der CLI — dann lieber gar nicht."""

    def broken(*args, **kwargs):
        raise OSError("schreibgeschützt")

    monkeypatch.setattr(modul, "_write_json_atomic", broken)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert fake.calls == []
    _assert_no_tech(str(fehler.value))


# --- Modelle -------------------------------------------------------------------


def test_no_model_means_the_cli_decides(signed_in, fake, provider):
    provider.execute("Test")

    assert "--model" not in fake.calls[0][0]
    assert provider.effective_model() == "auto"


def test_the_requested_model_is_passed_through_without_a_known_list(signed_in, fake, provider):
    """Ohne Liste (noch nicht abrufbar) entscheidet die CLI, ob sie das Modell kennt."""
    provider.execute("Test", model="Gemini 3.6 Flash (High)")
    command = fake.calls[-1][0]

    assert command[command.index("--model") + 1] == "Gemini 3.6 Flash (High)"
    assert provider.effective_model("Gemini 3.6 Flash (High)") == "Gemini 3.6 Flash (High)"


def test_the_addon_default_model_applies_without_a_request(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_MODEL", "Gemini 3.6 Flash (High)")

    provider.execute("Test")

    assert "Gemini 3.6 Flash (High)" in fake.calls[-1][0]


def test_the_request_beats_the_addon_default(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_MODEL", "Standard")

    provider.execute("Test", model="Anfrage")

    command = fake.calls[-1][0]
    assert command[command.index("--model") + 1] == "Anfrage"


def test_auto_means_no_model(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_MODEL", "auto")

    provider.execute("Test", model="auto")

    assert "--model" not in fake.calls[0][0]


@pytest.mark.parametrize("fremd", ["sonnet", "gpt-5.6-sol", "gemini-flash-latest"])
def test_a_default_model_of_another_provider_is_ignored(
    fremd, signed_in, fake, provider, monkeypatch
):
    """Nach dem Umstellen des Anbieters kann ein fremdes Standardmodell stehen bleiben."""
    monkeypatch.setenv("OMNIAI_MODEL", fremd)

    provider.execute("Test")

    assert "--model" not in fake.calls[0][0]
    assert provider.effective_model() == "auto"


MODELS_OUTPUT = """Fetching available models...
Available models:
  Gemini 4 Argon (Low)
  Gemini 4 Argon (Medium)
  Gemini 4 Argon (High)
  Gemini 3.8 Flash (Low)
  Gemini 3.8 Flash (Medium)
  Gemini 3.8 Flash (High)
  Gemini 3.1 Pro (Low)
  Gemini 3.1 Pro (High)
  Claude Opus 5.5 (Max)
"""


def _known_models():
    modul.store_models(parse_models(MODELS_OUTPUT))


def test_the_model_list_is_read_from_the_cli_output():
    labels = [m.label for m in parse_models(MODELS_OUTPUT)]

    assert labels[0] == "Gemini 4 Argon (Low)"
    assert "Gemini 3.8 Flash (Medium)" in labels
    assert len(labels) == 9
    assert not any("Fetching" in label or "Available" in label for label in labels)


@pytest.mark.parametrize(
    "ausgabe",
    [
        "Available models:\n- Gemini 4 Argon (High)\n- Gemini 3.8 Flash (Medium)\n",
        "1. Gemini 4 Argon (High)\n2) Gemini 3.8 Flash (Medium)\n",
        "* Gemini 4 Argon (High) (default)\n* Gemini 3.8 Flash (Medium) [current]\n",
        "Gemini 4 Argon (High)   ✓\nGemini 3.8 Flash (Medium)\n\n",
        "Gemini 4 Argon (High)\tgemini-4-argon-high\nGemini 3.8 Flash (Medium)\tg-3.8-flash\n",
        "Gemini 4 Argon (High)  |  gemini-4-argon-high\n",
    ],
)
def test_the_model_list_tolerates_common_layouts(ausgabe):
    labels = [m.label for m in parse_models(ausgabe)]

    assert labels[0] == "Gemini 4 Argon (High)"


def test_further_columns_become_alternative_names():
    models = parse_models("Gemini 4 Argon (High)\tgemini-4-argon-high\n")

    assert models[0].aliases == ("gemini-4-argon-high",)
    assert pick_model("gemini-4-argon-high", models) == "Gemini 4 Argon (High)"


@pytest.mark.parametrize(
    "ausgabe",
    [
        "",
        "Error: Please sign in to view available models.",
        "No models available\n",
        "Use --model <name> to choose one of these models.\n",
        '{"status": "SUCCESS"}',
    ],
)
def test_text_without_model_names_gives_no_models(ausgabe):
    assert parse_models(ausgabe) == []


def test_doubled_lines_count_once():
    assert len(parse_models("Gemini 4 Argon (High)\nGemini 4 Argon (High)\n")) == 1


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        ("Gemini 4 Argon (High)", "Gemini 4 Argon (High)"),
        ("gemini 4 argon (high)", "Gemini 4 Argon (High)"),
        ("argon-4", "Gemini 4 Argon (Medium)"),
        ("Argon 4", "Gemini 4 Argon (Medium)"),
        ("flash-3.8", "Gemini 3.8 Flash (Medium)"),
        ("gemini-3.8-flash", "Gemini 3.8 Flash (Medium)"),
        ("flash 3.8 high", "Gemini 3.8 Flash (High)"),
        ("argon-4-low", "Gemini 4 Argon (Low)"),
        ("3.8", "Gemini 3.8 Flash (Medium)"),
        ("opus", "Claude Opus 5.5 (Max)"),
        ("3.1 pro", "Gemini 3.1 Pro (High)"),
    ],
)
def test_short_names_find_the_model(eingabe, erwartet):
    """„flash-3.8“ und „argon-4“ genügen; ohne Stufe gilt Medium, sonst High."""
    assert pick_model(eingabe, parse_models(MODELS_OUTPUT)) == erwartet


def test_a_short_name_must_not_match_inside_a_number():
    models = parse_models("Gemini 13.8 Flash (High)\nGemini 3.8 Flash (High)\n")

    assert pick_model("3.8", models) == "Gemini 3.8 Flash (High)"


def test_an_unknown_name_gets_the_choices():
    with pytest.raises(UnknownModel) as fehler:
        pick_model("gpt-9", parse_models(MODELS_OUTPUT))

    text = str(fehler.value)
    assert "„gpt-9“" in text
    assert "Gemini 4 Argon (Low)" in text
    assert " …" in text
    _assert_no_tech(text.replace("agy", ""))


def test_an_ambiguous_name_gets_the_candidates():
    with pytest.raises(UnknownModel) as fehler:
        pick_model("gemini", parse_models(MODELS_OUTPUT))

    text = str(fehler.value)
    assert "mehrere Modelle" in text
    assert "Gemini 3.8 Flash" in text
    assert "Gemini 4 Argon" in text


def test_the_known_list_resolves_the_requested_model(signed_in, fake, provider):
    _known_models()

    provider.execute("Test", model="flash-3.8")

    command = fake.calls[-1][0]
    assert command[command.index("--model") + 1] == "Gemini 3.8 Flash (Medium)"
    assert len(fake.calls) == 1, "mit bekannter Liste fragt der Provider die CLI nicht erneut"
    assert provider.effective_model("argon-4") == "Gemini 4 Argon (Medium)"


def test_the_configured_default_model_is_resolved_too(signed_in, fake, provider, monkeypatch):
    _known_models()
    monkeypatch.setenv("GEMINI_SUB_MODEL", "Gemini 4 Argon (High)")

    provider.execute("Test")

    assert "Gemini 4 Argon (High)" in fake.calls[-1][0]


def test_the_request_beats_the_configured_default(signed_in, fake, provider, monkeypatch):
    _known_models()
    monkeypatch.setenv("GEMINI_SUB_MODEL", "Gemini 4 Argon (High)")

    provider.execute("Test", model="flash-3.8")

    assert "Gemini 3.8 Flash (Medium)" in fake.calls[-1][0]


def test_the_default_option_beats_the_old_global_model(signed_in, fake, provider, monkeypatch):
    _known_models()
    monkeypatch.setenv("GEMINI_SUB_MODEL", "argon-4")
    monkeypatch.setenv("OMNIAI_MODEL", "flash-3.8")

    assert provider.effective_model() == "Gemini 4 Argon (Medium)"


def test_an_unknown_model_fails_before_the_cli_starts(signed_in, fake, provider):
    _known_models()

    with pytest.raises(UnknownModel) as fehler:
        provider.execute("Test", model="gibt-es-nicht")

    assert "Zur Auswahl stehen" in str(fehler.value)
    assert fake.calls == []


def test_without_a_list_it_is_fetched_before_the_model_is_resolved(
    signed_in, provider, monkeypatch
):
    """Etwa nach einem Update: die Anmeldung gibt es, die Liste noch nicht."""
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1] == "models":
            return _result(stdout=MODELS_OUTPUT)
        return _result(stdout=_envelope())

    monkeypatch.setattr(modul, "run_agy", run)

    provider.execute("Test", model="argon-4")

    assert calls[0][1] == "models"
    assert calls[1][calls[1].index("--model") + 1] == "Gemini 4 Argon (Medium)"
    assert load_models()[1][0].label == "Gemini 4 Argon (Low)"


def test_a_failed_list_fetch_does_not_block_the_request(signed_in, provider, monkeypatch):
    def run(command, **kwargs):
        if command[1] == "models":
            return _result(stderr="Error: Please sign in", returncode=1)
        return _result(stdout=_envelope())

    monkeypatch.setattr(modul, "run_agy", run)

    assert provider.execute("Test", model="argon-4") == {"ok": True}


def test_the_cli_rejecting_a_model_lists_the_choices(signed_in, fake, provider):
    """Die Liste kann veralten; dann lehnt die CLI ab und die Meldung nennt die Auswahl."""
    modul.store_models([ModelInfo("Gemini 4 Argon (High)")])
    fake.result = _result(
        stdout=_envelope(status="ERROR", response="", error="unknown model"), returncode=1
    )

    with pytest.raises(UnknownModel) as fehler:
        provider.execute("Test", model="Gemini 4 Argon (High)")

    assert "Gemini 4 Argon (High)" in str(fehler.value)


def test_the_list_survives_in_a_file_until_the_last_account_leaves(signed_in):
    _known_models()
    assert load_models()[1][0].label == "Gemini 4 Argon (Low)"
    assert oct(modul.models_path().stat().st_mode & 0o777) == "0o600"

    remove_token()
    assert load_models()[1], "ein einzelnes Konto abzumelden räumt die gemeinsame Liste nicht"

    modul.clear_models()
    assert load_models() == (0.0, [])


def test_a_damaged_list_file_counts_as_no_list(signed_in):
    modul.models_path().parent.mkdir(parents=True, exist_ok=True)
    modul.models_path().write_text("{kaputt", encoding="utf-8")

    assert load_models() == (0.0, [])


def test_available_models_are_empty_without_a_login(fake):
    assert available_models() == []
    assert fake.calls == []


def test_available_models_fetch_once_and_then_use_the_file(signed_in, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return _result(stdout=MODELS_OUTPUT)

    monkeypatch.setattr(modul, "run_agy", run)

    first = available_models()
    second = available_models()

    assert first == second
    assert first[0] == "Gemini 4 Argon (Low)"
    assert len(calls) == 1


def test_an_old_list_is_fetched_again(signed_in, monkeypatch):
    _known_models()
    stale = time.time() - modul.MODELS_MAX_AGE_SEKUNDEN - 10
    data = json.loads(modul.models_path().read_text(encoding="utf-8"))
    data["fetched_at"] = stale
    modul.models_path().write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(modul, "run_agy", lambda *a, **k: _result(stdout="Gemini 5 Neu (High)\n"))

    assert available_models() == ["Gemini 5 Neu (High)"]


def test_a_forced_refresh_ignores_the_age(signed_in, monkeypatch):
    _known_models()
    monkeypatch.setattr(modul, "run_agy", lambda *a, **k: _result(stdout="Gemini 5 Neu (High)\n"))

    assert [m.label for m in refresh_models(force=True)] == ["Gemini 5 Neu (High)"]


def test_a_running_request_keeps_the_known_list(signed_in, fake):
    """Auf die Sperre wartet die Abfrage der Liste nicht — die Oberfläche fragt oft."""
    _known_models()
    assert modul.RUN_LOCK.acquire(timeout=1)
    try:
        labels = [m.label for m in refresh_models(force=True)]
    finally:
        modul.RUN_LOCK.release()

    assert labels[0] == "Gemini 4 Argon (Low)"
    assert fake.calls == []


def test_a_failing_fetch_keeps_the_old_list(signed_in, monkeypatch):
    _known_models()
    monkeypatch.setattr(
        modul, "run_agy", lambda *a, **k: _result(stderr="Error: Please sign in", returncode=1)
    )

    assert refresh_models(force=True)[0].label == "Gemini 4 Argon (Low)"


def test_the_provider_has_no_fixed_model_list():
    """Die Modelle kennt die CLI erst nach der Anmeldung — eine feste Liste wäre geraten."""
    assert GEMINI_SUB_MODELS == []


# --- Fehler --------------------------------------------------------------------


def test_missing_cli_gets_an_install_hint(signed_in, fake, provider):
    fake.result = FileNotFoundError("agy")

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "nicht verfügbar" in str(fehler.value)
    _assert_no_tech(str(fehler.value))


def test_timeout_of_the_process_becomes_a_provider_timeout(signed_in, fake, provider):
    fake.result = _result(timed_out=True, returncode=-9)

    with pytest.raises(ProviderTimeout) as fehler:
        provider.execute("Test")

    _assert_no_tech(str(fehler.value))


@pytest.mark.parametrize("status", ["CANCELED", "INTERRUPTED"])
def test_a_canceled_run_counts_as_timeout(status, signed_in, fake, provider):
    """Mit ``--print-timeout`` beendet sich die CLI selbst; der Status verrät es."""
    fake.result = _result(stdout=_envelope(status=status, response=""), returncode=3)

    with pytest.raises(ProviderTimeout):
        provider.execute("Test")


def test_a_demand_for_login_during_the_run_is_reported_at_once(signed_in, fake, provider):
    fake.result = _result(auth_required=True, returncode=-15)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "erneut anmelden" in str(fehler.value)
    _assert_no_tech(str(fehler.value))


@pytest.mark.parametrize(
    ("ausgabe", "erwartet"),
    [
        ("Your AI credits balance is too low to continue.", "Kontingent"),
        ("RESOURCE_EXHAUSTED: quota exceeded", "Kontingent"),
        ("rate limit hit", "Kontingent"),
        ("Your account is not eligible for Antigravity", "Konto"),
        ("This account is suspended", "Konto"),
        ("authentication failed: invalid_grant", "erneut anmelden"),
        ("Error: Please sign in", "erneut anmelden"),
        ("irgendetwas Unerwartetes", "nicht beantwortet"),
    ],
)
def test_failures_get_a_sentence_without_technical_detail(
    ausgabe, erwartet, signed_in, fake, provider
):
    """Die Rohausgabe der CLI geht ins Log, nie an den Aufrufer (Regel 12)."""
    fake.result = _result(
        stdout=_envelope(status="ERROR", response="", error=ausgabe),
        stderr="/data/.gemini/antigravity-cli/x.go:42 Traceback",
        returncode=3,
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert erwartet in str(fehler.value)
    _assert_no_tech(str(fehler.value))
    assert "Traceback" not in str(fehler.value)


def test_failure_without_envelope_uses_the_error_output(signed_in, fake, provider):
    fake.result = _result(stdout="", stderr="Error: authentication failed", returncode=1)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert "erneut anmelden" in str(fehler.value)


def test_an_unknown_model_is_named_and_not_a_generic_failure(signed_in, fake, provider):
    fake.result = _result(
        stdout=_envelope(status="ERROR", response="", error="unknown model: gibt-es-nicht"),
        returncode=1,
    )

    with pytest.raises(UnknownModel) as fehler:
        provider.execute("Test", model="gibt-es-nicht")

    assert "gibt-es-nicht" in str(fehler.value)
    _assert_no_tech(str(fehler.value).replace("gibt-es-nicht", ""))


def test_the_raw_output_goes_to_the_log(signed_in, fake, provider, caplog):
    fake.result = _result(
        stdout=_envelope(status="ERROR", response="", error="seltsamer Fehler xyz"),
        returncode=3,
    )

    with pytest.raises(RuntimeError), caplog.at_level("ERROR"):
        provider.execute("Test")

    assert "seltsamer Fehler xyz" in caplog.text


def test_an_answer_without_json_is_reported_as_such(signed_in, fake, provider):
    fake.result = _result(stdout=_envelope(response="Hier ist kein JSON."))

    with pytest.raises(NotJson):
        provider.execute("Test")


def test_an_empty_answer_is_reported_as_not_json(signed_in, fake, provider):
    fake.result = _result(stdout=_envelope(response=""))

    with pytest.raises(NotJson):
        provider.execute("Test")


def test_plain_output_without_envelope_is_still_read(signed_in, fake, provider):
    """Rückfall, falls eine künftige Fassung den Umschlag ändert."""
    fake.result = _result(stdout='{"a": 1}')

    assert provider.execute("Test") == {"a": 1}


def test_a_prompt_beyond_the_argument_limit_is_refused(signed_in, fake, provider):
    with pytest.raises(RuntimeError) as fehler:
        provider.execute("x" * 200_000)

    assert "zu lang" in str(fehler.value)
    assert fake.calls == []


# --- Eine Anfrage nach der anderen ------------------------------------------------


def test_a_second_request_waits_and_gives_up(signed_in, fake, provider, monkeypatch):
    monkeypatch.setattr(modul, "QUEUE_WAIT_MAX_SEKUNDEN", 0.05)
    assert modul.RUN_LOCK.acquire(timeout=1)
    try:
        with pytest.raises(RuntimeError) as fehler:
            provider.execute("Test")
    finally:
        modul.RUN_LOCK.release()

    assert "andere Anfrage" in str(fehler.value)
    assert fake.calls == []


def test_the_lock_is_released_after_a_failure(signed_in, fake, provider):
    fake.result = _result(stdout="", stderr="kaputt", returncode=1)

    with pytest.raises(RuntimeError):
        provider.execute("Test")

    assert modul.RUN_LOCK.acquire(timeout=0.1)
    modul.RUN_LOCK.release()


def test_too_little_time_left_after_waiting_counts_as_busy(signed_in, fake, provider):
    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test", timeout=5)

    assert "andere Anfrage" in str(fehler.value)


# --- Aufräumen -----------------------------------------------------------------


def _fill_state():
    state = state_dir()
    for name in ("conversations", "brain", "implicit"):
        (state / name).mkdir(parents=True, exist_ok=True)
    return state


def test_conversation_data_of_a_run_does_not_survive_it(signed_in, fake, provider, monkeypatch):
    """Das Add-on führt keinen Verlauf — auch nicht in den Dateien der CLI."""
    state = _fill_state()
    (state / "conversations" / "alt.pb").write_text("fremd", encoding="utf-8")

    def run_that_leaves_traces(command, **kwargs):
        (state / "conversations" / "konv-1.pb").write_text("Prompt im Klartext", encoding="utf-8")
        (state / "brain" / "konv-1").mkdir()
        (state / "brain" / "konv-1" / "task.md").write_text("Plan", encoding="utf-8")
        (state / "implicit" / "konv-1.pb").write_text("x", encoding="utf-8")
        (state / "conversation_summaries.db").write_text("Titel", encoding="utf-8")
        (state / "conversation_summaries.db-wal").write_text("Titel", encoding="utf-8")
        (workspace_dir() / "notizen.md").write_text("vom Agenten", encoding="utf-8")
        return _result(stdout=_envelope())

    monkeypatch.setattr(modul, "run_agy", run_that_leaves_traces)

    provider.execute("Test")

    assert [p.name for p in (state / "conversations").iterdir()] == ["alt.pb"]
    assert list((state / "brain").iterdir()) == []
    assert list((state / "implicit").iterdir()) == []
    assert not any(p.name.startswith("conversation_summaries.db") for p in state.iterdir())
    assert list(workspace_dir().iterdir()) == []


def test_the_login_survives_the_cleanup(signed_in, fake, provider):
    provider.execute("Test")

    assert is_signed_in()
    assert (state_dir() / "settings.json").is_file()


def test_cleanup_also_happens_after_a_failure(signed_in, provider, monkeypatch):
    state = _fill_state()

    def failing_run(command, **kwargs):
        (state / "conversations" / "konv-2.pb").write_text("x", encoding="utf-8")
        return _result(stderr="kaputt", returncode=1)

    monkeypatch.setattr(modul, "run_agy", failing_run)

    with pytest.raises(RuntimeError):
        provider.execute("Test")

    assert list((state / "conversations").iterdir()) == []


def test_entries_of_the_run_are_found_by_conversation_id_too(signed_in):
    state = _fill_state()
    before = snapshot_state()
    (state / "brain" / "konv-9").mkdir()
    # Schon vor dem Lauf vorhanden, trägt aber die Kennung des Gesprächs.
    before["brain"].add("konv-9")

    cleanup_state(before, "konv-9")

    assert list((state / "brain").iterdir()) == []


def test_only_the_newest_logs_stay(signed_in):
    log_dir = _fill_state() / "log"
    log_dir.mkdir()
    for number in range(9):
        path = log_dir / f"cli-{number}.log"
        path.write_text("x", encoding="utf-8")
        os.utime(path, (1_000_000 + number, 1_000_000 + number))

    cleanup_state(snapshot_state())

    assert sorted(p.name for p in log_dir.iterdir()) == [f"cli-{n}.log" for n in range(4, 9)]


def test_cleanup_never_fails_on_a_missing_state(tmp_path, monkeypatch):
    monkeypatch.setenv("OMNIAI_GEMINI_HOME", str(tmp_path / "gibt-es-nicht"))

    cleanup_state(snapshot_state(), "irgendwas")


def test_prepare_state_creates_a_private_workspace():
    workspace = prepare_state("web")

    assert workspace == workspace_dir()
    assert oct(workspace.stat().st_mode & 0o777) == "0o700"


# --- Umschlag ------------------------------------------------------------------


def test_envelope_is_found_behind_log_lines():
    text = "Hinweis der CLI\n" + _envelope(response="x")

    assert parse_envelope(text)["response"] == "x"


@pytest.mark.parametrize("text", ["", "kein json", "[1, 2]", "{kaputt"])
def test_no_envelope_in_garbage(text):
    assert parse_envelope(text) is None


# --- Prozess (mit Skript an Stelle der CLI) ------------------------------------------


def _script(tmp_path, body):
    path = tmp_path / "fake_agy.py"
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return [sys.executable, str(path)]


def test_run_agy_collects_output_and_exit_code(tmp_path):
    command = _script(
        tmp_path,
        """
        import sys
        print("aus stdout")
        print("aus stderr", file=sys.stderr)
        sys.exit(3)
        """,
    )

    result = run_agy(command, env={}, cwd=tmp_path, timeout=20)

    assert result.stdout.strip() == "aus stdout"
    assert result.stderr.strip() == "aus stderr"
    assert result.returncode == 3
    assert not result.timed_out
    assert not result.auth_required


def test_run_agy_kills_a_run_after_the_time_limit(tmp_path):
    command = _script(tmp_path, "import time\ntime.sleep(60)\n")
    started = time.monotonic()

    result = run_agy(command, env={}, cwd=tmp_path, timeout=0.3)

    assert result.timed_out
    assert time.monotonic() - started < 20


def test_run_agy_aborts_at_once_when_the_cli_asks_for_a_login(tmp_path):
    """Sonst wartete die CLI 60 Sekunden auf einen Code, den niemand eingibt."""
    command = _script(
        tmp_path,
        """
        import sys, time
        print("Authentication required. Please log in:", file=sys.stderr, flush=True)
        time.sleep(60)
        """,
    )
    started = time.monotonic()

    result = run_agy(command, env={}, cwd=tmp_path, timeout=30)

    assert result.auth_required
    assert not result.timed_out
    assert time.monotonic() - started < 15


def test_run_agy_does_not_abort_when_watching_is_off(tmp_path):
    command = _script(
        tmp_path,
        """
        import sys
        print("Authentication required", file=sys.stderr)
        """,
    )

    result = run_agy(command, env={}, cwd=tmp_path, timeout=20, watch_auth=False)

    assert not result.auth_required
    assert result.returncode == 0


def test_run_agy_leaves_no_child_process_behind(tmp_path):
    """Die CLI startet je Lauf einen Sprachserver; er darf den Lauf nicht überleben."""
    pid_file = tmp_path / "kind.pid"
    command = _script(
        tmp_path,
        f"""
        import subprocess, sys
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        open({str(pid_file)!r}, "w").write(str(child.pid))
        """,
    )

    run_agy(command, env={}, cwd=tmp_path, timeout=20)

    pid = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        pytest.fail("Kindprozess lief weiter")


def test_run_agy_reports_a_missing_binary(tmp_path):
    with pytest.raises(FileNotFoundError):
        run_agy(["gibt-es-nicht-agy"], env={}, cwd=tmp_path, timeout=5)


# --- Mehrere Konten (D-024) -----------------------------------------------------------


class PerAccountAgy:
    """Ersatz für ``run_agy``, der je Konto (Heimatverzeichnis) anders antwortet."""

    def __init__(self, by_label: dict[str, AgyResult]):
        self.by_label = by_label
        self.calls: list[tuple[str, list[str], dict]] = []

    def __call__(self, command, **kwargs):
        home = kwargs["env"]["HOME"]
        label = next(a.label for a in accounts.list_accounts() if str(a.home) == home)
        self.calls.append((label, command, kwargs))
        return self.by_label[label]

    @property
    def used(self) -> list[str]:
        return [label for label, _, _ in self.calls]


QUOTA = _result(
    stdout=_envelope(status="ERROR", response="", error="Your AI credits balance is too low"),
    returncode=3,
)
OK = _result(stdout=_envelope(response='{"von": "ok"}'))


def _two_accounts(*labels):
    labels = labels or ("Privat", "Arbeit")
    for label in labels:
        account = accounts.new_account(label)
        token_path(account.home).parent.mkdir(parents=True, exist_ok=True)
        token_path(account.home).write_text(TOKEN_JSON, encoding="utf-8")
        accounts.add_account(account)


def _agy(monkeypatch, **by_label):
    agy = PerAccountAgy({label.replace("_", " "): result for label, result in by_label.items()})
    monkeypatch.setattr(modul, "run_agy", agy)
    return agy


def _state(label):
    return next(a for a in accounts.list_accounts() if a.label == label).state()


def test_the_first_account_with_quota_answers(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=OK, Arbeit=OK)

    assert provider.execute("Test") == {"von": "ok"}
    assert agy.used == ["Privat"], "solange das erste Konto Kontingent hat, bleibt es dabei"


def test_an_empty_account_hands_over_to_the_next_within_the_same_request(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=OK)

    assert provider.execute("Test") == {"von": "ok"}
    assert agy.used == ["Privat", "Arbeit"]
    assert _state("Privat") == "exhausted"
    assert _state("Arbeit") == "ok"


def test_the_prompt_and_the_model_are_the_same_for_the_second_account(provider, monkeypatch):
    _two_accounts()
    _known_models()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=OK)

    provider.execute("Meine Frage", model="argon-4")

    first, second = agy.calls[0][1], agy.calls[1][1]
    assert first[first.index("-p") + 1] == second[second.index("-p") + 1]
    assert "Meine Frage" in first[first.index("-p") + 1]
    assert first[first.index("--model") + 1] == second[second.index("--model") + 1]


def test_each_account_runs_in_its_own_home_and_workspace(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=OK)

    provider.execute("Test")

    (_, _, first), (_, _, second) = agy.calls
    assert first["env"]["HOME"] != second["env"]["HOME"]
    assert first["cwd"] == workspace_dir(accounts.list_accounts()[0].home)
    assert second["cwd"] == workspace_dir(accounts.list_accounts()[1].home)
    for account in accounts.list_accounts():
        settings = json.loads((state_dir(account.home) / "settings.json").read_text())
        assert "command(*)" in settings["permissions"]["deny"]


def test_a_waiting_account_is_skipped_by_the_next_requests(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=OK)
    provider.execute("Test")
    agy.calls.clear()

    provider.execute("Test")
    provider.execute("Test")

    assert agy.used == ["Arbeit", "Arbeit"]


def test_a_waiting_account_is_tried_again_when_its_time_has_come(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=OK)
    provider.execute("Test")
    first = accounts.list_accounts()[0]
    accounts.update_account(first.id, exhausted_until=time.time() - 1)
    monkeypatch.setattr(modul, "run_agy", PerAccountAgy({"Privat": OK, "Arbeit": OK}))
    agy = modul.run_agy

    provider.execute("Test")

    assert agy.used == ["Privat"]
    assert _state("Privat") == "ok"
    assert accounts.list_accounts()[0].strikes == 0


def test_when_every_account_is_empty_the_answer_says_when_to_try_again(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=QUOTA)

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    text = str(fehler.value)
    assert agy.used == ["Privat", "Arbeit"]
    assert "allen angemeldeten Google-Konten" in text
    assert re.search(r"\b\d\d:\d\d\b", text), text
    _assert_no_tech(text)


def test_while_every_account_waits_no_cli_is_started(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=QUOTA, Arbeit=QUOTA)
    with pytest.raises(RuntimeError):
        provider.execute("Test")
    agy.calls.clear()

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert agy.calls == []
    assert "allen angemeldeten Google-Konten" in str(fehler.value)


def test_a_single_account_keeps_the_plain_quota_sentence(provider, signed_in, monkeypatch):
    agy = _agy(monkeypatch, **{"Konto_1": QUOTA})

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")
    with pytest.raises(RuntimeError) as zweite:
        provider.execute("Test")

    assert str(fehler.value) == modul.FEHLER_KONTINGENT
    assert str(zweite.value) == modul.FEHLER_KONTINGENT
    assert agy.used == ["Konto 1"], "die zweite Anfrage wartet auf die Wartezeit statt zu raten"


def test_a_login_gone_bad_marks_the_account_and_the_next_one_answers(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=_result(auth_required=True, returncode=-15), Arbeit=OK)

    assert provider.execute("Test") == {"von": "ok"}
    assert agy.used == ["Privat", "Arbeit"]
    assert _state("Privat") == "login_expired"

    agy.calls.clear()
    provider.execute("Test")
    assert agy.used == ["Arbeit"]


def test_when_no_login_is_valid_any_more_the_answer_says_to_sign_in_again(provider, monkeypatch):
    _two_accounts()
    _agy(
        monkeypatch,
        Privat=_result(auth_required=True, returncode=-15),
        Arbeit=_result(auth_required=True, returncode=-15),
    )

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")
    with pytest.raises(RuntimeError) as zweite:
        provider.execute("Test")

    assert "erneut anmelden" in str(fehler.value)
    assert "erneut anmelden" in str(zweite.value)


def test_a_restricted_account_hands_over_and_is_named_so(provider, monkeypatch):
    _two_accounts()
    restricted = _result(
        stdout=_envelope(status="ERROR", response="", error="account is not eligible"),
        returncode=1,
    )
    agy = _agy(monkeypatch, Privat=restricted, Arbeit=OK)

    assert provider.execute("Test") == {"von": "ok"}
    assert agy.used == ["Privat", "Arbeit"]
    assert _state("Privat") == "restricted"


def test_a_single_restricted_account_says_so(provider, signed_in, monkeypatch):
    restricted = _result(
        stdout=_envelope(status="ERROR", response="", error="account is not eligible"),
        returncode=1,
    )
    _agy(monkeypatch, **{"Konto_1": restricted})

    with pytest.raises(RuntimeError) as fehler:
        provider.execute("Test")

    assert str(fehler.value) == modul.FEHLER_KONTO


def test_other_failures_never_switch_the_account(provider, monkeypatch):
    """Eine schlechte Antwort ist kein Grund, ein zweites Konto zu belasten."""
    _two_accounts()
    agy = _agy(monkeypatch, Privat=_result(stderr="irgendwas", returncode=1), Arbeit=OK)

    with pytest.raises(RuntimeError):
        provider.execute("Test")

    assert agy.used == ["Privat"]
    assert _state("Privat") == "ok"


def test_an_answer_that_is_no_json_never_switches_the_account(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=_result(stdout=_envelope(response="Prosa")), Arbeit=OK)

    with pytest.raises(NotJson):
        provider.execute("Test")

    assert agy.used == ["Privat"]


def test_a_timeout_never_switches_the_account(provider, monkeypatch):
    _two_accounts()
    agy = _agy(monkeypatch, Privat=_result(timed_out=True, returncode=-9), Arbeit=OK)

    with pytest.raises(ProviderTimeout):
        provider.execute("Test")

    assert agy.used == ["Privat"]


def test_a_handover_with_too_little_time_left_ends_as_a_timeout(provider, monkeypatch):
    _two_accounts()

    def slow(command, **kwargs):
        time.sleep(1.3)
        return QUOTA

    monkeypatch.setattr(modul, "run_agy", slow)

    with pytest.raises(ProviderTimeout):
        provider.execute("Test", timeout=16)


def test_the_conversation_data_of_every_tried_account_is_cleaned(provider, monkeypatch):
    _two_accounts()
    traces = []

    def leaving(command, **kwargs):
        home = kwargs["env"]["HOME"]
        from pathlib import Path

        conversations = state_dir(Path(home)) / "conversations"
        conversations.mkdir(parents=True, exist_ok=True)
        (conversations / "spur.pb").write_text("Prompt", encoding="utf-8")
        traces.append(conversations)
        return QUOTA if len(traces) == 1 else OK

    monkeypatch.setattr(modul, "run_agy", leaving)

    provider.execute("Test")

    assert len(traces) == 2
    assert all(list(path.iterdir()) == [] for path in traces)


def test_the_model_list_is_fetched_from_the_first_signed_in_account(monkeypatch):
    _two_accounts()
    accounts.mark_needs_login("konto-1")
    agy = _agy(
        monkeypatch, Privat=_result(stdout=MODELS_OUTPUT), Arbeit=_result(stdout=MODELS_OUTPUT)
    )

    assert available_models()[0] == "Gemini 4 Argon (Low)"
    assert agy.used == ["Arbeit"]


def test_the_model_list_is_shared_by_all_accounts():
    _two_accounts()
    _known_models()

    assert modul.models_path().parent == accounts.base_home()
    assert load_models()[1][0].label == "Gemini 4 Argon (Low)"


@pytest.mark.parametrize("hours", [1, 30])
def test_the_retry_time_is_shown_as_a_clock_time(hours):
    text = modul.format_retry_time(time.time() + hours * 3600)

    assert re.fullmatch(r"(\d\d\.\d\d\., )?\d\d:\d\d", text), text
    assert ("," in text) == (hours >= 24)
    for fremd in ("UTC", "MESZ", "+0", "Berlin"):
        assert fremd not in text
