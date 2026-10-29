"""Anfragen, Kontowechsel und Pausen ohne Bibliothek, Netz oder echte Anmeldung."""

import json
from types import SimpleNamespace

import pytest

from providers import gemini_web_accounts as accounts
from providers import gemini_web_provider as web
from providers.base_provider import Attachment, NotJson, ProviderTimeout, UnknownModel
from providers.gemini_web_client import WebClientError


@pytest.fixture
def signed():
    def create(label="Testkonto"):
        account = accounts.prepare_account(label, "synthetisch-psid", "synthetisch-psidts")
        accounts.add_account(account)
        return account

    return create


@pytest.fixture
def bridge(monkeypatch):
    calls = []
    responses = []

    def call(account, **kwargs):
        calls.append((account.id, kwargs))
        answer = (
            responses.pop(0) if responses else {"text": '{"ok":true}', "models": ["gemini-pro"]}
        )
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(web, "client", SimpleNamespace(call=call))
    return calls, responses


def test_json_and_attachments_reach_a_new_request(signed, bridge, monkeypatch):
    signed()
    calls, _ = bridge
    monkeypatch.setenv("OMNIAI_GEMINI_WEB_MODEL", "gemini-pro")
    attachment = Attachment("test.txt", "text/plain", b"Beispiel")
    assert web.GeminiWebProvider().execute("Test", attachments=[attachment]) == {"ok": True}
    assert calls[0][1]["attachments"] == [attachment]
    assert calls[0][1]["model"] == "gemini-pro"
    assert "IMPORTANT" in calls[0][1]["prompt"]
    assert accounts.load_models() == ["gemini-pro"]
    assert web.GeminiWebProvider().effective_model() == "gemini-pro"


@pytest.mark.parametrize("text", ["", "Antwort ohne JSON"])
def test_non_json_is_rejected_without_switching(signed, bridge, text):
    signed()
    signed("Zweites")
    calls, responses = bridge
    responses.append({"text": text, "models": []})
    with pytest.raises(NotJson):
        web.GeminiWebProvider().execute("Test")
    assert len(calls) == 1


@pytest.mark.parametrize("kind,state", [("quota", "exhausted"), ("auth", "login_expired")])
def test_rotation_uses_the_next_account(signed, bridge, kind, state):
    signed()
    signed("Zweites")
    calls, responses = bridge
    responses.append(WebClientError(kind))
    assert web.GeminiWebProvider().execute("Test") == {"ok": True}
    assert [item[0] for item in calls] == ["konto-1", "konto-2"]
    assert accounts.public_status()["accounts"][0]["state"] == state
    assert calls[0][1]["prompt"] == calls[1][1]["prompt"]


def test_exhausted_accounts_fail_immediately(signed, bridge):
    account = signed()
    accounts.mark_exhausted(account)
    with pytest.raises(RuntimeError, match=r"Nächster Versuch um \d\d:\d\d"):
        web.GeminiWebProvider().execute("Test")
    assert bridge[0] == []


def test_no_account_never_calls_the_bridge(bridge):
    with pytest.raises(RuntimeError, match="anmelden"):
        web.GeminiWebProvider().execute("Test")
    assert not bridge[0]
    assert web.available_models() == []
    assert not web.is_signed_in()


@pytest.mark.parametrize(
    "kind,error", [("timeout", ProviderTimeout), ("model", UnknownModel), ("failure", RuntimeError)]
)
def test_other_failures_never_rotate(signed, bridge, kind, error):
    signed()
    signed("Zweites")
    calls, responses = bridge
    responses.append(WebClientError(kind))
    with pytest.raises(error):
        web.GeminiWebProvider().execute("Test")
    assert len(calls) == 1
    assert all(a.strikes == 0 and not a.needs_login for a in accounts.list_accounts())


def test_ip_block_pauses_all_accounts_and_survives_next_request(signed, bridge):
    signed()
    signed("Zweites")
    calls, responses = bridge
    responses.append(WebClientError("blocked"))
    for _ in range(2):
        with pytest.raises(RuntimeError, match="Verbindung vorübergehend gesperrt"):
            web.GeminiWebProvider().execute("Test")
    assert len(calls) == 1
    assert all(account.strikes == 0 for account in accounts.list_accounts())


@pytest.mark.parametrize("month,hour", [(1, "13:00"), (7, "14:00")])
def test_retry_message_is_berlin_time_without_zone(month, hour):
    from datetime import UTC, datetime

    timestamp = datetime(2026, month, 1, 12, tzinfo=UTC).timestamp()
    message = web._retry_message(timestamp)
    assert hour in message
    assert all(part not in message for part in ("UTC", "Berlin", "+0"))


def test_bad_login_leaves_no_account_or_private_files(bridge, caplog):
    calls, responses = bridge
    responses.append(WebClientError("auth"))
    with pytest.raises(RuntimeError, match="anmelden"):
        web.add_account("Beispiel", "synthetisch-psid", "synthetisch-psidts")
    assert not accounts.list_accounts()
    assert not (accounts.base_home() / "omniai-gemini-web-accounts" / "konto-1").exists()
    assert calls[-1][1]["close"] is True
    assert "synthetisch" not in caplog.text


def test_add_remove_and_refresh_are_independent_of_settings(bridge):
    state = web.add_account("Beispiel", "synthetisch-psid", "synthetisch-psidts")
    assert state["signed_in"] is True
    assert "synthetisch" not in json.dumps(state)
    assert web.refresh_models() == ["gemini-pro"]
    account = accounts.list_accounts()[0]
    assert account.home.stat().st_mode & 0o777 == 0o700
    assert (account.home / "cookies.json").stat().st_mode & 0o777 == 0o600
    assert web.remove_account(account.id)["accounts"] == []
    assert not account.home.exists()
    assert not accounts.models_path().exists()


@pytest.mark.parametrize(
    "label,psid,psidts", [("../x", "a", "b"), ("", "", "b"), ("", "a\n", "b"), ("", None, "b")]
)
def test_invalid_account_input_is_rejected(label, psid, psidts):
    with pytest.raises(accounts.AccountError):
        accounts.prepare_account(label, psid, psidts)
    assert not accounts.list_accounts()


def test_failed_storage_does_not_leave_a_registered_account(bridge, monkeypatch):
    def fail(*args):
        raise OSError("Ablage nicht verfügbar")

    monkeypatch.setattr(accounts, "store_models", fail)
    with pytest.raises(OSError):
        web.add_account("Beispiel", "synthetisch-a", "synthetisch-b")
    assert accounts.list_accounts() == []
    assert not (accounts.base_home() / "omniai-gemini-web-accounts" / "konto-1").exists()


@pytest.mark.parametrize("provider_name", ["claude_sub", "codex_sub", "gemini", "gemini_agy"])
def test_other_providers_never_ignore_attachments(provider_name):
    from providers.factory import ProviderFactory

    with pytest.raises(ValueError, match="keine Anhänge"):
        ProviderFactory.create(provider_name).execute(
            "Bild prüfen", attachments=[Attachment("test.png", "image/png", b"test")]
        )


def test_rotation_never_starts_another_request_after_the_total_deadline(
    signed, bridge, monkeypatch
):
    signed()
    signed("Zweites")
    clock_values = iter([0, 1, 4])
    monkeypatch.setattr(
        web,
        "time",
        SimpleNamespace(monotonic=lambda: next(clock_values), time=__import__("time").time),
    )
    bridge[1].append(WebClientError("quota"))
    with pytest.raises(ProviderTimeout):
        web.GeminiWebProvider().execute("Test", timeout=3)
    assert len(bridge[0]) == 1
