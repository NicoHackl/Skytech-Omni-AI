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
- **Ein Bereich je Anbieter.** Die Seite ist in Bereiche geteilt, die in der Seitenleiste unter
  „Einstellungen“ stehen: **Allgemein** (Anbieter, Standardmodell, Werkzeuge), **Claude**,
  **ChatGPT**, **Google Gemini** (Schlüssel), **Google Gemini (AGY)** (Anmeldung der Google-Konten)
  und **Skytech X** (Token der Schnittstelle). Jeder Bereich zeigt nur seine eigenen Felder. Der
  Entwurf gilt für alle Bereiche gemeinsam: ein Wechsel verliert nichts, **Speichern** speichert
  alles. Meldet der Server ein Feld als ungültig, öffnet die Seite den Bereich, in dem es steht.
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
| `provider` | ja | `claude_sub` | Aktiver Anbieter: `claude_sub`, `codex_sub`, `gemini` (Schlüssel), `gemini_agy` (Antigravity) oder `gemini_web` (Web-App) |
| `model` | ja | `auto` | Add-on-weites Standardmodell. `auto` heißt: der Anbieter entscheidet |
| `tool_access` | ja | `web` | Welche Werkzeuge die Befehlszeilen benutzen dürfen: `off`, `web` oder `full` |
| `claude_oauth_token` | nein | leer | Langlebiges Token des Claude-Pro/Max-Abos, erzeugt mit `claude setup-token` |
| `anthropic_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter Anthropic-Schlüssel |
| `codex_auth_json` | nein | leer | Anmeldung des ChatGPT-Abos: vollständiger Inhalt der Datei `auth.json`, die `codex login` anlegt |
| `openai_api_key` | nein | leer | Alternative zum Abo: nach Verbrauch abgerechneter OpenAI-Schlüssel |
| `gemini_api_key` | nein | leer | Schlüssel aus Google AI Studio |
| `gemini_web_model` | nein | leer | Standardmodell der Gemini-Web-App, nach Cookie-Anmeldung aus dem Konto gelesen |
| `gemini_agy_model` | nein | leer | Standardmodell für `gemini_agy`: eine Bezeichnung wie `Gemini 4 Argon (High)` oder eine Kurzform wie `flash-3.8`. Leer = Google wählt. Siehe „Modelle bei Google Gemini (AGY)“ |
| `api_token` | nein | leer | Token der Schnittstelle v1 für Skytech X, mindestens 32 Zeichen (z. B. `openssl rand -base64 32`). Leer = `/v1` lehnt jede Anfrage ab. Dasselbe Token in Skytech X unter „Anbindungen“ eintragen |

`gemini_agy` hat **keinen Zugang unter den Optionen**: seine Anmeldung entsteht auf der Seite
„Einstellungen“ (siehe unten) und liegt als Datei unter `/data`. Das gemeinsame Feld `model` bleibt
bei diesem Anbieter `auto`; sein Standardmodell steht in `gemini_agy_model`.

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
| `OMNIAI_GEMINI_WEB_MODEL` | nein | — | Standardmodell der Web-App, aus `gemini_web_model` |
| `GEMINI_AGY_MODEL` | nein | — | Standardmodell für Google Gemini (AGY), aus der Option `gemini_agy_model` |
| `GOOGLE_API_KEY` | nein | — | Wird als zweiter gängiger Name ebenfalls akzeptiert |
| `OMNIAI_API_TOKEN` | nein | — | Token der Schnittstelle v1 (aus der Option `api_token`) |
| `HOME` | nein | `/data` | Die Claude-CLI legt ihren Zustand unter `$HOME/.claude` ab; über `/data` übersteht er einen Neustart |
| `CODEX_HOME` | nein | `/data/.codex` | Dasselbe für die Codex-CLI. Sie erneuert ihre Tokens dort selbst |
| `OMNIAI_GEMINI_AGY_HOME` | nein | `/data` | Heimatverzeichnis der Antigravity-CLI (`gemini_agy`): Anmeldung und Zustand liegen darunter in `.gemini/`. Nur für Entwicklung und Tests zu ändern |
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
3. Auf der Seite „Einstellungen“ im Bereich „ChatGPT“ in das Feld „Anmeldung des ChatGPT-Abos“ einfügen, als Anbieter
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
Die Anmeldung geschieht deshalb **im Add-on selbst**, auf der Seite „Einstellungen“ im Bereich
„Google Gemini (AGY)“:

1. In der Karte „Google-Anmeldung (Abo)“ auf „Mit Google anmelden“ klicken.
2. „Google-Seite öffnen“ und dort mit dem Konto anmelden, das Google AI Pro hat. Am besten ist der
   Browser vorher schon bei Google angemeldet.
3. Den Code kopieren, den Google danach anzeigt, hier einfügen und „Anmeldung abschließen“. Google
   lässt dafür etwa eine Minute Zeit (der Rest der Zeit steht neben dem Feld). Wer stattdessen die
   ganze Adresse der Zielseite kopiert, kommt ebenfalls zum Ziel.
4. Das Add-on prüft die Anmeldung mit einem kurzen Probeauftrag und danach in einem neuen Prozess.
   Erst dann steht das Konto in der Liste mit „Bereit“, und der Anbieter „Google Gemini (AGY)“ ist
   nutzbar.

Die Anmeldung liegt je Konto unter `/data` (Rechte `0600`), samt einer Sicherung. Die CLI erneuert sie
selbst; das Add-on überschreibt sie nie. „Entfernen“ löscht das Konto aus dem Add-on. Den Zugriff
widerrufen lässt sich zusätzlich im Google-Konto unter „Sicherheit“. Gilt eine Anmeldung später nicht
mehr, markiert das Add-on das Konto („Anmeldung abgelaufen“) und nimmt das nächste; ein solches Konto
wird entfernt und neu angemeldet.

### Mehrere Google-Konten

Die Karte „Google-Anmeldung (Abo)“ nimmt beliebig viele Konten (höchstens zehn); jede weitere
Anmeldung — „Weiteres Konto anmelden“, auf Wunsch mit einem Namen — legt ein **eigenes Konto** an,
mit eigener Anmeldung und eigenem Zustand der CLI. Jedes Konto bringt sein eigenes Kontingent mit.

So wechselt das Add-on (D-024):

- Es arbeitet mit dem **ersten Konto der Liste, das Kontingent hat**, und bleibt dabei. Reihum wird
  nicht verteilt.
- Meldet die CLI „Kontingent aufgebraucht“, markiert das Add-on das Konto und wiederholt **dieselbe
  Anfrage** mit dem nächsten. Der Aufrufer merkt davon nichts als eine etwas längere Antwortzeit.
- Ein aufgebrauchtes Konto wird erst nach einer Wartezeit wieder versucht: 30 Minuten, nach jedem
  weiteren Fehlschlag doppelt so lange, höchstens fünf Stunden. So wird ein früher erneuertes
  Kontingent bald genutzt, ohne dass jede Anfrage ein leeres Konto antippt. In der Liste steht der
  nächste Versuch.
- Dasselbe gilt für ein Konto, das Google einschränkt („Von Google eingeschränkt“). Ein Konto mit
  abgelaufener Anmeldung wird übersprungen, bis es neu angemeldet ist.
- Sind alle Konten in Wartezeit, antwortet das Add-on sofort mit einem Satz, der den nächsten Versuch
  nennt; es startet dann keine CLI.
- Nur diese drei Gründe führen zum Wechsel — nie eine schlechte Antwort oder ein Zeitlimit.
- Die Modellliste gilt für alle Konten; sie müssen demselben Tarif angehören, sonst nennt die Auswahl
  Modelle, die ein Konto nicht kennt.

**Google nennt „automating account rotation“ ausdrücklich als nicht unterstützt** (Wortlaut in der
[Recherche](erweiterungen/gemini-provider/recherche.md)). Das Add-on wechselt offen — ein Rechner, eine
Software, im Protokoll sichtbar — und tarnt nichts. Trotzdem steigt das Risiko mit jedem Konto, und eine
Maßnahme von Google kann alle treffen.

### Modelle bei Google Gemini (AGY)

Die Bezeichnungen kennt nur die Google-Befehlszeile, und erst nach der Anmeldung. Das Add-on holt
die Liste deshalb selbst (`agy models`), merkt sie sich unter `/data/.gemini/…` und zeigt sie

- in der Auswahl „Standardmodell“ im Bereich „Allgemein“ der Seite „Einstellungen“, sobald „Google Gemini (AGY)“
  gewählt ist (gespeichert in `gemini_agy_model`),
- auf der Seite „Modelle“ und in `GET /models` sowie `GET /v1/capabilities`.

Die Liste wird nach der Anmeldung gelesen, bei Bedarf nach sechs Stunden erneuert und lässt sich in der
Karte „Google-Anmeldung“ mit „Modelle neu laden“ neu abrufen (etwa nach einem Tarifwechsel).

Ein Modell kann auf drei Arten genannt werden — im Feld `model` einer Anfrage ebenso wie in
`gemini_agy_model`:

| Eingabe | Ergebnis |
|---|---|
| die Bezeichnung aus der Liste, z. B. `Gemini 4 Argon (High)` | genau dieses Modell (Groß- und Kleinschreibung egal) |
| eine Kurzform, deren Teile alle im Namen stehen, z. B. `flash-3.8`, `argon-4`, `gemini-3.8-flash` | das Modell dazu; **ohne Stufe** gilt die erste vorhandene aus Medium, High, Low, Max. Mit Stufe (`flash-3.8-high`) genau diese |
| nichts oder `auto` | Google wählt selbst |

Passt eine Kurzform auf mehrere Modelle (`flash`) oder auf keines, bekommt der Aufrufer einen Satz mit
der Auswahl, und die Anfrage startet gar nicht erst. Ist die Liste noch nicht bekannt, geht die Eingabe
unverändert an die Befehlszeile.

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

Bei Google Gemini (AGY) sind es Regeln in der `settings.json` der CLI, die das Add-on bei jedem Lauf
prüft: `web` erlaubt das Lesen von Webseiten, `off` nicht. **Befehle gibt das Add-on nie frei**, auch
bei `full` nicht — dort wirkt `full` wie `web`. Eine eingebaute Websuche der CLI lässt sich nicht
über diese Regeln abschalten; bei `off` bittet das Add-on das Modell nur, keine Werkzeuge zu nutzen.

Warum `web` und nicht `full` die Vorgabe ist: D-012 in
[design-entscheidungen.md](design-entscheidungen.md).

Die Option betrifft `claude_sub`, `codex_sub` und `gemini_agy`. Der Gemini-Provider mit Schlüssel
(`gemini`) ruft die Schnittstelle direkt auf und hat keine Werkzeuge; er antwortet aus seinem
Trainingswissen.

Auf der Seite „Einstellungen“ heißt die Option „Werkzeuge“ und gilt nach dem Speichern sofort; im
Reiter „Konfiguration“ geändert, braucht sie einen Neustart. Ein unbekannter Wert wird nicht übernommen,
sondern fällt auf die Vorgabe zurück und erscheint als Warnung im Log — ein Tippfehler soll den
Provider nicht lahmlegen.

## Konfigurationsdateien

| Datei | Zweck | Eingecheckt |
|---|---|---|
| `skytech_omniai/config.yaml` | Add-on-Konfiguration, Version und Optionsschema. **Einzige Quelle der Versionsnummer** — auf `dev/dev` immer `dev`, die echte setzt der Release-Job auf `main` nach dem Merge des Pull Requests | ja |
| `skytech_omniai/CHANGELOG.md` | Änderungen je Version, erscheint im Update-Dialog von Home Assistant. Nur auf `main`, vom Release-Job aus den Changelog-Trailern erzeugt | nur auf `main` |
| `skytech_omniai/build.yaml` | Basisimages je Architektur, festgenagelt | ja |
| `skytech_omniai/requirements.txt` | Laufzeit-Abhängigkeiten mit festen Versionen | ja |
| `requirements-dev.txt` | pytest, pytest-cov, PyYAML und ruff, nur für Entwicklung | ja |
| `.hadolint.yaml` | Regeln für die Prüfung des Dockerfiles in der CI | ja |
| `.github/dependabot.yml` | Wöchentliche Updates der Abhängigkeiten als PR gegen `dev/dev` | ja |
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

## Google Gemini (Web)

- `provider: gemini_web`, `gemini_web_model: ""` lässt Google das Modell wählen.
- Die Modelloption entspricht `OMNIAI_GEMINI_WEB_MODEL`; eine unbekannte Kennung führt
  zu einer Meldung mit Auswahl, ohne Kontowechsel.
- Anmeldung in den Einstellungen unter **Google Gemini (Web)**, unabhängig vom Speichern
  der Add-on-Optionen. Ein privates Browserfenster mit dem separaten Konto öffnen,
  bei Gemini anmelden, in den Entwicklerwerkzeugen die Cookie-Werte `__Secure-1PSID`
  und `__Secure-1PSIDTS` kopieren und in die zwei Passwortfelder einfügen. Danach das
  Fenster schließen, ohne sich vorher abzumelden. Die Eingabefelder werden beim
  Absenden sofort geleert. Keine Werte an Support, Chat oder Protokolle weitergeben.
- Höchstens zehn Konten. Das erste mit Kontingent wird verwendet. Leeres Kontingent
  führt zu wachsender Wartezeit und zum nächsten Konto. Ungültige Anmeldung muss
  entfernt und neu hinzugefügt werden. Eine Verbindungssperre pausiert alle Konten.
- Bestehende Google-Konten für AGY und Web sind getrennte Anmeldungen.
- Cookies sind keine Add-on-Optionen und werden nie in Antworten zurückgegeben.
- Für lokale Entwicklung kann `OMNIAI_GEMINI_WEB_HOME` ein anderes Datenverzeichnis
  bestimmen; im Add-on bleibt es `/data`.

Die Handprüfung im echten Konto erfolgt nach Installation. Es gibt keine Zusage,
wie lange eine Anmeldung auf der Serveradresse gültig bleibt. Google kann das Konto
sperren. Die Werkzeugstufe wirkt hier nicht; Verbindungen zu anderen Google-Diensten
im separaten Konto deaktivieren. Siehe [D-030](adr/D-030-gemini-web-inoffiziell.md).
