"""Versionssprung und Changelog für ein Release des Add-ons.

Der Release-Job in .github/workflows/ci.yaml ruft dieses Skript auf, sobald alle
Prüfungen auf agent/main grün sind. Lokal läuft es genauso, etwa als Trockenlauf:

    python scripts/release.py plan     # zeigt, was ein Release jetzt täte
    python scripts/release.py apply    # schreibt config.yaml und CHANGELOG.md

Grundlage sind die Commits seit dem letzten Tag "v*", die etwas unter
skytech_omniai/ geändert haben. Ändert sich dort nichts, gibt es kein Release.
Die Regeln stehen in docs/git-workflow.md, die Begründung in D-016.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
ADDON_DIR = "skytech_omniai"
CONFIG_PATH = ROOT / ADDON_DIR / "config.yaml"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"
TAG_PREFIX = "v"

BUMP_NONE = "none"
BUMP_PATCH = "patch"
BUMP_MINOR = "minor"
BUMP_MAJOR = "major"

UNRELEASED_HEADING = "## [Unveröffentlicht]"
# Steht im Changelog, wenn ein Release keinen Eintrag mitbringt — etwa ein reines
# Refactoring oder ein Update von Abhängigkeiten. Aus Nutzersicht formuliert.
DEFAULT_CHANGELOG_ENTRY = "### Geändert\n\n- Interne Verbesserungen ohne sichtbare Änderung."

BERLIN = ZoneInfo("Europe/Berlin")

_CONVENTIONAL_SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\([^)]*\))?(?P<breaking>!)?: ")
_BREAKING_FOOTER = re.compile(r"^BREAKING[ -]CHANGE: ", re.MULTILINE)
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_CONFIG_VERSION_LINE = re.compile(r'^version: "(?P<version>[^"]*)"$', re.MULTILINE)


@dataclass(frozen=True)
class Commit:
    subject: str
    body: str = ""


@dataclass(frozen=True)
class Plan:
    bump: str
    current: str
    version: str
    changelog_empty: bool


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


def _unreleased_bounds(text: str) -> tuple[int, int]:
    """Anfang und Ende des Inhalts unter "## [Unveröffentlicht]"."""
    start = text.find(UNRELEASED_HEADING + "\n")
    if start == -1:
        raise ValueError(f"CHANGELOG.md enthält keinen Abschnitt '{UNRELEASED_HEADING}'")
    content_start = start + len(UNRELEASED_HEADING) + 1
    next_heading = text.find("\n## ", content_start - 1)
    content_end = len(text) if next_heading == -1 else next_heading + 1
    return content_start, content_end


def unreleased_is_empty(text: str) -> bool:
    content_start, content_end = _unreleased_bounds(text)
    return not text[content_start:content_end].strip()


def format_date(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def berlin_today(now: datetime | None = None) -> date:
    """Heutiges Datum in Berlin — auch wenn der Runner in UTC läuft."""
    moment = now if now is not None else datetime.now(tz=BERLIN)
    return moment.astimezone(BERLIN).date()


def roll_changelog(text: str, version: str, day: date) -> str:
    """Macht aus "Unveröffentlicht" den Abschnitt der neuen Version.

    Darüber entsteht ein neuer, leerer Abschnitt "Unveröffentlicht". Bringt das
    Release keinen Eintrag mit, steht dort die Standardzeile.
    """
    content_start, content_end = _unreleased_bounds(text)
    entries = text[content_start:content_end].strip() or DEFAULT_CHANGELOG_ENTRY
    released = f"## [{version}] — {format_date(day)}\n\n{entries}\n\n"
    head = text[:content_start]
    tail = text[content_end:]
    return f"{head}\n{released}{tail}"


def build_plan(config_text: str, changelog_text: str, commits: list[Commit]) -> Plan:
    current = read_config_version(config_text)
    bump = determine_bump(commits)
    return Plan(
        bump=bump,
        current=current,
        version=next_version(current, bump),
        changelog_empty=unreleased_is_empty(changelog_text),
    )


# --- Git -------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout


def last_tag() -> str | None:
    try:
        return _git("describe", "--tags", "--abbrev=0", "--match", f"{TAG_PREFIX}*").strip()
    except subprocess.CalledProcessError:
        return None


def addon_commits_since(tag: str) -> list[Commit]:
    """Commits seit dem Tag, die etwas unter skytech_omniai/ geändert haben."""
    # \x1f trennt Betreff und Rumpf, \x1e die Commits — beides kommt in
    # Commit-Messages nicht vor.
    raw = _git("log", "--format=%s%x1f%b%x1e", f"{tag}..HEAD", "--", f"{ADDON_DIR}/")
    commits = []
    for record in raw.split("\x1e"):
        if not record.strip():
            continue
        subject, _, body = record.strip("\n").partition("\x1f")
        commits.append(Commit(subject=subject, body=body))
    return commits


# --- Befehlszeile ----------------------------------------------------------


def _current_plan() -> Plan:
    tag = last_tag()
    if tag is None:
        raise SystemExit(
            f"Kein Tag '{TAG_PREFIX}*' gefunden. Den aktuellen Stand einmalig taggen, z. B. "
            f'git tag -a v0.9.1 -m "Version 0.9.1" && git push origin v0.9.1'
        )
    return build_plan(
        CONFIG_PATH.read_text(encoding="utf-8"),
        CHANGELOG_PATH.read_text(encoding="utf-8"),
        addon_commits_since(tag),
    )


def _emit(values: dict[str, str]) -> None:
    """Gibt die Werte aus und reicht sie in GitHub Actions an die Folgeschritte."""
    lines = [f"{key}={value}" for key, value in values.items()]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


def _warn_if_changelog_empty(plan: Plan) -> None:
    if plan.bump != BUMP_NONE and plan.changelog_empty:
        # In GitHub Actions wird daraus eine Warnung am Lauf, lokal ist es nur eine Zeile.
        print(
            "::warning file=CHANGELOG.md::Das Add-on hat sich geändert, aber "
            f"'{UNRELEASED_HEADING}' ist leer. Das Release bekommt die Standardzeile.",
            file=sys.stderr,
        )


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("plan", "apply"):
        print("Aufruf: release.py plan|apply", file=sys.stderr)
        return 2

    plan = _current_plan()
    _warn_if_changelog_empty(plan)

    if argv[0] == "apply" and plan.bump != BUMP_NONE:
        config_text = CONFIG_PATH.read_text(encoding="utf-8")
        CONFIG_PATH.write_text(set_config_version(config_text, plan.version), encoding="utf-8")
        changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
        CHANGELOG_PATH.write_text(
            roll_changelog(changelog_text, plan.version, berlin_today()), encoding="utf-8"
        )

    _emit({"bump": plan.bump, "current": plan.current, "version": plan.version})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
