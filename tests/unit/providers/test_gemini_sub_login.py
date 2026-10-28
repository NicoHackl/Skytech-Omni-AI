"""Tests der Anmeldung bei Google. Statt der CLI läuft ein Python-Skript, das ihren
Ablauf nachspielt: Adresse auf die Fehlerausgabe, Code von der Eingabe lesen,
Anmeldedatei schreiben.

Die Eingabe des Skripts ist wie bei der echten CLI ein Terminal (Pty) — genau das
unterscheidet eine Anmeldung, die wartet, von einer, die sofort aufgibt.
"""

import json
import stat
import sys
import textwrap
import time

import pytest

from providers import gemini_sub_login as login_modul
from providers import gemini_sub_provider as cli
from providers.gemini_sub_login import GeminiLogin, LoginError, extract_code

GOOD_CODE = "4/0AGOODCODE-12345"
SECRET_STATE = "ZUFALLSWERT-DER-SITZUNG"

# Gemeinsamer Kopf aller Skripte: Zustandsordner und Anmeldedatei finden.
HEAD = """
import json, os, sys, time
home = os.environ["HOME"]
token = os.path.join(home, ".gemini", "antigravity-cli", "antigravity-oauth-token")
"""

# Das Skript spielt die CLI nach: `models` kennt nur, wer angemeldet ist; ein Auftrag
# ohne Anmeldung druckt die Adresse und liest den Code.
CLI_SCRIPT = (
    HEAD
    + """
if sys.argv[1] == "models":
    if os.path.exists(token):
        print("Gemini Probe (Low)")
        sys.exit(0)
    print("Error: Please sign in to view available models.", file=sys.stderr)
    sys.exit(1)

print("Authentication required. Please visit the URL to log in:", file=sys.stderr)
print("  https://accounts.google.com/o/oauth2/auth?client_id=x&state=%(state)s", file=sys.stderr)
print("", file=sys.stderr)
print("Waiting for authentication (timeout 60s)...", file=sys.stderr)
print("Or, paste the authorization code here and press Enter:", file=sys.stderr, flush=True)
code = sys.stdin.readline().strip()
if code == "%(code)s":
    %(write_token)s
    print(json.dumps({"conversation_id": "konv-1", "status": "SUCCESS", "response": "{}"}))
    sys.exit(0)
print('Error: token exchange failed: oauth2: "invalid_grant"', file=sys.stderr)
print(json.dumps({"conversation_id": "", "status": "ERROR", "error": "authentication failed"}))
sys.exit(1)
"""
)

WRITE_TOKEN = (
    "os.makedirs(os.path.dirname(token), exist_ok=True); "
    'open(token, "w").write(json.dumps({"token": {"refresh_token": "geheim-refresh"}}))'
)


