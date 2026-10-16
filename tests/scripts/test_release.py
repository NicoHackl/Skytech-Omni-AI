"""Tests für Versionssprung und Changelog des Release-Skripts."""

from datetime import UTC, date, datetime

import pytest

from release import (
    BUMP_MAJOR,
    BUMP_MINOR,
    BUMP_NONE,
    BUMP_PATCH,
    DEFAULT_CHANGELOG_ENTRY,
    Commit,
    berlin_today,
    build_plan,
    determine_bump,
    format_date,
    next_version,
    read_config_version,
    roll_changelog,
    set_config_version,
    unreleased_is_empty,
)

CONFIG = 'name: "Skytech OmniAI"\nversion: "0.9.1"\nslug: "skytech_omniai"\n'

CHANGELOG = """# Changelog

## [Unveröffentlicht]

### Behoben

- Etwas funktioniert wieder.

## [0.9.1] — 16.10.2026

### Behoben

- Älterer Eintrag.
"""

EMPTY_CHANGELOG = """# Changelog

## [Unveröffentlicht]

## [0.9.1] — 16.10.2026

- Älterer Eintrag.
"""


# --- determine_bump ----------------------------------------------------------


def test_no_commits_mean_no_release():
    """Leerzustand: ohne Änderung am Add-on gibt es kein Release."""
    assert determine_bump([]) == BUMP_NONE


def test_a_fix_bumps_the_patch():
    """Normalfall: eine Fehlerbehebung hebt die Patch-Stelle."""
    assert determine_bump([Commit("fix(api): Zeitzone korrigiert")]) == BUMP_PATCH


def test_a_feature_bumps_the_minor():
    """Eine neue Funktion hebt die Minor-Stelle, auch neben Fehlerbehebungen."""
    commits = [Commit("fix: etwas"), Commit("feat(codex): neuer Anbieter"), Commit("docs: x")]

    assert determine_bump(commits) == BUMP_MINOR


def test_an_exclamation_mark_bumps_the_major():
    """Ein "!" hinter dem Typ kennzeichnet einen Bruch der Schnittstelle."""
    assert determine_bump([Commit("feat(api)!: Feld umbenannt")]) == BUMP_MAJOR


def test_a_breaking_change_footer_bumps_the_major():
    """Auch die Fußzeile "BREAKING CHANGE:" im Rumpf zählt als Bruch."""
    commit = Commit("refactor: Antwortformat", "Rumpf\n\nBREAKING CHANGE: Feld entfällt")

    assert determine_bump([commit]) == BUMP_MAJOR


def test_a_subject_without_convention_still_bumps_the_patch():
    """Fehlerfall: ein Betreff ohne Konvention verhindert das Release nicht."""
    assert determine_bump([Commit("Bump flask from 3.1.2 to 3.1.3")]) == BUMP_PATCH


def test_breaking_change_in_running_text_is_not_a_footer():
    """Nur die Fußzeile zählt, nicht das Wort mitten im Text."""
    commit = Commit("fix: x", "Kein BREAKING CHANGE: hier, nur Erwähnung")

    assert determine_bump([commit]) == BUMP_PATCH


# --- next_version ------------------------------------------------------------


@pytest.mark.parametrize(
    ("bump", "expected"),
    [
        (BUMP_PATCH, "0.9.2"),
        (BUMP_MINOR, "0.10.0"),
        (BUMP_MAJOR, "1.0.0"),
        (BUMP_NONE, "0.9.1"),
    ],
)
def test_next_version_follows_semver(bump, expected):
    """Normalfall: jede Stelle wird nach SemVer erhöht, die niedrigeren zurückgesetzt."""
    assert next_version("0.9.1", bump) == expected


def test_next_version_rejects_a_malformed_version():
    """Fehlerfall: eine Version, die kein MAJOR.MINOR.PATCH ist, bricht ab."""
    with pytest.raises(ValueError):
        next_version("0.9", BUMP_PATCH)


def test_next_version_rejects_an_unknown_bump():
    """Fehlerfall: ein unbekannter Sprung bricht ab, statt still nichts zu tun."""
    with pytest.raises(ValueError):
        next_version("0.9.1", "huge")


# --- config.yaml -------------------------------------------------------------


def test_set_config_version_replaces_only_the_version():
    """Normalfall: nur die Versionszeile ändert sich."""
    result = set_config_version(CONFIG, "0.9.2")

    assert result == CONFIG.replace('"0.9.1"', '"0.9.2"')


