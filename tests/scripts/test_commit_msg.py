"""Tests für die Prüfung der Commit-Messages (commit-msg-Hook)."""

import pytest

from commit_msg import check_message, main


def test_a_conventional_message_with_trailer_passes():
    """Normalfall: Betreff nach Konvention, Leerzeile, Rumpf mit Trailer."""
    message = (
        "fix(einstellungen): Speichern reparieren\n\nWarum.\n\nChangelog-Behoben: Geht wieder.\n"
    )

    assert check_message(message) == []


def test_scopes_with_underscore_are_allowed():
    """Bereiche wie "claude_sub" sind Modulnamen und damit zulässig."""
    assert check_message("fix(claude_sub): Web-Recherche freigeben") == []


def test_a_breaking_change_marker_is_allowed():
    """Das "!" für einen Bruch gehört zur Konvention."""
    assert check_message("feat(api)!: Feld umbenennen") == []


@pytest.mark.parametrize(
    "subject",
    ["Merge branch 'x'", 'Revert "fix: a"', "fixup! fix: a", "squash! feat: b"],
)
def test_messages_generated_by_git_pass(subject):
    """Von Git erzeugte Betreffzeilen folgen keiner Konvention und bleiben erlaubt."""
    assert check_message(subject) == []


def test_a_subject_without_type_is_rejected():
    """Fehlerfall: ohne Typ lässt sich keine Version ableiten."""
    assert len(check_message("Einstellungen repariert")) == 1


def test_an_unknown_type_is_rejected():
    """Fehlerfall: ein Typ außerhalb der Liste ist meist ein Tippfehler."""
    assert check_message("feature: neu") != []


def test_a_too_long_subject_is_rejected():
    """Fehlerfall: mehr als 72 Zeichen im Betreff."""
    assert check_message("fix: " + "x" * 70) != []


def test_a_missing_blank_line_is_rejected():
    """Fehlerfall: ohne Leerzeile verschmilzt Git Betreff und Rumpf."""
    assert check_message("fix: a\nRumpf direkt dahinter") != []


def test_an_unknown_changelog_category_is_rejected():
    """Fehlerfall: Tippfehler in der Kategorie — nach dem Push nicht mehr zu retten."""
    problems = check_message("fix: a\n\nChangelog-Behobn: Text.")

    assert len(problems) == 1
    assert "Changelog-Behoben" in problems[0]


def test_a_changelog_trailer_without_text_is_rejected():
    """Fehlerfall: ein leerer Eintrag ergäbe eine leere Zeile im Changelog."""
    assert check_message("fix: a\n\nChangelog-Behoben:") != []


def test_comment_lines_from_the_editor_are_ignored():
    """Die "#"-Zeilen der Vorlage entfernt Git selbst; sie zählen nicht."""
    assert check_message("# Kommentar\nfix: a\n\n# noch einer\n") == []


def test_an_empty_message_is_rejected():
    """Leerzustand: eine leere Message lehnt der Hook ab."""
    assert check_message("\n# nur Kommentar\n") != []


def test_main_returns_an_error_code_for_a_bad_message(tmp_path, capsys):
    """Der Hook bricht den Commit über den Rückgabewert ab und nennt den Grund."""
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("kaputt", encoding="utf-8")

    assert main([str(message_file)]) == 1
    assert "Betreff" in capsys.readouterr().err
