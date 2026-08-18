# Konfiguration

Alles, was das Add-on braucht, wird in Home Assistant im Reiter **Konfiguration** eingetragen.
Der Supervisor schreibt die Werte nach `/data/options.json`; `config_loader.py` liest sie beim
Start und legt sie als Umgebungsvariablen ab. Im Code steht kein einziger Zugangsdatenwert.

## Add-on-Optionen

| Option | Pflicht | Vorgabe | Bedeutung |
|---|---|---|---|
| `provider` | ja | `claude_sub` | Aktiver Anbieter: `claude_sub` oder `gemini` |
| `model` | ja | `auto` | Add-on-weites Standardmodell. `auto` heißt: der Anbieter entscheidet |
| `claude_oauth_token` | nein | leer | Langlebiges Token des Claude-Pro/Max-Abos, erzeugt mit `claude setup-token` |
| `anthropic_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter Anthropic-Schlüssel |
| `gemini_api_key` | nein | leer | Schlüssel aus Google AI Studio |

Für den aktiven Anbieter muss **einer** der passenden Zugänge gesetzt sein — sonst antwortet
`/ask` mit einer Meldung, die sagt, welches Feld fehlt. Die Übersicht der Oberfläche zeigt
denselben Zustand.

## Umgebungsvariablen

Aus den Optionen abgeleitet. Beim Betrieb außerhalb von Home Assistant werden sie direkt gesetzt
(Vorlage: `.env.example`).

| Variable | Pflicht | Vorgabe | Bedeutung |
|---|---|---|---|
| `AI_PROVIDER` | nein | `claude_sub` | Aktiver Anbieter |
| `OMNIAI_MODEL` | nein | — | Standardmodell. Nicht gesetzt heißt: der Anbieter entscheidet |
| `CLAUDE_CODE_OAUTH_TOKEN` | nein | — | Token des Abos, wird an die Claude-CLI durchgereicht |
| `ANTHROPIC_API_KEY` | nein | — | Anthropic-Schlüssel als Alternative zum Abo |
| `GEMINI_API_KEY` | nein | — | Schlüssel für Google Gemini |
| `GOOGLE_API_KEY` | nein | — | Wird als zweiter gängiger Name ebenfalls akzeptiert |
| `HOME` | nein | `/data` | Die Claude-CLI legt ihren Zustand unter `$HOME/.claude` ab; über `/data` übersteht er einen Neustart |
| `PORT` | nein | `8000` | Port der Schnittstelle |
| `LOG_LEVEL` | nein | `INFO` | `DEBUG`, `INFO`, `WARNING` oder `ERROR` |
| `TZ` | nein | `Europe/Berlin` | Zeitzone der Log-Zeitstempel; im Bild fest gesetzt |

`auto` im Feld `model` ist ein Sentinel und wird wie ein leeres Feld behandelt — er landet nicht
in `OMNIAI_MODEL`.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `skytech_omniai/config.yaml` | Add-on-Konfiguration, Version und Optionsschema. **Einzige Quelle der Versionsnummer** | ja |
| `skytech_omniai/build.yaml` | Basisimages je Architektur, festgenagelt | ja |
| `skytech_omniai/requirements.txt` | Laufzeit-Abhängigkeiten mit festen Versionen | ja |
| `requirements-dev.txt` | pytest und ruff, nur für Entwicklung | ja |
| `.env.example` | Vorlage ohne echte Werte | ja |
| `.env` | Lokale Werte, enthält Zugangsdaten | **nein** |
| `/data/options.json` | Vom Supervisor geschrieben, liegt nur im Container | **nein** |

## Zugangsdaten

- Zugangsdaten kommen ausschließlich aus den Add-on-Optionen bzw. aus Umgebungsvariablen — **nie**
  aus dem Code, nie aus einer eingecheckten Datei.
- Ein Zugangsdatenwert taucht nie in Logs, Antworten, Fehlermeldungen oder Commit-Messages auf.
  Das Log meldet nur, **welche** Zugänge gesetzt wurden, nicht womit.
- Fehlt der Zugang, bricht das Add-on **nicht** beim Start ab: Schnittstelle und Oberfläche laufen
  weiter, damit sich der Zustand überhaupt ansehen lässt. Die erste Anfrage antwortet dann mit
  einer Meldung, die sagt, was zu tun ist.
- Weitergehende Regeln: [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Grundsatz

Alles, was sich zwischen Umgebungen unterscheidet (Anbieter, Modell, Port, Ausführlichkeit des
Logs), ist konfigurierbar und hat eine sinnvolle Vorgabe. Fest verdrahtete Werte im Code sind ein
Fehler, kein Feature.
