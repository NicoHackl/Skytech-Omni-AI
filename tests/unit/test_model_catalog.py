"""Modellkatalog, „-latest“ und Denkaufwand je Anbieter (Vertrag 1.4.0)."""

import pytest

import model_catalog
from model_catalog import UnsupportedEffort
from providers.gemini_agy_provider import ModelInfo

CODEX_LIST = {
    "data": [
        {
            "id": "gpt-5.6-sol",
            "model": "gpt-5.6-sol",
            "isDefault": True,
            "hidden": False,
            "defaultReasoningEffort": "low",
            "supportedReasoningEfforts": [
                {"reasoningEffort": e} for e in ("low", "medium", "high", "ultra")
            ],
        },
        {
            "id": "gpt-6.1-sol",
            "model": "gpt-6.1-sol",
            "isDefault": False,
            "hidden": False,
            "supportedReasoningEfforts": [
                {"reasoningEffort": "medium"},
                {"reasoningEffort": "high"},
            ],
        },
        {
            "id": "gpt-5.6-luna",
            "model": "gpt-5.6-luna",
            "isDefault": False,
            "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
        },
        {"id": "gpt-reserve", "model": "gpt-reserve", "hidden": True},
    ]
}


@pytest.fixture(autouse=True)
def fresh_codex(monkeypatch):
    model_catalog._codex_cache.update(at=0.0, models=None)
    monkeypatch.setattr(
        model_catalog, "_codex_rpc_models", lambda: model_catalog.parse_codex_models(CODEX_LIST)
    )
    yield
    model_catalog._codex_cache.update(at=0.0, models=None)


def test_claude_latest_resolves_to_cli_alias_and_checks_effort():
    resolution = model_catalog.resolve("claude_sub", "opus-latest", "XHIGH")
    assert (resolution.model, resolution.effort) == ("opus", "xhigh")
    assert model_catalog.resolve("claude_sub", "claude-opus-5-5", None).model == "claude-opus-5-5"
    with pytest.raises(UnsupportedEffort):
        model_catalog.resolve("claude_sub", "opus-latest", "ultra")


def test_claude_catalog_shows_last_seen_model():
    model_catalog.remember_claude_model("claude-haiku-5-5")
    entries = {e["id"]: e for e in model_catalog.catalog("claude_sub")}
    assert entries["haiku-latest"]["resolvesTo"] == "claude-haiku-5-5"
    assert entries["sonnet-latest"]["recommended"] is True


def test_codex_latest_names_and_efforts_per_model():
    entries = {e["id"]: e for e in model_catalog.catalog("codex_sub")}
    assert entries["latest"]["resolvesTo"] == "gpt-5.6-sol"
    assert entries["sol-latest"]["resolvesTo"] == "gpt-6.1-sol"
    assert entries["luna-latest"]["resolvesTo"] == "gpt-5.6-luna"
    assert "gpt-reserve" not in entries
    assert entries["gpt-5.6-sol"]["efforts"] == ["low", "medium", "high", "ultra"]
    assert entries["gpt-5.6-sol"]["defaultEffort"] == "low"

    assert model_catalog.resolve("codex_sub", "sol-latest", "high").model == "gpt-6.1-sol"
    with pytest.raises(UnsupportedEffort, match="medium, high"):
        model_catalog.resolve("codex_sub", "sol-latest", "low")
    # Unbekannte gpt-Modelle: die übliche Stufenliste
    assert model_catalog.resolve("codex_sub", "gpt-9-nova", "max").effort == "max"


def test_codex_without_app_server_uses_known_list(monkeypatch):
    monkeypatch.setattr(model_catalog, "_codex_rpc_models", lambda: None)
    models = model_catalog.codex_models(now=1.0)
    assert models[0].default and models[0].efforts == model_catalog.CODEX_FALLBACK_EFFORTS


def test_gemini_efforts_and_thinking_config():
    assert model_catalog.resolve("gemini", "gemini-pro-latest", "high").effort == "high"
    with pytest.raises(UnsupportedEffort):
        model_catalog.resolve("gemini", "gemini-pro-latest", "medium")
    assert model_catalog.gemini_thinking("gemini-3.6-flash", "low") == {"thinking_level": "low"}
    assert model_catalog.gemini_thinking("gemini-2.5-flash", "medium") == {"thinking_budget": 8192}
    assert model_catalog.gemini_thinking("gemini-3.6-flash", None) == {}
    # Ohne Modell gilt die Vorgabe (Flash): medium erlaubt
    assert model_catalog.resolve("gemini", None, "medium").effort == "medium"


def test_agy_families_latest_and_effort_in_label(monkeypatch):
    models = [
        ModelInfo(label)
        for label in (
            "Gemini 3.8 Flash (Low)",
            "Gemini 3.8 Flash (Medium)",
            "Gemini 3.8 Flash (High)",
            "Gemini 3.5 Flash (Medium)",
            "Gemini 4 Argon (Medium)",
            "Gemini 4 Argon (Max)",
        )
    ]
    monkeypatch.setattr(model_catalog, "_agy_models", lambda: models)
    entries = {e["id"]: e for e in model_catalog.catalog("gemini_agy")}
    assert entries["flash-latest"]["resolvesTo"] == "Gemini 3.8 Flash"
    assert entries["flash-latest"]["efforts"] == ["low", "medium", "high"]
    assert entries["argon-latest"]["efforts"] == ["medium", "max"]
    resolution = model_catalog.resolve("gemini_agy", "flash-latest", "high")
    assert (resolution.model, resolution.effort, resolution.requested_effort) == (
        "Gemini 3.8 Flash high",
        None,
        "high",
    )
    with pytest.raises(UnsupportedEffort):
        model_catalog.resolve("gemini_agy", "argon-latest", "low")
    assert model_catalog.resolve("gemini_agy", "flash-latest", None).model == "Gemini 3.8 Flash"


def test_agy_without_model_list_rejects_effort(monkeypatch):
    monkeypatch.setattr(model_catalog, "_agy_models", lambda: [])
    with pytest.raises(UnsupportedEffort):
        model_catalog.resolve("gemini_agy", "flash-latest", "high")


def test_web_has_no_effort(monkeypatch):
    monkeypatch.setattr(
        model_catalog, "_web_catalog", lambda: [model_catalog.Entry(id="gemini-pro")]
    )
    assert model_catalog.resolve("gemini_web", "gemini-pro", None).model == "gemini-pro"
    with pytest.raises(UnsupportedEffort):
        model_catalog.resolve("gemini_web", "gemini-pro", "high")


def test_broken_catalog_is_empty_not_an_error(monkeypatch):
    def boom():
        raise RuntimeError("kaputt")

    monkeypatch.setitem(model_catalog._CATALOGS, "gemini", boom)
    assert model_catalog.catalog("gemini") == []
    assert model_catalog.catalog("unbekannt") == []
