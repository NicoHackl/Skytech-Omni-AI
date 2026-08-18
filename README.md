# Skytech OmniAI

Home-Assistant-Add-on und modulare Brücke zwischen dem Smart Home und mehreren KI-Anbietern. Es
nimmt Prompts über eine HTTP-Schnittstelle entgegen, leitet sie an **Claude** (über das
Pro/Max-Abo, nicht über einen nach Verbrauch abgerechneten Schlüssel) oder an **Google Gemini**
weiter und liefert geprüftes JSON zurück. Eine Weboberfläche in Home Assistant zeigt den Zustand
und erlaubt Testanfragen.

## Installation

1. In Home Assistant unter **Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories** die
   Adresse `https://github.com/NicoHackl/Skytech-Omni-AI` hinzufügen.
2. **Skytech OmniAI** installieren.
3. Unter **Konfiguration** einen Zugang hinterlegen (siehe unten) und das Add-on starten.

## Zugang einrichten

### Claude über das Abo

Ein Add-on hat keinen Browser, der übliche Anmeldevorgang von Claude scheidet damit aus.
Stattdessen wird einmalig ein langlebiges Token erzeugt — auf einem Rechner, an dem die Anmeldung
im Browser möglich ist:

```bash
npm install -g @anthropic-ai/claude-code
claude setup-token
```

Das Ergebnis im Add-on unter **Konfiguration → `claude_oauth_token`** eintragen und das Add-on neu
starten.

> Alternative: Unter `anthropic_api_key` lässt sich ein Anthropic-Schlüssel hinterlegen. Der wird
> nach Verbrauch abgerechnet und nutzt das Abo **nicht**.

### Google Gemini

Unter <https://aistudio.google.com/apikey> einen Schlüssel erzeugen, ihn unter
**Konfiguration → `gemini_api_key`** eintragen, `provider` auf `gemini` stellen und das Add-on neu
starten.

## Nutzung

### Oberfläche

Nach dem Start erscheint **OmniAI** in der Seitenleiste von Home Assistant: Übersicht über
Anbieter, Standardmodell und hinterlegte Zugänge, eine Seite für Testanfragen und eine
Modellübersicht. Hell- und Dunkel-Modus lassen sich in der Kopfzeile umschalten.

### Aus einer Automatisierung

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

# Welche Anbieter und Modelle gibt es?
curl http://<HA-IP>:8000/models
```

Vollständige Beschreibung der Endpunkte: [docs/api-referenz.md](docs/api-referenz.md).

> **Hinweis:** Port 8000 ist nicht durch ein Passwort geschützt. Er gehört ins Heimnetz und nicht
> ins Internet. Wer nur die Oberfläche nutzt, kann ihn schließen — der Ingress funktioniert ohne
> ihn. Siehe [docs/sicherheit-datenschutz.md](docs/sicherheit-datenschutz.md).

## Entwicklung

```bash
pip install -r skytech_omniai/requirements.txt -r requirements-dev.txt
npm ci --prefix skytech_omniai/web

python skytech_omniai/app.py                    # Schnittstelle auf Port 8000
npm run dev --prefix skytech_omniai/web         # Oberfläche auf Port 5174

pytest                                          # Tests
ruff check . && ruff format --check .           # Linting
npm run typecheck --prefix skytech_omniai/web   # Typprüfung
docker build -t skytech-omniai skytech_omniai   # Add-on-Bild bauen
```

Vor dem ersten Commit lesen: [CONTRIBUTING.md](CONTRIBUTING.md).

## Dokumentation

| Wofür | Wo |
|---|---|
| Verbindliche Projektregeln (Menschen **und** KI-Agenten) | [AGENTS.md](AGENTS.md) |
| Technische Referenz | [docs/README.md](docs/README.md) |
| Beschreibung im Add-on-Store | [skytech_omniai/info.md](skytech_omniai/info.md) |
| Änderungen je Version | [CHANGELOG.md](CHANGELOG.md) |

## Lizenz

Privates Projekt, keine Lizenz erteilt.
