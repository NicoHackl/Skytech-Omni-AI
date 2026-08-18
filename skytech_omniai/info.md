# Skytech OmniAI

Ein modulares **Home-Assistant-Add-on**, das als Brücke zwischen deinem Smart Home und
verschiedenen KI-Modellen dient.

Das Kern-Feature ist die Anbindung des regulären **Claude-Pro/Max-Abos** über die offizielle
Claude-Befehlszeile. Damit lassen sich Anfragen direkt aus Home Assistant stellen, strukturierte
JSON-Antworten zurückbekommen und dabei das bestehende Abo-Limit nutzen — ohne zusätzliche Kosten
pro Anfrage.

## Was das Add-on kann

- **Zwei Anbieter, gleiche Bedienung.** Angebunden sind **Claude (Abo)** und **Google Gemini**.
  Weitere Anbieter wie OpenAI oder lokale Modelle lassen sich ergänzen, ohne dass sich für
  bestehende Automatisierungen etwas ändert.
- **Das Abo statt Kosten pro Anfrage.** Über die Claude-Befehlszeile zählt jede Anfrage auf dein
  rollierendes Fünf-Stunden-Limit.
- **Anmeldung übersteht Neustarts.** Der Anmeldezustand liegt im geschützten Datenverzeichnis des
  Add-ons.
- **Nachschlagen statt raten.** Für Claude lässt sich die Websuche freigeben, damit Anfragen
  nach Wetter, Nachrichten oder Preisen mit echten Quellen beantwortet werden.
- **Immer JSON.** Alle Anbieter werden angewiesen, sauberes JSON ohne Markdown zurückzuliefern —
  und was trotzdem verpackt ankommt, wird ausgepackt.
- **Eine Oberfläche in Home Assistant.** Zustand ansehen, Testanfrage stellen, Modelle
  nachschlagen — mit Hell- und Dunkel-Modus.

## Einrichtung — Claude (Abo)

Ein Add-on läuft **ohne Bildschirm**; der Anmeldevorgang von Claude über den Browser ist dort nicht
möglich. Stattdessen wird ein langlebiges **Token** deines Pro/Max-Abos verwendet:

1. **Token erzeugen** — auf einem Computer, an dem du dich im Browser bei Claude anmelden kannst:

   ```bash
   npm install -g @anthropic-ai/claude-code
   claude setup-token
   ```

   Die Anmeldung öffnet sich im Browser, anschließend wird ein Token ausgegeben.
2. **Token eintragen** — im Add-on unter **Konfiguration → `claude_oauth_token`** einfügen und
   speichern.
3. **Add-on neu starten.**

> **Alternative (kostenpflichtig):** Statt des Abos kann unter `anthropic_api_key` ein
> Anthropic-Schlüssel hinterlegt werden. Der wird nach Verbrauch abgerechnet und nutzt das Abo
> **nicht**.

Ohne eines der beiden Felder antwortet das Add-on mit einer Meldung, die sagt, was zu tun ist.

## Einrichtung — Google Gemini

Gemini wird über einen Schlüssel angebunden (nach Verbrauch abgerechnet, kein Abo-Modell).

1. **Schlüssel erzeugen** unter <https://aistudio.google.com/apikey>.
2. **Schlüssel eintragen** im Add-on unter **Konfiguration → `gemini_api_key`**.
3. **Anbieter und Modell wählen** — `provider` auf `gemini`, bei `model` einen `gemini-*`-Eintrag
   auswählen oder `auto` für die Vorgabe.
4. **Add-on neu starten.**

Der Verlauf wird bei Google ausdrücklich **nicht** gespeichert.

### Verfügbare Gemini-Modelle

| Modell | Beschreibung |
| --- | --- |
| `gemini-flash-latest` | Zeigt immer auf das neueste Flash-Modell (Vorgabe) |
| `gemini-3.6-flash` | Neuestes Modell, bestes Preis-Leistungs-Verhältnis |
| `gemini-3.5-flash` | Stark bei agentischen und Coding-Aufgaben |
| `gemini-3.5-flash-lite` | Schnellstes und günstigstes 3.5er |
| `gemini-3.1-flash-lite` | Günstig, Frontier-Klasse |
| `gemini-2.5-pro` | Komplexes Reasoning |
| `gemini-2.5-flash` | Bewährtes Preis-Leistungs-Modell |
| `gemini-2.5-flash-lite` | Sparsamstes Modell |

