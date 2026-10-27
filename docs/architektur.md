# Architektur

> Beschreibt den **tatsächlichen** Stand. Geplantes, aber nicht Umgesetztes gehört nach
> [roadmap.md](roadmap.md), Abweichungen nach [bekannte-luecken.md](bekannte-luecken.md).

## Zweck und Abgrenzung

Skytech OmniAI ist ein Home-Assistant-Add-on und eine modulare Brücke zwischen dem Smart Home und
mehreren KI-Anbietern. Es nimmt Prompts über eine HTTP-Schnittstelle entgegen, leitet sie an
Claude (Pro/Max-Abo über die Claude-Code-CLI), ChatGPT (Abo über die Codex-CLI) oder Google Gemini
weiter und liefert geprüftes JSON zurück. Eine Weboberfläche über den Ingress von Home Assistant zeigt den Zustand und erlaubt
Testanfragen.

**Nicht** Aufgabe dieses Projekts:

- Kein Gedächtnis über Anfragen hinweg. Jede Anfrage steht für sich; es gibt keinen Verlauf und
  keine Sitzung.
- Keine eigene Persistenz. Gespeichert wird nur, was die beiden Befehlszeilen selbst unter `/data`
  ablegen — ihr Anmeldezustand.
- Keine Automatisierungslogik. Wann etwas gefragt wird und was mit der Antwort geschieht,
  entscheidet Home Assistant.
