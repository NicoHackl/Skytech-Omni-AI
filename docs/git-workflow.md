# Git-Workflow

> Die Grundregel — Commit und Push ausschließlich im Branch `agent/main` — steht in
> [`AGENTS.md`](../AGENTS.md). Hier steht der ausführliche Ablauf.

## Branch-Modell

| Branch | Zweck |
|---|---|
| `main` | Veröffentlichter Stand — den installiert Home Assistant. **Kein direkter Commit, kein Merge von Hand.** |
| `agent/main` | Arbeitsbranch für KI-Agenten und laufende Entwicklung |
| `feature/<kurzname>` | Optional für größere, klar abgegrenzte Vorhaben |

`main` wird **ausschließlich von der CI** nachgezogen, per Fast-Forward auf den geprüften Stand
von `agent/main` — siehe [Release](#release) und D-016. Ein Ruleset sperrt `main` für alle
anderen Wege. Damit ist `main` immer ein Vorfahr von `agent/main`, und es gibt keine
Merge-Commits und keine Merge-Konflikte zwischen beiden.

Wird ein Merge-Konflikt pauschal zugunsten einer Seite aufgelöst („Branch X hat Vorrang"), wird
vorher geprüft, was die andere Seite dabei verliert: `git log <ziel>..<quelle>` und umgekehrt.
Eine Seite pauschal gewinnen zu lassen ist zulässig — sie ungesehen gewinnen zu lassen nicht.

## Commit-Format

[Conventional Commits](https://www.conventionalcommits.org/), Betreffzeile deutsch, max. 72 Zeichen:

```text
<typ>(<bereich>): <was sich ändert, Imperativ>

<optionaler Rumpf: warum, nicht was>
```

Typen: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`.

```text
feat(planer): Vorschlagswerte je Gerät berechnen
fix(api): Zeitzone bei Tageswechsel korrigiert
docs(architektur): Datenfluss aktualisiert
```

Der Rumpf ist nur nötig, wenn das „warum" nicht aus der Betreffzeile hervorgeht.

**Der Typ bestimmt die Version.** Der Release-Job liest ihn aus (siehe
[Versionierung](#versionierung)). Ein `feat` als `fix` getarnt ergibt die falsche Version — der
Typ ist deshalb keine Stilfrage.

## Ablauf je Arbeitspaket

1. **Zuerst `git fetch origin`.** Erst danach wird gewechselt oder abgezweigt, und zwar von
   `origin/<branch>`, nie von einem lokalen Zeiger. Ein lokaler Branch kann Wochen alt sein,
   ohne dass man es ihm ansieht — genau daran ist am 18.08.2026 ein Arbeitspaket verlorengegangen:
   der Arbeitsbranch entstand aus einem veralteten lokalen Stand, der fehlende Commit war damit
   nie enthalten und wurde beim späteren Merge stillschweigend überschrieben.
2. Auf `agent/main` wechseln — existiert er weder lokal noch remote, wird er neu angelegt:
   `git checkout agent/main 2>/dev/null || git checkout -b agent/main origin/main`
3. Aktuellen Stand holen: `git pull --rebase`. **Das ist nach jedem Release Pflicht**, denn
   der Release-Job legt einen eigenen Commit auf `agent/main` (Version und Changelog). Ohne
   `pull --rebase` wird der nächste Push abgewiesen.
4. Ändern, dann `scripts/check.sh` grün bekommen — dieselben Prüfungen wie in der CI (Details:
   [test-strategie.md](test-strategie.md))
5. [CHANGELOG.md](../CHANGELOG.md) unter `## [Unveröffentlicht]` ergänzen — **ohne**
   Versionsnummer, die setzt der Release-Job
6. Betroffene `docs/`-Dateien aktualisieren
7. `git add` gezielt — **nie** `git add -A` ohne vorherige Prüfung von `git status`
8. Committen und pushen auf `agent/main` — beim allerersten Push auf einen neuen Branch
   `git push -u origin agent/main`, danach reicht `git push`. Der pre-push-Hook führt
   `scripts/check.sh` vorher noch einmal aus.

Ein Commit bildet **eine** abgeschlossene Änderung ab. Sammelcommits über mehrere unabhängige
Themen sind nicht zulässig — sie machen ein späteres `git revert` unmöglich.

### pre-push-Hook einmalig aktivieren

```bash
git config core.hooksPath .githooks
```

Der Hook liegt versioniert unter `.githooks/pre-push` und ruft `scripts/check.sh` auf. Im
Notfall lässt er sich mit `git push --no-verify` überspringen — die CI prüft trotzdem.

## Versionierung

[Semantic Versioning](https://semver.org/lang/de/): `MAJOR.MINOR.PATCH`. Die Version in
`skytech_omniai/config.yaml` wird **nie von Hand** angehoben, auch nicht von Agenten. Der
Release-Job ([`scripts/release.py`](../scripts/release.py)) leitet sie aus den Commits seit dem
letzten Tag `v*` ab — gezählt werden nur Commits, die etwas unter `skytech_omniai/` ändern:

| Teil | Wann erhöhen | Erkennungsmerkmal im Commit |
|---|---|---|
| `MAJOR` | Bricht bestehende Schnittstellen oder Datenformate | `!` hinter dem Typ (`feat(api)!: …`) oder Fußzeile `BREAKING CHANGE: …` |
| `MINOR` | Neue Funktion, abwärtskompatibel | Typ `feat` |
| `PATCH` | Alles andere: Fehlerbehebung, Refactoring, Abhängigkeiten | jeder andere Typ, auch ein Betreff ohne Konvention |

Der höchste Sprung gewinnt: ein `feat` neben drei `fix` ergibt `MINOR`.

Was geschehen würde, zeigt der Trockenlauf `python3 scripts/release.py plan`.

## Release

Ein Release ist vollautomatisch und folgt auf jeden grünen Push auf `agent/main`, der etwas
unter `skytech_omniai/` geändert hat. Ablauf im Job `release` von
[`.github/workflows/ci.yaml`](../.github/workflows/ci.yaml):

1. Alle Prüfjobs grün (Python, Oberfläche, Add-on-Linter, Image mit Smoke-Test, Sicherheit).
2. Ist `agent/main` inzwischen weiter als der geprüfte Stand, übernimmt der neuere Lauf.
3. `scripts/release.py apply`: Version in `config.yaml` anheben, `## [Unveröffentlicht]` in
   `## [X.Y.Z] — TT.MM.JJJJ` umbenennen und darüber einen neuen, leeren Abschnitt anlegen. Ist
   der Abschnitt leer, warnt die CI und das Release bekommt die Zeile „Interne Verbesserungen
   ohne sichtbare Änderung.“
4. Commit `chore(release): Version X.Y.Z`, annotierter Tag `vX.Y.Z`.
5. `git push --atomic` von `agent/main`, `main` (Fast-Forward) und Tag — alles oder nichts.

Hat sich unter `skytech_omniai/` nichts geändert (nur `docs/`, `tests/`, CI), laufen die
Prüfungen, aber es gibt weder Bump noch Merge. Solche Änderungen gehen mit dem nächsten Release
nach `main`. Den Release-Commit selbst prüft die CI noch einmal; da er getaggt ist, löst er kein
weiteres Release aus.

Der Push nach `main` geht über einen Deploy-Key (Secret `RELEASE_DEPLOY_KEY`), der im Ruleset von
`main` als einzige Ausnahme eingetragen ist. Fehlt das Secret, bricht der Job mit einer Meldung ab.

## Was nie passiert

- Kein `git push --force` auf gemeinsam genutzte Branches
- Kein Commit und kein Merge von Hand auf `main`
- Keine Versionsnummer von Hand in `config.yaml` oder als Überschrift im Changelog
- Keine Secrets im Commit — vor dem Commit `git diff --staged` prüfen
- Keine generierten Artefakte (`dist/`, `node_modules/`, `.venv/`, Caches) im Repo