## Modellauswahl

Das Feld `model` in der Konfiguration ist ein **gemeinsames Auswahlfeld** für beide Anbieter und
legt nur den **add-on-weiten Standard** fest:

- `auto` — kein Modell erzwingen, der Anbieter entscheidet selbst.
- `sonnet` / `opus` / `haiku` — gehören zu `claude_sub`.
- `gemini-*` — gehören zu `gemini`.

Passen Anbieter und Modell nicht zusammen, sagt das Add-on das im Klartext. **Pro Anfrage** lässt
sich im Rumpf von `/ask` weiterhin jede Modellkennung setzen — auch eine, die nicht im Auswahlfeld
steht.

## Internet-Zugriff und Werkzeuge

Die Claude-Befehlszeile läuft im Add-on **ohne Bildschirm** (`claude -p`). In diesem Modus gibt es
keine Rückfrage — und ohne ausdrückliche Freigabe lehnt sie deshalb **jedes** Werkzeug ab, auch
die Websuche. Antwortet die KI, sie könne nichts nachschlagen, ist also nichts blockiert: es war
nur nichts freigegeben.

Gesteuert wird das über die Option **`tool_access`**:

| Stufe | Wirkung |
| --- | --- |
| `web` | **Vorgabe.** Websuche und Seitenabruf. Reicht für Wetter, Nachrichten, Preise, Fahrpläne. |
| `full` | Zusätzlich Befehle und Dateizugriff **im Add-on**. Nur für Sonderfälle. |
| `off` | Keine Werkzeuge. Die KI antwortet allein aus ihrem Trainingswissen. |

> ⚠️ **Zu `full`:** In dieser Stufe darf die KI im Add-on Befehle ausführen und Dateien lesen —
> dort liegt auch dein Claude-Token. Zusammen mit dem offenen Port 8000 ist das ein Weg, an das
> Token zu kommen. Für reine Recherche genügt `web`. Wer `full` einschaltet, sollte den Port
> schließen und nur die Oberfläche nutzen.

Nach dem Ändern der Option das **Add-on neu starten**. Ein vertippter Wert wird nicht übernommen,
sondern fällt auf `web` zurück.

> **Hinweis:** `tool_access` betrifft nur `provider: claude_sub`. Google Gemini hat keinen
> Web-Zugriff und antwortet allein aus seinem Trainingswissen.

### Wetterabfrage testen

```bash
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"model": "haiku",
       "prompt": "Wie wird das Wetter heute in Frauenau (94258)? Antworte als JSON mit den Feldern ort, datum, temperatur_min, temperatur_max, beschreibung, quelle."}'
```

Die Antwort dauert spürbar länger als eine Anfrage ohne Recherche: die KI sucht erst und liest
dann die Quelle.

> **Tipp:** Speziell fürs Wetter ist eine Wetter-Entität in Home Assistant (etwa DWD oder Met.no)
> schneller, zuverlässiger und verbraucht kein Abo-Kontingent. Der Web-Zugriff lohnt sich vor
> allem für alles, wofür es keine passende Integration gibt.

## Oberfläche

Nach dem Start erscheint **OmniAI** in der Seitenleiste von Home Assistant:

- **Übersicht** — aktiver Anbieter, Standardmodell, Werkzeugstufe, hinterlegte Zugänge,
  Verbindungsprüfung.
- **Anfrage** — Anbieter und Modell wählen, Prompt eingeben, Antwort ansehen.
- **Modelle** — was sich je Anbieter auswählen lässt.

Der Schalter für Hell und Dunkel sitzt oben rechts; die Wahl bleibt über das Neuladen hinweg
erhalten.

## Schnittstelle

```bash
# Anfrage stellen
curl -X POST http://<HA-IP>:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Gib mir ein JSON mit dem Feld status=ok"}'

# Anbieter und Modelle abfragen
curl http://<HA-IP>:8000/models

# Zustand abfragen (Anbieter, Version, Werkzeugstufe, Zugänge als ja/nein)
curl http://<HA-IP>:8000/status
```

> **Hinweis zur Sicherheit:** Port 8000 ist nicht durch ein Passwort geschützt. Er gehört ins
> Heimnetz und nicht ins Internet. Wer ausschließlich die Oberfläche nutzt, braucht ihn nicht.
