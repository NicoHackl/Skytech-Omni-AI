# Skytech OmniAI

Ein modulares **Home Assistant Add-on**, das als universelle Brücke zwischen deinem Smart Home und verschiedenen KI-Modellen (Large Language Models) fungiert. 

Das Kern-Feature zum Start ist die Integration des regulären **Claude Pro/Max Web-Abos** über die offizielle Claude CLI. Dies ermöglicht es, komplexe KI-Anfragen direkt aus Home Assistant heraus zu stellen, strukturierte JSON-Antworten zu erhalten und dabei das bestehende Abo-Limit zu nutzen – komplett ohne zusätzliche API-Kosten.

## 🚀 Features & Architektur

*   **Striktiv Modular:** Über ein Factory-Pattern können zukünftig problemlos weitere Provider wie OpenAI (ChatGPT), Google Gemini oder lokale LLMs (Ollama) per API oder Web-Schnittstelle angebunden werden.
*   **Abo-Limit Trigger:** Der Claude-Subscription-Provider nutzt die offizielle CLI, wodurch bei jeder Anfrage dein rollierendes 5-Stunden-Web-Limit gestartet und genutzt wird.
*   **Persistent Sessions:** Die Login-Session von Claude Code wird im geschützten `/data`-Verzeichnis von Home Assistant gespeichert und bleibt auch nach Add-on-Neustarts erhalten.
*   **JSON-First:** Alle Provider sind darauf ausgelegt, saubere, strukturierte JSON-Daten ohne störende Markdown-Formatierung an Home Assistant zurückzuliefern.

## 📂 Projektstruktur

```text
Skytech-Omni-AI/            # Repo-Root = Add-on-Root (Home Assistant Add-on Repository)
├── config.yaml          # Home Assistant Add-on Konfiguration
├── Dockerfile           # Docker-Umgebung (Node.js, Python, Claude CLI)
├── CHANGELOG.md         # Protokoll aller Änderungen (automatisch gepflegt)
├── info.md                 # Diese Projektdokumentation
├── app.py               # Flask-Webserver (Schnittstelle zu Home Assistant)
└── providers/
    ├── __init__.py
    ├── base_provider.py # Abstraktes Fundament für alle KIs
    ├── factory.py       # Steuert, welche KI geladen wird
    └── claude_sub_provider.py # Der Sonderfall: Claude über das Web-Abo
