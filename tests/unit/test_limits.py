"""Tests der Abo-Limits für GET /v1/limits (D-032).

Geprüft wird die Umsetzung der Rohdaten in den Vertrag. Die Quellen selbst
(Claude-Ereignis, Codex-App-Server) sind durch aufgezeichnete Antworten ersetzt.
"""

import json
import sys
from types import SimpleNamespace

import pytest

import limits
from app import app as flask_app

NOW = 1_800_000_000.0
TOKEN = "t" * 40

CODEX_RESULT = {
    "rateLimits": {"limitId": "codex"},
    "rateLimitsByLimitId": {
        "codex": {
            "limitId": "codex",
            "primary": {"usedPercent": 42, "windowDurationMins": 300, "resetsAt": NOW + 3600},
            "secondary": {"usedPercent": 7, "windowDurationMins": 10080, "resetsAt": NOW + 86400},
            "rateLimitReachedType": None,
        }
    },
}


@pytest.fixture(autouse=True)
def fresh_codex_cache():
    limits._codex_cache.update(at=0.0, entry=None)


# --- Claude -------------------------------------------------------------------


def test_claude_without_any_run_is_unknown_not_zero():
    entry = limits.claude_entry(True, NOW)
    assert entry["state"] == "unknown"
    assert entry["windows"] == []


def test_claude_without_credentials_is_unavailable():
    assert limits.claude_entry(False, NOW)["state"] == "unavailable"


def test_claude_event_becomes_observed_windows():
    limits.record_claude(
        {
            "status": "allowed",
            "unifiedWindows": {
                "five_hour": {"utilization": 0.123, "resetsAt": NOW + 600},
                "seven_day": {"utilization": 0.5, "resetsAt": NOW + 86400},
                "something_new": {"utilization": "kaputt"},
            },
        },
        now=NOW,
    )
    entry = limits.claude_entry(True, NOW + 10)
    assert entry["state"] == "ok"
    assert entry["accountRef"] == "default"
    assert entry["observedAt"] == limits.iso(NOW)
    windows = {w["id"]: w for w in entry["windows"]}
    assert windows["five_hour"]["usedPercent"] == 12.3
    assert windows["five_hour"]["durationMinutes"] == 300
    assert windows["seven_day"]["durationMinutes"] == 10080
    assert windows["seven_day"]["source"] == "observed"
    # Unbekannter Name: Fenster bleibt, Länge und Verbrauch unbekannt.
    assert windows["something_new"]["usedPercent"] is None
    assert windows["something_new"]["durationMinutes"] is None


def test_claude_rejected_is_exhausted_until_reset_then_unknown():
    limits.record_claude({"status": "rejected", "resetsAt": NOW + 600}, now=NOW)
    entry = limits.claude_entry(True, NOW + 1)
    assert entry["state"] == "exhausted"
    assert entry["retryAt"] == limits.iso(NOW + 600)
    assert entry["retryAtSource"] == "provider"
    assert limits.claude_entry(True, NOW + 601)["state"] == "unknown"


def test_claude_ignores_garbage_and_broken_file(tmp_path):
    limits.record_claude(None)
    assert limits.claude_entry(True, NOW)["state"] == "unknown"
    (limits.limits_dir()).mkdir(parents=True, exist_ok=True)
    (limits.limits_dir() / limits.CLAUDE_FILE_NAME).write_text("{kaputt")
    assert limits.claude_entry(True, NOW)["state"] == "unknown"


# --- Codex --------------------------------------------------------------------


@pytest.fixture
def codex_seeded(monkeypatch, tmp_path):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "codex"))
    monkeypatch.setenv("CODEX_AUTH_JSON", '{"tokens": {}}')


