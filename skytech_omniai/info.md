# Skytech OmniAI

Ein modulares **Home-Assistant-Add-on**, das als Brücke zwischen deinem Smart Home und
verschiedenen KI-Modellen dient.

Das Kern-Feature ist die Anbindung bestehender **Abos** über die offiziellen Befehlszeilen der
Anbieter: **Claude Pro/Max** und **ChatGPT**. Damit lassen sich Anfragen direkt aus Home Assistant
stellen, strukturierte JSON-Antworten zurückbekommen und dabei das jeweilige Abo-Kontingent
nutzen — ohne zusätzliche Kosten pro Anfrage.

> Voraussetzung: ein **64-Bit-System** (`amd64` oder `aarch64`).

## Was das Add-on kann

- **Vier Zugänge, gleiche Bedienung.** Angebunden sind **Claude (Abo)**, **ChatGPT (Abo)**,
  **Google Gemini (Abo)** über Google AI Pro und **Google Gemini** mit Schlüssel. Weitere Anbieter wie lokale Modelle lassen sich ergänzen, ohne dass sich für
  bestehende Automatisierungen etwas ändert.
- **Das Abo statt Kosten pro Anfrage.** Über die jeweilige Befehlszeile zählt jede Anfrage auf das
  Kontingent deines Abos.
- **Anmeldung übersteht Neustarts.** Der Anmeldezustand liegt im geschützten Datenverzeichnis des
  Add-ons.
- **Nachschlagen statt raten.** Für Claude und ChatGPT lässt sich die Websuche freigeben, damit
  Anfragen nach Wetter, Nachrichten oder Preisen mit echten Quellen beantwortet werden.
- **Immer JSON.** Alle Anbieter werden angewiesen, sauberes JSON ohne Markdown zurückzuliefern —
  und was trotzdem verpackt ankommt, wird ausgepackt.
- **Eine Oberfläche in Home Assistant.** Zustand ansehen, Testanfrage stellen, Modelle
  nachschlagen — mit Hell- und Dunkel-Modus.

## Einstellungen

Alles, was das Add-on braucht, lässt sich in seiner Oberfläche einstellen: in der Seitenleiste
von Home Assistant **OmniAI** öffnen und links **Einstellungen** wählen. Dort stehen Anbieter,
Standardmodell, Werkzeuge und alle Zugänge. Gespeichertes gilt ab der nächsten Anfrage — ein
Neustart ist nicht nötig.

Der Reiter **Konfiguration** des Add-ons zeigt dieselben Werte und funktioniert weiterhin; beide
Wege schreiben an dieselbe Stelle. Hinterlegte Zugänge zeigt die Oberfläche nur als
„Hinterlegt“ — ein leeres Feld behält sie, „Entfernen“ löscht sie.

> Beim Update auf 0.9.0 fragt Home Assistant einmal nach der Berechtigung „manager“. Ohne sie darf
> das Add-on seine eigenen Einstellungen nicht speichern.

## Einrichtung — Claude (Abo)

Ein Add-on läuft **ohne Bildschirm**; der Anmeldevorgang von Claude über den Browser ist dort nicht
möglich. Stattdessen wird ein langlebiges **Token** deines Pro/Max-Abos verwendet:

1. **Token erzeugen** — auf einem Computer, an dem du dich im Browser bei Claude anmelden kannst:

   ```bash
   npm install -g @anthropic-ai/claude-code
   claude setup-token
   ```

   Die Anmeldung öffnet sich im Browser, anschließend wird ein Token ausgegeben.
2. **Token eintragen** — in der Seitenleiste unter **OmniAI → Einstellungen** in das Feld „Token des Claude-Abos“
   einfügen und speichern. Ein Neustart ist nicht nötig.

> **Alternative (kostenpflichtig):** Statt des Abos kann unter `anthropic_api_key` ein
> Anthropic-Schlüssel hinterlegt werden. Der wird nach Verbrauch abgerechnet und nutzt das Abo
> **nicht**.

