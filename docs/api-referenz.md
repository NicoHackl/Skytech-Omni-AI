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
| `provider` | Text | nein | `claude_sub`, `codex_sub` oder `gemini`. Ohne Angabe gilt die Add-on-Konfiguration |
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
    "gemini": { "models": ["gemini-flash-latest", "…"], "default": "gemini-flash-latest" }
  }
}
```

## `GET /status`

Zustand des Add-ons, gedacht für die Oberfläche.

```json
{
  "provider": "claude_sub",
  "version": "0.9.0",
  "default_model": null,
  "tool_access": "web",
  "credentials": { "claude_sub": true, "codex_sub": false, "gemini": false }
}
```

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
  "can_save": true
}
```

- Zugänge kommen **immer leer** zurück; ob einer hinterlegt ist, steht in `secrets_set`. Das ist
  dieselbe Auskunft, die `GET /status` ohnehin gibt.
- `stored_revision` ist der Fingerabdruck des gespeicherten Stands und wird beim Speichern
  zurückgeschickt.
- `can_save` ist nur `true`, wenn das Add-on in Home Assistant läuft **und** der Aufruf über den
  Ingress kam. Sonst zeigt die Oberfläche die Werte nur an.
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
| `provider` | `claude_sub`, `codex_sub` oder `gemini` |
| `model` | `auto` oder ein Modell **des gewählten Anbieters** aus `GET /models` |
| `tool_access` | `off`, `web` oder `full` |
| Zugänge | fehlt oder `""` = unverändert, `null` = entfernen, sonst neuer Wert. `codex_auth_json` muss ein JSON-Objekt sein |

Fehlende Felder bleiben unverändert; unbekannte Felder werden ignoriert.

**Nur über den Ingress.** Aufrufe über Port 8000 werden mit `403` abgelehnt — sonst könnte jeder,
der den Port erreicht, die Werkzeugstufe `full` setzen und damit an die Zugänge kommen. Geprüft
wird die Absenderadresse des Ingress-Proxys, nicht ein Kopf; Begründung als D-015 in
[design-entscheidungen.md](design-entscheidungen.md).

**Antwort `200`** — wie `GET /settings`, mit dem neuen Stand.

## `GET /health`

```json
{ "status": "ok" }
```

Antwortet, sobald der Prozess läuft. Der Watchdog des Add-ons hängt an diesem Endpunkt
(`config.yaml`) und startet das Add-on neu, wenn er ausbleibt.

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
| Home Assistant Supervisor | `GET /addons/self/info`, `POST /addons/self/options/validate`, `POST /addons/self/options`, Zeitlimit 10 s, ohne Proxy | Einstellungen lesen und speichern | Lesen: Rückfall auf `/data/options.json`, Seite nur zur Anzeige. Speichern: Meldung „nicht erreichbar“ bzw. „nicht übernommen“, Meldung des Supervisors nur im Log |

Alle Aufrufe haben ein ausdrückliches Zeitlimit und ein definiertes Verhalten im Fehlerfall.
Welche Daten dabei das Haus verlassen: [sicherheit-datenschutz.md](sicherheit-datenschutz.md).
