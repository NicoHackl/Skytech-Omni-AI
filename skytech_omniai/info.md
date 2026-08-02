# Skytech OmniAI

Ein modulares **Home Assistant Add-on**, das als universelle Brücke zwischen deinem Smart Home und verschiedenen KI-Modellen (Large Language Models) fungiert. 

Das Kern-Feature zum Start ist die Integration des regulären **Claude Pro/Max Web-Abos** über die offizielle Claude CLI. Dies ermöglicht es, komplexe KI-Anfragen direkt aus Home Assistant heraus zu stellen, strukturierte JSON-Antworten zu erhalten und dabei das bestehende Abo-Limit zu nutzen – komplett ohne zusätzliche API-Kosten.

## 🚀 Features & Architektur

*   **Striktiv Modular:** Über ein Factory-Pattern sind aktuell **Claude (Abo)** und **Google Gemini** angebunden; weitere Provider wie OpenAI (ChatGPT) oder lokale LLMs (Ollama) lassen sich problemlos ergänzen.
*   **Abo-Limit Trigger:** Der Claude-Subscription-Provider nutzt die offizielle CLI, wodurch bei jeder Anfrage dein rollierendes 5-Stunden-Web-Limit gestartet und genutzt wird.
*   **Persistent Sessions:** Die Login-Session von Claude Code wird im geschützten `/data`-Verzeichnis von Home Assistant gespeichert und bleibt auch nach Add-on-Neustarts erhalten.
*   **JSON-First:** Alle Provider sind darauf ausgelegt, saubere, strukturierte JSON-Daten ohne störende Markdown-Formatierung an Home Assistant zurückzuliefern.

## 🔑 Einrichtung / Anmeldung — Claude (Abo)

Ein Home-Assistant-Add-on läuft **headless** – der interaktive Browser-Login
von Claude (`claude login`) ist dort nicht möglich. Stattdessen wird ein
langlebiges **OAuth-Token** deines Pro/Max-Abos verwendet:

1.  **Token erzeugen** – auf einem Computer, an dem du dich im Browser bei
    Claude anmelden kannst, Claude Code installieren und ausführen:
    ```bash
    npm install -g @anthropic-ai/claude-code
    claude setup-token
    ```
    Der Login öffnet sich im Browser; anschließend wird ein Token ausgegeben.
2.  **Token eintragen** – im Add-on unter **Konfiguration → `claude_oauth_token`**
    einfügen und speichern.
3.  **Add-on neu starten.** Das Token wird beim Start als
    `CLAUDE_CODE_OAUTH_TOKEN` an die CLI übergeben.

> **Alternative (kostenpflichtig):** Statt des Abos kann unter
> `anthropic_api_key` ein Anthropic-API-Key hinterlegt werden. Dieser wird
> metered abgerechnet und nutzt **nicht** das Web-Abo.

Ohne eines der beiden Felder liefert `/ask` eine klare Fehlermeldung mit
Anleitung.

## 🔑 Einrichtung / Anmeldung — Google Gemini

Gemini wird über einen API-Schlüssel angebunden (metered, kein Abo-Modell).

1.  **Schlüssel erzeugen** – unter <https://aistudio.google.com/apikey> einen
    API-Key für Google AI Studio anlegen.
2.  **Schlüssel eintragen** – im Add-on unter **Konfiguration →
    `gemini_api_key`** einfügen.
3.  **Provider und Modell wählen** – `provider` auf `gemini` stellen und bei
    `model` einen `gemini-*`-Eintrag auswählen (oder `auto` für den Standard).
4.  **Add-on neu starten.**

Technisch spricht das Add-on Googles **Interactions API**
(`POST /v1beta/interactions`) an — seit 2026 Googles primäre Schnittstelle.
Der Verlauf wird dabei bewusst **nicht** bei Google gespeichert (`store: false`).

### Verfügbare Gemini-Modelle

| Modell-ID | Beschreibung |
| --- | --- |
| `gemini-flash-latest` | Alias, zeigt immer auf das neueste Flash-Modell (Standard) |
| `gemini-3.6-flash` | Neuestes Modell, bestes Preis-Leistungs-Verhältnis |
| `gemini-3.5-flash` | Stark bei agentischen und Coding-Aufgaben |
| `gemini-3.5-flash-lite` | Schnellstes und günstigstes 3.5er |
| `gemini-3.1-flash-lite` | Günstig, Frontier-Klasse |
| `gemini-2.5-pro` | Komplexes Reasoning |
| `gemini-2.5-flash` | Bewährtes Preis-Leistungs-Modell |
| `gemini-2.5-flash-lite` | Sparsamstes Modell |

## 🎛️ Modellauswahl

Das Feld `model` in der Add-on-Konfiguration ist ein **gemeinsames Dropdown**
für beide Provider und legt nur den **Add-on-weiten Standard** fest:

*   `auto` – kein Modell erzwingen, der Provider entscheidet selbst.
*   `sonnet` / `opus` / `haiku` – gehören zu `provider: claude_sub`.
*   `gemini-*` – gehören zu `provider: gemini`.

Passen Provider und Modell nicht zusammen, meldet `/ask` das im Klartext.
**Pro Anfrage** kann im `/ask`-Body weiterhin jede beliebige Modell-ID gesetzt
werden — auch solche, die nicht im Dropdown stehen (z. B. eine vollständige
Claude-Modell-ID oder ein brandneues `gemini-*`-Modell).

> **Hinweis beim Update von einer älteren Version:** Das `model`-Feld war früher
> ein Freitextfeld mit leerem Standardwert und ist jetzt ein Dropdown. Home
> Assistant meldet dadurch einmalig eine ungültige Konfiguration — einfach die
> Konfiguration öffnen, `auto` (oder das gewünschte Modell) auswählen und
> speichern.

### API testen

```bash
# Claude (Abo) – nutzt den in der Konfiguration gesetzten Standard
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# Gemini mit explizitem Modell
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "model": "gemini-3.6-flash",
       "prompt": "Gib mir ein JSON mit dem Feld status=ok"}'
```

### Verfügbare Provider und Modelle abfragen

```bash
curl http://<HA-IP>:8000/models
```

Liefert den aktiven Provider sowie je Provider die auswählbaren Modelle und
dessen Standardmodell (`null` = der Provider entscheidet selbst).

## 📂 Projektstruktur

```text
Skytech-Omni-AI/                    # Repo-Root = Add-on-Repository
├── repository.yaml                # Manifest, das HA als Add-on-Repo erkennt
├── CHANGELOG.md                   # Protokoll aller Änderungen (automatisch gepflegt)
├── README.md
└── skytech_omniai/                # Das eigentliche Add-on (Unterordner = Pflicht)
    ├── config.yaml                # Home Assistant Add-on Konfiguration
    ├── Dockerfile                 # Docker-Umgebung (Node.js, Python, Claude CLI)
    ├── info.md                    # Diese Projektdokumentation
    ├── app.py                     # Flask-Webserver (Schnittstelle zu Home Assistant)
    ├── config_loader.py           # Liest die Add-on-Optionen aus /data/options.json
    └── providers/
        ├── __init__.py
        ├── base_provider.py       # Abstraktes Fundament für alle KIs
        ├── factory.py             # Steuert, welche KI geladen wird
        ├── claude_sub_provider.py # Der Sonderfall: Claude über das Web-Abo
        └── gemini_provider.py     # Google Gemini über die Interactions API
```