def test_codex_windows_are_measured(monkeypatch, codex_seeded):
    calls = []

    def rpc(env, timeout):
        calls.append(env["CODEX_HOME"])
        return {"id": 2, "result": CODEX_RESULT}

    monkeypatch.setattr(limits, "_codex_rpc", rpc)
    entry = limits.codex_entry(True, NOW)
    assert entry["state"] == "ok"
    assert [
        (w["id"], w["limitId"], w["usedPercent"], w["durationMinutes"]) for w in entry["windows"]
    ] == [
        ("primary", "codex", 42.0, 300),
        ("secondary", "codex", 7.0, 10080),
    ]
    assert entry["windows"][0]["source"] == "measured"
    # Zweiter Aufruf innerhalb einer Minute kommt aus dem Zwischenspeicher.
    limits.codex_entry(True, NOW + 30)
    assert len(calls) == 1
    limits.codex_entry(True, NOW + 61)
    assert len(calls) == 2


def test_codex_reached_limit_is_exhausted_with_provider_reset(monkeypatch, codex_seeded):
    result = {
        "rateLimits": {
            "limitId": "codex",
            "primary": {"usedPercent": 100, "windowDurationMins": 300, "resetsAt": NOW + 900},
            "rateLimitReachedType": "rate_limit_reached",
        }
    }
    monkeypatch.setattr(limits, "_codex_rpc", lambda env, timeout: {"id": 2, "result": result})
    entry = limits.codex_entry(True, NOW)
    assert entry["state"] == "exhausted"
    assert entry["retryAt"] == limits.iso(NOW + 900)
    assert entry["retryAtSource"] == "provider"


def test_codex_login_error_needs_login(monkeypatch, codex_seeded):
    monkeypatch.setattr(
        limits, "_codex_rpc", lambda env, timeout: {"error": {"message": "401 Unauthorized"}}
    )
    assert limits.codex_entry(True, NOW)["state"] == "login_required"


def test_codex_timeout_is_unknown(monkeypatch, codex_seeded):
    def rpc(env, timeout):
        raise TimeoutError

    monkeypatch.setattr(limits, "_codex_rpc", rpc)
    assert limits.codex_entry(True, NOW)["state"] == "unknown"


def test_codex_missing_cli_is_unavailable(monkeypatch, codex_seeded):
    def rpc(env, timeout):
        raise FileNotFoundError

    monkeypatch.setattr(limits, "_codex_rpc", rpc)
    assert limits.codex_entry(True, NOW)["state"] == "unavailable"


