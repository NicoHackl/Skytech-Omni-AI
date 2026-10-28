# Konfiguration

Alles, was das Add-on braucht, wird auf der Seite **Einstellungen** der Oberfläche eingetragen
(Seitenleiste **OmniAI**). Der Reiter **Konfiguration** des Add-ons zeigt dieselben Werte und
funktioniert weiterhin: beide Wege schreiben dieselben Optionen über den Supervisor, es gibt keine
zweite Konfigurationsdatei (D-015).

Der Supervisor legt die Werte in `/data/options.json` ab. `config_loader.py` liest sie beim Start
und legt sie als Umgebungsvariablen ab; die Datei wird vom Add-on nie beschrieben. Im Code steht
kein einziger Zugangsdatenwert.

## Seite „Einstellungen“

- **Gilt sofort.** Nach dem Speichern setzt das Add-on die Umgebung neu; die Provider lesen ihre
  Werte bei jeder Anfrage. Ein Neustart ist nicht nötig. Eine Änderung im Reiter „Konfiguration“
  braucht dagegen weiterhin einen Neustart, weil dort niemand dem laufenden Prozess Bescheid sagt.
- **Zugänge** werden nie angezeigt, nur „Hinterlegt“ oder „Kein Zugang“. Ein leeres Feld behält
  den gespeicherten Wert, „Entfernen“ löscht ihn.
- **Standardmodell** bietet nur Modelle des gewählten Anbieters an.
- **Speichern nur über die Seitenleiste.** Über Port 8000 geöffnet, zeigt die Seite die Werte nur
  an — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md).
- **Konflikt.** Wurde inzwischen anderswo gespeichert, lehnt das Add-on den alten Stand ab und
  die Seite bietet an, den gespeicherten Stand zu laden.
- Außerhalb von Home Assistant (kein `SUPERVISOR_TOKEN`) zeigt die Seite die Vorgabewerte nur an.

Endpunkte: `GET /settings`, `PUT /settings` in [api-referenz.md](api-referenz.md).

## Add-on-Optionen

| Option | Pflicht | Vorgabe | Bedeutung |
|---|---|---|---|
| `provider` | ja | `claude_sub` | Aktiver Anbieter: `claude_sub`, `codex_sub`, `gemini` (Schlüssel) oder `gemini_sub` (Google-AI-Pro-Abo) |
| `model` | ja | `auto` | Add-on-weites Standardmodell. `auto` heißt: der Anbieter entscheidet |
| `tool_access` | ja | `web` | Welche Werkzeuge die Befehlszeilen benutzen dürfen: `off`, `web` oder `full` |
| `claude_oauth_token` | nein | leer | Langlebiges Token des Claude-Pro/Max-Abos, erzeugt mit `claude setup-token` |
| `anthropic_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter Anthropic-Schlüssel |
| `codex_auth_json` | nein | leer | Anmeldung des ChatGPT-Abos: vollständiger Inhalt der Datei `auth.json`, die `codex login` anlegt |
| `openai_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter OpenAI-Schlüssel |
| `gemini_api_key` | nein | leer | Schlüssel aus Google AI Studio |

