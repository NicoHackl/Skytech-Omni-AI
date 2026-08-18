"""Tests für die Auswahl des Providers."""

import pytest

from providers.claude_sub_provider import ClaudeSubProvider
from providers.factory import ProviderFactory
from providers.gemini_provider import GeminiProvider


def test_defaults_to_the_subscription_provider():
    """Ohne Angabe bleibt es bei Claude — bestehende Installationen ändern sich nicht."""
    assert isinstance(ProviderFactory.create(), ClaudeSubProvider)


def test_creates_the_requested_provider():
    """Normalfall: der Name aus der Anfrage entscheidet."""
    assert isinstance(ProviderFactory.create("gemini"), GeminiProvider)


def test_reads_the_configured_provider(monkeypatch):
    """Ohne Angabe in der Anfrage gilt die Add-on-Konfiguration."""
    monkeypatch.setenv("AI_PROVIDER", "gemini")

    assert isinstance(ProviderFactory.create(), GeminiProvider)


def test_rejects_an_unknown_provider():
    """Fehlerfall: ein unbekannter Name führt zu einer verständlichen Meldung."""
    with pytest.raises(ValueError) as fehler:
        ProviderFactory.create("openai")

    text = str(fehler.value)
    assert "Claude (Abo)" in text
    assert "Google Gemini" in text
    # Kein Klassenname und keine Python-Schreibweise im sichtbaren Text.
    assert "Provider" not in text
    assert "[" not in text