Ohne eines der beiden Felder antwortet das Add-on mit einer Meldung, die sagt, was zu tun ist.

## Einrichtung — ChatGPT (Abo)

Für ChatGPT gibt es **kein** einzelnes Token zum Eintragen: die Codex-Befehlszeile speichert ihre
Anmeldung als Datei und frischt sie im Betrieb selbst auf. Deshalb wird diese Datei einmalig
eingefügt.

1. **Anmelden** — auf einem Computer, an dem du dich im Browser bei ChatGPT anmelden kannst:

   ```bash
   npm install -g @openai/codex
   codex login
   cat ~/.codex/auth.json
   ```

   Wichtig: mit dem **ChatGPT-Konto** anmelden, nicht mit einem API-Schlüssel — nur so zählen die
   Anfragen auf dein Abo.
2. **Inhalt eintragen** — den vollständigen Inhalt von `auth.json` in der Seitenleiste unter **OmniAI → Einstellungen** in das
   Feld „Anmeldung des ChatGPT-Abos“ einfügen.
3. **Anbieter wählen** — auf derselben Seite „ChatGPT (Abo)“ und ein Modell oder „Vorgabe des
   Anbieters“ wählen und speichern.

Das Add-on übernimmt den eingetragenen Wert nur, **wenn er sich geändert hat** — sonst würde jeder
Neustart die zwischenzeitlich erneuerte Anmeldung durch den alten Stand ersetzen. Meldet das
Add-on später, die Anmeldung gelte nicht mehr: Schritt 1 und 2 wiederholen.

> **Alternative (kostenpflichtig):** Statt des Abos kann unter `openai_api_key` ein
> OpenAI-Schlüssel hinterlegt werden. Der wird nach Verbrauch abgerechnet und nutzt das Abo
> **nicht**.

### Verfügbare ChatGPT-Modelle

| Modell | Beschreibung |
| --- | --- |
| `gpt-5.6-sol` | Für komplexe Aufgaben |
| `gpt-5.6-terra` | Ausgewogen, für den Alltag |
| `gpt-5.6-luna` | Schnell und günstig |
| `gpt-5.3-codex-spark` | Nur mit ChatGPT Pro |

## Einrichtung — Google Gemini über das Abo (Google AI Pro)

Die Anmeldung geschieht im Add-on selbst, einmalig:

1. In der Seitenleiste **OmniAI → Einstellungen**, Karte **Google-Anmeldung (Abo)**: **Mit Google anmelden**.
2. **Google-Seite öffnen** und mit dem Konto anmelden, das Google AI Pro hat. Am besten ist der
   Browser vorher schon bei Google angemeldet.
3. Den Code kopieren, den Google danach anzeigt, einfügen und **Anmeldung abschließen**. Google
   lässt dafür etwa eine Minute Zeit.
4. Als Anbieter **Google Gemini (Abo)** wählen und speichern.

Die Anmeldung bleibt gespeichert und wird vom Add-on erneuert. **Abmelden** entfernt sie wieder.
Ein Modell lässt sich pro Anfrage über das Feld `model` nennen; ohne Angabe wählt Google selbst.

> **Risiko:** Google unterstützt es bei privaten Abos nicht, die Antigravity-Befehlszeile über
> andere Anwendungen zu nutzen, und kann Konten dafür einschränken oder sperren. Die Nutzung
> geschieht auf eigenes Risiko — am besten mit einem Konto, dessen Verlust nicht schmerzt. Bei
> privaten Konten gelten außerdem die Datenbedingungen für Verbraucher: Was im Prompt steht, kann
> Google zur Verbesserung nutzen.

## Einrichtung — Google Gemini mit Schlüssel

Der von Google vorgesehene Weg: ein Schlüssel (nach Verbrauch abgerechnet, kein Abo-Modell).

