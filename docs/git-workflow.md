# Git-Workflow

> Die Grundregel — Commit und Push ausschließlich im Branch `agent/main` — steht in
> [`AGENTS.md`](../AGENTS.md). Hier steht der ausführliche Ablauf.

## Branch-Modell

| Branch | Zweck |
|---|---|
| `agent/main` | Arbeitsbranch für KI-Agenten und laufende Entwicklung. Enthält nur Quellstand: `version: "dev"`, kein Changelog. **Nur Menschen und Agenten schreiben hier, nie die CI.** |
| `main` | Release-Branch — den installiert Home Assistant. **Schreibt ausschließlich die CI.** |
| `feature/<kurzname>` | Optional für größere, klar abgegrenzte Vorhaben |

Jeder Commit auf `main` ist ein Release: der geprüfte Stand von `agent/main`, gestempelt mit
Version (`skytech_omniai/config.yaml`) und Changelog (`skytech_omniai/CHANGELOG.md`). Er hat
zwei Elternteile — das vorige `main` und den veröffentlichten Stand von `agent/main` — und
unterscheidet sich von diesem nur in diesen beiden Dateien. Ein Ruleset sperrt `main` für alle
außer dem Release-Job und den Admins. Begründung: D-017.

Weil die CI nie nach `agent/main` schreibt, braucht es nach einem Release **kein**
`git pull --rebase`. Nötig ist es nur, wenn jemand anderes (ein zweiter Agent, ein gemergter
Dependabot-PR) inzwischen auf `agent/main` gepusht hat — dann weist Git den Push ab, und
`git pull --rebase` löst es ohne Konflikt im Changelog, denn es gibt dort keine Datei mehr.

