"""Modellkatalog und Denkaufwand je Anbieter (Vertrag 1.4.0, D-036).

Skytech X wählt Anbieter → Modell → Denkaufwand einheitlich. Dieses Modul
weiß je Anbieter, welche Modelle es gibt, welche Stufen sie annehmen und
welche „-latest“-Namen auf welches Modell zeigen. „-latest“ wird bei jedem
Aufruf neu aufgelöst — ein neues Modell ist ohne Änderung an Code oder
Konfiguration sofort aktiv.

* **Claude** — die CLI kennt Kurznamen, die immer das neueste Modell meinen
  (``opus`` …); ``opus-latest`` geht als ``opus`` an die CLI. Stufen über
  ``--effort``.
* **Codex** — Modelle und Stufen je Modell liefert der App-Server
  (``model/list``) ohne Modellaufruf; ``latest`` = Empfehlung, ``sol-latest``
  usw. = höchste Version der Familie.
* **Gemini (API)** — Google-Kurznamen ``gemini-flash-latest`` und
  ``gemini-pro-latest``; Stufen über ``thinking_level`` (2.5: Budget).
* **Gemini (AGY)** — die Stufe steckt im Modellnamen der CLI („(Medium)“);
  sie wird in die Bezeichnung für ``--model`` übersetzt.
* **Gemini (Web)** — keine einstellbare Stufe.
"""

import logging
import re
import threading
import time
from dataclasses import dataclass, field

log = logging.getLogger("omniai.models")

EFFORTS = ("minimal", "low", "medium", "high", "xhigh", "max", "ultra")

FEHLER_STUFE = "Diese Denkstufe bietet das gewählte Modell nicht an. Möglich sind: {choices}."
FEHLER_KEINE_STUFE = "Für dieses Modell lässt sich der Denkaufwand nicht einstellen."
FEHLER_STUFE_UNBEKANNT = (
    "Die Denkstufen dieses Modells sind noch nicht bekannt. Bitte ohne Stufe anfragen."
)


class UnsupportedEffort(ValueError):
    """Die Stufe gibt es für dieses Modell nicht (Vertrag: ``UNSUPPORTED_EFFORT``)."""


@dataclass(frozen=True)
class Entry:
    """Ein wählbares Modell, wie es unter ``modelCatalog`` erscheint."""

    id: str
    label: str | None = None
    family: str | None = None
    latest: bool = False
    resolves_to: str | None = None
    recommended: bool = False
    efforts: tuple[str, ...] = ()
    default_effort: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "family": self.family,
            "latest": self.latest,
            "resolvesTo": self.resolves_to,
            "recommended": self.recommended,
            "efforts": list(self.efforts),
            "defaultEffort": self.default_effort,
        }


@dataclass(frozen=True)
class Resolution:
    """Was tatsächlich an den Anbieter geht: Modell und ggf. Stufe."""

    model: str | None
    effort: str | None = None
    requested_effort: str | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


def _ordered(efforts) -> tuple[str, ...]:
    wanted = {str(e).lower() for e in efforts if e}
    return tuple(e for e in EFFORTS if e in wanted)


def _check_effort(effort: str | None, efforts: tuple[str, ...]) -> None:
    if effort is None:
        return
    if not efforts:
        raise UnsupportedEffort(FEHLER_KEINE_STUFE)
    if effort not in efforts:
        raise UnsupportedEffort(FEHLER_STUFE.format(choices=", ".join(efforts)))


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


# --- Claude -----------------------------------------------------------------

CLAUDE_FAMILIES = ("opus", "sonnet", "haiku", "fable")
CLAUDE_EFFORTS = ("low", "medium", "high", "xhigh", "max")
_seen_claude: dict[str, str] = {}
_seen_lock = threading.Lock()


def remember_claude_model(model: str | None) -> None:
    """Merkt sich, auf welches Modell ein Kurzname zuletzt zeigte (aus dem Init-Ereignis)."""
    if not model:
        return
    lowered = model.lower()
    for family in CLAUDE_FAMILIES:
        if family in lowered:
            with _seen_lock:
                _seen_claude[family] = model
            return


