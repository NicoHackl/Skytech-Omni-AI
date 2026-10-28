# D-017: main ist ein reiner Release-Branch, die CI schreibt nie nach agent/main

- **Datum:** 16.10.2026
- **Status:** Ersetzt durch [D-025](D-025-dev-workflow.md) — ersetzte zuvor [D-016](D-016-automatisches-release.md)
- **Betrifft:** `.github/workflows/ci.yaml`, `scripts/release.py`, `scripts/commit_msg.py`,
  `.githooks/`, `skytech_omniai/config.yaml` (Version), Changelog, Branch `main`

## Kontext

D-016 hat das Release automatisiert: nach grüner CI legte der Bot einen Commit mit Version und
Changelog auf `agent/main` und zog `main` per Fast-Forward nach. Schon am ersten Tag zeigte
sich der Preis: Nach jedem Release fehlte dem lokalen Stand der Bot-Commit, jeder nächste Push
wurde abgewiesen, bis `git pull --rebase` lief. Wer inzwischen einen Eintrag unter
„Unveröffentlicht“ geschrieben hatte, bekam beim Rebase einen Konflikt in `CHANGELOG.md`, weil
der Bot genau dort die Versionsüberschrift eingefügt hatte.

Außerdem lag der Changelog im Repo-Root. Home Assistant zeigt beim Update nur einen
`CHANGELOG.md` aus dem Add-on-Ordner an — die Nutzer sahen bisher keinen.

## Betrachtete Optionen

### Option A — D-016 beibehalten, `pull --rebase` automatisieren

- Dafür: keine Umstellung.
- Dagegen: ein Hook kann den abgewiesenen Push nicht selbst wiederholen; der Konflikt im
  Changelog bleibt.

### Option B — Bot schreibt nur nach `main`, Changelog als Fragment-Dateien

- Dafür: Einträge bleiben Dateien, nachträglich editierbar.
- Dagegen: der Bot darf `agent/main` nicht anfassen, also bleiben veröffentlichte Fragmente
  dort für immer liegen.

### Option C — Bot schreibt nur nach `main`, Changelog als Trailer im Commit

- Dafür: `agent/main` gehört allein den Menschen und Agenten; keine Datei, die zwei Seiten
  bearbeiten, also kein Konflikt. Der Eintrag hängt an der Änderung, die er beschreibt.
- Dagegen: nach dem Push nicht mehr korrigierbar; `main` ist kein Vorfahr von `agent/main` mehr.

## Entscheidung

**Option C.** `agent/main` enthält nur Quellstand mit `version: "dev"` (Konvention der
Community-Add-ons, der Add-on-Linter kennt sie) und keinen Changelog. Ein Release ist ein Commit
auf `main`, mit `git commit-tree` direkt aus dem geprüften Baum gebaut und mit Version und
`skytech_omniai/CHANGELOG.md` gestempelt. Elternteile: das vorige `main` und der veröffentlichte
Stand von `agent/main`. Über diesen zweiten Elternteil liefert `git merge-base` den zuletzt
veröffentlichten Stand — kein Tag, keine Zusatzdatei nötig.

Changelog-Einträge stehen als `Changelog-<Kategorie>:`-Trailer im Commit. Weil sie nach dem
Push nicht mehr änderbar sind, prüft ein commit-msg-Hook Betreff und Kategorien lokal; die CI
wiederholt die Prüfung als Warnung.

Gegen B: liegen gebliebene Fragmente sind dauerhafter Ballast, und ein Agent könnte ein schon
veröffentlichtes Fragment für unveröffentlicht halten. Gegen A: es bekämpft das Symptom.

Der Rest von D-016 gilt unverändert: Release nur bei Änderung unter `skytech_omniai/`, Version
aus Conventional Commits, Push über Deploy-Key, leerer Changelog nur als Warnung.

## Folgen

- **Positiv:** nach einem Release ist lokal nichts zu tun; kein Changelog-Konflikt mehr. Die
  Nutzer sehen den Changelog im Update-Dialog von Home Assistant. Commit-Messages werden vor dem
  Push geprüft — davon hängt die Version ab.
- **Negativ:** ein falscher Trailer bleibt stehen. `main` ist kein Vorfahr von `agent/main`;
  wer einen Branch von `main` abzweigt, hat die gestempelten Dateien darin. Die Oberfläche zeigt
  bei einem lokal gebauten Image „Version dev“.
- **Aufwand:** einmalig `CHANGELOG.md` aus dem Root entfernen (die Historie lebt auf `main`
  weiter), Version auf `dev`, Hooks und Doku umstellen.

## Rücknahmebedingung

Wenn sich falsche oder fehlende Trailer häufen — mehr als ein nachträglich ergänzter Eintrag je
Quartal —, ist der Commit der falsche Ort für den Eintrag. Dann wechselt der Changelog zu
Fragment-Dateien (Option B), das Release-Modell bleibt.
