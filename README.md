# Skytech OmniAI

[![CI](https://github.com/NicoHackl/Skytech-Omni-AI/actions/workflows/ci.yaml/badge.svg?branch=agent%2Fmain)](https://github.com/NicoHackl/Skytech-Omni-AI/actions/workflows/ci.yaml)

Home-Assistant-Add-on und modulare Brücke zwischen dem Smart Home und mehreren KI-Anbietern. Es
nimmt Prompts über eine HTTP-Schnittstelle entgegen, leitet sie an **Claude** (über das
Pro/Max-Abo), **ChatGPT** (über das ChatGPT-Abo) oder **Google Gemini** (über das Google-AI-Pro-Abo
oder mit Schlüssel) weiter und liefert geprüftes JSON zurück — bei Claude, ChatGPT und Gemini
(Abo) über das jeweilige Abo statt über einen nach Verbrauch abgerechneten Schlüssel. Eine Weboberfläche in Home Assistant zeigt den Zustand
und erlaubt Testanfragen.

## Installation

Voraussetzung: ein **64-Bit-System** (`amd64` oder `aarch64`).

1. In Home Assistant unter **Einstellungen → Add-ons → Add-on-Store → ⋮ → Repositories** die
   Adresse `https://github.com/NicoHackl/Skytech-Omni-AI` hinzufügen.
2. **Skytech OmniAI** installieren.
3. Das Add-on starten, in der Seitenleiste **OmniAI → Einstellungen** öffnen und einen Zugang
   hinterlegen (siehe unten). Gespeichertes gilt sofort, ohne Neustart. Der Reiter
   **Konfiguration** des Add-ons zeigt dieselben Werte und funktioniert weiterhin.

## Zugang einrichten

### Claude über das Abo

Ein Add-on hat keinen Browser, der übliche Anmeldevorgang von Claude scheidet damit aus.
Stattdessen wird einmalig ein langlebiges Token erzeugt — auf einem Rechner, an dem die Anmeldung
im Browser möglich ist:

```bash
npm install -g @anthropic-ai/claude-code
claude setup-token
```

Das Ergebnis unter **Einstellungen → Token des Claude-Abos** eintragen und speichern.

> Alternative: Unter `anthropic_api_key` lässt sich ein Anthropic-Schlüssel hinterlegen. Der wird
> nach Verbrauch abgerechnet und nutzt das Abo **nicht**.

### ChatGPT über das Abo

Für ChatGPT gibt es kein einzelnes Token. Die Anmeldung entsteht auf einem Rechner mit Browser und
wird als Datei eingefügt:

```bash
npm install -g @openai/codex
codex login          # Anmeldung mit dem ChatGPT-Konto, nicht mit einem API-Schlüssel
cat ~/.codex/auth.json
```

Den vollständigen Inhalt unter **Einstellungen → Anmeldung des ChatGPT-Abos** einfügen, als
Anbieter „ChatGPT (Abo)“ wählen und speichern. Das Add-on schreibt die Anmeldung nur dann neu,
wenn sich der eingetragene Wert ändert — die Codex-Befehlszeile frischt ihre Tokens sonst selbst
auf.

> Alternative: Unter `openai_api_key` lässt sich ein OpenAI-Schlüssel hinterlegen. Der wird nach
> Verbrauch abgerechnet und nutzt das Abo **nicht**.

### Google Gemini mit Schlüssel

Unter <https://aistudio.google.com/apikey> einen Schlüssel erzeugen, ihn unter
**Einstellungen → Gemini-Schlüssel** eintragen, als Anbieter „Google Gemini“ wählen und speichern.
Das ist der von Google vorgesehene Weg; er wird nach Verbrauch abgerechnet.

### Google Gemini über das Google-AI-Pro-Abo

Unter **Einstellungen → Google-Anmeldung (Abo)** auf „Mit Google anmelden“ klicken, die Google-Seite
öffnen, mit dem Konto anmelden, das Google AI Pro hat, den angezeigten Code kopieren und einfügen
(Google lässt dafür etwa eine Minute Zeit). Danach als Anbieter „Google Gemini (Abo)“ wählen und
speichern. Die Anmeldung entsteht im Add-on selbst und bleibt gespeichert. Mit „Weiteres Konto
anmelden“ lassen sich mehrere Google-Konten anmelden; ist das Kontingent eines Kontos aufgebraucht,
nimmt das Add-on das nächste. Die Modelle (z. B.
*Gemini 4 Argon*, *Gemini 3.8 Flash*) liest das Add-on von Google ein; pro Anfrage genügt im Feld
`model` auch eine Kurzform wie `flash-3.8` oder `argon-4`.

> **Risiko:** Google unterstützt es bei privaten Abos nicht, die Antigravity-Befehlszeile über
> andere Anwendungen zu nutzen, und kann Konten dafür einschränken oder sperren. Das automatische
> Wechseln zwischen Konten nennt Google ausdrücklich nicht unterstützt; mit jedem Konto steigt das
> Risiko, und eine Maßnahme kann alle treffen. Die Nutzung
> geschieht auf eigenes Risiko — am besten mit einem Konto, dessen Verlust nicht schmerzt. Hintergrund:
> [D-022](docs/adr/D-022-gemini-abo-antigravity.md).

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

# ChatGPT über das Abo
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "codex_sub", "model": "gpt-5.6-luna",
       "prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# Gemini mit ausdrücklichem Modell
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"provider": "gemini", "model": "gemini-3.6-flash",
       "prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# Welche Anbieter und Modelle gibt es?
curl http://<HA-IP>:8000/models
```

Vollständige Beschreibung der Endpunkte: [docs/api-referenz.md](docs/api-referenz.md).

### Nachschlagen statt raten

Damit Claude oder ChatGPT Wetter, Nachrichten oder Preise beantworten können, braucht die
Befehlszeile eine ausdrückliche Freigabe — ohne sie benutzt sie im Add-on **kein** Werkzeug. Die
Option `tool_access` steht deshalb auf `web` (Websuche und Seitenabruf). `full` gibt zusätzlich Befehle
und Dateizugriff im Add-on frei und gehört nur in Sonderfälle; `off` schaltet alles ab.
Einzelheiten: [skytech_omniai/info.md](skytech_omniai/info.md) und
[docs/sicherheit-datenschutz.md](docs/sicherheit-datenschutz.md).

> **Hinweis:** Port 8000 ist nicht durch ein Passwort geschützt. Er gehört ins Heimnetz und nicht
> ins Internet. Wer nur die Oberfläche nutzt, kann ihn schließen — der Ingress funktioniert ohne
> ihn. Siehe [docs/sicherheit-datenschutz.md](docs/sicherheit-datenschutz.md).

## Entwicklung

```bash
pip install -r skytech_omniai/requirements.txt -r requirements-dev.txt
npm ci --prefix skytech_omniai/web

python skytech_omniai/app.py                    # Schnittstelle auf Port 8000
npm run dev --prefix skytech_omniai/web         # Oberfläche auf Port 5174

git config core.hooksPath .githooks             # einmalig: commit-msg- und pre-push-Hook
scripts/check.sh                                # alle Prüfungen wie in der CI
scripts/check.sh --docker                       # zusätzlich Bild bauen und Smoke-Test
```

Gearbeitet wird auf `agent/main`. Jeder grüne Push mit Änderung am Add-on wird automatisch
veröffentlicht: die CI setzt Version und Changelog und schreibt `main` — von Hand wird dort nichts
geändert. Changelog-Einträge stehen als Trailer im Commit. Ablauf:
[docs/git-workflow.md](docs/git-workflow.md). Vor dem ersten Commit lesen:
[CONTRIBUTING.md](CONTRIBUTING.md).

## Dokumentation

| Wofür | Wo |
|---|---|
| Verbindliche Projektregeln (Menschen **und** KI-Agenten) | [AGENTS.md](AGENTS.md) |
| Technische Referenz | [docs/README.md](docs/README.md) |
| Beschreibung im Add-on-Store | [skytech_omniai/info.md](skytech_omniai/info.md) |
| Änderungen je Version | [skytech_omniai/CHANGELOG.md](https://github.com/NicoHackl/Skytech-Omni-AI/blob/main/skytech_omniai/CHANGELOG.md) auf `main` — auch im Update-Dialog von Home Assistant |

## Lizenz

Privates Projekt, keine Lizenz erteilt.
