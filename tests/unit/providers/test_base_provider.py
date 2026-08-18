"""Tests für die Auswertung der Modellantwort."""

import pytest

from providers.base_provider import BaseProvider


def test_parses_plain_json():
    """Normalfall: das Modell hält sich an die Anweisung."""
    assert BaseProvider.parse_json('{"status": "ok"}') == {"status": "ok"}


def test_unwraps_markdown_fence():
    """Der häufigste Verstoß: JSON in einem Codeblock."""
    roh = '```json\n{"status": "ok"}\n```'

    assert BaseProvider.parse_json(roh) == {"status": "ok"}


def test_finds_json_inside_prose():
    """Zweithäufigster Verstoß: JSON zwischen erklärenden Sätzen."""
    roh = 'Gerne! Hier ist das Ergebnis:\n{"status": "ok"}\nViel Erfolg.'

    assert BaseProvider.parse_json(roh) == {"status": "ok"}


def test_parses_json_array():
    """Auch eine Liste ist eine gültige Antwort."""
    assert BaseProvider.parse_json("[1, 2, 3]") == [1, 2, 3]


@pytest.mark.parametrize("roh", ["", "   ", "Ich kann das leider nicht."])
def test_raises_on_unusable_output(roh):
    """Fehler- und Leerzustand: ohne JSON gibt es einen definierten Fehler."""
    with pytest.raises(ValueError):
        BaseProvider.parse_json(roh)


def test_error_message_stays_free_of_raw_output():
    """Eiserne Regel 12: die Rohausgabe gehört ins Log, nicht in die Meldung."""
    roh = "Fehler in /usr/lib/python/foo.py, Zeile 12"

    with pytest.raises(ValueError) as fehler:
        BaseProvider.parse_json(roh)

    assert roh not in str(fehler.value)
    assert "/usr/lib" not in str(fehler.value)
