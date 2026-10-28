"""Tests für Versionssprung, Changelog-Trailer und Changelog des Release-Skripts."""

from datetime import UTC, date, datetime

import pytest

from release import (
    BUMP_MAJOR,
    BUMP_MINOR,
    BUMP_NONE,
    BUMP_PATCH,
    CHANGELOG_HEADER,
    Commit,
    Trailer,
    berlin_today,
    build_entries,
    build_plan,
    determine_bump,
    format_date,
    next_version,
    parse_trailers,
    prepend_section,
    read_config_version,
    render_section,
    set_config_version,
)

CONFIG = 'name: "Skytech OmniAI"\nversion: "dev"\nslug: "skytech_omniai"\n'

# Changelog, wie er bis 0.9.2 im Repo-Root stand — mit Abschnitt "Unveröffentlicht".
LEGACY_CHANGELOG = """# Changelog

Alter Kopf mit anderem Text.

## [Unveröffentlicht]

## [0.9.2] — 16.10.2026

### Geändert

- Älterer Eintrag.

## [0.9.1] — 16.10.2026

- Noch älter.
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


def test_next_version_rejects_the_dev_placeholder():
    """Fehlerfall: "dev" ist keine veröffentlichte Version und kein Ausgangspunkt."""
    with pytest.raises(ValueError):
        next_version("dev", BUMP_PATCH)


def test_next_version_rejects_an_unknown_bump():
    """Fehlerfall: ein unbekannter Sprung bricht ab, statt still nichts zu tun."""
    with pytest.raises(ValueError):
        next_version("0.9.1", "huge")


# --- config.yaml -------------------------------------------------------------


def test_set_config_version_replaces_only_the_version():
    """Normalfall: nur die Versionszeile ändert sich."""
    assert set_config_version(CONFIG, "0.9.3") == CONFIG.replace('"dev"', '"0.9.3"')


def test_config_without_version_is_rejected():
    """Leerzustand: fehlt die Versionszeile, wird nichts geschrieben."""
    with pytest.raises(ValueError):
        set_config_version('name: "x"\n', "1.0.0")


def test_config_with_two_versions_is_rejected():
    """Fehlerfall: zwei Versionszeilen sind mehrdeutig."""
    with pytest.raises(ValueError):
        read_config_version('version: "1.0.0"\nversion: "1.0.1"\n')


# --- Trailer -----------------------------------------------------------------


def test_parse_trailers_reads_category_and_text():
    """Normalfall: jede Zeile "Changelog-<Kategorie>:" ist ein Eintrag."""
    body = "Warum.\n\nChangelog-Behoben: Speichern geht wieder.\nChangelog-Geändert: Neuer Text."

    assert parse_trailers(body) == [
        Trailer("Behoben", "Speichern geht wieder."),
        Trailer("Geändert", "Neuer Text."),
    ]


def test_indented_lines_continue_the_previous_trailer():
    """Ein langer Eintrag darf über mehrere eingerückte Zeilen laufen."""
    body = "Changelog-Hinzugefügt: Die Seite zeigt jetzt\n  auch den Anbieter."

    assert parse_trailers(body) == [
        Trailer("Hinzugefügt", "Die Seite zeigt jetzt auch den Anbieter.")
    ]


def test_a_body_without_trailers_yields_nothing():
    """Leerzustand: ein Commit ohne Trailer trägt nichts zum Changelog bei."""
    assert parse_trailers("Nur Begründung.\n\nCo-Authored-By: X <x@example.org>") == []


def test_build_entries_groups_by_category_in_commit_order():
    """Einträge mehrerer Commits landen je Kategorie, älteste zuerst."""
    commits = [
        Commit("fix: a", "Changelog-Behoben: Erstens."),
        Commit("feat: b", "Changelog-Hinzugefügt: Neu.\nChangelog-Behoben: Zweitens."),
    ]

    entries, warnings = build_entries(commits)

    assert entries == {"Behoben": ["Erstens.", "Zweitens."], "Hinzugefügt": ["Neu."]}
    assert warnings == []


def test_an_unknown_category_is_kept_under_changed_with_a_warning():
    """Fehlerfall: ein veröffentlichter Tippfehler verliert den Eintrag nicht."""
    entries, warnings = build_entries([Commit("fix: a", "Changelog-Behobn: Text.")])

    assert entries == {"Geändert": ["Text."]}
    assert len(warnings) == 1


# --- Changelog-Datei ---------------------------------------------------------


def test_render_section_orders_categories_like_keep_a_changelog():
    """Anzeigeform: Version, Datum TT.MM.JJJJ, Kategorien in fester Reihenfolge."""
    section = render_section(
        "0.10.0", date(2026, 10, 17), {"Behoben": ["B."], "Hinzugefügt": ["H."]}
    )

    assert section == (
        "## [0.10.0] — 17.10.2026\n\n### Hinzugefügt\n\n- H.\n\n### Behoben\n\n- B.\n"
    )


def test_render_section_without_entries_uses_the_default_line():
    """Leerzustand: ein Release ohne Trailer bekommt die Standardzeile."""
    section = render_section("0.9.3", date(2026, 10, 17), {})

    assert "### Geändert\n\n- Interne Verbesserungen ohne sichtbare Änderung." in section


def test_prepend_section_replaces_header_and_drops_unreleased():
    """Der Kopf kommt vom Skript, "Unveröffentlicht" entfällt, ältere Versionen bleiben."""
    section = render_section("0.9.3", date(2026, 10, 17), {"Behoben": ["Neu."]})

    result = prepend_section(LEGACY_CHANGELOG, section)

    assert result.startswith(CHANGELOG_HEADER + "\n## [0.9.3] — 17.10.2026")
    assert "Unveröffentlicht" not in result
    assert "Alter Kopf" not in result
    assert result.index("## [0.9.3]") < result.index("## [0.9.2]") < result.index("## [0.9.1]")
    assert result.endswith("- Noch älter.\n")


def test_prepend_section_starts_a_changelog_from_scratch():
    """Leerzustand: ohne bisherigen Changelog entsteht einer mit Kopf und einer Version."""
    section = render_section("1.0.0", date(2026, 1, 2), {"Hinzugefügt": ["Alles."]})

    assert prepend_section(None, section) == f"{CHANGELOG_HEADER}\n{section}"


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


def test_build_plan_takes_the_version_from_the_release_branch():
    """Normalfall: Ausgangspunkt ist die veröffentlichte Version, nicht "dev"."""
    commits = [Commit("feat: neu", "Changelog-Hinzugefügt: Neu.")]

    plan, warnings = build_plan("0.9.2", commits, commits)

    assert (plan.bump, plan.current, plan.version) == (BUMP_MINOR, "0.9.2", "0.10.0")
    assert plan.entries == {"Hinzugefügt": ["Neu."]}
    assert warnings == []


def test_build_plan_counts_trailers_from_commits_outside_the_addon():
    """Ein Eintrag aus einem Commit ohne Add-on-Änderung geht nicht verloren."""
    addon = [Commit("fix: code")]
    everything = [*addon, Commit("docs: x", "Changelog-Geändert: Anleitung ergänzt.")]

    plan, _ = build_plan("0.9.2", addon, everything)

    assert plan.entries == {"Geändert": ["Anleitung ergänzt."]}


def test_build_plan_warns_when_a_release_has_no_entries():
    """Leerzustand: Release ohne Trailer läuft, aber mit Warnung."""
    plan, warnings = build_plan("0.9.2", [Commit("fix: x")], [Commit("fix: x")])

    assert plan.bump == BUMP_PATCH
    assert len(warnings) == 1


def test_build_plan_without_addon_commits_keeps_the_version():
    """Leerzustand: ohne Add-on-Commits bleibt die Version, wie sie ist."""
    plan, warnings = build_plan("0.9.2", [], [Commit("docs: x")])

    assert (plan.bump, plan.version) == (BUMP_NONE, "0.9.2")
    assert warnings == []


def test_release_base_ref_is_overridable(monkeypatch):
    """Der Release-Job setzt den Bezugsstand auf den ersten Elternteil des Merge-Commits."""
    import importlib

    import release

    monkeypatch.setenv("RELEASE_BASE_REF", "abc1234")
    try:
        assert importlib.reload(release).RELEASE_BRANCH == "abc1234"
    finally:
        monkeypatch.delenv("RELEASE_BASE_REF")
        importlib.reload(release)
