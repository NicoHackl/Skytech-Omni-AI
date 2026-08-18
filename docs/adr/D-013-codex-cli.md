# D-013: ChatGPT wird über die Codex-CLI angesprochen, die Anmeldung als eingefügte `auth.json`

- **Datum:** 18.08.2026
- **Status:** Aktiv
- **Betrifft:** `providers/codex_sub_provider.py`, `config_loader.py`, `Dockerfile`, `config.yaml`

## Kontext

Für Claude gilt seit D-006: nur der Umweg über die Befehlszeile zählt eine Anfrage auf das Abo,
ein API-Schlüssel wird nach Verbrauch abgerechnet. Für ChatGPT stellte sich dieselbe Frage. Sie
lässt sich genauso beantworten: OpenAI liefert mit der Codex-CLI ein Werkzeug, das sich mit dem
ChatGPT-Konto anmeldet und dann auf dessen Kontingent zählt, und mit `codex exec` einen Betrieb
ohne Bildschirm.

Ein Unterschied bestimmt den Entwurf. Für Claude gibt es `claude setup-token`: ein einzelnes,
langlebiges Token, das man in ein Feld einträgt und das dort stehen bleibt. Für Codex gibt es das
**nicht**. Die CLI legt ihren Anmeldezustand als Datei `auth.json` unter `$CODEX_HOME` ab,
**erneuert die Tokens im Betrieb selbst und schreibt die Datei dabei zurück**. Eine Anmeldung
besteht also nicht aus einem Wert, sondern aus einem Zustand, der sich verändert.

## Betrachtete Optionen

### Option A — OpenAI-API mit Schlüssel

- Dafür: Ein HTTPS-Aufruf wie bei Gemini, keine zusätzliche Laufzeit im Bild, zugesichertes Format,
  läuft auf jeder Architektur.
- Dagegen: Wird nach Verbrauch abgerechnet und rührt das vorhandene Abo nicht an — genau das, was
  vermieden werden soll.

### Option B — Geräte-Anmeldung aus der Oberfläche heraus

- Dafür: Kein Kopieren von Zugangsdaten. Der Betreiber klickt einen Knopf, meldet sich am Handy an.
- Dagegen: Die CLI müsste interaktiv gesteuert, ihr Zustand abgefragt und in zwei zusätzlichen
  Endpunkten abgebildet werden. Deutlich mehr bewegliche Teile für einen Vorgang, der einmal
  stattfindet.

### Option C — `auth.json` einmalig einfügen

- Dafür: Gleiche Bauart wie das Claude-Feld, ein Feld in der Konfiguration, kein zusätzlicher
  Endpunkt. Die Anmeldung entsteht dort, wo ohnehin ein Browser ist.
- Dagegen: Der Betreiber hantiert einmalig mit einer Datei, die Tokens enthält. Und: der Wert in
  der Konfiguration veraltet, sobald die CLI die Tokens erneuert.

## Entscheidung

Option C, mit Option A als ausdrücklichem Rückfall (`openai_api_key`) — parallel zu D-006.
Option B ist nicht verworfen, sondern zurückgestellt: sie ist Komfort für einen einmaligen
Vorgang, der Rest des Add-ons hat davon nichts.

Untrennbar zur Entscheidung gehört, **wie** der eingetragene Wert abgelegt wird: Der Provider
schreibt ihn nur dann nach `$CODEX_HOME/auth.json`, wenn sich sein Fingerabdruck gegenüber der
Marke `.seed` daneben geändert hat. Würde bei jedem Start blind geschrieben, ersetzte der alte
Stand aus der Konfiguration regelmäßig die von der CLI aufgefrischten Tokens — die Anmeldung liefe
ab, obwohl sie gültig war. Umgekehrt muss ein **neu** eingetragener Wert sich durchsetzen, sonst
ließe sich ein abgelaufener Zugang nie ersetzen. Der Fingerabdruck unterscheidet genau diese
beiden Fälle.

Ebenfalls Teil der Entscheidung:

- `CODEX_HOME=/data/.codex`, damit die Anmeldung einen Neustart übersteht — dieselbe Falle wie
  seinerzeit `HOME` bei Claude.
- Der Aufruf läuft mit `--cd /data`: aus dem Quellbaum heraus läse die CLI eine `AGENTS.md` und
  deutete die Anfrage als Programmieraufgabe um.
- `codex exec` kennt kein `--append-system-prompt`. Die Rolle „JSON-Endpunkt“ wird dem Prompt
  deshalb vorangestellt.
- Der Prompt geht über die Standardeingabe, nicht als Argument: Argumente stehen in der
  Prozessliste.
- Werkzeug-Freigabe (`--sandbox`, `--search`) steht **vor** dem Unterbefehl `exec` — `--search`
  kennt nur der Hauptbefehl.
- Der Rückfall über `openai_api_key` braucht keinen eigenen Anmeldeschritt: `codex exec` nimmt
  den Schlüssel aus der Umgebungsvariablen `OPENAI_API_KEY` (an Fassung 0.147.0 geprüft).

## Folgen

- **Positiv:** Anfragen an ChatGPT kosten nichts über das Abo hinaus. Der Anbieter fügt sich ohne
  Änderung an `app.py` ein (D-005), und die Werkzeugstufe aus D-012 gilt für beide Befehlszeilen.
- **Negativ:** Eine zweite Befehlszeile im Bild und ein zweiter Unterprozess-Pfad, der nur mit
  Attrappe getestet ist. Die Werkzeugstufen bilden bei Codex etwas anderes ab als bei Claude — dort
  eine Liste einzelner Werkzeuge, hier eine Sandbox-Stufe; in der Stufe `web` sind lesende Befehle
  im Container damit möglich, siehe [../sicherheit-datenschutz.md](../sicherheit-datenschutz.md).
  Und: die CLI gibt es nur für 64 Bit, was D-014 nach sich zieht.
- **Aufwand:** Erledigt.

## Rücknahmebedingung

Wenn OpenAI einen Weg anbietet, das Abo-Kontingent unmittelbar über eine Schnittstelle
anzusprechen, entfällt der Grund für den Umweg. Ebenso, wenn `codex exec` sein Verhalten mehrfach
so ändert, dass die Antworten unbrauchbar werden — oder wenn die Anmeldung über die eingefügte
Datei wiederholt abläuft, obwohl der Zustand unter `/data` erhalten blieb: dann ist die
Geräte-Anmeldung (Option B) fällig.
