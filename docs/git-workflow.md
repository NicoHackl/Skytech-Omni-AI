# Git-Workflow

> Die Grundregel — Commit und Push ausschließlich im Branch `dev/dev` — steht in
> [`AGENTS.md`](../AGENTS.md). Hier steht der ausführliche Ablauf.

## Branch-Modell

| Branch | Zweck |
|---|---|
| `dev/dev` | Arbeitsbranch für KI-Agenten und laufende Entwicklung. Enthält nur Quellstand: `version: "dev"`, kein Changelog. **Nur Menschen und Agenten schreiben hier, nie die CI.** |
| `dev/main` | Geprüfter Zwischenstand. **Wird ausschließlich von der CI befüllt**, per Fast-Forward aus `dev/dev` — nie von Hand, nie zurück. |
| `main` | Release-Branch — den installiert Home Assistant. **Schreibt ausschließlich die CI**, nach dem Merge des freigegebenen Pull Requests. |
| `feature/<kurzname>` | Optional für größere, klar abgegrenzte Vorhaben |

```text
dev/dev ──push──▶ CI: alles grün? ──ja──▶ dev/main ──Pull Request──▶ main ──Merge──▶ Release
                                          (automatisch,             (Freigabe        (Version,
                                           einseitig)                 durch User)      Changelog, Tag)
```

Jeder Commit auf `main`, der etwas unter `skytech_omniai/` verändert hat, wird mit einem
Release-Commit abgeschlossen: der gemergte Stand, gestempelt mit Version
(`skytech_omniai/config.yaml`) und Changelog (`skytech_omniai/CHANGELOG.md`). Ein Ruleset verlangt
für jede Änderung an `main` einen Pull Request (Merge-Commit) und sperrt Force-Push und Löschen;
nur der Release-Job darf per Deploy-Key direkt schreiben. Es gibt bewusst keinen Admin-Bypass und
keine Regel „Restrict updates": Die GitHub-App (iOS) kann keine Regel umgehen, der Pull Request
ließe sich dort sonst nicht freigeben. Freigabe ist der Merge-Knopf des Repo-Besitzers, auch in
der App. Begründung: D-025.

Weil die CI nie nach `dev/dev` schreibt, braucht es nach einem Release **kein**
`git pull --rebase`. Nötig ist es nur, wenn jemand anderes (ein zweiter Agent, ein gemergter
Dependabot-PR) inzwischen auf `dev/dev` gepusht hat — dann weist Git den Push ab, und
`git pull --rebase` löst es ohne Konflikt im Changelog, denn es gibt dort keine Datei mehr.

