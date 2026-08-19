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
| Lokale Modelle über Ollama | offen | |

### M3 — Bedienbar ohne Kommandozeile

**Ziel:** Zustand und Testanfrage direkt in Home Assistant, ohne `curl`.

| Punkt | Status | Verweis |
|---|---|---|
| Oberfläche über den Ingress | fertig | D-009 |
| Übersicht mit Anbieter und hinterlegten Zugängen | fertig | [frontend.md](frontend.md) |
| Testanfrage in der Oberfläche | fertig | [frontend.md](frontend.md) |
| Modellübersicht | fertig | [frontend.md](frontend.md) |
| Hell- und Dunkel-Modus mit Schalter | fertig | [design-system.md](design-system.md) |

### M4 — Betrieb

**Ziel:** Das Add-on lässt sich betreiben, ohne dass jemand ins Log schauen muss.

| Punkt | Status | Verweis |
|---|---|---|
| Produktionsserver statt Entwicklungsserver | fertig | D-008 |
| Feste Versionen für Bild und Abhängigkeiten | fertig | [entwicklerrichtlinien.md](entwicklerrichtlinien.md) |
| Tests und Linting | fertig | [test-strategie.md](test-strategie.md) |
| Automatischer Neustart über den Watchdog | fertig | [konfiguration.md](konfiguration.md) |
| Anfragen und Antwortzeiten in der Oberfläche sichtbar | offen | |

## Zurückgestellt

| Thema | Warum zurückgestellt | Bedingung für Wiederaufnahme |
|---|---|---|
| Geräte-Anmeldung für ChatGPT aus der Oberfläche | Der Zugang wird einmalig eingefügt; ein eigener Anmeldevorgang mit zwei Endpunkten lohnt für einen einmaligen Schritt nicht (D-013) | Sobald die eingefügte Anmeldung im Betrieb wiederholt abläuft |
| Authentifizierung des offenen Ports | Automatisierungen bräuchten ein zusätzliches Token; im Heimnetz kein Gewinn | Sobald jemand das Add-on außerhalb des Heimnetzes erreichbar machen will |
| Verlauf über mehrere Anfragen | Hieße Persistenz und ein Datenschutzthema, das keiner gefordert hat | Sobald ein Anwendungsfall mehr als eine Runde braucht |

---

Beschlossen, aber noch nicht gebaut → hier mit Status `offen`.
Gebaut, aber abweichend von der Doku → [bekannte-luecken.md](bekannte-luecken.md).
Warum so entschieden → [design-entscheidungen.md](design-entscheidungen.md).
