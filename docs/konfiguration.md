# Konfiguration

Alles, was das Add-on braucht, wird in Home Assistant im Reiter **Konfiguration** eingetragen.
Der Supervisor schreibt die Werte nach `/data/options.json`; `config_loader.py` liest sie beim
Start und legt sie als Umgebungsvariablen ab. Im Code steht kein einziger Zugangsdatenwert.

## Add-on-Optionen

| Option | Pflicht | Vorgabe | Bedeutung |
|---|---|---|---|
| `provider` | ja | `claude_sub` | Aktiver Anbieter: `claude_sub`, `codex_sub` oder `gemini` |
| `model` | ja | `auto` | Add-on-weites Standardmodell. `auto` heißt: der Anbieter entscheidet |
| `tool_access` | ja | `web` | Welche Werkzeuge die beiden Befehlszeilen benutzen dürfen: `off`, `web` oder `full` |
| `claude_oauth_token` | nein | leer | Langlebiges Token des Claude-Pro/Max-Abos, erzeugt mit `claude setup-token` |
| `anthropic_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter Anthropic-Schlüssel |
| `codex_auth_json` | nein | leer | Anmeldung des ChatGPT-Abos: vollständiger Inhalt der Datei `auth.json`, die `codex login` anlegt |
| `openai_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter OpenAI-Schlüssel |
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
| `OMNIAI_TOOL_ACCESS` | nein | `web` | Werkzeugstufe. Unbekannter Wert fällt auf `web` zurück |
| `CLAUDE_CODE_OAUTH_TOKEN` | nein | — | Token des Abos, wird an die Claude-CLI durchgereicht |
| `ANTHROPIC_API_KEY` | nein | — | Anthropic-Schlüssel als Alternative zum Abo |
| `CODEX_AUTH_JSON` | nein | — | Anmeldung des ChatGPT-Abos, wird vom Provider ins Datenverzeichnis geschrieben |
| `OPENAI_API_KEY` | nein | — | OpenAI-Schlüssel als Alternative zum Abo |
| `GEMINI_API_KEY` | nein | — | Schlüssel für Google Gemini |
| `GOOGLE_API_KEY` | nein | — | Wird als zweiter gängiger Name ebenfalls akzeptiert |
| `HOME` | nein | `/data` | Die Claude-CLI legt ihren Zustand unter `$HOME/.claude` ab; über `/data` übersteht er einen Neustart |
| `CODEX_HOME` | nein | `/data/.codex` | Dasselbe für die Codex-CLI. Sie erneuert ihre Tokens dort selbst |
| `PORT` | nein | `8000` | Port der Schnittstelle |
| `LOG_LEVEL` | nein | `INFO` | `DEBUG`, `INFO`, `WARNING` oder `ERROR` |
| `TZ` | nein | `Europe/Berlin` | Zeitzone der Log-Zeitstempel; im Bild fest gesetzt |

`auto` im Feld `model` ist ein Sentinel und wird wie ein leeres Feld behandelt — er landet nicht
in `OMNIAI_MODEL`.

## So kommt der ChatGPT-Zugang ins Add-on

Für Claude gibt es ein einzelnes, langlebiges Token (`claude setup-token`). Für ChatGPT gibt es das
**nicht**: die Codex-CLI legt ihre Anmeldung als Datei ab und erneuert sie im Betrieb selbst.
Deshalb wird diese Datei einmalig eingefügt.

1. Auf einem Rechner **mit Browser** die Codex-CLI installieren und `codex login` ausführen. Die
   Anmeldung erfolgt mit dem ChatGPT-Konto, nicht mit einem API-Schlüssel — nur so zählen die
   Anfragen später auf das Abo.
2. Den vollständigen Inhalt der dabei entstandenen Datei `~/.codex/auth.json` kopieren.
3. Im Add-on unter „Konfiguration“ in das Feld `codex_auth_json` einfügen, `provider` auf
   `codex_sub` stellen und das Add-on neu starten.

Das Add-on legt den Inhalt unter `/data/.codex/auth.json` ab — aber **nur, wenn sich der
eingetragene Wert geändert hat**. Der Grund: die CLI frischt ihre Tokens im Betrieb auf und
schreibt sie in dieselbe Datei zurück. Würde bei jedem Start der Wert aus der Konfiguration
darübergeschrieben, wäre die Anmeldung irgendwann abgelaufen, obwohl sie längst erneuert war. Wer
einen **neuen** Zugang einträgt, bekommt ihn dagegen sofort — der Unterschied wird am
Fingerabdruck des Werts erkannt, nicht am Zeitpunkt.

Meldet das Add-on später, die Anmeldung gelte nicht mehr: Schritt 1 bis 3 wiederholen. Das Feld
`openai_api_key` ist der Rückfall ohne Abo; er wird nach Verbrauch abgerechnet und nur benutzt,
wenn `codex_auth_json` leer ist.

## Werkzeuge der Befehlszeilen

Beide CLIs laufen im Add-on ohne Bildschirm (`claude -p`, `codex exec`). In diesem Modus gibt es keine interaktive
Rückfrage — und **ohne ausdrückliche Freigabe lehnt die CLI jedes genehmigungspflichtige Werkzeug
automatisch ab**, auch `WebSearch` und `WebFetch`. Es ist also nie etwas blockiert; es war nur nie
freigegeben. `tool_access` steuert diese Freigabe:

| Stufe | Was die KI darf | Wofür |
|---|---|---|
| `off` | Nichts. Antwort allein aus dem Trainingswissen | Wenn nur formatiert oder umformuliert werden soll |
| `web` | Websuche und Seitenabruf | **Vorgabe.** Wetter, Nachrichten, Preise, Fahrpläne |
| `full` | Alle Werkzeuge, inklusive Befehle und Dateizugriff im Container | Sonderfälle. Vorher [sicherheit-datenschutz.md](sicherheit-datenschutz.md) lesen |

Was eine Stufe technisch bewirkt, unterscheidet sich je Befehlszeile: bei Claude ist es eine
Liste einzeln freigegebener Werkzeuge (`--allowedTools`), bei Codex eine Sandbox-Stufe
(`--sandbox`) plus Schalter für die Websuche (`--search`). Was das für die Reichweite bedeutet,
steht in [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

Warum `web` und nicht `full` die Vorgabe ist: D-012 in
[design-entscheidungen.md](design-entscheidungen.md).

Die Option betrifft `claude_sub` und `codex_sub`. Der Gemini-Provider ruft die Schnittstelle
direkt auf und hat keine Werkzeuge; er antwortet aus seinem Trainingswissen.

Nach dem Ändern der Option das Add-on neu starten. Ein unbekannter Wert wird nicht übernommen,
sondern fällt auf die Vorgabe zurück und erscheint als Warnung im Log — ein Tippfehler soll den
Provider nicht lahmlegen.

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
