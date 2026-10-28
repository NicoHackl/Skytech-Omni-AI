"""Die Google-Konten hinter ``gemini_sub``: Liste, Orte und Zustand (D-024).

Jedes Konto hat ein **eigenes Heimatverzeichnis** und damit seine eigene
Anmeldung, seinen eigenen Zustand der Antigravity-CLI und seinen eigenen
Arbeitsbereich. Die CLI ist für genau ein Konto je Zustandsordner gebaut; ein
Wechsel des Kontos hieße Dateien tauschen, und das Format der Anmeldung kennt
nur sie selbst. Ein Wechsel ist darum nur ein anderes ``HOME`` für den Aufruf.

Das erste Konto liegt im Basisverzeichnis selbst (``/data``), wo die Anmeldung
vor der Einführung mehrerer Konten schon lag — bestehende Installationen
behalten sie, ohne etwas zu tun. Jedes weitere liegt in einem Unterordner.

Wann ein Konto an der Reihe ist, entscheidet die Reihenfolge der Liste: das
erste, das gerade Kontingent hat. Wird eines aufgebraucht, merkt sich das
Add-on einen Zeitpunkt für den nächsten Versuch (wachsend, siehe
``mark_exhausted``). Das geschieht ohne jede Tarnung — dieselbe Maschine,
dieselbe Software, ein offener Wechsel. Google nennt das automatische Wechseln
zwischen Konten ausdrücklich nicht unterstützt (docs/adr/D-024).
"""

import contextlib
import json
import logging
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger("omniai.gemini_sub.accounts")

# Die CLI legt Anmeldung und Zustand unter $HOME/.gemini ab. HOME zeigt auf das
# dauerhafte /data-Verzeichnis des Add-ons, sonst wäre die Anmeldung nach jedem
# Neustart weg. Außerhalb des Containers (Tests, lokale Entwicklung) darf ein
# anderer Ort vorgegeben werden.
HOME_ENV = "OMNIAI_GEMINI_HOME"
DEFAULT_HOME = "/data"

# Eigenes, leeres Arbeitsverzeichnis je Konto. Die CLI darf darin ohne Rückfrage
# lesen und schreiben; läge dort /data selbst, gehörten die Optionen mit allen
# Zugängen dazu.
WORKSPACE_NAME = "omniai-gemini-workspace"

TOKEN_FILE_NAME = "antigravity-oauth-token"
TOKEN_BACKUP_SUFFIX = ".bak"

ACCOUNTS_FILE_NAME = "omniai-gemini-accounts.json"
ACCOUNTS_DIR_NAME = "omniai-gemini-accounts"

# Eine Obergrenze gegen versehentliches Anlegen ohne Ende; jedes Konto kostet
# Platz (Zustand der CLI) und Google-Anmeldungen.
MAX_ACCOUNTS = 10

LABEL_PATTERN = re.compile(r"^[\w .\-@+()]{1,40}$")
ID_PATTERN = re.compile(r"^konto-(\d+)$")

# Nach einem aufgebrauchten Kontingent wartet das Add-on, bevor es das Konto
# wieder versucht: erst eine halbe Stunde, jeder weitere Fehlschlag doppelt so
# lange, höchstens fünf Stunden (so lange erneuert sich das Kontingent laut
# Google). Der erste Zeitpunkt ist bewusst kurz: ein Versuch auf ein leeres Konto
# kostet nur einen schnellen Fehler, ein zu spät freigegebenes Konto kostet
# Antworten.
BACKOFF_START_SEKUNDEN = 1800
BACKOFF_MAX_SEKUNDEN = 5 * 3600

_LOCK = threading.RLock()


class AccountError(ValueError):
    """Ein Konto lässt sich nicht anlegen; der Satz ist für Nutzer geschrieben."""


FEHLER_ZU_VIELE_KONTEN = f"Es sind höchstens {MAX_ACCOUNTS} Konten möglich."
FEHLER_NAME = (
    "Der Name darf höchstens 40 Zeichen lang sein und nur Buchstaben, Ziffern und "
    "einfache Satzzeichen enthalten."
)


# --- Orte ---------------------------------------------------------------------


def base_home() -> Path:
    return Path(os.environ.get(HOME_ENV, "").strip() or DEFAULT_HOME)


def state_dir(home: Path | None = None) -> Path:
    """Zustandsordner der CLI: Anmeldung, Einstellungen, Gespräche, Protokolle."""
    return (home or base_home()) / ".gemini" / "antigravity-cli"


def token_path(home: Path | None = None) -> Path:
    return state_dir(home) / TOKEN_FILE_NAME


