---
description: Changelog-Trailer für die Commit-Message aus den aktuellen Änderungen erzeugen
allowed-tools: Bash(git diff:*), Bash(git status), Bash(git log:*), Read
---

Erzeuge die Changelog-Trailer für die Commit-Message aus den aktuellen Änderungen. Eine Datei
`CHANGELOG.md` gibt es auf `dev/dev` nicht — den Changelog baut der Release-Job aus diesen
Trailern (docs/git-workflow.md, D-017).

Aktueller Stand:
- Status: !`git status --short`
- Diff: !`git diff HEAD --stat`

Vorgehen:

1. Ermittle aus dem Diff, was sich **funktional** geändert hat — nicht welche Dateien angefasst
   wurden. Reine Formatierung, Refactoring ohne Verhaltensänderung und Testanpassungen erzeugen
   keinen Eintrag.
2. Ordne jede Änderung einer Kategorie zu: `Hinzugefügt`, `Geändert`, `Veraltet`, `Entfernt`,
   `Behoben`, `Sicherheit`.
3. Formuliere je Änderung **eine** Zeile auf Deutsch, aus Sicht des Nutzers — was er jetzt anders
   erlebt, nicht wie es implementiert wurde.
4. Gib je Änderung eine Zeile `Changelog-<Kategorie>: <Eintrag>` aus, zum Einfügen am Ende der
   Commit-Message (nach einer Leerzeile). Längere Einträge laufen auf eingerückten Folgezeilen
   weiter, damit keine Zeile 72 Zeichen überschreitet. Keine Versionsnummer, kein Datum.

Ergibt der Diff keine nutzerrelevante Änderung: sag das und ändere nichts.
