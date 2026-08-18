# D-008: waitress als WSGI-Server statt des Entwicklungsservers von Flask

- **Datum:** 18.08.2026
- **Status:** Aktiv
- **Betrifft:** `app.py`, `requirements.txt`

## Kontext

Das Add-on lief bisher mit `app.run(host="0.0.0.0", port=8000)`. Das ist der Entwicklungsserver
von Flask: er ist einfädig, hat kein Zeitlimit für hängende Verbindungen, warnt beim Start selbst
davor, so betrieben zu werden — und ein Add-on läuft dauerhaft. Anfragen an Claude dauern zudem bis
zu 300 Sekunden; währenddessen blockiert der Entwicklungsserver alles andere, auch den Aufruf des
Watchdogs auf `/health`.

Randbedingung: Das Bild ist Alpine-basiert (musl) und wird für aarch64, amd64, armv7, armhf und
i386 gebaut. Alles, was eine Werkzeugkette zum Übersetzen braucht, ist dort teuer bis unmöglich.

## Betrachtete Optionen

### Option A — Beim Entwicklungsserver bleiben

- Dafür: Keine zusätzliche Abhängigkeit, kein Aufwand.
- Dagegen: Eine Anfrage blockiert den Prozess. Der Watchdog antwortet dann nicht und startet das
  Add-on mitten in einer laufenden Anfrage neu. Die Warnung im Log bleibt dauerhaft stehen.

### Option B — gunicorn

- Dafür: Weit verbreitet, gut dokumentiert.
- Dagegen: Setzt auf `fork` und Signalbehandlung, unter Alpine mit mehr Feinabstimmung verbunden;
  bringt zusätzliche Konfiguration mit, die für vier Endpunkte niemand pflegen will.

### Option C — uvicorn

- Dafür: Modern, schnell.
- Dagegen: ASGI. Flask ist WSGI; es bräuchte eine Zwischenschicht, ohne dass das Projekt etwas
  Asynchrones täte.

### Option D — waitress

- Dafür: Reines Python, keine Übersetzung, läuft damit auf jeder gebauten Architektur. Mehrfädig,
  eine Zeile zum Starten, keine eigene Konfigurationsdatei.
- Dagegen: Weniger verbreitet als gunicorn; bei sehr hoher Last langsamer — was hier keine Rolle
  spielt, es geht um einzelne Anfragen aus einem Haushalt.

## Entscheidung

Option D. Entscheidend ist die Mehrfädigkeit: `/health` und die Oberfläche müssen antworten, während
eine Anfrage an ein Modell läuft. Dass waitress reines Python ist, macht es zur einzigen Option, die
ohne Zusatzaufwand auf armv7 und armhf durchbaut.

## Folgen

- **Positiv:** Der Watchdog bekommt auch während einer langen Anfrage eine Antwort und startet das
  Add-on nicht grundlos neu. Die Oberfläche bleibt bedienbar. Die Warnung im Log ist weg.
- **Negativ:** Eine Laufzeit-Abhängigkeit mehr, die gepflegt und aktualisiert werden muss.
- **Aufwand:** Erledigt — `waitress==3.0.2` in `requirements.txt`, `serve(...)` in `app.py`.

## Rücknahmebedingung

Wenn das Add-on einmal mehr als einzelne Anfragen bedienen soll und waitress dabei zum Engpass wird
— messbar an Anfragen, die in der Warteschlange stehen, obwohl kein Modell arbeitet. Dann ist
gunicorn mit mehreren Arbeitern der nächste Schritt.
