# Git-Workflow

> Die Grundregel — Commit und Push ausschließlich im Branch `agent/main` — steht in
> [`AGENTS.md`](../AGENTS.md). Hier steht der ausführliche Ablauf.

## Branch-Modell

| Branch | Zweck |
|---|---|
| `main` | Stabiler Stand. **Kein direkter Commit.** |
| `agent/main` | Arbeitsbranch für KI-Agenten und laufende Entwicklung |
| `feature/<kurzname>` | Optional für größere, klar abgegrenzte Vorhaben |

Der Merge nach `main` erfolgt **manuell auf Zuruf**, nie automatisch durch einen Agenten.

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

## Ablauf je Arbeitspaket

1. **Zuerst `git fetch origin`.** Erst danach wird gewechselt oder abgezweigt, und zwar von
   `origin/<branch>`, nie von einem lokalen Zeiger. Ein lokaler Branch kann Wochen alt sein,
   ohne dass man es ihm ansieht — genau daran ist am 18.08.2026 ein Arbeitspaket verlorengegangen:
   der Arbeitsbranch entstand aus einem veralteten lokalen Stand, der fehlende Commit war damit
   nie enthalten und wurde beim späteren Merge stillschweigend überschrieben.
2. Auf `agent/main` wechseln — existiert er weder lokal noch remote, wird er neu angelegt:
   `git checkout agent/main 2>/dev/null || git checkout -b agent/main origin/main`
3. Existiert der Branch bereits, aktuellen Stand holen: `git pull --rebase`
4. Ändern, Tests (`pytest`) und Linting (`ruff check . && ruff format --check . && npm run typecheck --prefix skytech_omniai/web`) grün bekommen
5. [CHANGELOG.md](../CHANGELOG.md) ergänzen
6. Betroffene `docs/`-Dateien aktualisieren
7. `git add` gezielt — **nie** `git add -A` ohne vorherige Prüfung von `git status`
8. Committen und pushen auf `agent/main` — beim allerersten Push auf einen neuen Branch
   `git push -u origin agent/main`, danach reicht `git push`

Ein Commit bildet **eine** abgeschlossene Änderung ab. Sammelcommits über mehrere unabhängige
Themen sind nicht zulässig — sie machen ein späteres `git revert` unmöglich.

## Versionierung

[Semantic Versioning](https://semver.org/lang/de/): `MAJOR.MINOR.PATCH`

| Teil | Wann erhöhen |
|---|---|
| `PATCH` | Fehlerbehebung, keine Schnittstellenänderung |
| `MINOR` | Neue Funktion, abwärtskompatibel |
| `MAJOR` | Bricht bestehende Schnittstellen oder Datenformate |

Versionsstand wird gepflegt in: `skytech_omniai/config.yaml`

## Release

1. Version in `skytech_omniai/config.yaml` anheben
2. `CHANGELOG.md`: Abschnitt `Unveröffentlicht` in die neue Versionsnummer mit Datum umbenennen
3. Commit `chore(release): Version X.Y.Z`
4. Tag setzen: `git tag -a vX.Y.Z -m "Version X.Y.Z"` und pushen: `git push --tags`

## Was nie passiert

- Kein `git push --force` auf gemeinsam genutzte Branches
- Kein Commit direkt auf `main`
- Keine Secrets im Commit — vor dem Commit `git diff --staged` prüfen
- Keine generierten Artefakte (`dist/`, `node_modules/`, `.venv/`, Caches) im Repo
