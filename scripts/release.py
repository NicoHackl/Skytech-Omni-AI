"""Release des Add-ons: Version und Changelog für den Release-Branch main.

dev/dev und dev/main enthalten nur den Quellstand — mit version: "dev" und ohne
Changelog. Ein Release ist ein Commit auf main, der nach dem freigegebenen Pull
Request von dev/main entsteht: der Stand von main, gestempelt mit Version und
Changelog. Der Bot schreibt dadurch nie nach dev/dev oder dev/main zurück.
Regeln: docs/git-workflow.md, Begründung: D-025.

Lokal als Trockenlauf (vorher git fetch, damit origin/main aktuell ist):

    python3 scripts/release.py plan     # Versionssprung und Changelog-Abschnitt
    python3 scripts/release.py apply    # schreibt beide Dateien in den Arbeitsbaum

Grundlage sind die Commits seit dem zuletzt veröffentlichten Stand — das ist
der jüngste gemeinsame Vorfahr von main (vor dem Merge) und dem Stand, der
hineingemergt wird. Der Bezugsstand ist über die Umgebungsvariable
RELEASE_BASE_REF überschreibbar (Standard: origin/main); der Release-Job setzt
sie auf den ersten Elternteil des Merge-Commits. Den Versionssprung bestimmen
nur Commits, die skytech_omniai/ ändern; Changelog-Einträge kommen aus den
Trailern aller Commits.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = "skytech_omniai"
CONFIG_FILE = f"{ADDON_DIR}/config.yaml"
# Liegt im Add-on-Ordner, damit Home Assistant ihn im Update-Dialog anzeigt.
CHANGELOG_FILE = f"{ADDON_DIR}/CHANGELOG.md"
# Ort des Changelogs bis 0.9.2. Nur noch gelesen, solange main ihn so enthält.
LEGACY_CHANGELOG_FILE = "CHANGELOG.md"
RELEASE_BRANCH = os.environ.get("RELEASE_BASE_REF", "origin/main")
DEV_VERSION = "dev"

BUMP_NONE = "none"
BUMP_PATCH = "patch"
BUMP_MINOR = "minor"
BUMP_MAJOR = "major"

# Reihenfolge nach Keep a Changelog; so erscheinen die Abschnitte im Changelog.
CATEGORIES = ("Hinzugefügt", "Geändert", "Veraltet", "Entfernt", "Behoben", "Sicherheit")
TRAILER_PREFIX = "Changelog-"
# Steht im Changelog, wenn ein Release keinen Eintrag mitbringt — etwa ein reines
# Refactoring oder ein Update von Abhängigkeiten. Aus Nutzersicht formuliert.
DEFAULT_ENTRY = ("Geändert", "Interne Verbesserungen ohne sichtbare Änderung.")

CHANGELOG_HEADER = """# Changelog

