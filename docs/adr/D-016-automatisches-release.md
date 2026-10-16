# D-016: Grüne CI auf agent/main veröffentlicht automatisch nach main

- **Datum:** 16.10.2026
- **Status:** Ersetzt durch [D-017](D-017-release-branch.md) — der Bot schreibt nicht mehr nach
  `agent/main`, der Changelog steht in Trailern
- **Betrifft:** `.github/workflows/ci.yaml`, `scripts/release.py`, `scripts/check.sh`,
  `skytech_omniai/config.yaml` (Version), `CHANGELOG.md`, Branch `main`

## Kontext

Bis 0.9.1 wurden Version, Changelog-Überschrift und Merge nach `main` von Hand gepflegt — der
Merge „auf Zuruf“ über einen Pull Request. Es gab keine CI; ob Tests und Linting vor dem Commit
liefen, hing an der Disziplin des jeweiligen Agenten. Die Folgen: Merge-Commits auf `main`, die
`agent/main` fehlten, Versionen, die am selben Tag zweimal von Hand angehoben wurden, und kein
Nachweis, dass das Image überhaupt startet.

`main` ist der Branch, den der Add-on-Store von Home Assistant liest. Was dort landet, bekommt
jede Installation als Update angeboten.

## Betrachtete Optionen

### Option A — Weiter von Hand, nur CI als Prüfung

- Dafür: volle Kontrolle über jeden Release-Zeitpunkt.
- Dagegen: die fehleranfälligen Schritte (Version, Changelog, Merge) bleiben manuell; Agenten
  heben Versionen weiter selbst an.

### Option B — CI öffnet einen Pull Request und merged ihn automatisch

- Dafür: sichtbare Spur je Release im PR-Verlauf.
- Dagegen: Merge-Commits auf `main`, die wieder in `agent/main` fehlen; `GITHUB_TOKEN` löst auf
  dem PR keine Prüfungen aus, es bräuchte ein persönliches Token oder eine GitHub-App.

### Option C — CI hebt die Version an und zieht `main` per Fast-Forward nach

- Dafür: `main` ist immer ein geprüfter Stand von `agent/main`, lineare Historie, keine
  Konflikte zwischen beiden. Version aus Conventional Commits, kein Handgriff.
- Dagegen: ein Bot-Commit auf `agent/main` je Release; jeder Push mit Add-on-Änderung erreicht
  die Nutzer ohne zweiten Blick.

## Entscheidung

**Option C.** Die Prüfungen laufen lokal (`scripts/check.sh`, pre-push-Hook) und in GitHub
identisch. Sind sie grün und hat sich seit dem letzten Tag etwas unter `skytech_omniai/`
geändert, hebt `scripts/release.py` die Version an (`!`/`BREAKING CHANGE` → MAJOR, `feat` →
MINOR, sonst PATCH), schreibt den Changelog fort, taggt `vX.Y.Z` und pusht `agent/main`, `main`
und Tag atomar. Änderungen nur an Doku, Tests oder CI lösen kein Release aus und gehen mit dem
nächsten nach `main`. Ein leerer Abschnitt „Unveröffentlicht“ ist eine Warnung, kein Abbruch.

Gegen B: der Gewinn „sichtbare PR-Spur“ wiegt die Merge-Commits nicht auf — genau die haben
zuvor `main` und `agent/main` auseinanderlaufen lassen. Die Spur liefern Tags und Changelog.

Gepusht wird über einen Deploy-Key, den das Ruleset von `main` als einzige Ausnahme kennt.
`GITHUB_TOKEN` scheidet aus, weil es sich nicht gezielt für `main` freigeben lässt, ohne die
Sperre für alle Actions zu öffnen.

## Folgen

- **Positiv:** kein Release ohne grüne Tests, Linting und startendes Image; Version und
  Changelog-Überschrift entstehen aus den Commits statt aus Handarbeit.
- **Negativ:** nach jedem Release liegt ein Bot-Commit auf `agent/main` — vor der nächsten
  Arbeit `git pull --rebase`. Ein Push mit Add-on-Änderung ist ein Release an alle Nutzer;
  „erst mal pushen und später aufräumen“ gibt es auf `agent/main` nicht mehr. Für Unfertiges
  dient ein `feature/<kurzname>`-Branch.
- **Aufwand:** Deploy-Key mit Schreibrecht, Secret `RELEASE_DEPLOY_KEY`, Rulesets für `main` und
  `agent/main`; einmaliger Tag `v0.9.1` als Ausgangspunkt.

## Rücknahmebedingung

Wenn innerhalb eines Quartals mehr als ein Release zurückgenommen werden muss, weil es Nutzer
mit einem Fehler erreicht hat, den ein zweiter Blick vor dem Merge gefunden hätte — dann wird
der Fast-Forward nach `main` an eine manuelle Freigabe (GitHub-Environment mit Prüfer) gebunden,
der Rest der Kette bleibt.