def test_codex_with_api_key_has_no_subscription_windows(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(limits, "_codex_rpc", lambda env, timeout: pytest.fail("keine Abfrage"))
    entry = limits.codex_entry(True, NOW)
    assert entry["state"] == "ok" and entry["windows"] == []


def test_codex_without_credentials_is_unavailable():
    assert limits.codex_entry(False, NOW)["state"] == "unavailable"


# --- Gemini -------------------------------------------------------------------


def web_account(**fields):
    values = {"id": "a1", "label": "Privat", "exhausted_until": 0.0, "needs_login": False}
    values.update(fields)
    signed = values.pop("signed", True)
    return SimpleNamespace(**values, signed_in=lambda: signed)


def test_gemini_web_states_and_estimated_retry(monkeypatch):
    accounts = [
        web_account(),
        web_account(id="a2", exhausted_until=NOW + 1800),
        web_account(id="a3", needs_login=True),
        web_account(id="a4", signed=False),
    ]
    monkeypatch.setattr(limits.gemini_web_accounts, "list_accounts", lambda: accounts)
    entries = limits.gemini_web_entries(NOW)
    assert [e["state"] for e in entries] == ["ok", "exhausted", "login_required", "login_required"]
    assert entries[1]["retryAt"] == limits.iso(NOW + 1800)
    assert entries[1]["retryAtSource"] == "estimated"
    assert entries[0]["retryAtSource"] is None
    assert all(e["windows"] == [] for e in entries)
    assert entries[0]["accountRef"] == "a1" and entries[0]["label"] == "Privat"


def test_gemini_agy_states(monkeypatch):
    def agy(state, until=0.0):
        return SimpleNamespace(id=state, label="", exhausted_until=until, state=lambda now: state)

    accounts = [
        agy("ok"),
        agy("restricted", NOW + 60),
        agy("exhausted", NOW + 120),
        agy("signed_out"),
    ]
    monkeypatch.setattr(limits.gemini_agy_accounts, "list_accounts", lambda: accounts)
    entries = limits.gemini_agy_entries(NOW)
    assert [e["state"] for e in entries] == ["ok", "restricted", "exhausted", "login_required"]
    assert entries[1]["retryAt"] == limits.iso(NOW + 60)
    assert entries[3]["label"] is None


# --- Gesamt und Schnittstelle -------------------------------------------------


def test_report_covers_all_providers_and_survives_broken_account_list(monkeypatch):
    def broken():
        raise ValueError("kaputt")

    monkeypatch.setattr(limits.gemini_agy_accounts, "list_accounts", broken)
    monkeypatch.setattr(limits.gemini_web_accounts, "list_accounts", lambda: [web_account()])
    report = limits.report({"claude_sub": False, "codex_sub": False, "gemini": True}, NOW)
    assert report["measuredAt"] == limits.iso(NOW)
    assert [(a["provider"], a["state"]) for a in report["accounts"]] == [
        ("claude_sub", "unavailable"),
        ("codex_sub", "unavailable"),
        ("gemini", "ok"),
        ("gemini_web", "ok"),
    ]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OMNIAI_API_TOKEN", TOKEN)
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


def test_limits_endpoint_needs_token(client):
    assert client.get("/v1/limits").status_code == 401


def test_limits_endpoint_returns_report(client, monkeypatch):
    monkeypatch.setattr(limits, "report", lambda present: {"measuredAt": "x", "accounts": []})
    response = client.get("/v1/limits", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.get_json() == {"measuredAt": "x", "accounts": []}


def test_limits_endpoint_hides_errors(client, monkeypatch):
    def boom(present):
        raise RuntimeError("/data/geheim")

    monkeypatch.setattr(limits, "report", boom)
    response = client.get("/v1/limits", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 500
    assert "geheim" not in response.get_data(as_text=True)


# --- echter Prozess mit nachgebautem App-Server ------------------------------

FAKE_APP_SERVER = """#!{python}
import json, sys
mode = {mode!r}
for line in sys.stdin:
    message = json.loads(line)
    if message.get("id") == 1:
        if mode == "init-error":
            print(json.dumps({{"id": 1, "error": {{"message": "not logged in"}}}}), flush=True)
            continue
        # Mehrere Zeilen auf einmal: dürfen im Lesepuffer nicht verloren gehen.
        sys.stdout.write("kein json\\n" + json.dumps({{"method": "status"}}) + "\\n")
        print(json.dumps({{"id": 1, "result": {{}}}}), flush=True)
    elif message.get("id") == 2:
        if mode == "silent":
            continue
        print(json.dumps({{"id": 2, "result": json.loads({result!r})}}), flush=True)
"""


def fake_cli(tmp_path, monkeypatch, mode):
    bin_dir = tmp_path / f"bin-{mode}"
    bin_dir.mkdir()
    script = bin_dir / "codex"
    script.write_text(
        FAKE_APP_SERVER.format(python=sys.executable, mode=mode, result=json.dumps(CODEX_RESULT))
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))


def test_rpc_reads_buffered_lines_of_app_server(tmp_path, monkeypatch):
    fake_cli(tmp_path, monkeypatch, "ok")
    answer = limits._codex_rpc({"PATH": str(tmp_path / "bin-ok")}, 5)
    assert answer["result"] == CODEX_RESULT


def test_rpc_initialize_error_is_returned(tmp_path, monkeypatch):
    fake_cli(tmp_path, monkeypatch, "init-error")
    assert "error" in limits._codex_rpc({"PATH": str(tmp_path / "bin-init-error")}, 5)


def test_rpc_times_out(tmp_path, monkeypatch):
    fake_cli(tmp_path, monkeypatch, "silent")
    with pytest.raises(TimeoutError):
        limits._codex_rpc({"PATH": str(tmp_path / "bin-silent")}, 1)
