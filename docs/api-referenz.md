# API-Referenz

> Öffentliche Schnittstellen des Add-ons. Der Aufbau der Komponenten steht in
> [architektur.md](architektur.md) und wird hier nicht wiederholt.

## Grundsätzliches

- Basis-URL bei direktem Zugriff: `http://<HA-IP>:8000`
- Über den Ingress von Home Assistant liegen dieselben Endpunkte unter dem eingeblendeten Pfad.
- **Keine Versionierung im Pfad und kein `/api`-Präfix.** Die Endpunkte heißen seit der ersten
  Fassung `/ask`, `/models` und `/health`; bestehende Automatisierungen zeigen darauf. Ein Präfix
  nachzuschieben wäre ein Bruch ohne Gegenwert — D-010 in
  [design-entscheidungen.md](design-entscheidungen.md).
- **Keine Authentifizierung** auf dem offenen Port. Wer ihn erreicht, kann Anfragen stellen und
  damit Kontingent verbrauchen — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md).
  **Ausnahme:** `PUT /settings` nimmt nur Aufrufe über den Ingress an (siehe unten).
- Format: JSON, UTF-8.

## Vertrag v1 für Skytech X

Für das Backend von Skytech X gibt es einen eigenen, versionierten Vertrag unter `/v1/…`
(D-019): Gesundheit, Fähigkeiten, Einmal-Antworten mit Schema-Prüfung und Agent-Läufe mit
Ereignisstrom und MCP-Werkzeugen des Backends, alle mit Token-Pflicht. Er ist als OpenAPI-Datei
festgelegt und wird hier nicht wiederholt: [contract/contract_skytech_x_omniai/omniai-api-v1.yaml](../contract/contract_skytech_x_omniai/omniai-api-v1.yaml).
Masterkopie ist `contract/contract_skytech_x_omniai/omniai-api-v1.yaml` im Repo Skytech-X-Backend. Die Endpunkte unten
bleiben davon unberührt.

Umsetzungsstand (Einzelheiten im Vertrag):

| Endpunkt | Stand |
|---|---|
| Token-Pflicht (`api_token`, Fehler `401 UNAUTHORIZED`) | umgesetzt |
| `GET /v1/health`, `GET /v1/capabilities` | umgesetzt; `tools` und `usage` nur bei `claude_sub` |
| `POST /v1/completions` | umgesetzt: Schema-Prüfung mit einem zweiten Versuch, Zeitlimit je Anfrage, Fehlercodes; Nutzungsdaten fehlen noch |
| `POST /v1/runs`, `GET /v1/runs/{id}`, `…/events` (SSE), `…/cancel` | umgesetzt (D-021): `claude_sub` mit MCP-Werkzeugen des Backends; andere Anbieter nur ohne Werkzeuge als einzelne Anfrage. Höchstens 2 Läufe gleichzeitig, höchstens 120 Minuten, Übergabe am Ende jedes Laufs |

| `POST /v1/embeddings` | umgesetzt (D-023): Vektoren für die Suche nach Bedeutung im Wissen von Skytech X, ausschließlich `gemini-embedding-001` mit dem Gemini-Schlüssel, Vorgabe 768 Dimensionen, höchstens 100 Texte je Anfrage |

Läufe liegen als Dateien unter `/data/runs` (Zustand und Ereignisse, ohne Lauf-Token) und werden
24 Stunden nach ihrem Ende gelöscht. Ein Lauf, der bei einem Neustart des Add-ons noch lief,
gilt danach als gescheitert.

Jeder `/v1`-Fehler hat die Form `{"error": "<deutscher Satz>", "code": "<STABIL>"}`; unbekannte
Pfade unter `/v1` antworten ebenso, nicht mit der Oberfläche.

## Fehlerformat

Jeder Fehler antwortet mit demselben Rumpf:

```json
{ "error": "Es wurde kein Prompt übergeben." }
```

Der Text ist bereits der Satz, den ein Mensch lesen kann: deutsch, ohne Antwortcode, ohne
Klassennamen, ohne Pfad, ohne Rohausgabe des Modells. Die technische Ursache steht im Log des
Add-ons (eiserne Regel 12, [nutzertexte.md](nutzertexte.md)).