- Keine Zugriffssteuerung auf dem offenen Port — siehe
  [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Tech-Stack

| Schicht | Technologie | Warum |
|---|---|---|
| Sprache / Laufzeit | Python 3 (Alpine, nur 64 Bit) | Die Befehlszeilen werden als Prozess gestartet; Python genügt dafür und ist im Basisimage vorhanden. 32 Bit entfällt, weil es die Codex-CLI dort nicht gibt — D-014 |
| Webserver | Flask + waitress | Flask für die wenigen Endpunkte, waitress als Produktionsserver — D-008 |
| Anbieter Claude | Claude-Code-CLI als Unterprozess | Nutzt das Pro/Max-Abo statt eines nach Verbrauch abgerechneten Schlüssels — D-006 |
| Anbieter ChatGPT | Codex-CLI als Unterprozess (`codex exec`) | Dasselbe für das ChatGPT-Abo; die Anmeldung wird als `auth.json` eingetragen — D-013 |
| Anbieter Gemini | `urllib` aus der Standardbibliothek | Das offizielle SDK zöge über pydantic-core eine Rust-Werkzeugkette ins musl-Bild nach — D-007 |
| Oberfläche | React 18 + TypeScript + Vite | Festgelegter Stack, siehe [frontend.md](frontend.md) |
| Auslieferung | Ein Container, ein Prozess | Die Oberfläche liegt als gebautes Bündel im Bild und wird von Flask ausgeliefert — D-009 |
| Tests | pytest, ruff | Keine Netzzugriffe, keine echten Zugangsdaten — siehe [test-strategie.md](test-strategie.md) |

## Komponenten

```text
  Home Assistant
   ├── Automatisierung ──── POST /ask ────┐
   └── Ingress-Panel ─── GET / (Bündel) ──┤
                                          ▼
                                  ┌───────────────┐
                                  │    app.py     │  Flask + waitress
                                  └───────┬───────┘
                                          │ wählt
                                          ▼
                                  ┌───────────────┐
                                  │  factory.py   │
                                  └──┬─────┬────┬─┘
                                     │     │    │
              ┌──────────────────────┘     │    └──────────────────┐
              ▼                            ▼                       ▼
   ┌─────────────────────┐     ┌────────────────────┐   ┌────────────────────┐
   │ claude_sub_provider │     │ codex_sub_provider │   │  gemini_provider   │
   │  Unterprozess       │     │  Unterprozess      │   │  HTTPS             │
   └──────────┬──────────┘     └─────────┬──────────┘   └──────────┬─────────┘
              │                          │                         │
              ▼                          ▼                         ▼
        Claude-Code-CLI              Codex-CLI                Google Gemini
              │                          │                         │
              └──────────► base_provider.parse_json ◄──────────────┘

  config_loader.py liest beim Start /data/options.json und legt die Werte
  als Umgebungsvariablen ab, aus denen sich alle Komponenten bedienen.
  PUT /settings speichert über supervisor_client und setzt die Umgebung neu.
```

| Komponente | Verantwortung | Darf nicht |
|---|---|---|
| `app.py` | HTTP-Schnittstelle, Auslieferung der Oberfläche, Übersetzung von Fehlern in Sätze | Mit einem Anbieter reden oder Modellnamen kennen |
| `config_loader.py` | Optionen lesen, in die Umgebung schreiben, Version aus `config.yaml` lesen | Entscheiden, welcher Anbieter genommen wird; `/data/options.json` beschreiben |
| `settings.py` | Was die Seite „Einstellungen“ sieht, Entwurf mit gespeichertem Stand verschmelzen, Felder prüfen | HTTP sprechen oder speichern |
| `supervisor_client.py` | Eigene Optionen über die Supervisor-API lesen, prüfen, speichern | Optionswerte oder das Token loggen |
| `api_v1.py` | Vertrag v1 für Skytech X: Token, Prüfung der Anfragen, Fehlercodes, Ereignisstrom | Eine Befehlszeile selbst starten |
| `embeddings.py` | Vektoren über `gemini-embedding-001` für `/v1/embeddings` | Ein anderes Modell wählen; Texte speichern oder loggen |
| `runs.py` | Agent-Läufe: Annahme, Grenzen, Ausführung mit der Claude-CLI bzw. als Einzelanfrage, Ereignisse, Ablage unter `/data/runs` | HTTP sprechen; das Lauf-Token speichern oder loggen |
| `providers/factory.py` | Anhand des Namens die Umsetzung wählen | Prompts ausführen |
| `providers/base_provider.py` | Gemeinsame Schnittstelle, Auswertung der Modellantwort, Auflösung der Werkzeugstufe | Einen bestimmten Anbieter kennen |
| `providers/*_provider.py` | Genau einen Anbieter ansprechen und seine Fehler übersetzen | HTTP-Antwortcodes des eigenen Servers festlegen |
| `web/` | Anzeigen und bedienen | Fachlogik enthalten oder Rohwerte ungefiltert zeigen |

Regel: Keine Komponente übernimmt Aufgaben einer anderen. Verschiebt sich eine Verantwortung,
ist das eine Design-Entscheidung → [design-entscheidungen.md](design-entscheidungen.md).

## Datenfluss

1. Beim Start liest `config_loader` die Datei `/data/options.json`, die der Supervisor verwaltet,
   und legt die Werte als Umgebungsvariablen ab. Speichert die Seite „Einstellungen“, schreibt
   `PUT /settings` die Optionen über den Supervisor und setzt die Umgebung sofort neu — die
   Provider lesen ihre Werte bei jeder Anfrage, ein Neustart ist deshalb nicht nötig (D-015).
2. Eine Anfrage trifft als `POST /ask` ein. `app.py` prüft, ob ein Prompt dabei ist.
3. `ProviderFactory` wählt die Umsetzung: Angabe in der Anfrage, sonst Konfiguration, sonst Claude.
4. Der Provider löst das Modell auf, hängt die JSON-Anweisung an den Prompt und ruft seinen Anbieter
   auf — als Unterprozess (Claude, ChatGPT) oder über HTTPS (Gemini).
5. `BaseProvider.parse_json` wertet die Antwort aus und verzeiht Markdown-Blöcke und umgebende
   Prosa.
6. Das Ergebnis geht unverändert an den Aufrufer. Scheitert ein Schritt, wird die technische
   Ursache geloggt und ein deutscher Satz zurückgegeben.

**Invariante über den ganzen Weg:** Was nach oben geht, ist entweder gültiges JSON des Modells oder
`{"error": "<deutscher Satz>"}` — nie eine Rohausgabe, nie ein Antwortcode im Text.

Details zu Endpunkten: [api-referenz.md](api-referenz.md).

## Auslieferung der Oberfläche

Home Assistant blendet Add-ons über einen **Ingress-Pfad** ein, der eine Sitzungskennung enthält
und bei jedem Aufruf ein anderer ist. Daraus folgt:

- Das Bündel wird mit relativen Verweisen gebaut (`base: './'` in `vite.config.ts`).
- Beim Ausliefern der `index.html` setzt `app.py` ein `<base>`-Element aus dem Kopf
  `X-Ingress-Path`. Ohne Einbettung steht es auf der Wurzel.
- Der Wert wird vorher gegen ein Muster geprüft, weil er im Markup landet.
- Die Seite wird mit `Cache-Control: no-store` ausgeliefert: ein zwischengespeicherter Pfad wäre
  in der nächsten Sitzung falsch.
- Jede unbekannte Route liefert die `index.html`, damit das Routing im Browser übernehmen kann.

Kein zweiter Prozess, kein nginx: ein Add-on-Container ohne Prozessverwalter startet genau einen
Befehl. Begründung: D-009 in [design-entscheidungen.md](design-entscheidungen.md).

## Verzeichnisstruktur

```text
Skytech-Omni-AI/                  # Repo-Wurzel = Add-on-Repository
├── repository.yaml               # Manifest, an dem Home Assistant das Repo erkennt
├── .github/workflows/            # CI und Release (ci.yaml), CodeQL
├── .githooks/                    # commit-msg und pre-push, aktiv über core.hooksPath
├── scripts/                      # check.sh, smoke_test.sh, release.py, commit_msg.py
├── docs/                         # diese Doku
├── tests/                        # Tests, Struktur spiegelt Quellcode und scripts/
└── skytech_omniai/               # das Add-on selbst (Unterordner ist Pflicht)
    ├── config.yaml               # Add-on-Konfiguration; Version "dev", echte Nummer nur auf main
    ├── CHANGELOG.md              # nur auf main, vom Release-Job erzeugt (D-017)
    ├── build.yaml                # Basisimages je Architektur, festgenagelt
    ├── Dockerfile                # Bild: Node, Python, Claude- und Codex-CLI, gebaute Oberfläche
    ├── requirements.txt          # Laufzeit-Abhängigkeiten, feste Versionen
    ├── info.md                   # Text, den der Add-on-Store anzeigt
    ├── app.py                    # HTTP-Schnittstelle und Auslieferung der Oberfläche
    ├── config_loader.py          # Optionen → Umgebungsvariablen
    ├── settings.py               # Fachlogik der Seite „Einstellungen“
    ├── supervisor_client.py      # eigene Optionen über die Supervisor-API
    ├── providers/                # je Anbieter eine Datei
    └── web/                      # Weboberfläche (React + TypeScript + Vite)
```

Der Build-Kontext des Supervisors ist **der Add-on-Ordner**, nicht die Repo-Wurzel. Alles, was ins
Bild soll, muss deshalb unter `skytech_omniai/` liegen — das ist der Grund, weshalb `web/` dort und
nicht in der Wurzel steht.

## Invarianten

Zusagen, auf die sich der gesamte Code verlässt:

1. Ein Zugangsdatenwert steht **ausschließlich** in der Umgebung. Er erscheint in keiner Antwort,
   keinem Log und keinem Markup — auch nicht gekürzt.
2. Jede Ausgabe an einen Aufrufer ist entweder das JSON des Modells oder ein deutscher Satz unter
   `error`.
3. Die Versionsnummer steht nur in `skytech_omniai/config.yaml`; alles andere liest sie von dort.
   Auf `agent/main` steht dort `dev`, die echte Nummer setzt der Release-Job auf `main` (D-017).
4. `parse_json` ist der einzige Ort, an dem aus Modellausgabe eine Datenstruktur wird.
5. `web/src/api.ts` ist der einzige Ort, an dem die Oberfläche `fetch` aufruft.

## Start und Betrieb

```bash
pip install -r skytech_omniai/requirements.txt -r requirements-dev.txt && npm ci --prefix skytech_omniai/web
docker build -t skytech-omniai skytech_omniai
```

Für die Entwicklung ohne Container: `python skytech_omniai/app.py` startet die Schnittstelle auf
Port 8000, `npm run dev --prefix skytech_omniai/web` die Oberfläche auf Port 5174 mit Weiterleitung
dorthin.

Konfiguration: [konfiguration.md](konfiguration.md).