`gemini_sub` hat **keine Option**: seine Anmeldung entsteht auf der Seite „Einstellungen“ (siehe
unten) und liegt als Datei unter `/data`, nicht in den Optionen. Auch das Standardmodell bleibt bei
diesem Anbieter `auto`; ein Modell lässt sich pro Anfrage über das Feld `model` nennen.
| `api_token` | nein | leer | Token der Schnittstelle v1 für Skytech X, mindestens 32 Zeichen (z. B. `openssl rand -base64 32`). Leer = `/v1` lehnt jede Anfrage ab. Dasselbe Token in Skytech X unter „Anbindungen“ eintragen |

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
| `OMNIAI_API_TOKEN` | nein | — | Token der Schnittstelle v1 (aus der Option `api_token`) |
| `HOME` | nein | `/data` | Die Claude-CLI legt ihren Zustand unter `$HOME/.claude` ab; über `/data` übersteht er einen Neustart |
| `CODEX_HOME` | nein | `/data/.codex` | Dasselbe für die Codex-CLI. Sie erneuert ihre Tokens dort selbst |
| `OMNIAI_GEMINI_HOME` | nein | `/data` | Heimatverzeichnis der Antigravity-CLI (`gemini_sub`): Anmeldung und Zustand liegen darunter in `.gemini/`. Nur für Entwicklung und Tests zu ändern |
| `PORT` | nein | `8000` | Port der Schnittstelle |
| `LOG_LEVEL` | nein | `INFO` | `DEBUG`, `INFO`, `WARNING` oder `ERROR` |
| `TZ` | nein | `Europe/Berlin` | Zeitzone der Log-Zeitstempel; im Bild fest gesetzt |
| `SUPERVISOR_TOKEN` | nein | vom Supervisor injiziert | Zugang zur Supervisor-API. Fehlt er, lässt sich auf der Seite „Einstellungen“ nichts speichern |
| `SUPERVISOR_URL` | nein | `http://supervisor` | Adresse der Supervisor-API; nur für Entwicklung und Tests zu ändern |

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
3. Auf der Seite „Einstellungen“ in das Feld „Anmeldung des ChatGPT-Abos“ einfügen, als Anbieter
   „ChatGPT (Abo)“ wählen und speichern. (Im Reiter „Konfiguration“: Feld `codex_auth_json`,
   `provider` auf `codex_sub`, danach neu starten.)

Das Add-on legt den Inhalt unter `/data/.codex/auth.json` ab — aber **nur, wenn sich der
eingetragene Wert geändert hat**. Der Grund: die CLI frischt ihre Tokens im Betrieb auf und
schreibt sie in dieselbe Datei zurück. Würde bei jedem Start der Wert aus der Konfiguration
darübergeschrieben, wäre die Anmeldung irgendwann abgelaufen, obwohl sie längst erneuert war. Wer
einen **neuen** Zugang einträgt, bekommt ihn dagegen sofort — der Unterschied wird am
Fingerabdruck des Werts erkannt, nicht am Zeitpunkt.

Meldet das Add-on später, die Anmeldung gelte nicht mehr: Schritt 1 bis 3 wiederholen. Das Feld
`openai_api_key` ist der Rückfall ohne Abo; er wird nach Verbrauch abgerechnet und nur benutzt,
wenn `codex_auth_json` leer ist.

## So kommt der Google-Zugang ins Add-on (Abo)

Die Antigravity-CLI kennt weder ein Token (wie Claude) noch eine Datei zum Einfügen (wie Codex).
Die Anmeldung geschieht deshalb **im Add-on selbst**, auf der Seite „Einstellungen“:

1. In der Karte „Google-Anmeldung (Abo)“ auf „Mit Google anmelden“ klicken.
2. „Google-Seite öffnen“ und dort mit dem Konto anmelden, das Google AI Pro hat. Am besten ist der
   Browser vorher schon bei Google angemeldet.
3. Den Code kopieren, den Google danach anzeigt, hier einfügen und „Anmeldung abschließen“. Google
   lässt dafür etwa eine Minute Zeit (der Rest der Zeit steht neben dem Feld). Wer stattdessen die
   ganze Adresse der Zielseite kopiert, kommt ebenfalls zum Ziel.
4. Das Add-on prüft die Anmeldung mit einem kurzen Probeauftrag und danach in einem neuen Prozess.
   Erst dann steht dort „Angemeldet“, und der Anbieter „Google Gemini (Abo)“ ist nutzbar.

Die Anmeldung liegt unter `/data/.gemini/antigravity-cli/` (Rechte `0600`), samt einer Sicherung.
Die CLI erneuert sie selbst; das Add-on überschreibt sie nie. „Abmelden“ löscht sie aus dem Add-on.
Den Zugriff widerrufen lässt sich zusätzlich im Google-Konto unter „Sicherheit“. Gilt die
Anmeldung später nicht mehr, meldet das Add-on es bei der nächsten Anfrage; dann erneut anmelden.

