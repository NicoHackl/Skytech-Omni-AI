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
    "OMNIAI_API_TOKEN",
    "SUPERVISOR_TOKEN",
    "SUPERVISOR_URL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    # Die Google-CLI legt Anmeldung und Zustand unter einem Heimatverzeichnis ab
    # (im Container /data). Kein Test darf an das echte heran.
    monkeypatch.setenv("OMNIAI_GEMINI_HOME", str(tmp_path / "gemini-home"))