def test_config_without_version_is_rejected():
    """Leerzustand: fehlt die Versionszeile, wird nichts geschrieben."""
    with pytest.raises(ValueError):
        set_config_version('name: "x"\n', "1.0.0")


def test_config_with_two_versions_is_rejected():
    """Fehlerfall: zwei Versionszeilen sind mehrdeutig."""
    with pytest.raises(ValueError):
        read_config_version('version: "1.0.0"\nversion: "1.0.1"\n')


# --- CHANGELOG.md ------------------------------------------------------------


def test_roll_changelog_turns_unreleased_into_the_version():
    """Normalfall: der Inhalt wandert unter die neue Version, darüber ein leerer Abschnitt."""
    expected = """# Changelog

## [Unveröffentlicht]

## [0.9.2] — 17.10.2026

### Behoben

- Etwas funktioniert wieder.

## [0.9.1] — 16.10.2026

### Behoben

- Älterer Eintrag.
"""

    assert roll_changelog(CHANGELOG, "0.9.2", date(2026, 10, 17)) == expected


def test_roll_changelog_fills_an_empty_section_with_the_default_entry():
    """Leerzustand: ohne Eintrag bekommt das Release die Standardzeile."""
    result = roll_changelog(EMPTY_CHANGELOG, "0.9.2", date(2026, 10, 17))

    assert f"## [0.9.2] — 17.10.2026\n\n{DEFAULT_CHANGELOG_ENTRY}\n\n## [0.9.1]" in result
    assert unreleased_is_empty(result)


def test_roll_changelog_works_when_no_older_version_exists():
    """Leerzustand: auch das allererste Release findet sein Ende."""
    text = "# Changelog\n\n## [Unveröffentlicht]\n\n- Erster Eintrag.\n"

    result = roll_changelog(text, "0.1.0", date(2026, 1, 2))

    assert result.endswith("## [0.1.0] — 02.01.2026\n\n- Erster Eintrag.\n\n")


def test_changelog_without_unreleased_section_is_rejected():
    """Fehlerfall: ohne Abschnitt "Unveröffentlicht" weiß das Skript nicht wohin."""
    with pytest.raises(ValueError):
        roll_changelog("# Changelog\n\n## [0.9.1] — 16.10.2026\n", "0.9.2", date(2026, 10, 17))


def test_subheadings_do_not_end_the_unreleased_section():
    """Die Kategorien "### …" gehören zum Abschnitt, erst "## " beendet ihn."""
    assert not unreleased_is_empty(CHANGELOG)
    assert unreleased_is_empty(EMPTY_CHANGELOG)


# --- Datum -------------------------------------------------------------------


def test_format_date_uses_the_german_form():
    """Anzeigeform: TT.MM.JJJJ, ohne Uhrzeit und ohne Zone."""
    assert format_date(date(2026, 8, 3)) == "03.08.2026"


def test_berlin_today_in_summer_time():
    """Sommerzeit: 22:30 UTC ist in Berlin schon der nächste Tag."""
    assert berlin_today(datetime(2026, 7, 14, 22, 30, tzinfo=UTC)) == date(2026, 7, 15)


def test_berlin_today_in_winter_time():
    """Winterzeit: um 22:30 UTC ist in Berlin noch derselbe Tag, um 23:30 nicht mehr."""
    assert berlin_today(datetime(2026, 1, 14, 22, 30, tzinfo=UTC)) == date(2026, 1, 14)
    assert berlin_today(datetime(2026, 1, 14, 23, 30, tzinfo=UTC)) == date(2026, 1, 15)


# --- Gesamtplan --------------------------------------------------------------


def test_build_plan_combines_bump_version_and_changelog_state():
    """Normalfall: der Plan nennt Sprung, alte und neue Version und den Changelog-Zustand."""
    plan = build_plan(CONFIG, EMPTY_CHANGELOG, [Commit("feat: neu")])

    assert (plan.bump, plan.current, plan.version, plan.changelog_empty) == (
        BUMP_MINOR,
        "0.9.1",
        "0.10.0",
        True,
    )


def test_build_plan_without_addon_commits_keeps_the_version():
    """Leerzustand: ohne Commits bleibt die Version, wie sie ist."""
    plan = build_plan(CONFIG, CHANGELOG, [])

    assert (plan.bump, plan.version) == (BUMP_NONE, "0.9.1")
