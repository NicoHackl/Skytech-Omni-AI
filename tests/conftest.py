"""Gemeinsame Vorbereitung für alle Tests.

Die Provider lesen ihre Zugangsdaten aus der Umgebung. Damit ein Test nicht
davon abhängt, was auf dem Rechner des Entwicklers gesetzt ist, wird die
Umgebung vor jedem Test von allen bekannten Werten befreit.
"""

import pytest

ENV_KEYS = [
    "AI_PROVIDER",
    "OMNIAI_MODEL",
    "OMNIAI_TOOL_ACCESS",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "ANTHROPIC_API_KEY",
    "CODEX_AUTH_JSON",
    "OPENAI_API_KEY",
    "CODEX_HOME",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
