"""Tests für den Provider „Google Gemini (Abo)“. Die CLI selbst wird nie aufgerufen.

Für den Prozessteil (``run_agy``) steht ein kleines Python-Skript an der Stelle
der CLI — es braucht weder Netz noch Anmeldung.
"""

import json
import os
import sys
import textwrap
import time

import pytest

from providers import gemini_sub_provider as modul
from providers.base_provider import NotJson, ProviderTimeout, UnknownModel
from providers.gemini_sub_provider import (
    GEMINI_SUB_MODELS,
    AgyResult,
    GeminiSubProvider,
    agy_env,
    backup_path,
    backup_token,
    cleanup_state,
    is_signed_in,
    parse_envelope,
    prepare_state,
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


def test_the_requested_model_is_passed_through_unchanged(signed_in, fake, provider):
    provider.execute("Test", model="Gemini 3.6 Flash (High)")
    command = fake.calls[0][0]

    assert command[command.index("--model") + 1] == "Gemini 3.6 Flash (High)"
    assert provider.effective_model("Gemini 3.6 Flash (High)") == "Gemini 3.6 Flash (High)"


def test_the_addon_default_model_applies_without_a_request(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_MODEL", "Gemini 3.6 Flash (High)")

    provider.execute("Test")

    assert "Gemini 3.6 Flash (High)" in fake.calls[0][0]


def test_the_request_beats_the_addon_default(signed_in, fake, provider, monkeypatch):
    monkeypatch.setenv("OMNIAI_MODEL", "Standard")

    provider.execute("Test", model="Anfrage")

    assert fake.calls[0][0][fake.calls[0][0].index("--model") + 1] == "Anfrage"


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
