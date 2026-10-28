"""Prüft eine Commit-Message gegen die Regeln aus docs/git-workflow.md.

Der Typ im Betreff bestimmt die Version, die Trailer "Changelog-<Kategorie>:"
den Changelog (scripts/release.py). Ein Fehler darin lässt sich nach dem Push
nicht mehr korrigieren — dev/dev verbietet das Umschreiben der Historie.
Deshalb wird hier geprüft, solange der Commit noch lokal ist:

    python3 scripts/commit_msg.py <datei>          # als commit-msg-Hook
    python3 scripts/commit_msg.py --range A..B     # alle Commits eines Bereichs (CI)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from release import CATEGORIES, TRAILER_PREFIX, parse_trailers

TYPES = ("feat", "fix", "docs", "refactor", "test", "chore", "perf", "build", "ci")
MAX_SUBJECT = 72

_SUBJECT = re.compile(rf"^(?:{'|'.join(TYPES)})(?:\([A-Za-z0-9._/-]+\))?!?: \S")
# Von Git selbst erzeugte Betreffzeilen folgen keiner Konvention und sind erlaubt.
_GENERATED = re.compile(r"^(?:Merge |Revert \"|fixup! |squash! |amend! )")


def check_message(message: str) -> list[str]:
    """Liefert die Verstöße einer Commit-Message; leer heißt: in Ordnung."""
    lines = [line for line in message.splitlines() if not line.startswith("#")]
    while lines and not lines[0].strip():
        lines.pop(0)
    if not lines:
        return ["Die Commit-Message ist leer."]

    subject, body = lines[0], "\n".join(lines[1:])
    if _GENERATED.match(subject):
        return []

    problems = []
    if not _SUBJECT.match(subject):
        problems.append(
            f"Betreff folgt nicht '<typ>(<bereich>): <text>' — erlaubte Typen: {', '.join(TYPES)}."
        )
    if len(subject) > MAX_SUBJECT:
        problems.append(f"Betreff hat {len(subject)} Zeichen, erlaubt sind {MAX_SUBJECT}.")
    if len(lines) > 1 and lines[1].strip():
        problems.append("Zwischen Betreff und Rumpf gehört eine Leerzeile.")
    for trailer in parse_trailers(body):
        if trailer.category not in CATEGORIES:
            problems.append(
                f"Unbekannte Kategorie '{TRAILER_PREFIX}{trailer.category}' — erlaubt: "
                + ", ".join(f"{TRAILER_PREFIX}{name}" for name in CATEGORIES)
                + "."
            )
        elif not trailer.text:
            problems.append(f"'{TRAILER_PREFIX}{trailer.category}:' ohne Text.")
    return problems


def _messages_in_range(revision_range: str) -> list[tuple[str, str]]:
    raw = subprocess.run(
        ["git", "log", "--format=%h%x1f%B%x1e", revision_range],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    result = []
    for record in raw.split("\x1e"):
        if record.strip():
            short, _, message = record.strip("\n").partition("\x1f")
            result.append((short, message))
    return result


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--range":
        # In der CI nur Warnungen: ein veröffentlichter Commit lässt sich nicht
        # mehr ändern, ein Abbruch würde den Branch blockieren.
        for short, message in _messages_in_range(argv[1]):
            for problem in check_message(message):
                print(f"::warning::Commit {short}: {problem}")
        return 0
    if len(argv) != 1:
        print("Aufruf: commit_msg.py <datei> | --range A..B", file=sys.stderr)
        return 2

    problems = check_message(Path(argv[0]).read_text(encoding="utf-8"))
    if problems:
        print("Commit abgelehnt:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        print("Regeln: docs/git-workflow.md", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
