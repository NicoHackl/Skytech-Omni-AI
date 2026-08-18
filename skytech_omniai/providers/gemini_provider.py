"""Google Gemini über die Interactions-Schnittstelle.

Der Aufruf läuft bewusst über ``urllib`` aus der Standardbibliothek: das
Add-on-Image ist Alpine-basiert und wird auch für armv7/armhf gebaut, wo das
offizielle SDK über pydantic-core eine Rust-Werkzeugkette nachziehen würde.
Für einen einzelnen JSON-POST lohnt diese Abhängigkeit nicht.
"""

import json
import logging
import os
import urllib.error
import urllib.request

from providers.base_provider import JSON_INSTRUCTION, BaseProvider

log = logging.getLogger("omniai.gemini")

# Googles Interactions-Schnittstelle ist seit 2026 der primäre Weg zu den
# Gemini-Modellen und löst das ältere „generateContent“ ab.
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# Gleiches Zeitlimit wie beim Claude-Provider, damit sich beide Provider
# gegenüber Home Assistant identisch verhalten.
REQUEST_TIMEOUT = 300

# Wird verwendet, wenn weder in der Anfrage noch in der Add-on-Konfiguration ein
# Modell gesetzt ist. Der Alias zeigt immer auf das neueste Flash-Modell.
DEFAULT_MODEL = "gemini-flash-latest"

# Sentinel-Wert aus der Add-on-Konfiguration. Er steht für „kein Modell
# erzwingen" und wird wie ein leeres Feld behandelt.
AUTO_MODEL = "auto"