def _claude_catalog() -> list[Entry]:
    with _seen_lock:
        seen = dict(_seen_claude)
    return [
        Entry(
            id=f"{family}-latest",
            label=f"{family.capitalize()} (neuestes)",
            family=family,
            latest=True,
            resolves_to=seen.get(family),
            recommended=family == "sonnet",
            efforts=CLAUDE_EFFORTS,
        )
        for family in CLAUDE_FAMILIES
    ]


def _claude_resolve(model: str | None, effort: str | None) -> Resolution:
    chosen = model
    if model and model.endswith("-latest") and model[: -len("-latest")] in CLAUDE_FAMILIES:
        chosen = model[: -len("-latest")]
    _check_effort(effort, CLAUDE_EFFORTS)
    return Resolution(chosen, effort, effort)


# --- Codex ------------------------------------------------------------------

CODEX_FALLBACK_EFFORTS = ("low", "medium", "high", "xhigh", "max")
CODEX_CACHE_SECONDS = 600
CODEX_TIMEOUT_SECONDS = 20
_CODEX_SLUG = re.compile(r"^gpt-(\d+(?:\.\d+)*)-([a-z][a-z0-9-]*)$")
_codex_cache: dict = {"at": 0.0, "models": None}
_codex_lock = threading.Lock()


@dataclass(frozen=True)
class CodexModel:
    id: str
    label: str | None
    default: bool
    efforts: tuple[str, ...]
    default_effort: str | None


def parse_codex_models(result) -> list[CodexModel]:
    """Liest die Antwort von ``model/list``; verdeckte Modelle zählen nicht."""
    data = result.get("data") if isinstance(result, dict) else result
    models = []
    for item in data if isinstance(data, list) else []:
        if not isinstance(item, dict) or item.get("hidden"):
            continue
        model_id = item.get("model") or item.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        efforts = []
        for level in item.get("supportedReasoningEfforts") or []:
            value = level.get("reasoningEffort") if isinstance(level, dict) else level
            if isinstance(value, str):
                efforts.append(value)
        default = item.get("defaultReasoningEffort")
        models.append(
            CodexModel(
                id=model_id.strip(),
                label=item.get("displayName") if isinstance(item.get("displayName"), str) else None,
                default=bool(item.get("isDefault")),
                efforts=_ordered(efforts),
                default_effort=default if default in EFFORTS else None,
            )
        )
    return models


def _codex_rpc_models() -> list[CodexModel] | None:
    # Import hier: der Provider legt beim Erzeugen den Zugang ab (wie vor jedem Aufruf).
    import limits
    from providers.codex_sub_provider import CodexSubProvider

    provider = CodexSubProvider()
    try:
        env = provider._build_env()
    except RuntimeError:
        return None
    try:
        answer = limits._codex_rpc(env, CODEX_TIMEOUT_SECONDS, method="model/list")
    except (OSError, TimeoutError) as error:
        log.warning("Modellliste von Codex nicht abrufbar: %s", type(error).__name__)
        return None
    if "error" in answer:
        log.warning("Codex lehnt die Modellliste ab")
        return None
    return parse_codex_models(answer.get("result")) or None


def codex_models(now: float | None = None, fetch=None) -> list[CodexModel]:
    """Modelle des Kontos (zwischengespeichert); ohne Antwort die bekannte Liste."""
    from providers.codex_sub_provider import CODEX_MODELS

    now = time.time() if now is None else now
    with _codex_lock:
        cached = _codex_cache["models"]
        if cached is not None and now - _codex_cache["at"] < CODEX_CACHE_SECONDS:
            return cached
        fresh = (fetch or _codex_rpc_models)()
        if fresh:
            _codex_cache.update(at=now, models=fresh)
            return fresh
        if cached is not None:
            return cached
    return [
        CodexModel(m, None, index == 0, CODEX_FALLBACK_EFFORTS, None)
        for index, m in enumerate(CODEX_MODELS)
    ]


