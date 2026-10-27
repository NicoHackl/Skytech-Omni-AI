"""Tests der Fachlogik hinter der Seite „Einstellungen“."""

import json

from settings import merge_update, public_view, revision

STORED = {
    "provider": "claude_sub",
    "model": "auto",
    "tool_access": "web",
    "claude_oauth_token": "geheim-claude",
    "anthropic_api_key": "",
    "codex_auth_json": "",
    "openai_api_key": "",
    "gemini_api_key": "geheim-gemini",
}


def test_public_view_never_contains_a_credential():
    """Zugänge kommen nur als ja/nein zurück — der Wert taucht nirgends auf."""
    view = public_view(STORED)

    assert view["options"]["claude_oauth_token"] == ""
    assert view["secrets_set"]["claude_oauth_token"] is True
    assert view["secrets_set"]["openai_api_key"] is False
    assert "geheim" not in json.dumps(view)


def test_public_view_fills_defaults_for_empty_options():
    """Leerzustand: außerhalb von Home Assistant zeigt die Seite, was tatsächlich gilt."""
    view = public_view({})

    assert view["options"]["provider"] == "claude_sub"
    assert view["options"]["model"] == "auto"
    assert view["options"]["tool_access"] == "web"


def test_revision_changes_with_the_stored_state():
    """Der Fingerabdruck verrät eine Änderung von anderer Stelle."""
    assert revision(STORED) == revision(dict(STORED))
    assert revision(STORED) != revision({**STORED, "tool_access": "off"})


def test_merge_keeps_a_credential_left_empty():
    """Ein leeres Feld heißt „unverändert“, nicht „löschen“."""
    merged, errors = merge_update(STORED, {"claude_oauth_token": "", "provider": "gemini"})

    assert errors == {}
    assert merged["claude_oauth_token"] == "geheim-claude"
    assert merged["provider"] == "gemini"


def test_merge_removes_a_credential_on_null():
    """``None`` ist der ausdrückliche Wunsch, den Zugang zu entfernen."""
    merged, errors = merge_update(STORED, {"gemini_api_key": None})

    assert errors == {}
    assert merged["gemini_api_key"] == ""


def test_merge_replaces_a_credential_and_keeps_unknown_options():
    """Ein neuer Wert ersetzt den alten; fremde Optionen bleiben erhalten."""
    merged, errors = merge_update(
        {**STORED, "zukunft": 1}, {"openai_api_key": " neu ", "unbekannt": "x"}
    )

    assert errors == {}
    assert merged["openai_api_key"] == "neu"
    assert merged["zukunft"] == 1
    assert "unbekannt" not in merged


def test_merge_rejects_unknown_values():
    """Fehlerfall: jedes unbrauchbare Feld bekommt einen eigenen Satz."""
    _, errors = merge_update(
        STORED,
        {"provider": "ollama", "tool_access": "alles", "codex_auth_json": "kein json"},
    )

    assert set(errors) == {"provider", "tool_access", "codex_auth_json"}


def test_merge_rejects_a_model_of_another_provider():
    """Ein Claude-Modell passt nicht zu Gemini."""
    _, errors = merge_update(STORED, {"provider": "gemini", "model": "opus"})

    assert set(errors) == {"model"}


def test_merge_accepts_a_matching_model_and_valid_chatgpt_access():
    """Normalfall: Modell des Anbieters und eine eingefügte auth.json."""
    merged, errors = merge_update(
        STORED,
        {"provider": "codex_sub", "model": "gpt-5.6-luna", "codex_auth_json": '{"tokens": {}}'},
    )

    assert errors == {}
    assert merged["model"] == "gpt-5.6-luna"
    assert merged["codex_auth_json"] == '{"tokens": {}}'


def test_short_api_token_is_rejected():
    """Ein neu eingetragenes Token für Skytech X braucht mindestens 32 Zeichen."""
    _, errors = merge_update(STORED, {"api_token": "zu-kurz"})
    merged, ok = merge_update(STORED, {"api_token": "x" * 32})

    assert errors["api_token"] == "Das Token braucht mindestens 32 Zeichen."
    assert ok == {}
    assert merged["api_token"] == "x" * 32
