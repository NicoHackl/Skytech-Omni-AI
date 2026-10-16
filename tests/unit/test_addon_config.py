"""Konsistenz der Add-on-Dateien untereinander und mit dem Code.

config.yaml, build.yaml und Dockerfile werden von Hand gepflegt,
und jede davon wiederholt etwas, das auch im Python-Code steht. Läuft eine
Stelle auseinander, merkt das kein Unit-Test der Module — erst der Nutzer, wenn
Home Assistant eine Option ablehnt oder der Container ohne ein Modul startet.
"""

import re
from pathlib import Path

import pytest
import yaml

from config_loader import MODEL_AUTO, OPTION_ENV_MAP, SECRET_OPTIONS
from providers.base_provider import TOOL_ACCESS_LEVELS
from providers.claude_sub_provider import CLAUDE_MODELS
from providers.codex_sub_provider import CODEX_MODELS
from providers.factory import _PROVIDERS
from providers.gemini_provider import GEMINI_MODELS

ROOT = Path(__file__).resolve().parents[2]
ADDON_DIR = ROOT / "skytech_omniai"

_LIST_SCHEMA = re.compile(r"^list\((?P<values>[^)]*)\)$")


@pytest.fixture(scope="module")
def config():
    return yaml.safe_load((ADDON_DIR / "config.yaml").read_text(encoding="utf-8"))


def _list_values(schema_entry: str) -> list[str]:
    match = _LIST_SCHEMA.match(schema_entry)
    assert match, f"'{schema_entry}' ist keine Auswahlliste"
    return match.group("values").split("|")


def test_every_option_has_a_schema_and_vice_versa(config):
    """Eine Option ohne Schema (oder umgekehrt) lehnt der Supervisor ab."""
    assert set(config["options"]) == set(config["schema"])


def test_the_code_reads_exactly_the_configured_options(config):
    """Jede Option kommt im Code an, und der Code erwartet keine, die es nicht gibt."""
    assert set(config["options"]) == set(OPTION_ENV_MAP)


def test_secrets_are_password_fields(config):
    """Zugänge erscheinen im Reiter „Konfiguration“ verdeckt, alles andere nicht."""
    password_fields = {
        key for key, entry in config["schema"].items() if str(entry).startswith("password")
    }

    assert password_fields == set(SECRET_OPTIONS)


def test_every_default_is_allowed_by_its_schema(config):
    """Ein Standardwert außerhalb der Auswahlliste verhindert schon die Installation."""
    for key, entry in config["schema"].items():
        if str(entry).startswith("list("):
            assert config["options"][key] in _list_values(entry), key


def test_provider_list_matches_the_factory(config):
    """Jeder wählbare Anbieter existiert, und jeder vorhandene ist wählbar."""
    assert set(_list_values(config["schema"]["provider"])) == set(_PROVIDERS)


def test_model_list_matches_the_providers(config):
    """Die Auswahlliste der Modelle entspricht den Listen der Anbieter plus „auto“."""
    expected = {MODEL_AUTO, *CLAUDE_MODELS, *CODEX_MODELS, *GEMINI_MODELS}

    assert set(_list_values(config["schema"]["model"])) == expected


def test_tool_access_list_matches_the_levels(config):
    """Die Werkzeugstufen der Konfiguration sind genau die, die der Code kennt."""
    assert set(_list_values(config["schema"]["tool_access"])) == set(TOOL_ACCESS_LEVELS)


def test_build_yaml_covers_exactly_the_supported_architectures(config):
    """Für jede Architektur des Add-ons gibt es ein Basisimage, und kein überzähliges."""
    build = yaml.safe_load((ADDON_DIR / "build.yaml").read_text(encoding="utf-8"))

    assert set(build["build_from"]) == set(config["arch"])


def test_version_is_the_dev_placeholder(config):
    """Auf agent/main steht "dev" — die Version setzt nur der Release-Job (D-017)."""
    assert config["version"] == "dev"


def test_no_changelog_on_the_working_branch():
    """Der Changelog entsteht beim Release aus den Trailern, nicht als Datei hier."""
    assert not (ROOT / "CHANGELOG.md").exists()
    assert not (ADDON_DIR / "CHANGELOG.md").exists()


def test_dockerfile_copies_every_python_module():
    """Ein Modul, das nicht ins Bild kopiert wird, fehlt erst beim Start im Container."""
    dockerfile = (ADDON_DIR / "Dockerfile").read_text(encoding="utf-8")
    copied = set(re.findall(r"^COPY (\S+) ", dockerfile, re.M))
    modules = {path.name for path in ADDON_DIR.glob("*.py")}
    packages = {path.parent.name for path in ADDON_DIR.glob("*/__init__.py")}

    assert modules | packages <= copied