**Google unterstützt diesen Weg bei privaten Abos nicht** und kann Konten dafür einschränken oder
sperren (Hintergrund: D-022 und [erweiterungen/gemini-provider/](erweiterungen/gemini-provider/README.md)).
Die Karte weist darauf hin. Der unterstützte Weg ist der Schlüssel aus Google AI Studio
(`gemini_api_key`, Anbieter `gemini`).

## Werkzeuge der Befehlszeilen

Die CLIs laufen im Add-on ohne Bildschirm (`claude -p`, `codex exec`, `agy -p`). In diesem Modus gibt es keine interaktive
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

Bei Google Gemini (Abo) sind es Regeln in der `settings.json` der CLI, die das Add-on bei jedem Lauf
prüft: `web` erlaubt das Lesen von Webseiten, `off` nicht. **Befehle gibt das Add-on nie frei**, auch
bei `full` nicht — dort wirkt `full` wie `web`. Eine eingebaute Websuche der CLI lässt sich nicht
über diese Regeln abschalten; bei `off` bittet das Add-on das Modell nur, keine Werkzeuge zu nutzen.

Warum `web` und nicht `full` die Vorgabe ist: D-012 in
[design-entscheidungen.md](design-entscheidungen.md).

Die Option betrifft `claude_sub`, `codex_sub` und `gemini_sub`. Der Gemini-Provider mit Schlüssel
(`gemini`) ruft die Schnittstelle direkt auf und hat keine Werkzeuge; er antwortet aus seinem
Trainingswissen.

Auf der Seite „Einstellungen“ heißt die Option „Werkzeuge“ und gilt nach dem Speichern sofort; im
Reiter „Konfiguration“ geändert, braucht sie einen Neustart. Ein unbekannter Wert wird nicht übernommen,
sondern fällt auf die Vorgabe zurück und erscheint als Warnung im Log — ein Tippfehler soll den
Provider nicht lahmlegen.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `skytech_omniai/config.yaml` | Add-on-Konfiguration, Version und Optionsschema. **Einzige Quelle der Versionsnummer** — auf `agent/main` immer `dev`, die echte setzt der Release-Job auf `main` | ja |
| `skytech_omniai/CHANGELOG.md` | Änderungen je Version, erscheint im Update-Dialog von Home Assistant. Nur auf `main`, vom Release-Job aus den Changelog-Trailern erzeugt | nur auf `main` |
| `skytech_omniai/build.yaml` | Basisimages je Architektur, festgenagelt | ja |
| `skytech_omniai/requirements.txt` | Laufzeit-Abhängigkeiten mit festen Versionen | ja |
| `requirements-dev.txt` | pytest, pytest-cov, PyYAML und ruff, nur für Entwicklung | ja |
| `.hadolint.yaml` | Regeln für die Prüfung des Dockerfiles in der CI | ja |
| `.github/dependabot.yml` | Wöchentliche Updates der Abhängigkeiten als PR gegen `agent/main` | ja |
| `.env.example` | Vorlage ohne echte Werte | ja |
| `.env` | Lokale Werte, enthält Zugangsdaten | **nein** |
| `/data/options.json` | Vom Supervisor geschrieben, liegt nur im Container. Das Add-on liest sie nur | **nein** |
| `/data/runs/` | Zustand und Ereignisse der Agent-Läufe (D-021), 24 Stunden nach Laufende gelöscht; ohne Lauf-Token | **nein** |

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

## Secrets der CI

| Secret | Wo | Zweck |
|---|---|---|
| `RELEASE_DEPLOY_KEY` | GitHub → Settings → Secrets and variables → Actions | Privater Teil des Deploy-Keys „CI-Release“ (Schreibrecht). Der Release-Job pusht damit nach `main`; das Ruleset von `main` lässt außer ihm nur Admins zu. Fehlt er, scheitert nur ein Release, die Prüfungen laufen weiter |

Neu erzeugen, falls er je außerhalb von GitHub aufgetaucht ist — siehe
[sicherheit-datenschutz.md](sicherheit-datenschutz.md#release-zugang).
