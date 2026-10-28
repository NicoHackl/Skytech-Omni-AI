"""Tests der Kontenliste hinter „Google Gemini (Abo)“ (D-024)."""

import json
import time

import pytest

from providers import gemini_sub_accounts as accounts
from providers.gemini_sub_accounts import (
    Account,
    AccountError,
    add_account,
    base_home,
    list_accounts,
    mark_exhausted,
    mark_needs_login,
    mark_ok,
    new_account,
    next_try_time,
    ready_accounts,
    remove_account,
    token_path,
)

TOKEN = '{"token": {"refresh_token": "geheim"}}'


def _sign_in(account: Account) -> None:
    token_path(account.home).parent.mkdir(parents=True, exist_ok=True)
    token_path(account.home).write_text(TOKEN, encoding="utf-8")


def _add(label="") -> Account:
    account = new_account(label)
    _sign_in(account)
    add_account(account)
    return account


# --- Übernahme der bestehenden Anmeldung -------------------------------------------


def test_without_any_login_there_are_no_accounts():
    assert list_accounts() == []
    assert not accounts.accounts_path().exists()


def test_an_existing_login_becomes_the_first_account():
    """Stand vor mehreren Konten: die Anmeldung lag im Basisverzeichnis."""
    token_path().parent.mkdir(parents=True)
    token_path().write_text(TOKEN, encoding="utf-8")

    [account] = list_accounts()

    assert (account.id, account.label, account.home) == ("konto-1", "Konto 1", base_home())
    assert account.signed_in()
    assert accounts.accounts_path().is_file()
    assert oct(accounts.accounts_path().stat().st_mode & 0o777) == "0o600"


def test_an_existing_backup_alone_is_enough_to_take_over():
    accounts.backup_path().parent.mkdir(parents=True)
    accounts.backup_path().write_text(TOKEN, encoding="utf-8")

    assert [a.id for a in list_accounts()] == ["konto-1"]


def test_a_broken_login_without_backup_is_no_account():
    token_path().parent.mkdir(parents=True)
    token_path().write_text("kein json", encoding="utf-8")

    assert list_accounts() == []


def test_the_takeover_happens_once():
    token_path().parent.mkdir(parents=True)
    token_path().write_text(TOKEN, encoding="utf-8")
    list_accounts()
    remove_account("konto-1")

    assert list_accounts() == []


# --- Neue Konten ---------------------------------------------------------------------


def test_the_first_account_lives_in_the_base_home_and_the_next_ones_in_folders():
    first = _add()
    second = _add("Arbeit")
    third = _add("Reserve")

    assert first.home == base_home()
    assert second.home == base_home() / accounts.ACCOUNTS_DIR_NAME / "konto-2"
    assert third.home == base_home() / accounts.ACCOUNTS_DIR_NAME / "konto-3"
    assert [a.label for a in list_accounts()] == ["Konto 1", "Arbeit", "Reserve"]


def test_a_new_account_is_not_saved_before_its_login_succeeded():
    new_account("Wartet")

    assert list_accounts() == []


def test_a_freed_number_is_taken_again_and_never_reuses_a_live_folder():
    _add()
    _add()
    remove_account("konto-1")

    third = new_account()

    assert third.id == "konto-3"
    assert third.home != base_home() / accounts.ACCOUNTS_DIR_NAME / "konto-2"


def test_the_base_home_is_reused_after_the_first_account_left():
    _add()
    remove_account("konto-1")

    assert new_account().home == base_home()


@pytest.mark.parametrize("name", ["x" * 41, "a;b", "<b>", "zeile\nzwei", "a/b"])
def test_an_unusable_name_is_refused(name):
    with pytest.raises(AccountError):
        new_account(name)


@pytest.mark.parametrize("name", ["Privat", "Max (Arbeit)", "max@example.org", "Konto-2", ""])
def test_ordinary_names_are_accepted(name):
    assert new_account(name).label


def test_the_number_of_accounts_is_limited(monkeypatch):
    monkeypatch.setattr(accounts, "MAX_ACCOUNTS", 2)
    _add()
    _add()

    with pytest.raises(AccountError):
        new_account()


# --- Ablage ---------------------------------------------------------------------------


def test_the_list_stores_relative_folders_only():
    _add()
    _add("Arbeit")

    data = json.loads(accounts.accounts_path().read_text(encoding="utf-8"))

    assert [a["home"] for a in data["accounts"]] == ["", "omniai-gemini-accounts/konto-2"]
    assert str(base_home()) not in json.dumps(data)


