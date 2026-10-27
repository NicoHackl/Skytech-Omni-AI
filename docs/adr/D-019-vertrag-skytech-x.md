# D-019: Versionierter Vertrag v1 für Skytech X

- **Datum:** 27.10.2026
- **Status:** Geplant
- **Betrifft:** neue Endpunkte `/v1/…`, Add-on-Option `api_token`, [contracts/omniai-api-v1.yaml](../contracts/omniai-api-v1.yaml)

## Kontext

Skytech X (Backend im Repo `Skytech-X-Backend`) soll Automationen ausführen: Konnektoren zu
GitHub, Aufgaben, Kalender und E-Mail, ein Orchestrator und mehrere KI-Anbieter. Als Anbieter dient
dieses Add-on. Vorgabe des Users: **das Backend steuert, das Add-on führt aus.** Das Backend hält
die Zugangsdaten aller angebundenen Dienste, die Freigaben und den Verlauf; das Add-on hält die
Zugänge der KI-Anbieter.

Die bestehende Schnittstelle (`/ask` und Co.) reicht dafür nicht: kein Token, keine Fehlercodes,
kein Ereignisstrom, keine Werkzeuge, keine Nutzungsdaten, kein Schema-Check.

## Betrachtete Optionen

### Option A — `/ask` erweitern

- Dafür: kein zweiter Satz Endpunkte.
- Dagegen: bestehende HA-Automatisierungen hängen am heutigen Verhalten; Token-Pflicht und neue
  Felder würden sie brechen oder verwässern.

### Option B — eigener Vertrag v1 unter `/v1/…`

- Dafür: sauber versioniert, maschinenlesbar (OpenAPI), Token-Pflicht nur dort, Alt-Endpunkte
  unverändert (D-010 bleibt für sie gültig).
- Dagegen: zwei Schnittstellen nebeneinander.

## Entscheidung

Option B. Inhalt des Vertrags:

- `GET /v1/health`, `GET /v1/capabilities` (Anbieter, Modelle, Fähigkeiten, Grenzen, MCP-Versionen)
- `POST /v1/completions` — eine Antwort ohne Werkzeuge, optional gegen ein JSON-Schema geprüft
- `POST /v1/runs` + `GET /v1/runs/{runId}` + `GET /v1/runs/{runId}/events` (SSE) + `POST …/cancel`
  — Agent-Läufe; Werkzeuge kommen als MCP-Server des Backends mit kurzlebigem Lauf-Token.
  Freigaben passieren im Backend, das Add-on kennt keine.
- Alle `/v1`-Aufrufe brauchen `Authorization: Bearer <api_token>`.

Die Masterkopie liegt im Backend-Repo (`openapi/omniai-api-v1.yaml`), weil das Backend der einzige
Aufrufer ist und mehrere Laufzeiten bedienen wird; hier liegt eine unveränderte Kopie. Geändert
wird zuerst dort, dann hier im selben Arbeitspaket. Innerhalb von v1 nur Ergänzungen.

## Folgen

- **Positiv:** Das Add-on wird als Agent-Laufzeit nutzbar, ohne je Google-, Microsoft- oder
  GitHub-Zugangsdaten zu sehen; der offene Port bekommt für den neuen Teil eine Authentifizierung.
- **Negativ:** Zwei Schnittstellen sind zu pflegen; die Kopie des Vertrags muss synchron bleiben.
- **Aufwand:** Umsetzung in Meilenstein M5 ([roadmap.md](../roadmap.md)): zuerst Token,
  Gesundheit, Fähigkeiten und Einmal-Antworten, danach Agent-Läufe je Anbieter.

## Rücknahmebedingung

Wenn sich zeigt, dass das Backend den Orchestrator selbst übernehmen muss (z. B. weil die
Abo-Kommandozeilen keine Werkzeuge über MCP zuverlässig nutzen können), wird der Lauf-Teil durch
eine reine Modell-Schnittstelle ersetzt — neue Entscheidung, diese auf „Ersetzt“.