def codex_latest(models: list[CodexModel]) -> dict[str, CodexModel]:
    """``latest`` und ``<familie>-latest`` → Modell."""
    latest: dict[str, CodexModel] = {}
    default = next((m for m in models if m.default), models[0] if models else None)
    if default is not None:
        latest["latest"] = default
    best: dict[str, tuple[tuple[int, ...], CodexModel]] = {}
    for model in models:
        match = _CODEX_SLUG.match(model.id)
        if not match:
            continue
        version, family = _version_key(match.group(1)), match.group(2)
        if family not in best or version > best[family][0]:
            best[family] = (version, model)
    for family, (_, model) in best.items():
        latest[f"{family}-latest"] = model
    return latest


def _codex_catalog() -> list[Entry]:
    models = codex_models()
    entries = []
    for name, model in codex_latest(models).items():
        family = name[: -len("-latest")] if name != "latest" else None
        entries.append(
            Entry(
                id=name,
                label="Empfehlung (neueste)" if name == "latest" else f"{family} (neuestes)",
                family=family,
                latest=True,
                resolves_to=model.id,
                recommended=name == "latest",
                efforts=model.efforts,
                default_effort=model.default_effort,
            )
        )
    for model in models:
        match = _CODEX_SLUG.match(model.id)
        entries.append(
            Entry(
                id=model.id,
                label=model.label,
                family=match.group(2) if match else None,
                recommended=model.default,
                efforts=model.efforts,
                default_effort=model.default_effort,
            )
        )
    return entries


def _codex_resolve(model: str | None, effort: str | None) -> Resolution:
    models = codex_models()
    chosen = model
    target = None
    if model:
        target = codex_latest(models).get(model)
        if target is not None:
            chosen = target.id
        else:
            target = next((m for m in models if m.id == model), None)
    _check_effort(effort, target.efforts if target else CODEX_FALLBACK_EFFORTS)
    return Resolution(chosen, effort, effort)


# --- Gemini (API) -----------------------------------------------------------

GEMINI_LATEST = ("gemini-flash-latest", "gemini-pro-latest")
# Stufe → Budget für Gemini 2.5 (kennt kein thinking_level).
GEMINI_25_BUDGET = {"low": 1024, "medium": 8192, "high": 24576}


def gemini_efforts(model: str) -> tuple[str, ...]:
    """Stufen je Modell laut Google: 2.5 per Budget, Pro nur low/high, sonst low bis high."""
    if "2.5" in model:
        return ("low", "medium", "high")
    if "pro" in model:
        return ("low", "high")
    return ("low", "medium", "high")


def gemini_thinking(model: str, effort: str | None) -> dict:
    """Teil von ``generation_config`` für die Stufe; leer ohne Stufe."""
    if effort is None:
        return {}
    if "2.5" in model:
        return {"thinking_budget": GEMINI_25_BUDGET[effort]}
    return {"thinking_level": effort}


def _gemini_catalog() -> list[Entry]:
    from providers.gemini_provider import GEMINI_MODELS

    ids = list(GEMINI_LATEST) + [m for m in GEMINI_MODELS if m not in GEMINI_LATEST]
    return [
        Entry(
            id=m,
            label=None,
            family="pro" if "pro" in m else "flash",
            latest=m in GEMINI_LATEST,
            recommended=m == "gemini-flash-latest",
            efforts=gemini_efforts(m),
        )
        for m in ids
    ]


def _gemini_resolve(model: str | None, effort: str | None) -> Resolution:
    from providers.gemini_provider import DEFAULT_MODEL

    _check_effort(effort, gemini_efforts(model or DEFAULT_MODEL))
    return Resolution(model, effort, effort)


# --- Gemini (AGY) -----------------------------------------------------------

_AGY_VERSION = re.compile(r"(\d+(?:\.\d+)*)")


def _agy_families(models) -> dict[str, tuple[str, ...]]:
    """Familienbezeichnung → angebotene Stufen (aus den Varianten „(Low)“ …)."""
    from providers.gemini_agy_provider import _EFFORT_SUFFIX

    families: dict[str, list[str]] = {}
    for model in models:
        match = _EFFORT_SUFFIX.search(model.label)
        name = _EFFORT_SUFFIX.sub("", model.label).strip()
        families.setdefault(name, [])
        if match:
            families[name].append(match.group(1).lower())
    return {name: _ordered(levels) for name, levels in families.items()}


