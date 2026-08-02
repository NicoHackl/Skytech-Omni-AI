import json
import os
import socket
import urllib.error
import urllib.request

from providers.base_provider import JSON_INSTRUCTION, BaseProvider

# Googles Interactions-API ist seit 2026 die primäre Schnittstelle für die
# Gemini-Modelle und löst das ältere "generateContent" ab.
API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

# Gleiches Zeitlimit wie beim Claude-Provider, damit sich beide Provider
# gegenüber Home Assistant identisch verhalten.
REQUEST_TIMEOUT = 300

# Wird verwendet, wenn weder im Request noch in der Add-on-Konfiguration ein
# Modell gesetzt ist. Der Alias zeigt immer auf das neueste Flash-Modell.
DEFAULT_MODEL = "gemini-flash-latest"

# Sentinel-Wert aus der Add-on-Konfiguration. Er steht für "kein Modell
# erzwingen" und wird wie ein leeres Feld behandelt.
AUTO_MODEL = "auto"

# Reihenfolge = Anzeigereihenfolge im Add-on-Dropdown und unter GET /models.
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

MISSING_CREDENTIALS_MESSAGE = (
    "Kein Gemini-API-Schlüssel konfiguriert. Erzeuge einen Schlüssel unter "
    "https://aistudio.google.com/apikey, trage ihn im Add-on unter "
    "'Konfiguration' → 'gemini_api_key' ein und starte das Add-on neu."
)

# Zuordnung von HTTP-Status zu einer verständlichen Ursache. Alles andere
# bekommt die allgemeine Meldung aus _http_error_message.
HTTP_ERROR_HINTS = {
    400: "Die Anfrage an die Gemini-API war ungültig.",
    401: "Der Gemini-API-Schlüssel ist ungültig oder fehlt.",
    403: "Der Gemini-API-Schlüssel hat keine Berechtigung für dieses Modell.",
    404: "Das angeforderte Gemini-Modell existiert nicht oder wurde abgeschaltet.",
    429: "Das Kontingent bzw. das Rate-Limit der Gemini-API ist erschöpft.",
    500: "Die Gemini-API hat einen internen Fehler gemeldet.",
    503: "Die Gemini-API ist derzeit überlastet. Bitte später erneut versuchen.",
}