def _make_cli(tmp_path, monkeypatch, *, body=None, write_token=WRITE_TOKEN):
    """Legt das Skript an und lässt den Provider es statt der CLI aufrufen."""
    script = tmp_path / "fake-agy"
    source = body or CLI_SCRIPT % {
        "state": SECRET_STATE,
        "code": GOOD_CODE,
        "write_token": write_token,
    }
    script.write_text(f"#!{sys.executable}\n" + textwrap.dedent(source), encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(cli, "AGY_BINARY", str(script))
    return script


@pytest.fixture
def fake_cli(tmp_path, monkeypatch):
    return _make_cli(tmp_path, monkeypatch)


@pytest.fixture
def manager():
    created = GeminiLogin()
    yield created
    created.cancel()
    # Nach jedem Test muss die Sperre frei sein, sonst hinge der nächste daran.
    assert cli.RUN_LOCK.acquire(timeout=1)
    cli.RUN_LOCK.release()


def _wait_idle(manager, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        status = manager.status()
        if status["state"] == "idle":
            return status
        time.sleep(0.05)
    pytest.fail(f"Anmeldung wurde nicht fertig: {manager.status()}")


# --- Code lesen ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("eingabe", "erwartet"),
    [
        (GOOD_CODE, GOOD_CODE),
        (f"  {GOOD_CODE}\n", GOOD_CODE),
        (f"https://antigravity.google/oauth-callback?code={GOOD_CODE}&state=abc", GOOD_CODE),
        (f"code={GOOD_CODE}&state=abc", GOOD_CODE),
    ],
)
def test_extract_code_accepts_code_and_pasted_address(eingabe, erwartet):
    assert extract_code(eingabe) == erwartet


@pytest.mark.parametrize(
    "eingabe", ["", "   ", "kurz", "mit Leerzeichen drin 12345", "a" * 5000, "x;rm -rf /"]
)
def test_extract_code_refuses_what_is_not_a_code(eingabe):
    with pytest.raises(LoginError) as fehler:
        extract_code(eingabe)

    assert fehler.value.invalid


# --- Normalfall ----------------------------------------------------------------


def test_start_returns_the_google_address(fake_cli, manager):
    """Die Oberfläche bekommt die Adresse und die Zeit, die Google für den Code lässt."""
    status = manager.start()

    assert status["state"] == "waiting"
    assert status["url"].startswith("https://accounts.google.com/")
    assert 0 < status["seconds_left"] <= login_modul.CODE_WINDOW_SEKUNDEN
    assert status["signed_in"] is False


def test_the_address_is_hidden_from_callers_outside_the_ingress(fake_cli, manager):
    manager.start()

    assert manager.status()["url"] is None
    assert manager.status(include_url=True)["url"].startswith("https://")


def test_a_good_code_signs_in_and_survives_a_fresh_process(fake_cli, manager):
    """Ablauf wie im Betrieb: Code einfügen, Probeauftrag, Prüfung in neuem Prozess."""
    manager.start()

    manager.submit(GOOD_CODE)
    status = _wait_idle(manager)

    assert status["error"] is None
    assert status["signed_in"] is True
    assert cli.backup_path().is_file()
    assert json.loads(cli.token_path().read_text())["token"]["refresh_token"]


def test_the_models_of_the_cli_are_remembered_after_the_login(fake_cli, manager):
    """Die Liste kommt aus der Prüfung in neuem Prozess — ohne einen weiteren Aufruf."""
    manager.start()

    manager.submit(GOOD_CODE)
    _wait_idle(manager)

    assert [m.label for m in cli.load_models()[1]] == ["Gemini Probe (Low)"]


def test_logout_forgets_the_models(fake_cli, manager):
    manager.start()
    manager.submit(GOOD_CODE)
    _wait_idle(manager)

    manager.logout()

    assert cli.load_models() == (0.0, [])


def test_a_pasted_address_works_like_the_code(fake_cli, manager):
    manager.start()

    manager.submit(f"https://antigravity.google/oauth-callback?code={GOOD_CODE}&state=x")

    assert _wait_idle(manager)["signed_in"] is True


def test_the_lock_is_free_again_after_a_login(fake_cli, manager):
    manager.start()
    assert not cli.RUN_LOCK.acquire(blocking=False), "während der Anmeldung läuft sonst keine CLI"

    manager.submit(GOOD_CODE)
    _wait_idle(manager)

    assert cli.RUN_LOCK.acquire(blocking=False)
    cli.RUN_LOCK.release()


def test_the_probe_run_uses_the_restricted_settings(fake_cli, manager):
    """Schon der erste Lauf geschieht mit den Regeln für Werkzeuge, im Arbeitsbereich."""
    manager.start()
    settings = json.loads((cli.state_dir() / "settings.json").read_text())

    assert "command(*)" in settings["permissions"]["deny"]
    assert str(cli.workspace_dir()) in settings["trustedWorkspaces"]


def test_the_state_of_the_probe_run_is_cleaned_up(fake_cli, manager):
    state = cli.state_dir()
    manager.start()
    (state / "conversations").mkdir(parents=True, exist_ok=True)
    (state / "conversations" / "probe.pb").write_text("x")

    manager.cancel()

    assert list((state / "conversations").iterdir()) == []


# --- Fehlerfälle ---------------------------------------------------------------


def test_a_wrong_code_gets_a_clear_sentence(fake_cli, manager):
    manager.start()

    manager.submit("4/0AWRONGCODE-99999")
    status = _wait_idle(manager)

    assert status["signed_in"] is False
    assert status["error"] == login_modul.FEHLER_CODE_ABGELEHNT
    assert "invalid_grant" not in status["error"]


def test_a_malformed_code_is_refused_without_ending_the_session(fake_cli, manager):
    manager.start()

    with pytest.raises(LoginError) as fehler:
        manager.submit("das ist kein code")

    assert fehler.value.invalid
    assert manager.status()["state"] == "waiting"


def test_submit_without_a_running_login(manager):
    with pytest.raises(LoginError) as fehler:
        manager.submit(GOOD_CODE)

    assert str(fehler.value) == login_modul.FEHLER_KEINE_ANMELDUNG


def test_an_already_signed_in_account_is_not_replaced_silently(fake_cli, manager):
    cli.token_path().parent.mkdir(parents=True, exist_ok=True)
    cli.token_path().write_text('{"token": {"refresh_token": "x"}}')

    with pytest.raises(LoginError) as fehler:
        manager.start()

    assert str(fehler.value) == login_modul.FEHLER_BEREITS_ANGEMELDET
    assert manager.status()["state"] == "idle"


def test_a_missing_cli_is_reported_without_technical_detail(tmp_path, monkeypatch, manager):
    monkeypatch.setattr(cli, "AGY_BINARY", str(tmp_path / "gibt-es-nicht"))

    with pytest.raises(LoginError) as fehler:
        manager.start()

    assert "nicht verfügbar" in str(fehler.value)
    assert manager.status()["available"] is False


def test_a_busy_cli_blocks_the_start(fake_cli, manager, monkeypatch):
    """Läuft gerade eine Anfrage, wird keine zweite CLI daneben gestartet."""
    monkeypatch.setattr(login_modul, "START_LOCK_WAIT_SEKUNDEN", 0.05)
    assert cli.RUN_LOCK.acquire(timeout=1)
    try:
        with pytest.raises(LoginError) as fehler:
            manager.start()
    finally:
        cli.RUN_LOCK.release()

    assert fehler.value.busy


def test_a_cli_without_an_address_fails_cleanly(tmp_path, monkeypatch, manager):
    """Etwa nach einer neuen CLI-Fassung mit anderem Ablauf."""
    _make_cli(
        tmp_path,
        monkeypatch,
        body=HEAD
        + """
print("Etwas ganz anderes", file=sys.stderr, flush=True)
time.sleep(30)
""",
    )
    monkeypatch.setattr(login_modul, "URL_WAIT_SEKUNDEN", 0.6)

    with pytest.raises(LoginError) as fehler:
        manager.start()

    assert str(fehler.value) == login_modul.FEHLER_KEIN_START
    assert manager.status()["state"] == "idle"


def test_an_address_of_another_host_is_not_passed_on(tmp_path, monkeypatch, manager):
    _make_cli(
        tmp_path,
        monkeypatch,
        body=HEAD
        + """
print("Please visit:", file=sys.stderr)
print("  https://boese.example/phishing", file=sys.stderr, flush=True)
time.sleep(30)
""",
    )
    monkeypatch.setattr(login_modul, "URL_WAIT_SEKUNDEN", 0.6)

    with pytest.raises(LoginError):
        manager.start()


def test_without_a_code_the_session_expires(fake_cli, manager, monkeypatch):
    monkeypatch.setattr(login_modul, "CODE_WINDOW_SEKUNDEN", 1)
    monkeypatch.setattr(login_modul, "CODE_SAFETY_SEKUNDEN", 0)
    monkeypatch.setattr(login_modul, "WATCH_GRACE_SEKUNDEN", 0)
    manager.start()

    status = _wait_idle(manager)

    assert status["error"] == login_modul.FEHLER_ZEIT
    assert status["url"] is None


def test_an_accepted_login_that_does_not_persist_is_reported(tmp_path, monkeypatch, manager):
    """Der Fall, an dem andere Container gescheitert sind: angenommen, aber nicht gespeichert."""
    _make_cli(tmp_path, monkeypatch, write_token="pass")
    manager.start()

    manager.submit(GOOD_CODE)
    status = _wait_idle(manager)

    assert status["signed_in"] is False
    assert status["error"] == login_modul.FEHLER_NICHT_GESPEICHERT


def test_the_check_after_the_code_has_a_time_limit(fake_cli, manager, monkeypatch):
    monkeypatch.setattr(login_modul, "FINISH_WAIT_SEKUNDEN", 1)
    _make_cli_hanging = fake_cli
    _make_cli_hanging.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent(
            HEAD
            + """
print("Authentication required", file=sys.stderr)
print("  https://accounts.google.com/o/oauth2/auth?state=x", file=sys.stderr)
print("", file=sys.stderr, flush=True)
sys.stdin.readline()
time.sleep(60)
"""
        ),
        encoding="utf-8",
    )
    manager.start()

    manager.submit(GOOD_CODE)
    status = _wait_idle(manager)

    assert status["error"] == login_modul.FEHLER_PRUEFUNG_ZEIT


