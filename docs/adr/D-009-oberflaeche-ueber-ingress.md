# D-009: Die Oberfläche liefert Flask aus, der Ingress-Pfad kommt zur Laufzeit

- **Datum:** 18.08.2026
- **Status:** Aktiv
- **Betrifft:** `app.py`, `web/index.html`, `web/vite.config.ts`, `config.yaml`, `Dockerfile`

## Kontext

Das Add-on bekommt eine Weboberfläche, die Home Assistant über seinen **Ingress** einblendet. Der
Ingress hängt das Add-on unter einem Pfad wie `/api/hassio_ingress/<Kennung>/` ein. Diese Kennung
gehört zur Sitzung und ist bei jedem Öffnen eine andere. Ein Bündel mit absoluten Pfaden lädt dort
nicht: `/assets/index.js` zeigt an Home Assistant vorbei, nicht ins Add-on.

Zweite Randbedingung: Ein Add-on-Container startet genau einen Befehl. Es gibt keinen
Prozessverwalter, der nebeneinander einen Webserver und die Anwendung hochziehen würde.

## Betrachtete Optionen

### Option A — nginx im Bild, daneben die Anwendung

- Dafür: Das übliche Muster für eine SPA hinter einer Anwendung; die mitgelieferte `nginx.conf` der
  Vorlage wäre direkt verwendbar gewesen.
- Dagegen: Zwei Prozesse brauchen s6 oder einen anderen Verwalter. Für vier Endpunkte und drei
  Seiten ist das mehr Betriebsteil als Anwendung. Das Grundproblem — der wechselnde Pfad — löst es
  ohnehin nicht.

### Option B — Bündel relativ bauen, ohne `<base>`

- Dafür: Kein Server-Eingriff nötig.
- Dagegen: Relative Verweise werden gegen die **aktuelle** Adresse aufgelöst. Auf `/anfrage`
  funktioniert das noch, bei jeder tieferen Route bricht es. Eine Einschränkung, die man beim
  Anlegen der nächsten Route vergisst.

### Option C — Flask liefert das Bündel aus und setzt `<base>` aus `X-Ingress-Path`

- Dafür: Ein Prozess, ein Befehl. Der Pfad stimmt bei jeder Route und in jeder Sitzung. Home
  Assistant liefert ihn ohnehin in jedem Aufruf mit.
- Dagegen: Der Server fasst beim Ausliefern in das Markup — eine Stelle, die man verstehen muss.
  Der Wert kommt von außen und muss geprüft werden.

## Entscheidung

Option C.

- `vite.config.ts` baut mit `base: './'`, alle Verweise im Bündel sind relativ.
- `app.py` schiebt beim Ausliefern der `index.html` ein `<base href="…">` direkt hinter `<head>`.
  Der Wert stammt aus `X-Ingress-Path`; fehlt der Kopf, steht er auf `/`.
- Die `index.html` trägt selbst ein `<base href="/">`. Beim direkten Aufruf über den Port gilt es;
  bei Einbettung steht das eingesetzte davor, und im HTML gewinnt das erste `<base>`.
- Der Wert wird gegen `^/[A-Za-z0-9._~/-]*$` geprüft, bevor er ins Markup geht.
- Die Seite geht mit `Cache-Control: no-store` raus.
- Jede unbekannte Route liefert die `index.html`, damit das Routing im Browser übernimmt.

## Folgen

- **Positiv:** Ein Prozess, ein Bild, kein Prozessverwalter. Die Oberfläche funktioniert im Ingress
  und beim direkten Aufruf gleichermaßen. `nginx.conf` aus der Vorlage entfällt.
- **Negativ:** Die `index.html` wird bei jedem Aufruf gelesen und verändert — bei drei Seiten
  belanglos, aber es ist eine Zeile Serverlogik, die es sonst nicht gäbe. Wer das Bündel künftig
  anders baut, muss daran denken.
- **Aufwand:** Erledigt.

## Rücknahmebedingung

Wenn Home Assistant den Ingress-Pfad einmal stabil vergibt oder eine andere Möglichkeit anbietet,
ihn zur Bauzeit zu kennen, entfällt der Eingriff und das statische `<base>` genügt. Ebenso, wenn
die Oberfläche so wächst, dass sie einen eigenen Container verdient — dann ist Option A wieder im
Rennen, aber aus einem anderen Grund als heute.
