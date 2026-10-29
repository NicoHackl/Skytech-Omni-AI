"""Gemeinsame Kontenlogik funktioniert auch ohne eine konkrete Google-Anbindung."""

from dataclasses import dataclass

from providers import google_accounts as accounts


@dataclass
class OtherAccount:
    signed: bool = True
    needs_login: bool = False
    exhausted_until: float = 0

    def signed_in(self):
        return self.signed


def test_read_records_missing_and_broken(tmp_path):
    path = tmp_path / "accounts.json"
    assert accounts.read_records(path) is None
    path.write_text('{"accounts": 12}')
    assert accounts.read_records(path) == []


def test_atomic_records_are_private(tmp_path):
    path = tmp_path / "accounts.json"
    accounts.write_json(path, {"accounts": [{"label": "Beispiel"}]})
    assert accounts.read_records(path) == [{"label": "Beispiel"}]
    assert path.stat().st_mode & 0o777 == 0o600
    assert list(tmp_path.glob(".omniai-*")) == []


def test_order_and_backoff_for_another_account_kind():
    first, waiting = OtherAccount(), OtherAccount(exhausted_until=100)
    entries = [first, waiting, OtherAccount(signed=False), OtherAccount(needs_login=True)]
    assert accounts.ready_accounts(entries, 50) == [first]
    assert accounts.next_try_time(entries) == 100
    assert accounts.next_try_time([]) is None
    assert accounts.ready_accounts([], 50) == []
    assert [accounts.backoff_seconds(n) for n in (1, 2, 3, 4, 5, 99999)] == [
        1800,
        3600,
        7200,
        14400,
        18000,
        18000,
    ]