# Reihenfolge = Anzeigereihenfolge im Auswahlfeld und unter GET /models.
GEMINI_MODELS = [
    "gemini-flash-latest",  # Alias: zeigt immer auf das neueste Flash-Modell
    "gemini-3.6-flash",  # neuestes Modell, bestes Preis-Leistungs-Verhältnis
    "gemini-3.5-flash",  # stark bei agentischen und Coding-Aufgaben
    "gemini-3.5-flash-lite",  # schnellstes und günstigstes 3.5er
    "gemini-3.1-flash-lite",  # günstig, Frontier-Klasse
    "gemini-2.5-pro",  # komplexes Reasoning
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

# Systemanweisung an das Modell (kein Oberflächentext, daher englisch wie beim
# Claude-Provider). Sie zwingt Gemini in die Rolle eines reinen JSON-Endpunkts.
SYSTEM_INSTRUCTION = (
    "You are a headless JSON generation endpoint. Never ask clarifying "
    "questions and never refuse. Always answer the user's request by returning "
    "exactly one valid JSON object and nothing else."
)

FEHLER_KEIN_SCHLUESSEL = (
    "Für Google Gemini ist kein Schlüssel hinterlegt. Einen Schlüssel unter "
    "https://aistudio.google.com/apikey erzeugen, im Add-on unter "
    "„Konfiguration“ → „gemini_api_key“ eintragen und das Add-on neu starten."
)

FEHLER_ALLGEMEIN = "Google Gemini hat die Anfrage nicht beantwortet. Bitte später erneut versuchen."

FEHLER_NICHT_ERREICHBAR = (
    "Google Gemini war nicht erreichbar. Bitte die Internetverbindung prüfen "
    "und es später erneut versuchen."
)

FEHLER_KEINE_ANTWORT = (
    "Google Gemini hat keinen Text zurückgeliefert. Bitte die Anfrage erneut "
    "stellen oder ein anderes Modell wählen."
)

# Zuordnung von Antwortcode zu einer verständlichen Ursache. Der Code selbst
# bleibt im Log — der Aufrufer bekommt nur den Satz.
HTTP_FEHLERTEXTE = {
    400: "Google Gemini hat die Anfrage abgelehnt.",
    401: (
        "Der hinterlegte Gemini-Schlüssel ist ungültig. Im Add-on unter "
        "„Konfiguration“ → „gemini_api_key“ einen gültigen Schlüssel eintragen."
    ),
    403: "Der hinterlegte Gemini-Schlüssel ist für dieses Modell nicht freigeschaltet.",
    404: "Das gewählte Gemini-Modell gibt es nicht. Bitte ein anderes Modell wählen.",
    429: "Das Kontingent für Google Gemini ist aufgebraucht. Bitte später erneut versuchen.",
    500: "Bei Google ist ein Fehler aufgetreten. Bitte später erneut versuchen.",
    503: "Google Gemini ist derzeit überlastet. Bitte später erneut versuchen.",
}


class GeminiProvider(BaseProvider):
    """Führt Prompts über Googles Gemini-Modelle aus."""

    def _build_api_key(self) -> str:
        """Liest den Schlüssel aus der Umgebung.

        ``GEMINI_API_KEY`` ist der von der Add-on-Konfiguration gesetzte Name;
        ``GOOGLE_API_KEY`` wird zusätzlich akzeptiert, weil es der zweite
        gängige Name in Googles Werkzeugen ist.

        :raises RuntimeError: wenn keiner der beiden gesetzt ist.
        """
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            key = os.environ.get("GOOGLE_API_KEY", "").strip()
        if not key:
            log.error("Aufruf ohne hinterlegten Gemini-Schlüssel abgelehnt")
            raise RuntimeError(FEHLER_KEIN_SCHLUESSEL)
        return key

    def _resolve_model(self, model: str | None) -> str:
        """Wählt das Modell: Anfrage, dann ``OMNIAI_MODEL``, dann Vorgabe.

        Zusätzlich wird geprüft, ob das Ergebnis überhaupt ein Gemini-Modell
        ist. Das fängt den Fall ab, dass im gemeinsamen Auswahlfeld noch ein
        Claude-Alias (etwa „sonnet“) steht, der Provider aber auf Gemini
        umgestellt wurde.

        :raises ValueError: wenn das Modell nicht zu diesem Provider gehört.
        """
        chosen = (model or "").strip()
        if not chosen or chosen == AUTO_MODEL:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        if not chosen or chosen == AUTO_MODEL:
            chosen = DEFAULT_MODEL

        # Jede „gemini-*“-Kennung wird durchgelassen, damit neue Modelle von
        # Google ohne Codeänderung genutzt werden können.
        if chosen not in GEMINI_MODELS and not chosen.startswith("gemini-"):
            raise ValueError(
                f"„{chosen}“ ist kein Modell von Google Gemini. Zur Auswahl stehen: "
                + ", ".join(GEMINI_MODELS)
                + ". Weitere „gemini-“-Modelle sind ebenfalls erlaubt."
            )
        return chosen

    @staticmethod
    def _collect_step_text(step: dict) -> list:
        """Sammelt alle Textbausteine eines einzelnen Antwortschritts ein."""
        content = step.get("content") or []
        if isinstance(content, dict):
            content = [content]
        if not isinstance(content, list):
            return []
        return [block["text"] for block in content if isinstance(block, dict) and block.get("text")]

    def _extract_text(self, payload: dict, chosen_model: str) -> str:
        """Holt den Antworttext aus der Schrittfolge der Antwort.

        Die Antwort ist keine flache Struktur, sondern eine Liste von Schritten
        (``steps``); der eigentliche Text liegt in den Schritten vom Typ
        ``model_output`` unter ``content[].text``.

        :raises RuntimeError: wenn kein Text zu finden war. Die Rohantwort geht
            dabei ins Log — sie kann beliebige Inhalte enthalten.
        """
        if not isinstance(payload, dict):
            log.error("Unerwartete Antwortstruktur von Gemini: %s", str(payload)[:2000])
            raise RuntimeError(FEHLER_ALLGEMEIN)

        steps = [step for step in (payload.get("steps") or []) if isinstance(step, dict)]

        texts = []
        for step in steps:
            if step.get("type") == "model_output":
                texts.extend(self._collect_step_text(step))

        if not texts:
            # Notfallpfad: Sollte Google die Schritttypen umbenennen, wird
            # alles eingesammelt, was Text enthält, statt komplett zu scheitern.
            log.warning(
                "Kein Schritt vom Typ „model_output“ in der Antwort — es wird "
                "auf alle Schritte ausgewichen."
            )
            for step in steps:
                texts.extend(self._collect_step_text(step))

        text = "".join(texts).strip()
        if not text:
            log.error(
                "Gemini (%s) lieferte keinen Text. Antwort: %s",
                chosen_model,
                json.dumps(payload)[:2000],
            )
            raise RuntimeError(FEHLER_KEINE_ANTWORT)
        return text

    @staticmethod
    def _http_fehler(exc: urllib.error.HTTPError) -> RuntimeError:
        """Übersetzt einen Fehler der Gegenstelle in einen lesbaren Satz.

        Antwortcode und Originaltext von Google gehen ins Log; nach oben geht
        nur der Satz, den ein Mensch damit anfangen kann.
        """
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = (body.get("error") or {}).get("message", "")
        except (ValueError, AttributeError, OSError):
            detail = ""

        log.error(
            "Gemini antwortete mit Code %s. Meldung von Google: %s",
            exc.code,
            detail or "keine",
        )
        return RuntimeError(HTTP_FEHLERTEXTE.get(exc.code, FEHLER_ALLGEMEIN))

    def execute(self, prompt: str, model: str | None = None) -> dict:
        api_key = self._build_api_key()
        chosen_model = self._resolve_model(model)

        body = {
            "model": chosen_model,
            "input": prompt + JSON_INSTRUCTION,
            "system_instruction": SYSTEM_INSTRUCTION,
            # Ohne zusätzliches Schema ist das laut Google nur ein starker
            # Hinweis, keine Garantie — parse_json fängt übrig gebliebene
            # Markdown-Blöcke bzw. umgebende Prosa ab.
            "response_format": {"type": "text", "mime_type": "application/json"},
            # Kein serverseitiges Speichern des Verlaufs bei Google. Hier
            # laufen Daten aus dem Smart Home durch, die dort nichts zu suchen
            # haben.
            "store": False,
        }

        request = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                # Der Schlüssel geht als Kopfzeile raus und nicht als
                # Adressparameter, damit er nicht in Logs oder Proxys landet.
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        log.info("Anfrage an Gemini, Modell: %s", chosen_model)

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as fehler:
            raise self._http_fehler(fehler) from fehler
        except (TimeoutError, urllib.error.URLError) as fehler:
            log.error("Gemini nicht erreichbar oder Zeitüberschreitung: %s", fehler)
            raise RuntimeError(FEHLER_NICHT_ERREICHBAR) from fehler
        except ValueError as fehler:
            log.error("Antwort von Gemini war kein gültiges JSON: %s", fehler)
            raise RuntimeError(FEHLER_ALLGEMEIN) from fehler

        return self.parse_json(self._extract_text(payload, chosen_model))
