"""Zugriff auf die EIGENEN Add-on-Optionen über die Supervisor-API.

``/data/options.json`` wird ausschließlich gelesen und niemals beschrieben.
Geschrieben wird über ``http://supervisor/addons/self/…`` — dieselbe Quelle,
die auch der Reiter „Konfiguration“ von Home Assistant bedient. Eine zweite
Konfigurationsdatei gäbe es sonst, und die beiden liefen auseinander (D-015).

Das Lesen der eigenen Informationen ist mit der Standardrolle erlaubt; das
Prüfen und Speichern der eigenen Optionen braucht die Manager-Rolle, die das
Manifest ausdrücklich anfordert.

Der Aufruf läuft wie beim Gemini-Provider über ``urllib`` aus der
Standardbibliothek (D-007): für eine Handvoll JSON-Aufrufe lohnt keine
zusätzliche Abhängigkeit im Bild.
"""

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger("omniai.supervisor")

DEFAULT_SUPERVISOR_URL = "http://supervisor"
REQUEST_TIMEOUT = 10

# Der Supervisor liegt im internen Netz von Home Assistant. Ein in der Umgebung
# gesetzter Proxy darf diese Aufrufe nicht umleiten — sonst ginge das Token an
# den Proxy, und der Aufruf erreichte sein Ziel ohnehin nicht.
_open = urllib.request.build_opener(urllib.request.ProxyHandler({})).open

FEHLER_NICHT_ERREICHBAR = (
    "Home Assistant ist gerade nicht erreichbar. Die Einstellungen wurden nicht gespeichert."
)
FEHLER_KEINE_BERECHTIGUNG = (
    "Home Assistant erlaubt dem Add-on das Speichern der Einstellungen nicht. "
    "Bitte das Add-on aktualisieren und neu starten."
)
FEHLER_ABGELEHNT = "Home Assistant hat die Einstellungen nicht übernommen."


class SupervisorUnavailable(RuntimeError):
    """Es gibt keinen Supervisor-Zugang oder er antwortet nicht."""


class SupervisorRejected(RuntimeError):
    """Der Supervisor hat die Anfrage fachlich abgelehnt."""


class SupervisorClient:
    """Dünner Client für die drei benötigten ``self``-Endpunkte.

    Token, Kopfzeilen und Optionswerte tauchen nie in Logs oder Meldungen
    auf — die Optionen enthalten die Zugänge zu den KI-Abos, und das Token ist
    ein Vollzugriff auf den Supervisor.
    """

    def __init__(self, token: str | None = None, base_url: str | None = None):
        # Erst beim Erzeugen gelesen, nicht beim Import: so greift ein in
        # Tests gesetzter Wert, und außerhalb des Containers fehlt er einfach.
        self._token = os.environ.get("SUPERVISOR_TOKEN", "") if token is None else token
        base = base_url or os.environ.get("SUPERVISOR_URL", DEFAULT_SUPERVISOR_URL)
        self._base_url = base.rstrip("/")

    @property
    def available(self) -> bool:
        """Gibt es überhaupt eine Schreibschnittstelle?

        Den Token injiziert der Supervisor nur im Add-on-Container. Fehlt er,
        läuft der Prozess außerhalb von Home Assistant, und die Oberfläche
        zeigt die Einstellungen nur an.
        """
        return bool(self._token)

    def get_self_info(self) -> dict:
        """Angaben zum eigenen Add-on: Name, Slug samt Repository-Präfix, Optionen …"""
        return self._request("GET", "/addons/self/info")

    def get_self_options(self) -> dict:
        """Die gespeicherten Optionen des Add-ons, so wie der Supervisor sie hält."""
        data = self.get_self_info()
        options = data.get("options")
        return options if isinstance(options, dict) else {}

    def validate_options(self, options: dict) -> tuple[bool, str]:
        """Prüft die Optionen gegen das Schema aus ``config.yaml``.

        Der Endpunkt erwartet die rohen Optionen, nicht das ``options``-Objekt.
        """
        data = self._request("POST", "/addons/self/options/validate", payload=options)
        return bool(data.get("valid", False)), str(data.get("message") or "")

    def save_options(self, options: dict) -> None:
        """Speichert die Optionen. Startet das Add-on ausdrücklich NICHT neu."""
        self._request("POST", "/addons/self/options", payload={"options": options})

    def _request(self, method: str, path: str, *, payload: dict | None = None) -> dict:
        if not self.available:
            raise SupervisorUnavailable(FEHLER_NICHT_ERREICHBAR)

        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with _open(request, timeout=REQUEST_TIMEOUT) as response:
                body = self._parse(response.read())
        except urllib.error.HTTPError as fehler:
            body = self._parse(fehler.read())
            # Bewusst nur die Meldung des Supervisors, nie der gesendete Rumpf.
            log.warning(
                "Supervisor %s %s abgelehnt (%s): %s",
                method,
                path,
                fehler.code,
                body.get("message") or "keine Meldung",
            )
            if fehler.code == 403:
                raise SupervisorRejected(FEHLER_KEINE_BERECHTIGUNG) from fehler
            raise SupervisorRejected(FEHLER_ABGELEHNT) from fehler
        except (TimeoutError, urllib.error.URLError) as fehler:
            log.error("Supervisor %s %s nicht erreichbar: %s", method, path, fehler)
            raise SupervisorUnavailable(FEHLER_NICHT_ERREICHBAR) from fehler

        if body.get("result") == "error":
            log.warning(
                "Supervisor %s %s abgelehnt: %s",
                method,
                path,
                body.get("message") or "keine Meldung",
            )
            raise SupervisorRejected(FEHLER_ABGELEHNT)
        data = body.get("data")
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _parse(raw: bytes) -> dict:
        try:
            body = json.loads(raw.decode("utf-8", errors="replace"))
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}
