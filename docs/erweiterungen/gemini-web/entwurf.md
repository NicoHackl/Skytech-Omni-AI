# Entwurf: Anbieter „Gemini Web“

> Ursprünglicher Entwurf. Der aktuelle Umsetzungsstand und die noch offenen Punkte
> stehen in [README.md](README.md). Aussagen über Anhänge im HTTP-Endpunkt sind bis
> Abschluss von AP 9 weiterhin geplant. Der gemeinsame Kern wurde auf Ablage und
> Auswahlfunktionen begrenzt, siehe D-030.

## Überblick

```text
POST /ask  ─┐
POST /v1/… ─┴─► ProviderFactory ─► GeminiWebProvider
                                      │  1. Konto wählen (erstes mit Kontingent)
                                      │  2. Anfrage über die Brücke an gemini-webapi
                                      │  3. Antwort als JSON auswerten (BaseProvider.parse_json)
                                      │  4. Bei Limit/Anmeldung: nächstes Konto, dieselbe Anfrage
                                      ▼
                        gemini_web_client (eigener Ereignisschleifen-Thread)
                                      │  HTTPS, Cookies des Kontos
                                      ▼
                              gemini.google.com
```

Der Anbieter fügt sich in die Fabrik ein (D-005): ein Eintrag in `providers/factory.py`, sonst
bleibt `app.py` unberührt. Er hat **keine Werkzeuge im Sinne von `tool_access`** — die Web-App hat
eigene Suche und Erweiterungen, die sich nicht abschalten lassen ([Sicherheit](#sicherheit-und-datenschutz)).

## Anbieter `gemini_web`

| Thema | Entwurf |
|---|---|
| **Klasse** | `GeminiWebProvider(BaseProvider)` in `providers/gemini_web_provider.py` |
| **Aufruf** | `execute(prompt, model=None, timeout=None, attachments=None)`; die Erweiterung um `attachments` steht unter [Anhänge](#anhänge) |
| **JSON** | Die Web-App kennt keine strukturierte Ausgabe. Wie bei `codex_sub` hängt der Anbieter `JSON_INSTRUCTION` an den Prompt und wertet die Antwort mit `BaseProvider.parse_json` aus. Die Prüfung gegen ein Schema für `/v1` macht `api_v1.py` samt Wiederholung (D-020) |
| **Chats** | Jede Anfrage ist ein **eigener neuer Chat**, nie eine Fortsetzung (Grundsatz „kein Verlauf“ aus [architektur.md](../../architektur.md)). Ob er als **temporärer Chat** läuft, hängt an F3 und am Spike |
| **Zeitlimit** | Jede Anfrage bekommt ein Zeitlimit; bei Überschreitung `ProviderTimeout` (der Vertrag v1 meldet `TIMEOUT`). Der Brückenthread bricht die Aufgabe ab |
| **Parallelität** | Anfangs **eine Anfrage zur Zeit** über alle Konten, wie bei `gemini_sub`. Parallele Anfragen auf verschiedenen Konten sind möglich, aber ohne Messung nicht begründet |
| **Modelle** | Keine feste Liste im Code. Die Bibliothek liest sie beim Start aus dem Konto. Das Add-on merkt sie sich (Datei unter `/data`), zeigt sie in Oberfläche, `/models` und `/v1/capabilities` und nennt bei unbekannter Kennung die Auswahl (wie `pick_model` bei `gemini_sub`). Eigene Option `gemini_web_model` für das Standardmodell, weil das Auswahlfeld `model` des Supervisors eine feste Liste verlangt |
| **Werkzeugstufe** | `tool_access` hat **keine Wirkung** auf diesen Anbieter. Das steht in der Oberfläche beim Anbieter und in [bekannte-luecken.md](../../bekannte-luecken.md), wie bei `gemini` mit Schlüssel |

### Brücke zur Bibliothek (`gemini_web_client.py`)

Die Bibliothek ist `async`, Flask und waitress sind es nicht (Threads, `threads=8`). Die Brücke:

- **Ein Thread** mit eigener Ereignisschleife, gestartet beim ersten Gebrauch. Aufrufer geben
  Aufgaben mit `asyncio.run_coroutine_threadsafe` ab und warten mit Zeitlimit.
- **Ein Client je Konto**, im Thread gehalten, damit nicht jede Anfrage den Start der Bibliothek
  (Token holen, Modelle lesen) bezahlt. Der Spike misst, was ein Start kostet; ist er billig oder
  der Dauerbetrieb unzuverlässig, entfällt das Halten und jede Anfrage startet frisch.
- **Schließen** beim Entfernen eines Kontos und beim Beenden des Add-ons.
- Die Bibliothek wird **erst beim ersten Gebrauch importiert** (`import` in der Funktion). So
  laden Add-on und Tests auch dort, wo sie sich nicht installieren lässt, und Tests ersetzen die
  Brücke, ohne die Bibliothek zu brauchen.

Die Brücke ist die **einzige** Stelle, die `gemini_webapi` kennt. Wird die Bibliothek ersetzt (etwa
durch einen eigenen Client), ändert sich nur diese Datei.

## Konten

Wie bei D-024, aber mit Cookies statt eines Heimatverzeichnisses der CLI.

### Datenmodell und Speicherort

| Was | Wo |
|---|---|
| Liste mit Namen, Reihenfolge, Wartezeiten | `/data/omniai-gemini-web-accounts.json` (Vorschlag) |
| Cookies je Konto | `/data/omniai-gemini-web-accounts/konto-N/cookies.json`, Rechte `0600`, Ordner `0700` |
| Modellliste (gemeinsam, vom ersten Konto) | `/data/omniai-gemini-web-models.json` |

- Die Cookies liegen **nicht** in den Add-on-Optionen: Konten kommen und gehen zur Laufzeit, und
  die Optionen verwaltet der Supervisor mit festem Schema.
- Höchstens **zehn** Konten (wie D-024).
- Ein Konto hat: `id` (`konto-N`), `label` (Name, den der User vergibt), Zustand, `retry_at`, Zahl der
  Fehlschläge in Folge (für die wachsende Wartezeit).
- **Zustände:** `ok` (bereit), `exhausted` (Kontingent aufgebraucht, nächster Versuch ab `retry_at`),
  `login_expired` (Cookies ungültig). `restricted` aus D-024 entfällt, bis die Bibliothek einen
  eigenen Fehler dafür kennt (offen).

### Gemeinsamer Kern

Reihenfolge, Wartezeit und Zustandswechsel sind bei `gemini_sub` (heute `gemini_sub_accounts.py`)
und hier **dieselbe Logik**. Zwei Kopien laufen auseinander. Plan: Den neutralen Teil
(`list`, `ready_accounts`, `mark_exhausted`, `mark_needs_login`, `mark_ok`, `next_try_time`, Wartezeit,
Schreiben der Liste) in `providers/google_accounts.py` herauslösen, parametrisiert durch Dateiname,
Ordner und eine Funktion, die ein Konto auf der Platte beschreibt. Beide Anbieter nutzen ihn. Das
geschieht **nach** der Umbenennung und mit den vorhandenen Tests als Netz; die Entscheidung trifft der
Agent und hält sie im ADR fest.

### Wechsel (wie D-024)

Der Anbieter nimmt das **erste Konto der Liste, das Kontingent hat**, und bleibt dabei (kein Reihum).

| Fehler der Bibliothek | Reaktion |
|---|---|
| `UsageLimitExceededError` | Konto `exhausted`, Wartezeit 30 Minuten, nach jedem weiteren Fehlschlag doppelt, höchstens fünf Stunden; **gleiche Anfrage mit dem nächsten Konto** |
| `AuthError` | Konto `login_expired`; gleiche Anfrage mit dem nächsten Konto |
| `TemporarilyBlockedError` | **Kein Wechsel**, kein Zustand am Konto. Der Anbieter pausiert (Wartezeit wie oben) und antwortet sofort mit dem Zeitpunkt des nächsten Versuchs. Ein Wechsel hülfe nicht (die Adresse ist gesperrt, nicht das Konto) und wäre genau das Ausweichen, das dieses Projekt nicht tut |
| `ModelInvalidError` | Meldung mit der Auswahl, kein Wechsel |
| `TimeoutError`, `GeminiError`, `APIError`, nicht auswertbares JSON | kein Wechsel; Ursache ins Log, Satz für den Aufrufer |

Sind alle Konten in Wartezeit, antwortet der Anbieter **sofort** mit dem Zeitpunkt des nächsten Versuchs
und fragt Google nicht.

Die Wartezeit von 30 Minuten bis fünf Stunden passt zum Fenster von fünf Stunden. Das **Wochenlimit**
unterscheidet die Bibliothek womöglich nicht vom Fenster; dann versucht das Add-on ein leeres Konto
höchstens alle fünf Stunden (ein schneller Fehler, kein Schaden). Der Spike prüft es.

**Keine Tarnung — ausdrücklich, wie in D-024.** Keine Verteilung der Anfragen auf Zeiten oder
Adressen, kein Verwischen von Gerät, Browser-Kennung oder Anmeldeumgebung, kein Nachbauen eines
Browsers über das hinaus, was die Bibliothek ohnehin tut. Der Wechsel ist offen und im Protokoll mit
Kontoname zu lesen.

### Anmeldung: Cookies einfügen

Es gibt nichts anderes zum Einfügen (E6). Der Ablauf in der Oberfläche:

1. User legt im Konto, das nur diesem Zweck dient, die Web-App in einem **privaten Browserfenster**
   an, kopiert die Werte `__Secure-1PSID` und `__Secure-1PSIDTS` aus den Entwicklerwerkzeugen und
   schließt das Fenster nicht über „Abmelden“ (das würde die Cookies ungültig machen — der Wortlaut
   im Hinweis wird im Spike geprüft).
2. In der Oberfläche: Name vergeben, beide Werte einfügen, „Konto anmelden“.
3. Das Add-on legt das Konto an, startet die Bibliothek damit und prüft die Anmeldung. Gelingt es,
   erscheint das Konto als „Bereit“ und die Modellliste wird gelesen. Schlägt es fehl, wird das Konto
   **nicht** angelegt und die Oberfläche nennt einen Satz („Die Anmeldung wurde von Google nicht
   angenommen. Bitte die Werte erneut kopieren.“), die Ursache steht im Log.
4. Die Bibliothek erneuert `__Secure-1PSIDTS` im Betrieb und das Add-on schreibt es zurück in die
   Cookie-Datei des Kontos (der Spike klärt, ob der Pfad je Konto einstellbar ist).

Die Werte kommen **nie** zurück: weder in Antworten noch im Log noch in der Oberfläche. Die Liste zeigt
Name und Zustand.

## Anhänge

Heute kennt `/ask` nur `prompt`, `provider`, `model`; `/v1/completions` hat keine Anhänge
(Vertrag v1). Die Web-App kann Dateien und Bilder.

| Thema | Entwurf |
|---|---|
| **`/ask`** | Zusätzliches Feld `attachments`: Liste von `{ "name": …, "mimeType": …, "dataBase64": … }` (Übergabeform: F4) |
| **Provider-Schnittstelle** | `BaseProvider.execute(..., attachments=None)` mit `Attachment(name, mime_type, data)`. Ein Anbieter, der keine Anhänge kann, lehnt sie mit **einem Satz** ab („Dieser Anbieter nimmt keine Anhänge an. Anhänge gehen mit Gemini Web.“) und HTTP 400. Er ignoriert sie **nie** stillschweigend |
| **Übergabe an die Bibliothek** | Sie erwartet Dateipfade. Die Brücke schreibt die Daten in ein eigenes Verzeichnis unter `/tmp` (Rechte `0600`), übergibt die Pfade und löscht sie **immer** danach (`finally`) |
| **Grenzen** | Anzahl, Größe, erlaubte Typen: **Vorschlag**, im Spike an der Web-App gemessen und danach festgelegt. Zusätzlich Grenze für die Größe des Anfrage-Rumpfs in Flask. Ob der Ingress-Proxy von Home Assistant große Rümpfe annimmt, ist **ungeprüft** |
| **`/v1`** | Erst nach Änderung des Vertrags im Master ([README F4](README.md#offene-fragen--vor-dem-genannten-arbeitspaket-zu-klären)). Bis dahin sagt `GET /v1/capabilities` nichts über Anhänge und der Vertrag bleibt wortgleich (eiserne Regel 16) |
| **Datenschutz** | Anhänge gehen an Google (Verbraucherkonto), siehe [Sicherheit](#sicherheit-und-datenschutz). Auf der Platte liegen sie nur für die Dauer der Anfrage |

## Oberfläche

Neuer Bereich in „Einstellungen“ ([frontend.md](../../frontend.md#einstellungen-bereiche-unter-einer-elternroute)):
Eintrag in `settingsSections.ts`, Seite `pages/einstellungen/GeminiWeb.tsx`, Route `gemini-web`.

| Teil | Inhalt |
|---|---|
| **Hinweis** (`.hint-box`) | Google erlaubt diese Nutzung nicht; Konto kann eingeschränkt oder gesperrt werden; nur mit einem Konto, das nur diesem Zweck dient und dessen Verlust nicht schmerzt; Verhalten kann sich mit jeder Änderung von Google ändern. Ohne Technikwörter (Regel 12) |
| **Konten** | Liste mit Name, Zustand (`.pill`: Bereit / Kontingent aufgebraucht — nächster Versuch hh:mm / Anmeldung abgelaufen), „Entfernen“ mit Bestätigung mit Namen |
| **Konto anmelden** | Name, zwei Eingaben vom Typ Passwort (`autocomplete="off"`), Knopf „Konto anmelden“, Kurzanleitung zum Kopieren der Werte (aufklappbar, `<details>`) |
| **Modelle** | Standardmodell steht im Bereich „Allgemein“ (wie bei AGY); hier nur „Modelle neu laden“ |
| **Schalter** | Jeder Knopf `type="button"`; die Karte ist vom Speichern der Einstellungen unabhängig (wie `GoogleLogin`) |
| **Nur über Ingress** | Wie das Speichern der Einstellungen (D-015): über Port 8000 nur Anzeige |

Allgemein, Dashboard, Modelle und die Auswahl „Anbieter“ kennen den neuen Anbieter über
`provider.ts` (Klarname) und `types.ts`.

### Schnittstelle des Add-ons

| Route | Aufgabe |
|---|---|
| `GET /auth/gemini-web` | Konten mit Zustand; **nie** Cookies |
| `POST /auth/gemini-web` | Konto anlegen: `label`, beide Cookie-Werte; prüft die Anmeldung, antwortet mit dem neuen Stand |
| `DELETE /auth/gemini-web/<id>` | Konto entfernen, löscht dessen Ordner |
| `POST /auth/gemini-web/models` | Modellliste neu lesen |

Gleiche Sperre wie bei `/auth/gemini…`: Schreiben nur über den Ingress. Die Cookies stehen im
**Rumpf**, nie in der Adresse (kein Zugangswert in URLs, Regel 6). Aufnahme in
[api-referenz.md](../../api-referenz.md).

## Konfiguration

| Stelle | Änderung |
|---|---|
| `config.yaml` | `provider`-Liste um `gemini_web` erweitern; neue Option `gemini_web_model` (`str?`, Vorgabe leer) |
| `config_loader.py` | `gemini_web_model` → Umgebungsvariable (`OMNIAI_GEMINI_WEB_MODEL`) |
| `settings.py` | Anbieter `gemini_web` kennen; Prüfung der Modellbezeichnung wie bei `gemini_sub_model` |
| `GET /status` | `credentials` nennt für `gemini_web`, ob mindestens ein Konto bereit ist (ja/nein, nie ein Wert) |
| `GET /models`, `GET /v1/capabilities` | `gemini_web` mit der gelesenen Modellliste; leer, solange kein Konto angemeldet ist |

## Sicherheit und Datenschutz

Ausführlich kommt das in [sicherheit-datenschutz.md](../../sicherheit-datenschutz.md) (AP 10).

- **Cookies sind die Anmeldung des Kontos.** Wer sie hat, hat das Konto, nicht nur Gemini. Sie
  liegen nur unter `/data` (Rechte `0600`), stehen in **keinem** Log, keiner Antwort, keiner
  Fehlermeldung und keiner Adresse. Das Protokoll nennt Kontonamen, nie Werte. Der
  Standard-Logger der Bibliothek (`loguru`) wird so gesetzt, dass er nichts mit Cookies ausgibt
  (Prüfpunkt im Test).
- **Das Konto darf nichts Wertvolles enthalten.** Die Web-App hat Verbindungen zu Gmail, Drive und
  anderen Diensten desselben Kontos. Im Hinweis steht, sie im Konto abzuschalten; auf dem
  eigenen Konto liegt ohnehin nichts.
- **Eingaben gehen an Google** und fallen bei Verbraucherkonten unter deren Datenbedingungen
  (Verbesserung der Produkte, Durchsicht durch Menschen). Chats stehen im Verlauf des Kontos, solange
  F3 nicht auf „temporär“ entschieden wird und der Spike sie bestätigt.
- **Prompt-Injection:** Die Web-App sucht und liest Seiten selbst. Antworten sind unvertrauenswürdige
  Daten; das gilt wie bei den anderen Anbietern und wird dort nicht anders behandelt.
- **Schreiben nur über den Ingress**, wie die Einstellungen (D-015): Port 8000 ist unauthentifiziert.

## Risiko

Sperrung des Kontos ist möglich (Googles Bedingungen, [recherche.md](recherche.md#3-bedingungen-und-risiko)).
Das Risiko liegt beim User; es steht im ADR, in der Oberfläche und in `bekannte-luecken.md`. Damit es
nur der trägt, der es will: Ohne angemeldetes Konto tut der Anbieter nichts, und `claude_sub` bleibt
Vorgabe des Add-ons.

## Abhängigkeit und Lizenz

| Thema | Entwurf |
|---|---|
| **Festnageln** | `gemini-webapi` und seine Abhängigkeiten in `requirements.txt` mit fester Version (wie `jsonschema`), damit ein späterer Build dasselbe Bild ergibt |
| **Python-Matrix** | Die CI läuft mit 3.11 und 3.14. Gibt es für 3.14 keine Wheels der übersetzten Pakete, wird die Bibliothek dort nicht installiert; die Tests ersetzen die Brücke und laufen ohne sie (Import erst beim Gebrauch) |
| **Musl-Wheels** | Fehlen sie für aarch64 oder amd64, wäre ein Compiler im Bild nötig — dann wird neu entschieden (Bildgröße, Bauzeit), nicht stillschweigend hingenommen. Prüfung im Spike und mit `scripts/check.sh --docker` |
| **Lizenz** | Das Repo ist MIT (eiserne Regel 14), die Bibliothek AGPL-3.0. Das ausgelieferte Image enthält beides. Welche Pflichten das für das Gesamtwerk auslöst, ist eine **rechtliche Frage, die der Plan nicht entscheidet**. Der User hat die Bibliothek gewählt (E3); der ADR hält fest, was bekannt ist, und nennt die Folgen: Quelltext und Lizenz der Bibliothek beilegen, Hinweis in der `README.md` (Abschnitt „Lizenz“), Quellangabe in der Oberfläche oder `info.md`. Wer Rechtssicherheit braucht, holt sie ein |
| **Ersatz** | Weil nur `gemini_web_client.py` die Bibliothek kennt, bleibt ein späterer Wechsel auf einen eigenen Client (der die AGPL-Frage erübrigt) auf eine Datei begrenzt |

## Code-Übersicht

| Datei | Neu / geändert |
|---|---|
| `providers/gemini_web_provider.py` | neu: Anbieter, Wechsel der Konten |
| `providers/gemini_web_client.py` | neu: Brücke zur Bibliothek (Thread, Schleife, Anhänge) |
| `providers/gemini_web_accounts.py` | neu: Konten auf der Platte (Cookies, Modelle) |
| `providers/google_accounts.py` | neu: gemeinsamer Kern der Kontenliste (aus `gemini_agy_accounts.py` herausgelöst) |
| `providers/base_provider.py` | geändert: `attachments`, `Attachment`, Ablehnung ohne Unterstützung |
| `providers/factory.py` | geändert: Eintrag `gemini_web` |
| `app.py` | geändert: Routen `/auth/gemini-web…`, `/ask` mit `attachments`, `/status`, `/models` |
| `settings.py`, `config_loader.py`, `config.yaml` | geändert: Anbieter, Option `gemini_web_model` |
| `api_v1.py` | geändert: `gemini_web` in `capabilities` |
| `requirements.txt` | geändert: Bibliothek festgenagelt |
| `web/src/…` | `pages/einstellungen/GeminiWeb.tsx`, `settingsSections.ts`, `provider.ts`, `types.ts`, `api.ts` |
| `tests/unit/…` | zu jedem Teil, ohne Netz und ohne Bibliothek |