Alle nennenswerten Änderungen an Skytech OmniAI.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).
"""

BERLIN = ZoneInfo("Europe/Berlin")

_CONVENTIONAL_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?: ")
_BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_CONFIG_VERSION_LINE = re.compile(r'^version: "(?P<version>[^"]*)"$', re.MULTILINE)
_TRAILER = re.compile(rf"^{TRAILER_PREFIX}(?P<category>[^:\s]+):[ \t]*(?P<text>.*)$")
_FIRST_RELEASE_HEADING = re.compile(r"^## \[\d", re.MULTILINE)


@dataclass(frozen=True)
class Commit:
    subject: str
    body: str = ""


@dataclass(frozen=True)
class Plan:
    bump: str
    current: str
    version: str
    entries: dict[str, list[str]] = field(default_factory=dict)


# --- Versionssprung ----------------------------------------------------------


def determine_bump(commits: list[Commit]) -> str:
    """Leitet den Versionssprung aus Conventional Commits ab.

    BREAKING CHANGE oder "!" hinter dem Typ → major, "feat" → minor, alles
    andere → patch. Ein Betreff ohne Conventional-Format zählt als patch:
    geändert hat sich trotzdem etwas, nur sagt der Commit nicht, was.
    """
    if not commits:
        return BUMP_NONE
    bump = BUMP_PATCH
    for commit in commits:
        match = _CONVENTIONAL_SUBJECT.match(commit.subject)
        if (match and match.group("breaking")) or _BREAKING_FOOTER.search(commit.body):
            return BUMP_MAJOR
        if match and match.group("type") == "feat":
            bump = BUMP_MINOR
    return bump


def next_version(current: str, bump: str) -> str:
    match = _VERSION.match(current)
    if not match:
        raise ValueError(f"Version '{current}' ist kein MAJOR.MINOR.PATCH")
    major, minor, patch = (int(part) for part in match.groups())
    if bump == BUMP_MAJOR:
        return f"{major + 1}.0.0"
    if bump == BUMP_MINOR:
        return f"{major}.{minor + 1}.0"
    if bump == BUMP_PATCH:
        return f"{major}.{minor}.{patch + 1}"
    if bump == BUMP_NONE:
        return current
    raise ValueError(f"Unbekannter Versionssprung '{bump}'")


def read_config_version(text: str) -> str:
    matches = _CONFIG_VERSION_LINE.findall(text)
    if len(matches) != 1:
        raise ValueError(f"config.yaml braucht genau eine Versionszeile, gefunden: {len(matches)}")
    return matches[0]


def set_config_version(text: str, version: str) -> str:
    read_config_version(text)  # bricht ab, wenn die Zeile fehlt oder doppelt ist
    return _CONFIG_VERSION_LINE.sub(f'version: "{version}"', text)


# --- Changelog-Trailer -------------------------------------------------------


@dataclass(frozen=True)
class Trailer:
    category: str
    text: str


def parse_trailers(body: str) -> list[Trailer]:
    """Liest alle "Changelog-<Kategorie>: …"-Zeilen aus einem Commit-Rumpf.

    Eingerückte Folgezeilen gehören zum Eintrag davor — so bleibt ein langer
    Eintrag im Commit unter 72 Zeichen je Zeile. Die Kategorie wird hier nicht
    geprüft; das tun der commit-msg-Hook und build_entries.
    """
    trailers: list[Trailer] = []
    for line in body.splitlines():
        match = _TRAILER.match(line)
        if match:
            trailers.append(Trailer(match.group("category"), match.group("text").strip()))
        elif trailers and line[:1] in (" ", "\t") and line.strip():
            last = trailers[-1]
            trailers[-1] = Trailer(last.category, f"{last.text} {line.strip()}")
    return trailers


def build_entries(commits: list[Commit]) -> tuple[dict[str, list[str]], list[str]]:
    """Sammelt die Einträge je Kategorie; liefert dazu Warnungen für Unbekanntes.

    Eine unbekannte Kategorie verwirft den Eintrag nicht — der Commit ist schon
    veröffentlicht und lässt sich nicht mehr ändern. Er landet unter "Geändert".
    Reihenfolge: älteste Commits zuerst, wie sie entstanden sind.
    """
    entries: dict[str, list[str]] = {}
    warnings: list[str] = []
    for commit in commits:
        for trailer in parse_trailers(commit.body):
            category = trailer.category
            if category not in CATEGORIES:
                warnings.append(
                    f"Unbekannte Kategorie '{TRAILER_PREFIX}{category}' in "
                    f"'{commit.subject}' — Eintrag steht unter 'Geändert'."
                )
                category = "Geändert"
            if trailer.text:
                entries.setdefault(category, []).append(trailer.text)
    return entries, warnings


# --- Changelog-Datei ---------------------------------------------------------


def format_date(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def berlin_today(now: datetime | None = None) -> date:
    """Heutiges Datum in Berlin — auch wenn der Runner in UTC läuft."""
    moment = now if now is not None else datetime.now(tz=BERLIN)
    return moment.astimezone(BERLIN).date()


def render_section(version: str, day: date, entries: dict[str, list[str]]) -> str:
    """Abschnitt einer Version; ohne Einträge mit der Standardzeile."""
    if not any(entries.values()):
        entries = {DEFAULT_ENTRY[0]: [DEFAULT_ENTRY[1]]}
    parts = [f"## [{version}] — {format_date(day)}\n"]
    for category in CATEGORIES:
        if entries.get(category):
            lines = "\n".join(f"- {text}" for text in entries[category])
            parts.append(f"### {category}\n\n{lines}\n")
    return "\n".join(parts)


def prepend_section(previous: str | None, section: str) -> str:
    """Setzt den neuen Abschnitt über die bisherigen Versionen.

    Kopf und Abschnitt "Unveröffentlicht" des alten Changelogs entfallen: den
    Kopf schreibt dieses Skript selbst, und Unveröffentlichtes gibt es im
    Release-Branch nicht.
    """
    released = ""
    if previous:
        first = _FIRST_RELEASE_HEADING.search(previous)
        released = previous[first.start() :] if first else ""
    body = section if not released else f"{section}\n{released}"
    return f"{CHANGELOG_HEADER}\n{body.rstrip()}\n"


# --- Gesamtplan --------------------------------------------------------------


def build_plan(
    released_version: str, addon_commits: list[Commit], all_commits: list[Commit]
) -> tuple[Plan, list[str]]:
    bump = determine_bump(addon_commits)
    entries, warnings = build_entries(all_commits)
    plan = Plan(
        bump=bump,
        current=released_version,
        version=next_version(released_version, bump),
        entries=entries,
    )
    if bump != BUMP_NONE and not entries:
        warnings.append(
            "Das Add-on hat sich geändert, aber kein Commit trägt einen Changelog-Trailer. "
            "Das Release bekommt die Standardzeile."
        )
    return plan, warnings


# --- Git -------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def released_base(rev: str) -> str:
    """Zuletzt veröffentlichter Stand, der in rev enthalten ist."""
    try:
        return _git("merge-base", RELEASE_BRANCH, rev).strip()
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"Kein gemeinsamer Stand mit {RELEASE_BRANCH} gefunden. Vorher 'git fetch origin' "
            "ausführen; in der CI braucht checkout 'fetch-depth: 0'."
        ) from error


def commits_between(base: str, rev: str, path: str | None = None) -> list[Commit]:
    # \x1f trennt Betreff und Rumpf, \x1e die Commits — beides kommt in
    # Commit-Messages nicht vor. --reverse: älteste zuerst, wie im Changelog.
    args = ["log", "--reverse", "--format=%s%x1f%b%x1e", f"{base}..{rev}"]
    if path:
        args += ["--", path]
    commits = []
    for record in _git(*args).split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip("\n").partition("\x1f")
        commits.append(Commit(subject=subject, body=body))
    return commits


def release_file(path: str) -> str | None:
    try:
        return _git("show", f"{RELEASE_BRANCH}:{path}")
    except subprocess.CalledProcessError:
        return None


# --- Befehlszeile ----------------------------------------------------------


def _current_plan(rev: str) -> Plan:
    released_config = release_file(CONFIG_FILE)
    if released_config is None:
        raise SystemExit(f"{RELEASE_BRANCH} enthält keine {CONFIG_FILE}.")
    base = released_base(rev)
    plan, warnings = build_plan(
        read_config_version(released_config),
        commits_between(base, rev, f"{ADDON_DIR}/"),
        commits_between(base, rev),
    )
    for warning in warnings:
        # In GitHub Actions wird daraus eine Warnung am Lauf, lokal ist es nur eine Zeile.
        print(f"::warning::{warning}", file=sys.stderr)
    return plan


def _emit(values: dict[str, str]) -> None:
    """Gibt die Werte aus und reicht sie in GitHub Actions an die Folgeschritte."""
    lines = [f"{key}={value}" for key, value in values.items()]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def _apply(plan: Plan) -> None:
    """Schreibt Version und Changelog in den Arbeitsbaum — nur für den Release-Commit."""
    config_path = ROOT / CONFIG_FILE
    config_path.write_text(
        set_config_version(config_path.read_text(encoding="utf-8"), plan.version),
        encoding="utf-8",
    )
    previous = release_file(CHANGELOG_FILE) or release_file(LEGACY_CHANGELOG_FILE)
    section = render_section(plan.version, berlin_today(), plan.entries)
    (ROOT / CHANGELOG_FILE).write_text(prepend_section(previous, section), encoding="utf-8")


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in ("plan", "apply") or len(argv) > 2:
        print("Aufruf: release.py plan|apply [<rev>]", file=sys.stderr)
        return 2
    rev = argv[1] if len(argv) == 2 else "HEAD"

    plan = _current_plan(rev)
    if argv[0] == "apply" and plan.bump != BUMP_NONE:
        _apply(plan)

    _emit({"bump": plan.bump, "current": plan.current, "version": plan.version})
    if plan.bump != BUMP_NONE:
        print("\n" + render_section(plan.version, berlin_today(), plan.entries))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