def agy_latest(families: dict[str, tuple[str, ...]]) -> dict[str, str]:
    """``<art>-latest`` → Familienbezeichnung mit der höchsten Version (z. B. ``flash-latest``)."""
    best: dict[str, tuple[tuple[int, ...], str]] = {}
    for name in families:
        match = _AGY_VERSION.search(name)
        if not match:
            continue
        kind = re.sub(r"[^a-z0-9]+", "-", name.lower().replace(match.group(1), " ")).strip("-")
        kind = re.sub(r"^gemini-", "", kind) or "gemini"
        version = _version_key(match.group(1))
        if kind not in best or version > best[kind][0]:
            best[kind] = (version, name)
    return {f"{kind}-latest": name for kind, (_, name) in best.items()}


def _agy_models():
    from providers.gemini_agy_provider import load_models

    return load_models()[1]


def _agy_catalog() -> list[Entry]:
    families = _agy_families(_agy_models())
    entries = [
        Entry(
            id=alias,
            label=f"{alias[: -len('-latest')]} (neuestes)",
            family=alias[:-7],
            latest=True,
            resolves_to=name,
            efforts=families[name],
            default_effort="medium" if "medium" in families[name] else None,
        )
        for alias, name in agy_latest(families).items()
    ]
    entries += [
        Entry(
            id=name,
            label=name,
            efforts=levels,
            default_effort="medium" if "medium" in levels else None,
        )
        for name, levels in families.items()
    ]
    return entries


def _agy_resolve(model: str | None, effort: str | None) -> Resolution:
    families = _agy_families(_agy_models())
    chosen = agy_latest(families).get(model or "", model)
    if effort is None:
        return Resolution(chosen, None, None)
    if chosen is None:
        raise UnsupportedEffort(FEHLER_STUFE_UNBEKANNT)
    levels = families.get(chosen)
    if levels is None:
        raise UnsupportedEffort(FEHLER_STUFE_UNBEKANNT)
    _check_effort(effort, levels)
    # Die Stufe wird Teil der Bezeichnung; der Provider findet daraus die Variante.
    return Resolution(f"{chosen} {effort}", None, effort)


# --- Gemini (Web) -----------------------------------------------------------


def _web_catalog() -> list[Entry]:
    from providers.gemini_web_provider import available_models

    return [Entry(id=m, label=m) for m in available_models()]


def _web_resolve(model: str | None, effort: str | None) -> Resolution:
    _check_effort(effort, ())
    return Resolution(model, None, None)


# --- gemeinsam --------------------------------------------------------------

_CATALOGS = {
    "claude_sub": _claude_catalog,
    "codex_sub": _codex_catalog,
    "gemini": _gemini_catalog,
    "gemini_agy": _agy_catalog,
    "gemini_web": _web_catalog,
}
_RESOLVERS = {
    "claude_sub": _claude_resolve,
    "codex_sub": _codex_resolve,
    "gemini": _gemini_resolve,
    "gemini_agy": _agy_resolve,
    "gemini_web": _web_resolve,
}


def catalog(provider: str) -> list[dict]:
    """Katalog eines Anbieters für ``/v1/capabilities``; Fehler ergeben eine leere Liste."""
    build = _CATALOGS.get(provider)
    if build is None:
        return []
    try:
        return [entry.to_dict() for entry in build()]
    except Exception:  # Katalog ist Zusatz, darf die Fähigkeiten nie verhindern
        log.exception("Modellkatalog von %s nicht verfügbar", provider)
        return []


def resolve(provider: str, model: str | None, effort: str | None) -> Resolution:
    """„-latest“ auflösen und Stufe prüfen.

    :raises UnsupportedEffort: wenn das Modell die Stufe nicht anbietet.
    """
    model = (model or "").strip() or None
    effort = (effort or "").strip().lower() or None
    resolver = _RESOLVERS.get(provider)
    if resolver is None:
        if effort is not None:
            raise UnsupportedEffort(FEHLER_KEINE_STUFE)
        return Resolution(model)
    return resolver(model, effort)
