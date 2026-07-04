# Skytech OmniAI

Ein modulares **Home Assistant Add-on**, das als universelle Brücke zwischen deinem Smart Home und verschiedenen KI-Modellen (Large Language Models) fungiert. 

Das Kern-Feature zum Start ist die Integration des regulären **Claude Pro/Max Web-Abos** über die offizielle Claude CLI. Dies ermöglicht es, komplexe KI-Anfragen direkt aus Home Assistant heraus zu stellen, strukturierte JSON-Antworten zu erhalten und dabei das bestehende Abo-Limit zu nutzen – komplett ohne zusätzliche API-Kosten.

## 🚀 Features & Architektur

*   **Striktiv Modular:** Über ein Factory-Pattern können zukünftig problemlos weitere Provider wie OpenAI (ChatGPT), Google Gemini oder lokale LLMs (Ollama) per API oder Web-Schnittstelle angebunden werden.
*   **Abo-Limit Trigger:** Der Claude-Subscription-Provider nutzt die offizielle CLI, wodurch bei jeder Anfrage dein rollierendes 5-Stunden-Web-Limit gestartet und genutzt wird.
*   **Persistent Sessions:** Die Login-Session von Claude Code wird im geschützten `/data`-Verzeichnis von Home Assistant gespeichert und bleibt auch nach Add-on-Neustarts erhalten.
*   **JSON-First:** Alle Provider sind darauf ausgelegt, saubere, strukturierte JSON-Daten ohne störende Markdown-Formatierung an Home Assistant zurückzuliefern.

## 🔑 Einrichtung / Anmeldung

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

### API testen

```bash
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Gib mir ein JSON mit dem Feld status=ok"}'
```

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
    └── providers/
        ├── __init__.py
        ├── base_provider.py       # Abstraktes Fundament für alle KIs
        ├── factory.py             # Steuert, welche KI geladen wird
        └── claude_sub_provider.py # Der Sonderfall: Claude über das Web-Abo
```