| Code | Wann |
|---|---|
| `400` | Die Anfrage selbst ist unbrauchbar: kein Prompt, unbekannter Anbieter, Modell passt nicht zum Anbieter |
| `500` | Der Anbieter hat abgelehnt, war nicht erreichbar, hat kein auswertbares JSON geliefert, oder es trat etwas Unvorhergesehenes auf |
| `403` | `PUT /settings` kam nicht über den Ingress |
| `409` | `PUT /settings` beruht auf einem Stand, der inzwischen anderswo geändert wurde |
| `422` | `PUT /settings` mit unbrauchbaren Feldern. Zusätzlich `field_errors`: je Feld ein Satz |
| `502` | `PUT /settings`: der Supervisor war nicht erreichbar oder hat abgelehnt |
| `503` | `GET /` — das Bündel der Oberfläche fehlt im Bild; `PUT /settings` — das Add-on läuft außerhalb von Home Assistant |

## `POST /ask`

Führt einen Prompt gegen den gewählten Anbieter aus.

**Rumpf**

| Feld | Typ | Pflicht | Bedeutung |
|---|---|---|---|
| `prompt` | Text | ja | Die Frage an das Modell. Die Anweisung, ausschließlich JSON zu liefern, hängt das Add-on selbst an |
| `provider` | Text | nein | `claude_sub`, `codex_sub`, `gemini`, `gemini_agy` oder `gemini_web`. Ohne Angabe gilt die Add-on-Konfiguration |
| `model` | Text | nein | Modell für genau diese Anfrage. Erlaubt ist **jede** Kennung des Anbieters, auch eine, die nicht im Auswahlfeld steht |

**Antwort `200`** — das geparste JSON des Modells, unverändert durchgereicht:

```json
{ "status": "ok" }
```

**Beispiele**

```bash
# Claude über das Abo, mit dem konfigurierten Standardmodell
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# Gemini mit ausdrücklichem Modell
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "model": "gemini-3.6-flash",
       "prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# ChatGPT über das Abo
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "codex_sub", "model": "gpt-5.6-luna",
       "prompt": "Gib mir ein JSON mit dem Feld status=ok"}'
```

## `GET /models`

Liefert die auswählbaren Werte, damit Automatisierungen sie nicht fest verdrahten müssen.
`default` ist das Modell, das der Anbieter ohne Angabe nutzt; `null` heißt: er entscheidet selbst.

```json
{
  "active_provider": "claude_sub",
  "providers": {
    "claude_sub": { "models": ["sonnet", "opus", "haiku"], "default": null },
    "codex_sub": { "models": ["gpt-5.6-sol", "…"], "default": null },
    "gemini": { "models": ["gemini-flash-latest", "…"], "default": "gemini-flash-latest" },
    "gemini_agy": { "models": ["Gemini 4 Argon (High)", "…"], "default": null },
    "gemini_web": { "models": [], "default": null }
  }
}
```