def test_an_entry_that_points_out_of_the_data_folder_is_ignored():
    _add()
    path = accounts.accounts_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    data["accounts"].append({"id": "konto-2", "label": "Böse", "home": "../etc"})
    data["accounts"].append({"id": "konto-3", "label": "Böse", "home": "/etc"})
    data["accounts"].append({"id": "../../x", "label": "Böse", "home": ""})
    path.write_text(json.dumps(data), encoding="utf-8")

    assert [a.id for a in list_accounts()] == ["konto-1"]


def test_a_damaged_list_counts_as_empty_and_does_not_crash():
    accounts.accounts_path().parent.mkdir(parents=True, exist_ok=True)
    accounts.accounts_path().write_text("{kaputt", encoding="utf-8")

    assert list_accounts() == []


def test_removing_an_account_deletes_its_folder_but_never_the_base_home():
    first = _add()
    second = _add("Arbeit")

    remove_account(second.id)
    assert not second.home.exists()

    remove_account(first.id)
    assert base_home().exists()
    assert not token_path(first.home).exists()


def test_removing_an_unknown_account_returns_nothing():
    assert remove_account("konto-9") is None


# --- Zustand und Reihenfolge ----------------------------------------------------------------


def test_the_states_of_an_account():
    account = _add()
    now = time.time()
    assert account.state(now) == "ok"

    mark_exhausted(account.id, now)
    assert accounts.get_account(account.id).state(now) == "exhausted"
    assert accounts.get_account(account.id).state(now + 10**6) == "ok"

    mark_exhausted(account.id, now, kind="account")
    assert accounts.get_account(account.id).state(now) == "restricted"

    mark_needs_login(account.id)
    assert accounts.get_account(account.id).state(now) == "login_expired"

    token_path(account.home).unlink()
    assert accounts.get_account(account.id).state(now) == "signed_out"


def test_the_waiting_time_doubles_up_to_five_hours():
    account = _add()
    now = 1_000_000.0

    waits = []
    for _ in range(6):
        marked = mark_exhausted(account.id, now)
        waits.append(marked.exhausted_until - now)

    assert waits == [1800, 3600, 7200, 14400, 18000, 18000]


def test_a_successful_run_clears_every_marker():
    account = _add()
    mark_exhausted(account.id)
    mark_needs_login(account.id)

    mark_ok(account.id)

    marked = accounts.get_account(account.id)
    assert (marked.exhausted_until, marked.strikes, marked.problem, marked.needs_login) == (
        0.0,
        0,
        "",
        False,
    )


def test_a_successful_run_does_not_rewrite_the_list_needlessly():
    account = _add()
    path = accounts.accounts_path()
    path.touch()
    import os

    os.utime(path, (1_000_000, 1_000_000))

    mark_ok(account.id)

    assert path.stat().st_mtime == 1_000_000


def test_ready_accounts_follow_the_order_and_skip_the_unusable():
    first = _add("A")
    second = _add("B")
    third = _add("C")
    fourth = _add("D")
    mark_exhausted(first.id)
    mark_needs_login(third.id)
    token_path(fourth.home).unlink()

    assert [a.id for a in ready_accounts()] == [second.id]


def test_an_account_becomes_ready_again_when_its_time_has_come():
    account = _add()
    now = time.time()
    mark_exhausted(account.id, now)

    assert ready_accounts(now) == []
    assert [a.id for a in ready_accounts(now + 1801)] == [account.id]


def test_the_next_try_is_the_earliest_waiting_time():
    first = _add()
    second = _add()
    now = 1_000_000.0
    mark_exhausted(first.id, now)
    mark_exhausted(first.id, now)
    mark_exhausted(second.id, now)

    assert next_try_time() == now + 1800


def test_there_is_no_next_try_without_waiting_accounts():
    _add()

    assert next_try_time() is None


def test_describe_shows_no_path_and_a_machine_readable_time():
    account = _add("Privat")
    now = 1_000_000.0
    mark_exhausted(account.id, now)

    view = accounts.describe(accounts.get_account(account.id), now)

    assert view == {
        "id": "konto-1",
        "label": "Privat",
        "state": "exhausted",
        "retry_at": "1970-01-12T14:16:40Z",
    }
    assert str(base_home()) not in json.dumps(view)


def test_describe_has_no_time_for_a_ready_account():
    _add()

    assert accounts.describe(list_accounts()[0])["retry_at"] is None