def backup_path(home: Path | None = None) -> Path:
    path = token_path(home)
    return path.with_name(path.name + TOKEN_BACKUP_SUFFIX)


def workspace_dir(home: Path | None = None) -> Path:
    return (home or base_home()) / WORKSPACE_NAME


def read_token_file(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data else None


# --- Konto --------------------------------------------------------------------


@dataclass
class Account:
    id: str
    label: str
    home: Path
    added_at: float = 0.0
    # Bis wann das Add-on dieses Konto nicht versucht, und wie oft es hintereinander leer war.
    exhausted_until: float = 0.0
    strikes: int = 0
    # Warum es wartet: ``quota`` (Kontingent aufgebraucht) oder ``account`` (eingeschränkt).
    problem: str = ""
    # Google hat die Anmeldung zurückgewiesen; das Konto muss neu angemeldet werden.
    needs_login: bool = False

    def signed_in(self) -> bool:
        """Liegt eine lesbare Anmeldung vor? Ob Google sie gelten lässt, zeigt erst ein Lauf."""
        return read_token_file(token_path(self.home)) is not None

    def has_files(self) -> bool:
        return token_path(self.home).exists() or backup_path(self.home).exists()

    def state(self, now: float | None = None) -> str:
        """``signed_out``, ``login_expired``, ``restricted``, ``exhausted`` oder ``ok``."""
        if not self.signed_in():
            return "signed_out"
        if self.needs_login:
            return "login_expired"
        if self.exhausted_until > (time.time() if now is None else now):
            return "restricted" if self.problem == "account" else "exhausted"
        return "ok"


def _iso(timestamp: float) -> str | None:
    if timestamp <= 0:
        return None
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def describe(account: Account, now: float | None = None) -> dict:
    """Was die Oberfläche von einem Konto sieht — nie ein Pfad."""
    now = time.time() if now is None else now
    return {
        "id": account.id,
        "label": account.label,
        "state": account.state(now),
        "retry_at": _iso(account.exhausted_until) if account.exhausted_until > now else None,
    }


# --- Liste --------------------------------------------------------------------


def accounts_path() -> Path:
    return base_home() / ACCOUNTS_FILE_NAME


def _home_to_json(home: Path) -> str:
    return "" if home == base_home() else str(home.relative_to(base_home()))


def _home_from_json(value: str) -> Path | None:
    if not value:
        return base_home()
    relative = Path(value)
    # Die Liste liegt unter /data, ist aber kein Ort für Ausbrüche.
    if relative.is_absolute() or ".." in relative.parts:
        return None
    return base_home() / relative


def _write(accounts: list[Account]) -> None:
    payload = {
        "accounts": [
            {
                "id": a.id,
                "label": a.label,
                "home": _home_to_json(a.home),
                "added_at": a.added_at,
                "exhausted_until": a.exhausted_until,
                "strikes": a.strikes,
                "problem": a.problem,
                "needs_login": a.needs_login,
            }
            for a in accounts
        ]
    }
    path = accounts_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)
    except OSError as error:
        log.error("Liste der Google-Konten nicht speicherbar: %s", error)
        raise


def _read() -> list[Account] | None:
    """Die gespeicherte Liste; ``None``, wenn es noch keine gibt."""
    try:
        data = json.loads(accounts_path().read_text(encoding="utf-8"))
        entries = data["accounts"]
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError):
        log.error("Liste der Google-Konten unlesbar, sie gilt als leer")
        return []
    accounts = []
    for entry in entries:
        try:
            home = _home_from_json(str(entry.get("home", "")))
            if home is None or not ID_PATTERN.match(str(entry["id"])):
                continue
            accounts.append(
                Account(
                    id=str(entry["id"]),
                    label=str(entry.get("label") or entry["id"])[:40],
                    home=home,
                    added_at=float(entry.get("added_at", 0.0)),
                    exhausted_until=float(entry.get("exhausted_until", 0.0)),
                    strikes=int(entry.get("strikes", 0)),
                    problem=str(entry.get("problem", "")),
                    needs_login=bool(entry.get("needs_login", False)),
                )
            )
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return accounts


def list_accounts() -> list[Account]:
    """Alle Konten in der Reihenfolge, in der sie an die Reihe kommen.

    Gibt es noch keine Liste, aber eine Anmeldung im Basisverzeichnis (Stand vor
    der Einführung mehrerer Konten), wird sie als erstes Konto übernommen.
    """
    with _LOCK:
        accounts = _read()
        if accounts is not None:
            return accounts
        legacy = Account("konto-1", "Konto 1", base_home(), time.time())
        if (
            read_token_file(token_path(legacy.home)) is not None
            or read_token_file(backup_path(legacy.home)) is not None
        ):
            with contextlib.suppress(OSError):
                _write([legacy])
            log.info("Bestehende Google-Anmeldung als erstes Konto übernommen")
            return [legacy]
        return []


