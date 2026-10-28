# D-025: Git-Ablauf `dev/dev` → `dev/main` → Pull Request → `main` mit Release nach dem Merge

- **Datum:** 28.10.2026
- **Status:** Aktiv — ersetzt [D-017](D-017-release-branch.md)
- **Betrifft:** `.github/workflows/ci.yaml`, `.github/workflows/release.yaml`,
  `scripts/release.py`, `.github/dependabot.yml`, `.github/workflows/codeql.yaml`, Branches
  `dev/dev`, `dev/main`, `main`

## Kontext

D-017 machte jeden grünen Push auf `agent/main` mit Änderung am Add-on zu einem Release: die CI
schrieb den Release-Commit selbst nach `main`. Das war bequem, aber der User hatte keinen
Zeitpunkt, an dem er einen Stand vor der Veröffentlichung prüfen und freigeben konnte. Für
alle Skytech-Repos gilt inzwischen ein einheitlicher Ablauf: Arbeitsbranch `dev/dev`, geprüfte
Zwischenstände auf `dev/main`, Freigabe durch den User per Pull Request nach `main`.

## Betrachtete Optionen

### Option A — Release nach dem Merge des Pull Requests

- Dafür: der User gibt frei, bevor Nutzer das Update sehen; `dev/dev` und `dev/main` bleiben reiner
  Quellstand mit `version: "dev"`; der Release-Commit-Mechanismus aus D-017 bleibt erhalten.
- Dagegen: ein zusätzlicher Workflow und ein Merge-Commit-Zwang (bei Squash gehen die
  Trailer einzelner Commits verloren).

### Option B — Release-Commit schon in `dev/main`

- Dafür: Der Pull Request enthielte fertige Release-Stände.
- Dagegen: `dev/main` bekäme Version und Changelog, die es auf `dev/dev` nicht gibt; die
  Einseitigkeit `dev/dev` → `dev/main` bräche, sobald beide auseinanderlaufen.

### Option C — Release von Hand

- Dafür: volle Kontrolle.
- Dagegen: Versionssprung und Changelog sind fehleranfällig, genau das hatte D-016 gelöst.

## Entscheidung

Option A.

- Push auf `dev/dev` → alle Prüfungen → bei grün schiebt der Job `nach-dev-main` per Fast-Forward
  nach `dev/main`.
- Vorhaben abgeschlossen → **ein** Pull Request `dev/main` → `main`, vom User freigegeben, als
  Merge-Commit gemergt.
- Der Merge löst `release.yaml` aus. Bezugsstand ist der erste Elternteil des Merge-Commits
  (`RELEASE_BASE_REF`), neu sind die Commits des zweiten Elternteils. Der Release-Commit hat den
  Merge-Commit als Elternteil.
- Dependabot zielt auf `dev/dev`.

## Folgen

- **Positiv:** keine ungewollte Veröffentlichung; ein klarer Freigabepunkt.
- **Negativ:** Release-Commits liegen nur auf `main`, `main` ist weiterhin kein Vorfahr von
  `dev/main` (siehe [bekannte-luecken.md](../bekannte-luecken.md)). Pull Requests müssen als
  Merge-Commit gemergt werden.
- **Einmalig auf GitHub:** Branches `dev/dev` und `dev/main` anlegen, alte Branches entfernen,
  Ruleset von `main` auf „Pull Request mit Freigabe, Ausnahme nur Deploy-Key" stellen, nur
  Merge-Commits erlauben.

## Rücknahmebedingung

Squash-Merges werden gewünscht oder `dev/main` soll Release-Commits enthalten → neue Entscheidung,
diese auf „Ersetzt".