Wird ein Merge-Konflikt pauschal zugunsten einer Seite aufgelöst („Branch X hat Vorrang"), wird
vorher geprüft, was die andere Seite dabei verliert: `git log <ziel>..<quelle>` und umgekehrt.
Eine Seite pauschal gewinnen zu lassen ist zulässig — sie ungesehen gewinnen zu lassen nicht.

## Pull Request nach main

Ein Vorhaben kann aus mehreren Arbeitspaketen bestehen — jedes Paket erzeugt einen Push auf
`dev/dev` und damit eine automatische Übernahme nach `dev/main`. Nach `main` geht trotzdem nur
**ein** Pull Request:

1. Vorhaben abgeschlossen, `dev/main` ist grün, dann gleich dem Repo-Besitzer zugewiesen:
   `gh pr create --base main --head dev/main --assignee "$(gh repo view --json owner --jq .owner.login)"`.
   Der Workflow [`pr-zuweisen.yaml`](../.github/workflows/pr-zuweisen.yaml) weist zusätzlich jeden
   neu eröffneten Pull Request (auch von Dependabot) selbsttätig dem Besitzer zu.
2. **Der User gibt den Pull Request frei.** Ein Agent merged ihn nie.
3. Gemergt wird mit **Merge-Commit** (nicht Squash, nicht Rebase) — der Release-Job erkennt am
   zweiten Elternteil, welche Commits neu sind, und liest daraus die Changelog-Trailer.
4. Solange ein Pull Request offen ist, wird kein zweiter angelegt.

### Konflikt im Pull Request

Ein Konflikt entsteht, wenn `dev/main` und `main` dieselbe oder eine angrenzende Zeile geändert
haben — typisch in `skytech_omniai/config.yaml` (Release-Job ändert `version:`) und
`skytech_omniai/CHANGELOG.md`. Auflösen, ohne den Ablauf zu beschädigen:

1. `main` nach `dev/main` mergen und den Konflikt dort lösen (Weboberfläche oder lokal).
   In `config.yaml` bleibt `version: "dev"`; sonst gilt die Seite von `dev/main`.
2. Pull Request wie gewohnt mergen. Die Version setzt der Release-Job ohnehin neu.
3. Danach **einmalig** `dev/dev` nachziehen, weil `dev/main` den Merge-Commit hat und der
   nächste Push auf `dev/dev` sonst nicht mehr per Fast-Forward übernommen werden kann:
   `git fetch && git checkout dev/dev && git merge --ff-only origin/dev/main && git push`.
   Das ist die einzige zulässige Richtung `dev/main` → `dev/dev`; nie rebasen.

Dadurch liegt `skytech_omniai/CHANGELOG.md` als Kopie von `main` auch auf `dev/dev`. Sie wird dort
nicht gepflegt und nicht gelöscht (sonst entsteht beim nächsten Release ein Konflikt).

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

Der Rumpf ist nur nötig, wenn das „warum" nicht aus der Betreffzeile hervorgeht. Es steht
**kein** `Co-Authored-By` und keine KI-Signatur im Commit (eiserne Regel 13).

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

**Ein Trailer ist nach dem Push nicht mehr korrigierbar** — `dev/dev` verbietet das
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
2. Auf `dev/dev` wechseln — existiert er lokal nicht, wird er von `origin/dev/dev`
   angelegt: `git checkout dev/dev 2>/dev/null || git checkout -b dev/dev origin/dev/dev`
3. Existiert der Branch bereits, aktuellen Stand holen: `git pull --rebase`
4. Ändern, dann `scripts/check.sh` grün bekommen — dieselben Prüfungen wie in der CI, vollständig
   (eiserne Regel 15, [test-strategie.md](test-strategie.md#lokal--ci))
5. Betroffene `docs/`-Dateien aktualisieren
6. `git add` gezielt — **nie** `git add -A` ohne vorherige Prüfung von `git status`
7. Committen, bei nutzerrelevanter Änderung mit `Changelog-<Kategorie>:`-Trailer
8. Pushen auf `dev/dev` — beim allerersten Push auf einen neuen Branch
   `git push -u origin dev/dev`, danach reicht `git push`. Der pre-push-Hook führt
   `scripts/check.sh` vorher noch einmal aus.

Nach dem Push das CI-Ergebnis abwarten (`gh run watch`) und erst danach die nächste Aufgabe
beginnen. Rot → Regel 15: lokal nachstellen, beheben, erneut pushen.

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

[Semantic Versioning](https://semver.org/lang/de/): `MAJOR.MINOR.PATCH`. Auf `dev/dev` steht
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

Ein Release folgt auf den **Merge des freigegebenen Pull Requests** `dev/main` → `main`, sofern
dabei etwas unter `skytech_omniai/` neu ist. Ablauf im Workflow
[`.github/workflows/release.yaml`](../.github/workflows/release.yaml):

1. Der Merge löst den Lauf aus. Die Prüfungen sind bereits vorher gelaufen: auf `dev/dev` und
   noch einmal im Pull Request selbst ([`ci.yaml`](../.github/workflows/ci.yaml)).
2. Bezugsstand ist der erste Elternteil des Merge-Commits (das bisherige, zuletzt
   veröffentlichte `main`), neu sind die Commits des zweiten Elternteils (`dev/main`).
3. `scripts/release.py apply` schreibt in den Arbeitsbaum: die Version in `config.yaml` und
   `skytech_omniai/CHANGELOG.md` — den bisherigen Changelog von `main` mit dem neuen Abschnitt
   obenauf, gebaut aus den Trailern. Home Assistant zeigt diese Datei beim Update an.
4. Der Release-Commit `chore(release): Version X.Y.Z` wird mit `git commit-tree` direkt aus
   diesem Baum gebaut (Elternteil: der Merge-Commit) — kein Merge, also kein Konflikt.
5. Annotierter Tag `vX.Y.Z`, dann `git push --atomic` von `main` und Tag — alles oder nichts.
   Der eigene Release-Commit löst den Workflow nicht erneut aus.

Hat sich unter `skytech_omniai/` nichts geändert (nur `docs/`, `tests/`, CI), gibt es kein
Release. Solche Änderungen und ihre Trailer gehen mit dem nächsten Release nach `main`.

Der Push nach `main` und der Tag gehen über einen Deploy-Key (Secret `RELEASE_DEPLOY_KEY`), den das Ruleset von
`main` als einzige Ausnahme kennt. Fehlt das Secret, bricht der Job erst dann
ab, wenn wirklich etwas zu veröffentlichen ist.

**Dependabot** öffnet seine Pull Requests gegen `dev/dev`. Nach dem Merge laufen sie wie jede
andere Änderung durch `dev/main` und den Pull Request nach `main`.

## Was nie passiert

- Kein `git push --force` auf gemeinsam genutzte Branches
- Kein Commit und kein Merge von Hand auf `main`; kein Commit von Hand auf `dev/main`
- Kein Merge von `dev/main` zurück nach `dev/dev`
- Kein zweiter Pull Request nach `main`, solange einer offen ist
- Kein Pull Request ohne Zuweisung an den Repo-Besitzer
- Kein `Co-Authored-By`-Trailer und keine KI-Namensnennung in Commits oder Pull Requests
- Keine Tags von Hand — Tags und Releases setzt nur der Release-Workflow (User-Entscheidung 28.10.2026)
- Keine Versionsnummer von Hand in `config.yaml` und kein von Hand gepflegter Changelog
- Keine Secrets im Commit — vor dem Commit `git diff --staged` prüfen
- Keine generierten Artefakte (`dist/`, `node_modules/`, `.venv/`, Caches) im Repo
