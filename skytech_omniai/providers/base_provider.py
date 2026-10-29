"""Gemeinsames Fundament aller KI-Provider.

Hier steht, was jeder Provider können muss, und die Auswertung der Antwort:
Modelle verpacken gültiges JSON gern in Markdown oder umgeben es mit Prosa,
unabhängig davon, welcher Anbieter dahintersteht.

Dazu kommt die Werkzeug-Freigabe: sie ist keine Eigenheit eines einzelnen
Anbieters, sondern eine Einstellung des Add-ons, an die sich jede der beiden
Befehlszeilen (Claude, Codex) hält.
"""

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

log = logging.getLogger("omniai.provider")

# Wird von jedem Provider an den Prompt des Nutzers angehängt. Bewusst
# englisch: das ist eine Anweisung an das Modell, kein Text für Menschen.
JSON_INSTRUCTION = (
    "\n\nIMPORTANT: Respond with raw JSON only. Do not wrap the response in "
    "markdown code fences, do not add any explanation before or after the "
    "JSON, and do not include any text that is not valid JSON."
)

# Ein umschließender Codeblock, optional mit Sprachkennung (```json … ```).
# Gefangen wird der Rumpf, damit er ausgepackt werden kann.
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\s*\n?(.*?)\n?```$", re.DOTALL)
# Das erste in Prosa eingebettete Objekt bzw. die erste eingebettete Liste.
_EMBEDDED_JSON_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)


class ProviderTimeout(RuntimeError):
    """Der Anbieter hat nicht innerhalb des Zeitlimits geantwortet.

    Unterklasse von ``RuntimeError``, damit ``/ask`` unverändert antwortet;
    der Vertrag v1 unterscheidet den Fall (``TIMEOUT``).
    """


class UnknownModel(ValueError):
    """Das angefragte Modell gehört nicht zu diesem Anbieter."""


class NotJson(ValueError):
    """Die Antwort des Modells war kein auswertbares JSON."""


FEHLER_KEIN_JSON = (
    "Die Antwort des Modells war kein auswertbares JSON. Bitte die Anfrage "
    "erneut stellen oder den Prompt genauer formulieren."
)


# --- Werkzeug-Freigabe ------------------------------------------------------
# Beide Befehlszeilen laufen im Add-on ohne Bildschirm. In diesem Modus gibt es
# keine interaktive Rückfrage — und ohne ausdrückliche Freigabe benutzt die CLI
# deshalb kein genehmigungspflichtiges Werkzeug, auch keine Websuche. Es ist
# also nie etwas blockiert, es war nur nie freigegeben. Wie die Stufen auf die
# jeweiligen Aufrufparameter abgebildet werden, entscheidet jeder Provider für
# sich; welche Stufe gilt, steht hier an genau einer Stelle.

TOOL_ACCESS_OFF = "off"  # keine Werkzeuge, Antwort allein aus dem Trainingswissen
TOOL_ACCESS_WEB = "web"  # nur Websuche und Seitenabruf
TOOL_ACCESS_FULL = "full"  # alle Werkzeuge, inklusive Shell- und Dateizugriff

# Vorgabe ist bewusst „web" und nicht „full": „full" erlaubt der CLI auch Shell-
# und Dateizugriff im Container, und dort liegt unter /data der Zugang des Abos.
# Für Recherchefragen genügt die Websuche. Begründung: D-012.
DEFAULT_TOOL_ACCESS = TOOL_ACCESS_WEB

TOOL_ACCESS_LEVELS = (TOOL_ACCESS_OFF, TOOL_ACCESS_WEB, TOOL_ACCESS_FULL)


def resolve_tool_access() -> str:
    """Liest die Werkzeugstufe aus der Umgebung.

    Ein unbekannter oder leerer Wert fällt auf die Vorgabe zurück: ein
    Tippfehler in der Konfiguration soll keinen Provider lahmlegen.

    ``app.py`` meldet denselben Wert über ``GET /status``, damit Oberfläche und
    Provider nicht auseinanderlaufen.
    """
    level = os.environ.get("OMNIAI_TOOL_ACCESS", "").strip().lower()
    if level in TOOL_ACCESS_LEVELS:
        return level
    if level:
        log.warning(
            "Unbekannte Werkzeugstufe %r, es gilt die Vorgabe %r",
            level,
            DEFAULT_TOOL_ACCESS,
        )
    return DEFAULT_TOOL_ACCESS


@dataclass(frozen=True)
class Attachment:
    """Geprüfter Anhang einer Anfrage; Rohdaten werden niemals protokolliert."""

    name: str
    mime_type: str
    data: bytes


class BaseProvider(ABC):
    """Schnittstelle, die jeder Provider (Claude, Gemini, …) erfüllen muss."""

    @abstractmethod
    def execute(
        self,
        prompt: str,
        model: str | None = None,
        timeout: int | None = None,
        attachments: list[Attachment] | None = None,
    ) -> dict:
        """Führt den Prompt gegen den Provider aus und gibt geparstes JSON zurück.

        ``model`` wählt optional ein bestimmtes Modell innerhalb des Providers.
        Ohne Angabe greift der Standard des Providers oder das add-on-weite
        Standardmodell aus der Umgebungsvariablen ``OMNIAI_MODEL``.
        ``timeout`` begrenzt die Dauer in Sekunden; ohne Angabe gilt die
        Vorgabe des Providers.

        :raises ProviderTimeout: bei Zeitüberschreitung.
        :raises UnknownModel: wenn das Modell nicht zum Provider gehört.
        :raises NotJson: wenn die Antwort kein JSON ist.
        """
        raise NotImplementedError

    @staticmethod
    def reject_attachments(attachments: list[Attachment] | None) -> None:
        """Anbieter ohne Unterstützung lehnen Anhänge ausdrücklich ab."""
        if attachments:
            raise ValueError(
                "Dieser Anbieter nimmt keine Anhänge an. Anhänge gehen mit Gemini Web."
            )

    def _resolve_model(self, model: str | None) -> str:
        return (model or "").strip()

    def effective_model(self, model: str | None = None) -> str:
        """Name des Modells, das tatsächlich angefragt wird — ``auto``, wenn
        der Anbieter selbst entscheidet."""
        return self._resolve_model(model) or "auto"

    @staticmethod
    def parse_json(raw_output: str) -> dict:
        """Wertet die Ausgabe des Modells aus und verzeiht die üblichen Verpackungen.

        Versucht der Reihe nach: die Ausgabe selbst, die Ausgabe ohne
        Markdown-Codeblock und schließlich das erste eingebettete JSON.

        :raises ValueError: wenn keine der Varianten gültiges JSON ergibt. Die
            Rohausgabe steht dann im Log, nicht in der Meldung — sie kann
            beliebigen Text des Modells enthalten.
        """
        text = (raw_output or "").strip()

        candidates = [text]

        fence_match = _FENCE_RE.match(text)
        if fence_match:
            candidates.append(fence_match.group(1).strip())

        embedded_match = _EMBEDDED_JSON_RE.search(text)
        if embedded_match:
            candidates.append(embedded_match.group(1).strip())

        for candidate in candidates:
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

        log.error("Antwort ohne auswertbares JSON. Rohausgabe: %s", raw_output)
        raise NotJson(FEHLER_KEIN_JSON)