Wird ein Merge-Konflikt pauschal zugunsten einer Seite aufgelöst („Branch X hat Vorrang"), wird
vorher geprüft, was die andere Seite dabei verliert: `git log <ziel>..<quelle>` und umgekehrt.
Eine Seite pauschal gewinnen zu lassen ist zulässig — sie ungesehen gewinnen zu lassen nicht.

## Commit-Format

[Conventional Commits](https://www.conventionalcommits.org/), Betreffzeile deutsch, max. 72 Zeichen:

```text
<typ>(<bereich>): <was sich ändert, Imperativ>

<optionaler Rumpf: warum, nicht was>

Changelog-<Kategorie>: <Eintrag aus Nutzersicht>
```

Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`.

```text
feat(planer): Vorschlagswerte je Gerät berechnen
fix(api): Zeitzone bei Tageswechsel korrigiert
docs(architektur): Datenfluss aktualisiert
```

Der Rumpf ist nur nötig, wenn das „warum" nicht aus der Betreffzeile hervorgeht.

**Der Typ bestimmt die Version** (siehe [Versionierung](#versionierung)). Ein `feat` als `fix`
getarnt ergibt die falsche Version — der Typ ist deshalb keine Stilfrage.

### Changelog-Einträge als Trailer

Der Changelog-Eintrag (eiserne Regel 4) steht **im Commit**, als Trailer am Ende des Rumpfs —
nicht in einer Datei. Kategorien: `Hinzugefügt`, `Geändert`, `Veraltet`, `Entfernt`, `Behoben`,
`Sicherheit`. Formuliert aus Nutzersicht, wie bisher. Ein Commit darf mehrere Trailer tragen;
ein langer Eintrag läuft über eingerückte Folgezeilen weiter:

```text
fix(einstellungen): Supervisor-Token im Prozess verfügbar machen

Ohne with-contenv fehlte dem Prozess die Container-Umgebung.

Changelog-Behoben: Einstellungen lassen sich in Home Assistant wieder
  speichern.
Changelog-Behoben: Die Uhrzeiten im Protokoll stimmen wieder.
```

Commits ohne nutzerrelevante Änderung (Refactoring, Tests, Doku für Entwickler) tragen keinen
Trailer. Hat ein Release gar keinen, schreibt der Release-Job „Interne Verbesserungen ohne
sichtbare Änderung.“ und warnt.

**Ein Trailer ist nach dem Push nicht mehr korrigierbar** — `agent/main` verbietet das
Umschreiben der Historie. Deshalb prüft der commit-msg-Hook Betreff und Kategorien, solange der
Commit lokal ist (vor dem Push lässt sich mit `git commit --amend` noch alles ändern). Ist doch
ein falscher Eintrag hinausgegangen, bleibt er stehen; ein ergänzender Eintrag folgt mit dem
nächsten Commit.

## Ablauf je Arbeitspaket

1. **Zuerst `git fetch origin`.** Erst danach wird gewechselt oder abgezweigt, und zwar von
   `origin/<branch>`, nie von einem lokalen Zeiger. Ein lokaler Branch kann Wochen alt sein,
   ohne dass man es ihm ansieht — genau daran ist am 18.08.2026 ein Arbeitspaket verlorengegangen:
   der Arbeitsbranch entstand aus einem veralteten lokalen Stand, der fehlende Commit war damit
   nie enthalten und wurde beim späteren Merge stillschweigend überschrieben.
2. Auf `agent/main` wechseln — existiert er lokal nicht, wird er von `origin/agent/main`
   angelegt: `git checkout agent/main 2>/dev/null || git checkout -b agent/main origin/agent/main`
3. Existiert der Branch bereits, aktuellen Stand holen: `git pull --rebase`
4. Ändern, dann `scripts/check.sh` grün bekommen — dieselben Prüfungen wie in der CI (Details:
   [test-strategie.md](test-strategie.md))
5. Betroffene `docs/`-Dateien aktualisieren
6. `git add` gezielt — **nie** `git add -A` ohne vorherige Prüfung von `git status`
7. Committen, bei nutzerrelevanter Änderung mit `Changelog-<Kategorie>:`-Trailer
8. Pushen auf `agent/main` — beim allerersten Push auf einen neuen Branch
   `git push -u origin agent/main`, danach reicht `git push`. Der pre-push-Hook führt
   `scripts/check.sh` vorher noch einmal aus.

Ein Commit bildet **eine** abgeschlossene Änderung ab. Sammelcommits über mehrere unabhängige
Themen sind nicht zulässig — sie machen ein späteres `git revert` unmöglich.

### Hooks einmalig aktivieren

```bash
git config core.hooksPath .githooks
```

| Hook | Prüft |
|---|---|
| `commit-msg` | Betreff nach Conventional Commits, Leerzeile, Kategorien der Changelog-Trailer ([`scripts/commit_msg.py`](../scripts/commit_msg.py)) |
| `pre-push` | alle Prüfungen der CI ([`scripts/check.sh`](../scripts/check.sh)) |

Im Notfall lassen sich beide mit `--no-verify` überspringen — die CI prüft trotzdem (die
Commit-Messages dort nur noch als Warnung, weil sie dann schon veröffentlicht sind).

## Versionierung

[Semantic Versioning](https://semver.org/lang/de/): `MAJOR.MINOR.PATCH`. Auf `agent/main` steht
in `skytech_omniai/config.yaml` immer `version: "dev"` — das ist die Konvention der
Home-Assistant-Community-Add-ons, und der Add-on-Linter kennt sie. Die echte Version setzt
**nur** der Release-Job ([`scripts/release.py`](../scripts/release.py)), auch Agenten setzen sie
nie. Abgeleitet wird sie aus den Commits seit dem letzten Release, die etwas unter
`skytech_omniai/` ändern:

| Teil | Wann erhöhen | Erkennungsmerkmal im Commit |
|---|---|---|
| `MAJOR` | Bricht bestehende Schnittstellen oder Datenformate | `!` hinter dem Typ (`feat(api)!: …`) oder Fußzeile `BREAKING CHANGE: …` |
| `MINOR` | Neue Funktion, abwärtskompatibel | Typ `feat` |
| `PATCH` | Alles andere: Fehlerbehebung, Refactoring, Abhängigkeiten | jeder andere Typ, auch ein Betreff ohne Konvention |

Der höchste Sprung gewinnt: ein `feat` neben drei `fix` ergibt `MINOR`.

Was geschehen würde, zeigt der Trockenlauf `git fetch && python3 scripts/release.py plan` —
Versionssprung und fertiger Changelog-Abschnitt.

## Release

Ein Release ist vollautomatisch und folgt auf jeden grünen Push auf `agent/main`, der seit dem
letzten Release etwas unter `skytech_omniai/` geändert hat. Ablauf im Job `release` von
[`.github/workflows/ci.yaml`](../.github/workflows/ci.yaml):

1. Alle Prüfjobs grün (Python, Oberfläche, Add-on-Linter, Image mit Smoke-Test, Sicherheit).
2. Zuletzt veröffentlicht ist der jüngste gemeinsame Vorfahr von `main` und dem geprüften Stand
   (`git merge-base`) — das funktioniert, weil jeder Release-Commit den veröffentlichten Stand
   als zweiten Elternteil trägt.
3. `scripts/release.py apply` schreibt in den Arbeitsbaum: die Version in `config.yaml` und
   `skytech_omniai/CHANGELOG.md` — den bisherigen Changelog von `main` mit dem neuen Abschnitt
   obenauf, gebaut aus den Trailern. Home Assistant zeigt diese Datei beim Update an.
4. Der Release-Commit `chore(release): Version X.Y.Z` wird mit `git commit-tree` direkt aus
   diesem Baum gebaut (Eltern: `main` und der geprüfte Stand) — kein Merge, also kein Konflikt.
5. Annotierter Tag `vX.Y.Z`, dann `git push --atomic` von `main` und Tag — alles oder nichts.

Hat sich unter `skytech_omniai/` nichts geändert (nur `docs/`, `tests/`, CI), laufen die
Prüfungen, aber es gibt kein Release. Solche Änderungen und ihre Trailer gehen mit dem nächsten
Release nach `main`.

Der Push nach `main` geht über einen Deploy-Key (Secret `RELEASE_DEPLOY_KEY`), den das Ruleset von
`main` neben den Admins als einzige Ausnahme kennt. Fehlt das Secret, bricht der Job erst dann
ab, wenn wirklich etwas zu veröffentlichen ist.

## Was nie passiert

- Kein `git push --force` auf gemeinsam genutzte Branches
- Kein Commit und kein Merge von Hand auf `main`
- Keine Versionsnummer von Hand in `config.yaml` und kein von Hand gepflegter Changelog
- Keine Secrets im Commit — vor dem Commit `git diff --staged` prüfen
- Keine generierten Artefakte (`dist/`, `node_modules/`, `.venv/`, Caches) im Repo
