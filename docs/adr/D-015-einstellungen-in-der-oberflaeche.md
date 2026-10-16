# D-015: Einstellungen in der Oberfläche über die Supervisor-API, ohne Neustart, nur über den Ingress

- **Datum:** 16.10.2026
- **Status:** Aktiv
- **Betrifft:** `app.py` (`GET`/`PUT /settings`), `settings.py`, `supervisor_client.py`,
  `config_loader.py`, `config.yaml` (`hassio_api`, `hassio_role`, `panel_admin`),
  `web/src/pages/Einstellungen.tsx`

## Kontext

Bis 0.8.0 ließ sich OmniAI nur im Reiter „Konfiguration“ des Add-ons einstellen: technische
Feldnamen (`tool_access`, `codex_auth_json`), ein gemeinsames Modell-Auswahlfeld für alle Anbieter
und nach jeder Änderung ein Neustart. Das HEMS hat dafür bereits eine Konfigurationsseite in seiner
Oberfläche (HEMS D-042); OmniAI soll sich genauso bedienen lassen.

Randbedingungen:

- Port 8000 ist **unauthentifiziert** (bekannte-luecken.md). Die Oberfläche wird aber über
  denselben Prozess und Port ausgeliefert.
- Die Optionen enthalten die Zugänge zu den KI-Abos.
- Die Provider lesen Anbieter, Modell, Werkzeugstufe und Zugänge bei **jeder Anfrage** aus der
  Umgebung; die Codex-Anmeldung wird beim Aufruf mit Fingerabdruck abgeglichen (D-013).

## Betrachtete Optionen

### Option A — eigene Datei unter `/data`

- Dafür: kein Supervisor-Zugriff, keine zusätzliche Rolle.
- Dagegen: zwei Quellen. Welche gilt, wäre eine Frage der Startreihenfolge; der Reiter
  „Konfiguration“ zeigte einen anderen Stand als die Oberfläche.

### Option B — `/data/options.json` direkt beschreiben

- Dafür: eine Datei, kein Netzaufruf.
- Dagegen: Eigentümer der Datei ist der Supervisor. Er schreibt sie beim nächsten Optionswechsel
  oder Start neu; die Schema-Prüfung entfiele.

### Option C — eigene Optionen über die Supervisor-API

- Dafür: dieselbe Quelle wie der Reiter, dieselbe Schema-Prüfung, kein neuer Zustand. Im HEMS
  erprobt.
- Dagegen: braucht `hassio_role: manager`; Home Assistant fragt beim Update einmal danach.

## Entscheidung

**Option C**, mit drei Ergänzungen:

1. **Ohne Neustart.** Nach dem Speichern setzt `apply_options_to_env(…, clear_missing=True)` die
   Umgebung neu; ein entfernter Zugang verschwindet dabei auch aus der Umgebung. Das HEMS startet
   dagegen neu, weil es eine laufende Regelung nicht heimlich umbauen will — OmniAI hat keinen
   Zustand zwischen zwei Anfragen, der umgebaut werden müsste.
2. **Speichern nur über den Ingress.** `PUT /settings` prüft die Absenderadresse des
   Ingress-Proxys (`172.30.32.2`). Ohne diese Sperre könnte jeder, der Port 8000 erreicht,
   `tool_access` auf `full` stellen und über einen Prompt die Zugänge unter `/data` auslesen
   (Kette in sicherheit-datenschutz.md). Ein Kopf wie `X-Ingress-Path` wurde verworfen, weil ihn
   jeder Aufrufer selbst schicken kann. `GET /settings` bleibt offen, liefert aber nicht mehr als
   `GET /status`.
3. **Zugänge nur schreiben, Konfliktschutz** wie im HEMS: Zugangsfelder kommen leer zurück
   (`""` = unverändert, `null` = entfernen); ein Fingerabdruck des gespeicherten Stands verhindert,
   dass ein alter Tab eine Änderung aus dem Reiter überschreibt (`409`).

## Folgen

- **Positiv:** Einstellen ohne Reiterwechsel und ohne Neustart; Klarnamen statt Feldnamen;
  Modell passend zum Anbieter; Reiter und Oberfläche zeigen immer denselben Stand.
- **Negativ:** Manager-Rolle; Abhängigkeit von der festen Adresse des Ingress-Proxys. Eine
  Änderung im Reiter „Konfiguration“ wirkt weiter erst nach einem Neustart.
- **Aufwand:** zwei neue Module, zwei Endpunkte, eine Seite, Tests und Doku.

## Rücknahmebedingung

- Home Assistant ändert die Adresse des Ingress-Proxys oder bietet einen verlässlichen
  Anmeldebeleg im Kopf an → Prüfung umstellen.
- Port 8000 bekommt eine eigene Authentifizierung → die Ingress-Sperre kann entfallen.
- Ein Provider bekommt Zustand, der beim Start aufgebaut wird → Live-Übernahme überdenken und wie
  im HEMS neu starten.