1. **Schlüssel erzeugen** unter <https://aistudio.google.com/apikey>.
2. **Schlüssel eintragen** in der Seitenleiste unter **OmniAI → Einstellungen** in das Feld „Gemini-Schlüssel“.
3. **Anbieter und Modell wählen** — auf derselben Seite „Google Gemini“ und ein Modell oder
   „Vorgabe des Anbieters“ wählen und speichern.

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

Das Standardmodell legt nur den **add-on-weiten Standard** fest. In den Einstellungen stehen nur
die Modelle des gewählten Anbieters zur Auswahl; im Reiter „Konfiguration“ ist `model` dagegen ein
**gemeinsames Auswahlfeld** für alle Anbieter:

- `auto` — kein Modell erzwingen, der Anbieter entscheidet selbst.
- `sonnet` / `opus` / `haiku` — gehören zu `claude_sub`.
- `gpt-*` — gehören zu `codex_sub`.
- `gemini-*` — gehören zu `gemini`.
- `gemini_sub` hat keine feste Liste; dort bleibt es bei `auto`, ein Modell wird pro Anfrage genannt.

Passen Anbieter und Modell nicht zusammen, sagt das Add-on das im Klartext. **Pro Anfrage** lässt
sich im Rumpf von `/ask` weiterhin jede Modellkennung setzen — auch eine, die nicht im Auswahlfeld
steht.

## Internet-Zugriff und Werkzeuge

Die Befehlszeilen laufen im Add-on **ohne Bildschirm** (`claude -p`, `codex exec`, `agy -p`). In diesem
Modus gibt es keine Rückfrage — und ohne ausdrückliche Freigabe benutzt die KI deshalb **kein**
Werkzeug, auch nicht die Websuche. Antwortet sie, sie könne nichts nachschlagen, ist also nichts
blockiert: es war nur nichts freigegeben.

Gesteuert wird das über die Option **`tool_access`**:

| Stufe | Wirkung |
| --- | --- |
| `web` | **Vorgabe.** Websuche und Seitenabruf. Reicht für Wetter, Nachrichten, Preise, Fahrpläne. |
| `full` | Zusätzlich Befehle und Dateizugriff **im Add-on**. Nur für Sonderfälle. |
| `off` | Keine Werkzeuge. Die KI antwortet allein aus ihrem Trainingswissen. |

> ⚠️ **Zu `full`:** In dieser Stufe darf die KI im Add-on Befehle ausführen und Dateien lesen —
> dort liegen auch deine Zugänge. Zusammen mit dem offenen Port 8000 ist das ein Weg, an sie zu
> kommen. Für reine Recherche genügt `web`. Wer `full` einschaltet, sollte den Port schließen und
> nur die Oberfläche nutzen.

> **Unterschied zwischen den Anbietern:** Bei Claude gibt `web` genau zwei Werkzeuge frei
> (Websuche, Seitenabruf) — Dateien lesen kann die KI in dieser Stufe nicht. Bei ChatGPT ist `web`
> eine Schutzstufe statt einer Werkzeugliste: Schreiben und eigene Netzverbindungen sind
> unterbunden, lesende Befehle im Add-on bleiben möglich. Wer auch das ausschließen will, wählt
> `off` oder nutzt `claude_sub`.

Die Stufe heißt in den Einstellungen „Werkzeuge“ und gilt nach dem Speichern sofort. Ein im
Reiter „Konfiguration“ vertippter Wert wird nicht übernommen, sondern fällt auf `web` zurück.

> **Hinweis:** `tool_access` betrifft `claude_sub`, `codex_sub` und `gemini_sub`. Bei Google Gemini
> (Abo) führt das Add-on nie Befehle aus; „Alle Werkzeuge“ wirkt dort wie „Web-Recherche“. Google
> Gemini mit Schlüssel hat keinen Web-Zugriff und antwortet allein aus seinem Trainingswissen.

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
