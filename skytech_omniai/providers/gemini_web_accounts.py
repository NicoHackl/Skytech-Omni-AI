"""Private Cookie-Ablage und Kontenliste für Gemini Web; keine Zugänge in Antworten."""

import json
import os
import re
import shutil
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

from providers import google_accounts

HOME_ENV = "OMNIAI_GEMINI_WEB_HOME"
MAX_ACCOUNTS = 10
ID_PATTERN = re.compile(r"konto-[1-9][0-9]*")
LABEL_PATTERN = re.compile(r"[\w .\-@+()]{1,40}")
_LOCK = threading.RLock()


class AccountError(ValueError):
    """Ungültige Eingabe beim Verwalten eines Kontos."""


def base_home() -> Path:
    return Path(os.environ.get(HOME_ENV, "").strip() or "/data")


def accounts_path() -> Path:
    return base_home() / "omniai-gemini-web-accounts.json"


def models_path() -> Path:
    return base_home() / "omniai-gemini-web-models.json"


@dataclass
class Account:
    id: str
    label: str
    exhausted_until: float = 0.0
    strikes: int = 0
    needs_login: bool = False

    @property
    def home(self) -> Path:
        return base_home() / "omniai-gemini-web-accounts" / self.id

    def signed_in(self) -> bool:
        return bool(read_cookies(self))


def read_cookies(account: Account) -> dict:
    """Nur die zwei Anmeldewerte; beschädigte Ablage gilt als abgemeldet."""
    try:
        data = json.loads((account.home / "cookies.json").read_text(encoding="utf-8"))
        if isinstance(data, dict) and all(
            isinstance(data.get(key), str) and data[key] for key in ("psid", "psidts")
        ):
            return {"psid": data["psid"], "psidts": data["psidts"]}
    except (OSError, ValueError):
        return {}
    return {}


def list_accounts() -> list[Account]:
    """Gespeicherte Reihenfolge ohne Zugänge; ungültige Einträge werden ausgelassen."""
    with _LOCK:
        result = []
        seen = set()
        for entry in google_accounts.read_records(accounts_path()) or []:
            try:
                account_id = entry["id"]
                if not isinstance(account_id, str) or not ID_PATTERN.fullmatch(account_id):
                    continue
                if account_id in seen:
                    continue
                seen.add(account_id)
                result.append(
                    Account(
                        account_id,
                        str(entry.get("label") or "Google-Konto")[:40],
                        float(entry.get("exhausted_until", 0)),
                        max(0, int(entry.get("strikes", 0))),
                        bool(entry.get("needs_login", False)),
                    )
                )
            except (ValueError, TypeError, KeyError):
                continue
        return result


def _write(accounts: list[Account]) -> None:
    google_accounts.write_json(accounts_path(), {"accounts": [asdict(a) for a in accounts]})


def prepare_account(label: str, psid: str, psidts: str) -> Account:
    """Legt die private Ablage an; erst die gelungene Prüfung nimmt das Konto in die Liste auf."""
    if not isinstance(label, str) or (label.strip() and not LABEL_PATTERN.fullmatch(label.strip())):
        raise AccountError(
            "Bitte einen Namen mit höchstens 40 Zeichen und einfachen Satzzeichen wählen."
        )
    for value in (psid, psidts):
        if (
            not isinstance(value, str)
            or not value
            or len(value) > 8192
            or any(
                ord(character) < 33 or ord(character) > 126 or character in ';"\\'
                for character in value
            )
        ):
            raise AccountError("Bitte beide Anmeldewerte vollständig aus dem Browser kopieren.")
    accounts = list_accounts()
    if len(accounts) >= MAX_ACCOUNTS:
        raise AccountError(f"Es sind höchstens {MAX_ACCOUNTS} Konten möglich.")
    number = max((int(a.id.split("-")[1]) for a in accounts), default=0) + 1
    account = Account(f"konto-{number}", label.strip() or f"Konto {number}")
    # Auch nach einem Abbruch oder Stromausfall wird keine alte Sitzung übernommen.
    if account.home.exists():
        shutil.rmtree(account.home)
    account.home.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    account.home.parent.chmod(0o700)
    account.home.mkdir(mode=0o700)
    google_accounts.write_json(account.home / "cookies.json", {"psid": psid, "psidts": psidts})
    return account


def add_account(account: Account) -> None:
    with _LOCK:
        _write([*list_accounts(), account])


def remove_account(account_id: str) -> None:
    with _LOCK:
        accounts = list_accounts()
        account = next((a for a in accounts if a.id == account_id), None)
        if account is None:
            raise AccountError("Dieses Konto ist nicht mehr angemeldet. Bitte die Liste neu laden.")
        if account.home.exists():
            shutil.rmtree(account.home)
        _write([a for a in accounts if a.id != account_id])
        if not list_accounts():
            models_path().unlink(missing_ok=True)


def update_account(account_id: str, **fields) -> None:
    with _LOCK:
        _write([replace(a, **fields) if a.id == account_id else a for a in list_accounts()])


def mark_exhausted(account: Account) -> None:
    strikes = account.strikes + 1
    update_account(
        account.id,
        strikes=strikes,
        exhausted_until=time.time() + google_accounts.backoff_seconds(strikes),
    )


def mark_needs_login(account: Account) -> None:
    update_account(account.id, needs_login=True)


def mark_ok(account: Account) -> None:
    if account.strikes or account.needs_login or account.exhausted_until:
        update_account(account.id, strikes=0, exhausted_until=0, needs_login=False)


def ready_accounts() -> list[Account]:
    return google_accounts.ready_accounts(list_accounts(), time.time())


def public_status() -> dict:
    """Kontonamen und Zustand; weder Cookie-Werte noch Dateipfade."""
    now = time.time()
    entries = []
    for account in list_accounts():
        waiting = account.exhausted_until > now
        state = "ok"
        if account.needs_login or not account.signed_in():
            state = "login_expired"
        elif waiting:
            state = "exhausted"
        entries.append(
            {
                "id": account.id,
                "label": account.label,
                "state": state,
                "retry_at": datetime.fromtimestamp(account.exhausted_until, UTC).isoformat()
                if waiting
                else None,
            }
        )
    return {"accounts": entries, "signed_in": bool(ready_accounts())}


def load_models() -> list[str]:
    try:
        models = json.loads(models_path().read_text(encoding="utf-8"))
        return [m for m in models if isinstance(m, str) and m] if isinstance(models, list) else []
    except (OSError, ValueError):
        return []


def store_models(models: list[str]) -> None:
    google_accounts.write_json(models_path(), list(dict.fromkeys(models)))