Die Modelle von `gemini_agy` stehen nicht im Code: sie kommen von der Google-Befehlszeile und sind
erst nach der Anmeldung bekannt (vorher `[]`). `default` ist dort die Option `gemini_agy_model`.
Pro Anfrage lässt sich im Feld `model` die Bezeichnung aus der Liste nennen oder eine Kurzform
(`flash-3.8`, `argon-4`); die Regeln stehen in [konfiguration.md](konfiguration.md#modelle-bei-google-gemini-agy).
Eine unbekannte oder mehrdeutige Eingabe lehnt die Anfrage mit `400` und einem Satz ab, der die
Auswahl nennt.

## `GET /status`

Zustand des Add-ons, gedacht für die Oberfläche.

```json
{
  "provider": "claude_sub",
  "version": "0.9.0",
  "default_model": null,
  "tool_access": "web",
  "credentials": { "claude_sub": true, "codex_sub": false, "gemini": false, "gemini_agy": false, "gemini_web": false }
}
```

Bei `gemini_agy` heißt `true`: Eine lesbare Anmeldung bei Google liegt vor. Ob Google sie noch
gelten lässt, zeigt erst eine Anfrage.

Zu den Zugängen kommt **ausschließlich** `true`/`false` zurück — nie der Wert, nie ein Ausschnitt
davon und auch nicht seine Länge.

`tool_access` ist die Stufe, die **tatsächlich gilt** — nicht der rohe Wert aus der Konfiguration.
Ein unbekannter Eintrag erscheint hier als `web`, weil der Provider genauso darauf zurückfällt.
Beides stammt aus derselben Funktion, damit Oberfläche und Provider nicht auseinanderlaufen.

## `GET /settings`

Die Einstellungen für die gleichnamige Seite der Oberfläche — dieselben Optionen wie im Reiter
„Konfiguration“ von Home Assistant, gelesen über den Supervisor.

```json
{
  "options": {
    "provider": "claude_sub",
    "model": "auto",
    "tool_access": "web",
    "claude_oauth_token": "",
    "anthropic_api_key": "",
    "codex_auth_json": "",
    "openai_api_key": "",
    "gemini_api_key": ""
  },
  "secrets_set": {
    "claude_oauth_token": true,
    "anthropic_api_key": false,
    "codex_auth_json": false,
    "openai_api_key": false,
    "gemini_api_key": false
  },
  "stored_revision": "<sha256>",
  "can_save": true,
  "read_only_reason": null
}
```

- Zugänge kommen **immer leer** zurück; ob einer hinterlegt ist, steht in `secrets_set`. Das ist
  dieselbe Auskunft, die `GET /status` ohnehin gibt.
- `stored_revision` ist der Fingerabdruck des gespeicherten Stands und wird beim Speichern
  zurückgeschickt.
- `can_save` ist nur `true`, wenn das Add-on in Home Assistant läuft **und** der Aufruf über den
  Ingress kam. Sonst zeigt die Oberfläche die Werte nur an.
- `read_only_reason` sagt, warum nicht: `supervisor` (das Add-on kommt nicht an seine Optionen)
  oder `ingress` (Aufruf über Port 8000); sonst `null`. Die Oberfläche macht daraus einen Satz.
- Ohne Supervisor gilt die beim Start gelesene Datei `/data/options.json`.

## `PUT /settings`

Speichert die Einstellungen über den Supervisor und übernimmt sie **ohne Neustart** — die nächste
Anfrage arbeitet bereits mit dem neuen Stand.

**Rumpf**

```json
{
  "options": { "provider": "gemini", "model": "gemini-2.5-pro", "gemini_api_key": "…", "claude_oauth_token": null },
  "stored_revision": "<aus GET /settings>"
}
```

| Feld in `options` | Regel |
|---|---|
| `provider` | `claude_sub`, `codex_sub`, `gemini`, `gemini_agy` oder `gemini_web` |
| `model` | `auto` oder ein Modell **des gewählten Anbieters** aus `GET /models` |
| `tool_access` | `off`, `web` oder `full` |
| Zugänge | fehlt oder `""` = unverändert, `null` = entfernen, sonst neuer Wert. `codex_auth_json` muss ein JSON-Objekt sein |

Fehlende Felder bleiben unverändert; unbekannte Felder werden ignoriert.

**Nur über den Ingress.** Aufrufe über Port 8000 werden mit `403` abgelehnt — sonst könnte jeder,
der den Port erreicht, die Werkzeugstufe `full` setzen und damit an die Zugänge kommen. Geprüft
wird die Absenderadresse des Ingress-Proxys, nicht ein Kopf; Begründung als D-015 in
[design-entscheidungen.md](design-entscheidungen.md).

**Antwort `200`** — wie `GET /settings`, mit dem neuen Stand.

## Anmeldung bei Google: `/auth/gemini-agy`

Für den Anbieter `gemini_agy` (D-022, mehrere Konten D-024, Ablauf in [architektur.md](architektur.md)). Alle Antworten
haben dieselbe Form:

```json
{
  "available": true,
  "signed_in": true,
  "accounts": [
    { "id": "konto-1", "label": "Privat", "state": "exhausted", "retry_at": "2026-10-28T19:30:00Z" },
    { "id": "konto-2", "label": "Arbeit", "state": "ok", "retry_at": null }
  ],
  "pending_label": "Reserve",
  "state": "waiting",
  "url": "https://accounts.google.com/o/oauth2/auth?…",
  "seconds_left": 52,
  "error": null
}
```

| Feld | Bedeutung |
|---|---|
| `available` | Die Antigravity-CLI ist im Bild vorhanden |
| `signed_in` | Mindestens ein Konto hat eine lesbare Anmeldung (wie `credentials.gemini_agy` in `/status`) |
| `accounts` | Alle Konten in der Reihenfolge, in der sie an die Reihe kommen. `state`: `ok` (bereit), `exhausted` (Kontingent aufgebraucht), `restricted` (von Google eingeschränkt), `login_expired` (Anmeldung gilt nicht mehr), `signed_out`. `retry_at` (ISO, UTC) nennt bei `exhausted` und `restricted` den nächsten Versuch. Nie ein Pfad |
| `pending_label` | Name des Kontos, das sich gerade anmeldet; es steht noch nicht in `accounts` |
| `state` | `idle` (nichts läuft), `waiting` (Adresse ausgegeben, Code fehlt) oder `checking` (Code übergeben, Google prüft) |
| `url` | Anmeldeadresse bei Google, nur bei `waiting` und nur über den Ingress |
| `seconds_left` | Restzeit für den Code, nur bei `waiting` |
| `error` | Satz, warum die letzte Anmeldung nicht geklappt hat; nur bei `idle` |

| Aufruf | Wirkung |
|---|---|
| `GET /auth/gemini-agy` | Stand. Offen wie `/status`, aber ohne `url` |
| `POST /auth/gemini-agy/start` | Startet die Anmeldung eines **neuen Kontos** und liefert `waiting` mit Adresse. Der Rumpf darf `{"label": "Name"}` tragen (höchstens 40 Zeichen, Buchstaben, Ziffern, einfache Satzzeichen; leer = „Konto N“); `422` mit `field_errors.label`, wenn der Name nicht passt oder schon zehn Konten da sind. `400`, wenn die CLI fehlt; `409`, wenn gerade eine Anfrage läuft |
| `POST /auth/gemini-agy/code` | Rumpf `{"code": "…"}`. Gibt den Code an die CLI weiter und liefert `checking`; den Ausgang zeigt danach `GET`. `422` mit `field_errors.code`, wenn die Eingabe nicht nach einem Code aussieht. Auch die ganze Adresse der Zielseite wird angenommen |
| `POST /auth/gemini-agy/cancel` | Bricht eine laufende Anmeldung ab |
| `POST /auth/gemini-agy/models` | Holt die Modelle der Befehlszeile neu und liefert `{"models": ["…"]}`. Läuft gerade eine Anfrage, bleibt die bisherige Liste |
| `DELETE /auth/gemini-agy/<id>` | Entfernt dieses Konto samt Anmeldung, Sicherung und Zustand. `404`, wenn es das Konto nicht gibt; `409`, wenn gerade eine Anfrage läuft. Widerrufen lässt sich der Zugriff nur im Google-Konto |

**Nur über den Ingress**, außer `GET`: Aufrufe über Port 8000 werden mit `403` abgelehnt, und die
Adresse wird dort nicht ausgeliefert. Wer den offenen Port erreicht, soll weder ein Konto anmelden
noch die Anmeldung entfernen können (wie bei `PUT /settings`, D-015). Code und Adresse stehen nie
im Log.

## `GET /addon`

```json
{ "name": "Skytech OmniAI", "config_path": "/config/app/b80e8355_skytech_omniai/config" }
```

Name und Konfigurationsseite des Add-ons in Home Assistant für den Sidebar-Fuß (D-018). Antwortet
immer mit 200. `name` und Slug kommen aus `GET /addons/self/info` des Supervisors; der Slug trägt
das Präfix des Add-on-Repositorys und ist deshalb nicht fest verdrahtet. Ohne Supervisor oder bei
einem Fehler: `name` = „Skytech OmniAI“, `config_path` = `null`. Ein Erfolg wird bis zum Neustart
gemerkt.

## `GET /health`

```json
{ "status": "ok" }
```

Antwortet, sobald der Prozess läuft. Der `HEALTHCHECK` im `Dockerfile` fragt diesen Endpunkt
alle 30 Sekunden ab; meldet Docker das Add-on danach als „unhealthy“, startet der Supervisor es
neu. Der Smoke-Test der CI prüft Endpunkt und HEALTHCHECK.

## `GET /` und alle übrigen Pfade

Liefert die Weboberfläche. Existiert der Pfad als Datei im Bündel, wird sie ausgeliefert;
sonst die `index.html`, damit das Routing im Browser übernehmen kann. Der Kopf `X-Ingress-Path`
bestimmt dabei das `<base>`-Element — Einzelheiten in [architektur.md](architektur.md).

## Fremde Schnittstellen

| Dienst | Endpunkt | Wofür | Verhalten bei Ausfall |
|---|---|---|---|
| Anthropic | Claude-Code-CLI als Unterprozess, Zeitlimit 300 s | Prompts über das Pro/Max-Abo | Meldung „Claude hat die Anfrage nicht beantwortet", Ursache im Log |
| OpenAI | Codex-CLI als Unterprozess (`codex exec`), Zeitlimit 300 s | Prompts über das ChatGPT-Abo | Meldung je nach Ursache (Kontingent, abgelaufene Anmeldung, sonst allgemein), Rohausgabe nur im Log |
| Google | `POST https://generativelanguage.googleapis.com/v1beta/interactions`, Zeitlimit 300 s | Prompts über Gemini | Meldung je nach Ursache (Schlüssel, Kontingent, Überlastung), Antwortcode nur im Log |
| Google (Abo) | Antigravity-CLI als Unterprozess (`agy -p`), Zeitlimit 300 s; Anmeldung über `accounts.google.com` | Prompts über das Google-AI-Pro-Abo | Meldung je nach Ursache (nicht angemeldet, Anmeldung abgelaufen, Kontingent, Konto eingeschränkt, besetzt, sonst allgemein), Rohausgabe nur im Log. Von Google bei privaten Abos nicht unterstützt (D-022) |
| Home Assistant Supervisor | `GET /addons/self/info`, `POST /addons/self/options/validate`, `POST /addons/self/options`, Zeitlimit 10 s, ohne Proxy | Einstellungen lesen und speichern | Lesen: Rückfall auf `/data/options.json`, Seite nur zur Anzeige. Speichern: Meldung „nicht erreichbar“ bzw. „nicht übernommen“, Meldung des Supervisors nur im Log |

Alle Aufrufe haben ein ausdrückliches Zeitlimit und ein definiertes Verhalten im Fehlerfall.
Welche Daten dabei das Haus verlassen: [sicherheit-datenschutz.md](sicherheit-datenschutz.md).

## Anmeldung für Gemini Web: `/auth/gemini-web`

`gemini_web` wird von `/models`, `/status` und `/v1/capabilities` angeboten. Die Modellliste
ist ohne Anmeldung leer. `credentials.gemini_web` ist wahr, wenn mindestens ein Konto
lokal bereit ist; die Gültigkeit bei Google zeigt erst ein Aufruf. Standardmodell:
`gemini_web_model`, Umgebung `OMNIAI_GEMINI_WEB_MODEL`.

| Methode und Route | Bedeutung |
|---|---|
| `GET /auth/gemini-web` | `{accounts: [{id, label, state, retry_at}], signed_in}` ohne Cookies |
| `POST /auth/gemini-web` | JSON mit `label` (optional), `psid`, `psidts`; Anmeldung prüfen und erst bei Erfolg speichern |
| `DELETE /auth/gemini-web/<id>` | Client schließen, Konto und private Dateien entfernen |
| `POST /auth/gemini-web/models` | Modelle vom ersten nutzbaren Konto neu lesen |

Schreiben nur über den echten Ingress-Proxy; der Kopf `X-Ingress-Path` genügt nicht.
Antworten enthalten keine Anmeldewerte und sind nicht zwischenzuspeichern.
Zustände: `ok`, `exhausted`, `login_expired`; `retry_at` ist ein Maschinenzeitstempel.
Eingabefehler liefern 400, fehlender Ingress 403, Anbieterfehler 503. Die Meldungen sind
deutsche Sätze ohne Rohtexte der Bibliothek. Cookie-Eingaben sind auf 24 KiB begrenzt.

`/v1` erhält keine neuen Anhangfelder. Die Vertragskopie bleibt unverändert.

Bis AP 9 abgeschlossen ist, lehnt `/ask` nichtleere `attachments` ausdrücklich mit 400
ab. Sie werden niemals stillschweigend übergangen. Die interne Provider-Brücke kann
bereits Anhänge verarbeiten, die HTTP-Eingabe folgt nach Festlegung der lokalen Grenzen.
