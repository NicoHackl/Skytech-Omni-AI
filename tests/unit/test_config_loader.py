"""Tests für das Einlesen der Add-on-Optionen."""

import json
import os

import pytest

import config_loader
from config_loader import apply_options_to_env, load_options, read_addon_version


def test_load_options_reads_the_file(tmp_path, monkeypatch):
    """Normalfall: die Optionen kommen so zurück, wie sie in der Datei stehen."""
    options_file = tmp_path / "options.json"
    options_file.write_text(json.dumps({"provider": "gemini"}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "OPTIONS_PATH", str(options_file))

    assert load_options() == {"provider": "gemini"}


def test_load_options_without_file_returns_empty(monkeypatch):
    """Leerzustand: ohne Home Assistant fehlt die Datei — das ist kein Fehler."""
    monkeypatch.setattr(config_loader, "OPTIONS_PATH", "/nicht/vorhanden/options.json")

    assert load_options() == {}


def test_load_options_raises_on_broken_json(tmp_path, monkeypatch):
    """Fehlerfall: eine kaputte Datei wird nicht stillschweigend übergangen."""
    options_file = tmp_path / "options.json"
    options_file.write_text("{kein json", encoding="utf-8")
    monkeypatch.setattr(config_loader, "OPTIONS_PATH", str(options_file))

    with pytest.raises(RuntimeError):
        load_options()


def test_apply_options_maps_every_value():
    """Jede Option landet unter dem Namen, den Provider und CLI erwarten."""
    apply_options_to_env(
        {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "tool_access": "full",
            "claude_oauth_token": "token",
            "anthropic_api_key": "anthropic",
            "codex_auth_json": '{"tokens": {}}',
            "openai_api_key": "openai",
            "gemini_api_key": "google",
        }
    )

    assert os.environ["AI_PROVIDER"] == "gemini"
    assert os.environ["OMNIAI_MODEL"] == "gemini-2.5-pro"
    assert os.environ["OMNIAI_TOOL_ACCESS"] == "full"
    assert os.environ["CLAUDE_CODE_OAUTH_TOKEN"] == "token"
    assert os.environ["ANTHROPIC_API_KEY"] == "anthropic"
    assert os.environ["CODEX_AUTH_JSON"] == '{"tokens": {}}'
    assert os.environ["OPENAI_API_KEY"] == "openai"
    assert os.environ["GEMINI_API_KEY"] == "google"


def test_apply_options_treats_auto_like_an_empty_field():
    """„auto“ ist der Sentinel des Auswahlfelds und erzwingt kein Modell."""
    apply_options_to_env({"model": "auto"})

    assert "OMNIAI_MODEL" not in os.environ


def test_apply_options_ignores_empty_values():
    """Leerzustand: leere Felder setzen nichts, statt Leerstrings zu hinterlassen."""
    apply_options_to_env({"provider": "  ", "tool_access": "", "claude_oauth_token": ""})

    assert "AI_PROVIDER" not in os.environ
    assert "OMNIAI_TOOL_ACCESS" not in os.environ
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in os.environ


def test_read_addon_version_reads_config_yaml():
    """Die Version kommt aus config.yaml und wird nicht im Code gedoppelt."""
    version = read_addon_version()

    assert version is not None
    assert version[0].isdigit()


def test_read_addon_version_returns_none_without_file(tmp_path, monkeypatch):
    """Fehlt die Datei, wird keine Nummer erfunden."""
    monkeypatch.setattr(config_loader, "CONFIG_PATH", tmp_path / "fehlt.yaml")

    assert read_addon_version() is None