def test_the_account_not_being_eligible_is_named(tmp_path, monkeypatch, manager):
    _make_cli(
        tmp_path,
        monkeypatch,
        body=HEAD
        + """
print("Authentication required", file=sys.stderr)
print("  https://accounts.google.com/o/oauth2/auth?state=x", file=sys.stderr)
print("", file=sys.stderr, flush=True)
sys.stdin.readline()
print("Error: this account is not eligible for Antigravity", file=sys.stderr)
print(json.dumps({"conversation_id": "", "status": "ERROR", "error": "not eligible"}))
sys.exit(1)
""",
    )
    manager.start()

    manager.submit(GOOD_CODE)
    status = _wait_idle(manager)

    assert status["error"] == cli.FEHLER_KONTO


def test_a_used_up_quota_after_the_login_is_named_as_such(tmp_path, monkeypatch, manager):
    """Die Anmeldung kann klappen und der Probeauftrag trotzdem am Kontingent scheitern."""
    _make_cli(
        tmp_path,
        monkeypatch,
        body=HEAD
        + """
print("Authentication required", file=sys.stderr)
print("  https://accounts.google.com/o/oauth2/auth?state=x", file=sys.stderr)
print("", file=sys.stderr, flush=True)
sys.stdin.readline()
os.makedirs(os.path.dirname(token), exist_ok=True)
open(token, "w").write('{"token": {"refresh_token": "x"}}')
error = "Your AI credits balance is too low"
print(json.dumps({"conversation_id": "k", "status": "ERROR", "error": error}))
sys.exit(3)
""",
    )
    manager.start()

    manager.submit(GOOD_CODE)
    status = _wait_idle(manager)

    assert status["error"] == cli.FEHLER_KONTINGENT
    assert status["signed_in"] is True