class GeminiProvider(BaseProvider):
    """Führt Prompts über Googles Gemini-API (Interactions-Endpunkt) aus.

    Der Aufruf läuft bewusst über urllib aus der Standardbibliothek: das
    Add-on-Image ist Alpine-basiert und wird auch für armv7/armhf gebaut, wo
    das offizielle SDK über pydantic-core eine Rust-Toolchain nachziehen
    würde. Für einen einzelnen JSON-POST lohnt diese Abhängigkeit nicht.
    """

    def _build_api_key(self) -> str:
        """Liest den API-Schlüssel aus der Umgebung.

        ``GEMINI_API_KEY`` ist der von der Add-on-Konfiguration gesetzte Name;
        ``GOOGLE_API_KEY`` wird zusätzlich akzeptiert, weil es der zweite
        gängige Name in Googles Werkzeugen ist.
        """
        key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not key:
            key = os.environ.get("GOOGLE_API_KEY", "").strip()
        if not key:
            raise RuntimeError(MISSING_CREDENTIALS_MESSAGE)
        return key

    def _resolve_model(self, model: str) -> str:
        """Wählt das Modell: Request, dann OMNIAI_MODEL, dann DEFAULT_MODEL.

        Zusätzlich wird geprüft, ob das Ergebnis überhaupt ein Gemini-Modell
        ist. Das fängt den Fall ab, dass im gemeinsamen Modell-Dropdown noch
        ein Claude-Alias (z. B. 'sonnet') steht, der Provider aber auf 'gemini'
        umgestellt wurde.
        """
        chosen = (model or "").strip()
        if not chosen or chosen == AUTO_MODEL:
            chosen = os.environ.get("OMNIAI_MODEL", "").strip()
        if not chosen or chosen == AUTO_MODEL:
            chosen = DEFAULT_MODEL

        # Jede 'gemini-*'-ID wird durchgelassen, damit neue Google-Modelle ohne
        # Code-Änderung genutzt werden können.
        if chosen not in GEMINI_MODELS and not chosen.startswith("gemini-"):
            raise ValueError(
                f"'{chosen}' ist kein Gemini-Modell. Verfügbar: "
                + ", ".join(GEMINI_MODELS)
                + ". Weitere 'gemini-*'-Modell-IDs sind ebenfalls erlaubt."
            )
        return chosen

    @staticmethod
    def _collect_step_text(step: dict) -> list:
        """Sammelt alle Textbausteine eines einzelnen Antwort-Schritts ein."""
        content = step.get("content") or []
        if isinstance(content, dict):
            content = [content]
        if not isinstance(content, list):
            return []
        return [
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("text")
        ]

    def _extract_text(self, payload: dict, chosen_model: str) -> str:
        """Holt den Antworttext aus der Schritt-Zeitleiste der Interactions-API.

        Die Antwort ist keine flache Struktur, sondern eine Liste von Schritten
        (``steps``); der eigentliche Text liegt in den Schritten vom Typ
        ``model_output`` unter ``content[].text``.
        """
        if not isinstance(payload, dict):
            raise RuntimeError(
                f"Unerwartete Antwort der Gemini-API: {str(payload)[:500]}"
            )

        steps = [
            step for step in (payload.get("steps") or []) if isinstance(step, dict)
        ]

        texts = []
        for step in steps:
            if step.get("type") == "model_output":
                texts.extend(self._collect_step_text(step))

        if not texts:
            # Notfallpfad: Sollte Google die Schritt-Typen umbenennen, wird
            # alles eingesammelt, was Text enthält, statt komplett zu scheitern.
            for step in steps:
                texts.extend(self._collect_step_text(step))

        text = "".join(texts).strip()
        if not text:
            status = payload.get("status") or "unbekannt"
            raise RuntimeError(
                f"Gemini ({chosen_model}) hat keinen Text zurückgeliefert "
                f"(Status: {status}). Antwort: {json.dumps(payload)[:500]}"
            )
        return text

    @staticmethod
    def _http_error_message(exc: urllib.error.HTTPError) -> str:
        """Baut aus einem HTTP-Fehler eine verständliche deutsche Meldung."""
        try:
            body = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = (body.get("error") or {}).get("message", "")
        except (ValueError, AttributeError, OSError):
            detail = ""

        hint = HTTP_ERROR_HINTS.get(
            exc.code, "Die Gemini-API hat einen Fehler gemeldet."
        )
        message = f"{hint} (HTTP {exc.code})"
        if detail:
            message += f": {detail}"
        return message

    def execute(self, prompt: str, model: str = None) -> dict:
        api_key = self._build_api_key()
        chosen_model = self._resolve_model(model)

        body = {
            "model": chosen_model,
            "input": prompt + JSON_INSTRUCTION,
            "system_instruction": SYSTEM_INSTRUCTION,
            # Ohne zusätzliches Schema ist das laut Google nur ein starker
            # Hinweis, keine Garantie - parse_json fängt übrig gebliebene
            # Markdown-Fences bzw. umgebende Prosa ab.
            "response_format": {"type": "text", "mime_type": "application/json"},
            # Kein serverseitiges Speichern des Verlaufs bei Google. Hier
            # laufen Smart-Home-Daten durch, die dort nichts zu suchen haben.
            "store": False,
        }

        request = urllib.request.Request(
            API_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                # Der Schlüssel geht als Header raus und nicht als
                # URL-Parameter, damit er nicht in Logs oder Proxys landet.
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(self._http_error_message(exc)) from exc
        except (urllib.error.URLError, socket.timeout) as exc:
            raise RuntimeError(
                "Die Gemini-API war nicht erreichbar (Netzwerkfehler oder "
                f"Zeitüberschreitung nach {REQUEST_TIMEOUT} s): {exc}"
            ) from exc
        except ValueError as exc:
            raise RuntimeError(
                f"Die Gemini-API hat keine gültige JSON-Antwort geliefert: {exc}"
            ) from exc

        return self.parse_json(self._extract_text(payload, chosen_model))