def get_account(account_id: str) -> Account | None:
    return next((a for a in list_accounts() if a.id == account_id), None)


def clean_label(label: str | None) -> str:
    """Prüft den Namen eines Kontos; leer ist erlaubt.

    :raises AccountError: wenn der Name zu lang ist oder unübliche Zeichen enthält.
    """
    text = (label or "").strip()
    if text and not LABEL_PATTERN.match(text):
        raise AccountError(FEHLER_NAME)
    return text


def new_account(label: str = "") -> Account:
    """Legt ein Konto an, **ohne** es zu speichern: erst die gelungene Anmeldung tut das.

    Das erste Konto bekommt das Basisverzeichnis, jedes weitere einen Unterordner.

    :raises AccountError: bei zu vielen Konten oder einem ungültigen Namen.
    """
    text = clean_label(label)
    with _LOCK:
        accounts = list_accounts()
        if len(accounts) >= MAX_ACCOUNTS:
            raise AccountError(FEHLER_ZU_VIELE_KONTEN)
        numbers = [int(m.group(1)) for a in accounts if (m := ID_PATTERN.match(a.id))]
        number = max(numbers, default=0) + 1
        account_id = f"konto-{number}"
        base_taken = any(a.home == base_home() for a in accounts)
        home = base_home() / ACCOUNTS_DIR_NAME / account_id if base_taken else base_home()
        return Account(account_id, text or f"Konto {number}", home, time.time())


def add_account(account: Account) -> None:
    with _LOCK:
        accounts = [a for a in list_accounts() if a.id != account.id]
        accounts.append(account)
        _write(accounts)


def update_account(account_id: str, **fields) -> Account | None:
    with _LOCK:
        accounts = list_accounts()
        for index, account in enumerate(accounts):
            if account.id == account_id:
                accounts[index] = replace(account, **fields)
                _write(accounts)
                return accounts[index]
    return None


def discard_files(account: Account) -> None:
    """Löscht Anmeldung und Zustand eines Kontos; das Basisverzeichnis selbst bleibt."""
    for path in (token_path(account.home), backup_path(account.home)):
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
    if account.home != base_home():
        shutil.rmtree(account.home, ignore_errors=True)


def remove_account(account_id: str) -> Account | None:
    """Nimmt ein Konto aus der Liste und löscht seine Dateien. Widerrufen lässt sich der
    Zugriff nur im Google-Konto."""
    with _LOCK:
        accounts = list_accounts()
        account = next((a for a in accounts if a.id == account_id), None)
        if account is None:
            return None
        _write([a for a in accounts if a.id != account_id])
    try:
        discard_files(account)
    except OSError as error:
        log.error("Dateien eines Google-Kontos nicht löschbar: %s", error)
    return account


# --- Reihenfolge --------------------------------------------------------------


def ready_accounts(now: float | None = None) -> list[Account]:
    """Konten, die jetzt an der Reihe sein dürfen — in der Reihenfolge der Liste."""
    now = time.time() if now is None else now
    return [
        a
        for a in list_accounts()
        if a.signed_in() and not a.needs_login and a.exhausted_until <= now
    ]


def mark_exhausted(
    account_id: str, now: float | None = None, kind: str = "quota"
) -> Account | None:
    """Merkt sich, dass ein Konto nicht nutzbar ist (``quota``/``account``), samt Wartezeit."""
    now = time.time() if now is None else now
    account = get_account(account_id)
    if account is None:
        return None
    strikes = account.strikes + 1
    delay = min(BACKOFF_START_SEKUNDEN * 2 ** (strikes - 1), BACKOFF_MAX_SEKUNDEN)
    return update_account(account_id, strikes=strikes, exhausted_until=now + delay, problem=kind)


def mark_needs_login(account_id: str) -> Account | None:
    return update_account(account_id, needs_login=True)


def mark_ok(account_id: str) -> None:
    """Ein Lauf hat geklappt: Wartezeit und Fehlermerker des Kontos sind erledigt."""
    account = get_account(account_id)
    if account and (account.exhausted_until or account.strikes or account.needs_login):
        update_account(account_id, exhausted_until=0.0, strikes=0, problem="", needs_login=False)


def next_try_time() -> float | None:
    """Frühester Zeitpunkt, zu dem ein aufgebrauchtes Konto wieder versucht wird."""
    times = [
        a.exhausted_until
        for a in list_accounts()
        if a.signed_in() and not a.needs_login and a.exhausted_until > 0
    ]
    return min(times) if times else None