def test_the_lock_is_released_even_if_the_cleanup_fails(fake_cli, manager, monkeypatch):
    manager.start()

    def broken(*args, **kwargs):
        raise OSError("kaputt")

    monkeypatch.setattr(cli, "cleanup_state", broken)
    with pytest.raises(OSError):
        manager.cancel()

    assert cli.RUN_LOCK.acquire(timeout=1)
    cli.RUN_LOCK.release()


# --- Abbrechen, Abmelden, Neustart ------------------------------------------------


def test_cancel_ends_the_session_and_the_process(fake_cli, manager):
    manager.start()
    process = manager._session.process

    status = manager.cancel()

    assert status["state"] == "idle"
    assert status["error"] is None
    assert process.poll() is not None


def test_a_new_start_replaces_a_waiting_session(fake_cli, manager):
    first = manager.start()
    old_process = manager._session.process

    second = manager.start()

    assert old_process.poll() is not None
    assert second["state"] == "waiting"
    assert second["url"] == first["url"] or second["url"].startswith("https://")


def test_logout_removes_the_login_and_its_backup(fake_cli, manager):
    manager.start()
    manager.submit(GOOD_CODE)
    _wait_idle(manager)
    assert cli.is_signed_in()

    status = manager.logout()

    assert status["signed_in"] is False
    assert not cli.token_path().exists()
    assert not cli.backup_path().exists()


def test_logout_without_a_login_is_harmless(manager):
    assert manager.logout()["signed_in"] is False


# --- Geheimnisse ---------------------------------------------------------------


def test_neither_code_nor_address_state_appear_in_the_log(fake_cli, manager, caplog):
    """Der Code ist ein Zugang und die Adresse trägt Zufallswerte der Sitzung."""
    with caplog.at_level("DEBUG"):
        manager.start()
        manager.submit("4/0AWRONGCODE-99999")
        _wait_idle(manager)

    assert "4/0AWRONGCODE-99999" not in caplog.text
    assert SECRET_STATE not in caplog.text


def test_the_error_text_carries_nothing_technical(fake_cli, manager):
    manager.start()
    manager.submit("4/0AWRONGCODE-99999")

    error = _wait_idle(manager)["error"]

    for wort in ("invalid_grant", "oauth", "exit", "agy", "token exchange"):
        assert wort not in error.lower()
