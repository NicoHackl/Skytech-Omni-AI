# D-006: Claude wird über die Claude-Code-CLI angesprochen, nicht über die Anthropic-API

- **Datum:** 04.07.2026
- **Status:** Aktiv
- **Betrifft:** `providers/claude_sub_provider.py`, `Dockerfile`, `config.yaml`

## Kontext

Das Add-on soll KI-Anfragen aus Home Assistant beantworten, ohne dass dafür laufend Kosten
entstehen. Vorhanden ist ein Claude-Pro/Max-Abo mit einem rollierenden Fünf-Stunden-Limit. Ein
Anthropic-API-Schlüssel wäre technisch der einfachere Weg, wird aber nach Verbrauch abgerechnet und
rührt das Abo nicht an. Zusätzlich läuft ein Add-on ohne Bildschirm: der übliche Anmeldevorgang von
Claude öffnet einen Browser und ist dort nicht durchführbar.

## Betrachtete Optionen

### Option A — Anthropic-API mit Schlüssel

- Dafür: Eine HTTP-Anfrage, keine zusätzliche Laufzeit im Bild, klar zugesichertes Format.
- Dagegen: Kostet pro Anfrage Geld, obwohl ein bezahltes Abo vorliegt. Genau das war der Anlass für
  das Projekt.

### Option B — Claude-Code-CLI als Unterprozess

- Dafür: Anfragen laufen über das Abo und dessen Limit. Die CLI kann sich über ein langlebiges
  Token anmelden, das einmal auf einem Rechner mit Browser erzeugt wird — damit ist der Betrieb
  ohne Bildschirm möglich.
- Dagegen: Node und die CLI müssen ins Bild. Je Anfrage entsteht ein Unterprozess. Das Verhalten
  hängt an einem Werkzeug, dessen Ausgabeformat nicht als Schnittstelle zugesichert ist.

## Entscheidung

Option B. Der Zweck des Add-ons ist gerade, das vorhandene Abo zu nutzen; Option A würde ihn
aufheben. Option A bleibt als Ausweichweg erhalten: ist `anthropic_api_key` gesetzt und kein
Abo-Token, arbeitet dieselbe CLI gegen die abgerechnete Schnittstelle.

Zwei Punkte gehören untrennbar zur Entscheidung:

- Die CLI wird mit `cwd="/data"` gestartet. Aus einem Quellbaum heraus liest sie eine `CLAUDE.md`
  und deutet die Anfrage als Programmieraufgabe um.
- Ein zusätzlicher Systemprompt schiebt sie aus der Rolle des Programmierassistenten in die eines
  JSON-Endpunkts. Ohne ihn stellt sie Rückfragen, statt zu antworten.

## Folgen

- **Positiv:** Anfragen kosten nichts über das Abo hinaus. Die Anmeldung übersteht Neustarts, weil
  `HOME` auf das dauerhafte `/data` zeigt.
- **Negativ:** Node und npm liegen im Bild, obwohl das Add-on selbst Python ist. Ein Unterprozess
  je Anfrage ist langsamer als ein HTTP-Aufruf. Ein Verhaltenswechsel der CLI kann das Add-on
  brechen, ohne dass sich hier etwas geändert hat — deshalb ist ihre Version festgenagelt.
- **Aufwand:** Erledigt.

## Rücknahmebedingung

Wenn Anthropic eine Schnittstelle anbietet, über die sich das Abo-Limit direkt ansprechen lässt,
entfällt der Grund für den Umweg. Ebenso, wenn die CLI ihr Verhalten bei `-p` mehrfach so ändert,
dass die Antworten unbrauchbar werden — dann ist der Preis für die Ersparnis zu hoch geworden.
