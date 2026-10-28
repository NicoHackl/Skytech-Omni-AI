# Roadmap

Meilensteine und **ehrlicher** Umsetzungsstand. Der Status wird gegen den tatsächlichen Code
geprüft, nicht gegen die Absicht. Was hier „fertig" heißt, muss laufen.

## Status-Werte

`offen` · `in Arbeit` · `fertig` · `zurückgestellt`

## Meilensteine

### M1 — Anfragen stellen

**Ziel:** Aus Home Assistant heraus eine KI-Anfrage stellen und geprüftes JSON zurückbekommen.

| Punkt | Status | Verweis |
|---|---|---|
| Schnittstelle `POST /ask` | fertig | [api-referenz.md](api-referenz.md) |
| Claude über das Pro/Max-Abo | fertig | D-006 |
| Anmeldung ohne Browser über ein langlebiges Token | fertig | [konfiguration.md](konfiguration.md) |
| Modellwahl pro Anfrage | fertig | [api-referenz.md](api-referenz.md) |

### M2 — Mehr als ein Anbieter

**Ziel:** Der Anbieter ist austauschbar, ohne dass die Aufrufer davon etwas merken.

| Punkt | Status | Verweis |
|---|---|---|
| Fabrik mit austauschbaren Anbietern | fertig | D-005 |
| Google Gemini | fertig | D-007 |
| `GET /models` zum Abfragen der gültigen Werte | fertig | [api-referenz.md](api-referenz.md) |
| ChatGPT über das Abo als dritter Anbieter | fertig | D-013 |
| Google Gemini über das Google-AI-Pro-Abo (Antigravity-CLI, Anmeldung im Add-on) | umgesetzt, Handprüfung mit echtem Konto offen | D-022 |
| Mehrere Google-Konten für Gemini (Abo) mit Wechsel bei aufgebrauchtem Kontingent | umgesetzt, Handprüfung mit echten Konten offen | D-024 |
| Gemini mit Schlüssel auf den Stand von Google bringen (neue Modelle, `url_context`) | offen | [erweiterungen/gemini-provider/api-weg.md](erweiterungen/gemini-provider/api-weg.md) |
| Lokale Modelle über Ollama | offen | |

### M3 — Bedienbar ohne Kommandozeile

**Ziel:** Zustand und Testanfrage direkt in Home Assistant, ohne `curl`.

| Punkt | Status | Verweis |
|---|---|---|
| Oberfläche über den Ingress | fertig | D-009 |
| Übersicht mit Anbieter und hinterlegten Zugängen | fertig | [frontend.md](frontend.md) |
| Testanfrage in der Oberfläche | fertig | [frontend.md](frontend.md) |
| Modellübersicht | fertig | [frontend.md](frontend.md) |
| Einstellungen in der Oberfläche, ohne Neustart | fertig | D-015 |
| Hell- und Dunkel-Modus mit Schalter | fertig | [design-system.md](design-system.md) |

### M4 — Betrieb

**Ziel:** Das Add-on lässt sich betreiben, ohne dass jemand ins Log schauen muss.

| Punkt | Status | Verweis |
|---|---|---|
| Produktionsserver statt Entwicklungsserver | fertig | D-008 |
| Feste Versionen für Bild und Abhängigkeiten | fertig | [entwicklerrichtlinien.md](entwicklerrichtlinien.md) |
| Tests und Linting | fertig | [test-strategie.md](test-strategie.md) |
| Automatischer Neustart über den HEALTHCHECK des Bilds | fertig | [api-referenz.md](api-referenz.md) |
| CI: Prüfungen lokal und in GitHub identisch, Smoke-Test des Bilds | fertig | [test-strategie.md](test-strategie.md) |
| Automatisches Release mit Version und Changelog aus den Commits | fertig | D-017 |
| Bild für `aarch64` in der CI prüfen | offen | [bekannte-luecken.md](bekannte-luecken.md) |
| Anfragen und Antwortzeiten in der Oberfläche sichtbar | offen | |

### M5 — Agent-Laufzeit für Skytech X

**Ziel:** Das Backend von Skytech X kann über den Vertrag v1 Antworten und ganze Agent-Läufe
anfordern; die Werkzeuge liefert das Backend über MCP (D-019,
[contracts/omniai-api-v1.yaml](contracts/omniai-api-v1.yaml)).

| Punkt | Status | Verweis |
|---|---|---|
| Vertrag v1 als OpenAPI-Datei abgestimmt | fertig | D-019 |
| Option `api_token`, Token-Pflicht für `/v1/…` | fertig | D-019 |
| `GET /v1/health`, `GET /v1/capabilities` | fertig | |
| `POST /v1/completions` mit Schema-Prüfung | fertig | D-020 |
| Nutzungsdaten (Tokens) in Läufen (`claude_sub`) | fertig | D-021 |
| Nutzungsdaten in `/v1/completions` | offen | |
| `POST /v1/runs` + Ereignisstrom für `claude_sub` (Kommandozeile mit MCP-Konfiguration), Übergabe am Laufende | fertig | D-021 |
| Läufe ohne Werkzeuge für `codex_sub` und `gemini` (Einzelanfrage) | fertig | D-021 |
| Werkzeuge in Läufen für `codex_sub` und `gemini` | offen | |
| Embeddings für die Suche nach Bedeutung in Skytech X (`gemini-embedding-001`) | fertig | D-023 |
| Alt-Endpunkte nur noch über den Ingress, sobald Skytech X umgestellt ist | offen | [bekannte-luecken.md](bekannte-luecken.md) |

## Zurückgestellt

| Thema | Warum zurückgestellt | Bedingung für Wiederaufnahme |
|---|---|---|
| Geräte-Anmeldung für ChatGPT aus der Oberfläche | Der Zugang wird einmalig eingefügt; ein eigener Anmeldevorgang mit zwei Endpunkten lohnt für einen einmaligen Schritt nicht (D-013) | Sobald die eingefügte Anmeldung im Betrieb wiederholt abläuft |
| Authentifizierung der Alt-Endpunkte | Bestehende HA-Automatisierungen bräuchten ein zusätzliches Token; der neue Vertrag v1 bekommt die Token-Pflicht (M5) | Sobald Skytech X auf v1 umgestellt ist oder jemand das Add-on außerhalb des Heimnetzes erreichbar machen will |
| Verlauf über mehrere Anfragen | Hieße Persistenz und ein Datenschutzthema, das keiner gefordert hat | Sobald ein Anwendungsfall mehr als eine Runde braucht |

---

Beschlossen, aber noch nicht gebaut → hier mit Status `offen`.
Gebaut, aber abweichend von der Doku → [bekannte-luecken.md](bekannte-luecken.md).
Warum so entschieden → [design-entscheidungen.md](design-entscheidungen.md).
