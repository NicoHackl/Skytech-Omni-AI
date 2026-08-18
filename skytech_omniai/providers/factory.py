"""Wählt anhand des Namens die passende Provider-Umsetzung aus.

Neue Anbieter werden hier eingetragen; ``app.py`` bleibt davon unberührt.
"""

import logging
import os

from providers.base_provider import BaseProvider
from providers.claude_sub_provider import ClaudeSubProvider
from providers.gemini_provider import GeminiProvider

log = logging.getLogger("omniai.factory")

DEFAULT_PROVIDER = "claude_sub"

_PROVIDERS = {
    "claude_sub": ClaudeSubProvider,
    "gemini": GeminiProvider,
}

# Klarnamen für Meldungen. Das Publikum ist der Betreiber: er trägt den
# technischen Namen in die Konfiguration ein, deshalb steht er mit dabei.
_ANZEIGENAMEN = {
    "claude_sub": "Claude (Abo)",
    "gemini": "Google Gemini",
}


class ProviderFactory:
    """Erzeugt den konfigurierten Provider.

    Ohne Angabe gilt der Wert aus der Add-on-Konfiguration, ersatzweise Claude
    über das Abo — so bleibt eine bestehende Installation unverändert.
    """

    @staticmethod
    def create(name: str | None = None) -> BaseProvider:
        """Liefert eine Instanz des gewünschten Providers.

        :raises ValueError: wenn kein Provider unter diesem Namen bekannt ist.
        """
        provider_name = name or os.environ.get("AI_PROVIDER", DEFAULT_PROVIDER)
        provider_cls = _PROVIDERS.get(provider_name)
        if provider_cls is None:
            log.warning("Unbekannter Provider angefragt: %r", provider_name)
            auswahl = ", ".join(
                f"{_ANZEIGENAMEN[schluessel]} als „{schluessel}“" for schluessel in _PROVIDERS
            )
            raise ValueError(
                f"Der Anbieter „{provider_name}“ ist nicht verfügbar. "
                f"Zur Auswahl stehen: {auswahl}."
            )
        return provider_cls()
