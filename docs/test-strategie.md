# Teststrategie

## Befehle

```bash
scripts/check.sh                                    # alles, was auch die CI prüft
scripts/check.sh --docker                           # zusätzlich Image bauen und Smoke-Test
pytest                                              # alle Tests
pytest tests/unit/test_app.py                       # gezielt eine Datei
ruff check . && ruff format --check .               # Linting und Formatprüfung
npm run typecheck --prefix skytech_omniai/web       # Typprüfung der Oberfläche
```

`scripts/check.sh` muss vor jedem Commit fehlerfrei durchlaufen — siehe
[git-workflow.md](git-workflow.md). Als pre-push-Hook (`git config core.hooksPath .githooks`)
läuft es vor jedem Push von selbst; der commit-msg-Hook prüft dazu jede Commit-Message.

## Testarten

| Art | Umfang | Ort |
|---|---|---|
| Unit | Eine Funktion oder Klasse, keine externen Zugriffe | `tests/unit/` |
| Schnittstelle | Die Endpunkte über den Testclient von Flask, Anbieter als Attrappe | `tests/unit/test_app.py` |
| Regression | Ein konkret aufgetretener Bug, damit er nicht wiederkehrt | beim jeweiligen Modul |
| Konsistenz | Die von Hand gepflegten Dateien passen zueinander und zum Code: Optionen ↔ Schema ↔ `OPTION_ENV_MAP`, Auswahllisten ↔ Anbieter und Modelle, `build.yaml` ↔ `arch`, `COPY` im Dockerfile ↔ Module; Version `dev` und kein Changelog auf dem Arbeitsbranch (D-017) | `tests/unit/test_addon_config.py` |
| Werkzeuge | Versionssprung, Changelog-Trailer und Changelog des Release-Skripts; Prüfung der Commit-Messages | `tests/scripts/` |
| Smoke-Test | Das fertige Image startet, liefert `/health`, `/models`, die Oberfläche über den Ingress und bringt beide Befehlszeilen mit | `scripts/smoke_test.sh` |

Die Teststruktur spiegelt die Struktur des Quellcodes. Zu `skytech_omniai/providers/factory.py`
gehört `tests/unit/providers/test_factory.py`, zu `scripts/release.py` gehört
`tests/scripts/test_release.py`. Die Module werden dabei flach importiert
(`from providers.factory import …`) — genauso wie im Container; dafür sorgt `pythonpath` in
`pyproject.toml`.

Die Oberfläche wird nicht mit Testfällen geprüft, sondern über `tsc --noEmit` und die
Sichtprüfung aus [frontend.md](frontend.md). Bei drei Seiten ohne eigene Fachlogik wäre eine
Testeinrichtung für React mehr Pflege als Gewinn — kommt Logik hinzu, ändert sich das.

## Pflicht-Testfälle

Für jede neue Funktion mindestens:

1. **Normalfall** — erwartete Eingabe, erwartetes Ergebnis
2. **Fehlerfall** — ungültige Eingabe, definierter Fehler statt Absturz
3. **Leerzustand** — leere Liste, fehlende Datei, kein Wert gesetzt

Für alles, was ein Mensch am Ende liest, zusätzlich:

4. **Anzeigeform** — das Ergebnis entspricht dem Format aus
   [nutzertexte.md](nutzertexte.md): `15.08.2026`, `21:03`, `1.234,5` — **ohne** Zonenkürzel,
   Offset, Statuscode oder technische Kennung. Zeitfunktionen werden dabei mit einem festen
   Zeitpunkt geprüft, je einmal in Sommer- und Winterzeit, damit die Umrechnung nachweislich
   stimmt, ohne dass die Zone im Text auftaucht.
5. **Kein Durchreichen von Technik** — jede Fehlermeldung wird ausdrücklich daraufhin geprüft,
   dass sie **keinen** Antwortcode, Klassennamen, Pfad und keine Rohausgabe enthält. Das ist in
   diesem Projekt kein Nebenschauplatz, sondern die am leichtesten zu brechende Regel: die
   Ursachen kommen von zwei fremden Diensten, und ihr Wortlaut ändert sich ohne Vorwarnung.

Die Anmeldung bei Google und ihr Ablauf von den Endpunkten bis zur Antwort werden mit einem Skript
an Stelle der CLI getestet (`test_gemini_agy_login.py`, `test_gemini_agy_flow.py`): es spielt
Adresse, Eingabe über eine Pty, Anmeldedatei und Fehlerfälle nach — echte Prozesse, aber ohne Netz
und ohne Konto. Das schließt ein Verhalten der echten CLI nicht ein; dafür gibt es die Handprüfung
in D-022.

Beispiele dafür stehen in `test_gemini_provider.py`
(`test_http_errors_carry_no_status_code`) und in `test_app.py`
(`test_a_provider_failure_stays_free_of_technical_detail`).

Ein Bugfix ohne Regressionstest ist nicht abgeschlossen. Der Test muss **vor** dem Fix
nachweislich fehlschlagen.

## Grundregeln

- Tests laufen **ohne** Netzwerkzugriff, ohne echte Zugangsdaten und ohne die Befehlszeilen.
  `subprocess.run` und die HTTP-Aufrufe werden ersetzt, nie ausgeführt.
- `tests/conftest.py` räumt vor jedem Test die bekannten Umgebungsvariablen ab. Ohne das hinge
  das Ergebnis davon ab, was auf dem Rechner des Entwicklers gesetzt ist.
- Tests sind reihenfolgeunabhängig und hinterlassen keinen Zustand.
- Keine `sleep`-Aufrufe zur Synchronisierung — sie sind langsam und trotzdem instabil.
- Ein Test prüft **eine** Aussage. Der Testname beschreibt sie auf Englisch (eiserne Regel 2:
  Code englisch), der Docstring darunter auf Deutsch:
  `test_a_leftover_claude_alias_is_rejected`.
- Testdaten stehen im Test selbst, solange sie in wenige Zeilen passen. Erst wenn dieselbe Antwort
  in mehreren Tests gebraucht wird, wandert sie in eine Fixture.

## Abdeckung

Zielwert: Jede Funktion mit Verzweigungslogik ist abgedeckt; der reine Prozentwert wird nicht
verfolgt. `scripts/check.sh` und die CI zeigen ihn trotzdem an (in GitHub in der
Zusammenfassung des Laufs) — als Hinweis, wo Tests fehlen, nicht als Schwelle. Abdeckung ist ein Warnsignal, kein Ziel an sich — 100 % ohne Zusicherungen im Test ist
wertlos.

Ungetestet bleiben dürfen: die Verdrahtung in `main.tsx`, reine Anzeigekomponenten und der Aufruf
der echten Claude-, Codex- bzw. Antigravity-CLI. Letzterer ist als Lücke in
[bekannte-luecken.md](bekannte-luecken.md) geführt — nach jedem Anheben einer CLI-Version wird
über den betroffenen Anbieter von Hand eine Anfrage gestellt.

## Lokal = CI

Eine rote CI nach grünem lokalem Test hat fast immer dieselben Ursachen. Jede ist eine Abweichung
zwischen beiden Umgebungen — und jede wird vorab ausgeschlossen (eiserne Regel 15):

| Ursache | Gegenmaßnahme in diesem Projekt |
|---|---|
| Lokal nur der geänderte Test gelaufen, die CI führt alles aus | Vor dem Push immer `scripts/check.sh` (der pre-push-Hook erzwingt das) |
| CI nutzt andere Befehle oder Flags | `scripts/check.sh` und `ci.yaml` führen dieselben Prüfungen aus; wer eine ändert, ändert beide im selben Commit |
| Andere Versionen | Python 3.11 **und** 3.14 in der CI-Matrix, Node 20 wie im Image, alle Abhängigkeiten gepinnt, `npm ci` nach Lockfile |
| Datei lokal vorhanden, aber nicht eingecheckt oder ignoriert | Vor dem Push `git status` prüfen; im Zweifel in einem frischen Klon testen |
| Lokale `.env`, Dienste oder Netz | Tests laufen ohne diese; benötigte Werte setzt die CI mit Testwerten |
| Groß-/Kleinschreibung von Dateinamen (macOS vs. Linux), Zeitzone, Locale | Beim Auftreten mit einem Test absichern; Zeitzone im Test explizit setzen |
| Nur in der CI vorhandene Jobs (Image, Smoke-Test, Sicherheit, Add-on-Linter) | `scripts/check.sh --docker` bei Änderungen an Dockerfile, Add-on-Konfiguration oder Abhängigkeiten |

Lässt sich ein roter CI-Lauf lokal nicht nachstellen, ist das der eigentliche Fehler: erst die
Abweichung finden, dann den Test beheben. Ein erneuter Push „auf gut Glück" ist nicht zulässig.

## Automatische Prüfungen (CI)

[`.github/workflows/ci.yaml`](../.github/workflows/ci.yaml) läuft bei jedem Push auf
`dev/dev` und bei jedem Pull Request nach `dev/dev` oder `main`. Alle Jobs müssen grün sein, bevor
der Job „Nach dev/main übernehmen" den Stand weiterreicht
([git-workflow.md](git-workflow.md#branch-modell)). Das Release selbst ist ein eigener Workflow
([`release.yaml`](../.github/workflows/release.yaml), [git-workflow.md](git-workflow.md#release)).

| Job | Prüft | Lokal |
|---|---|---|
| Python 3.11 / 3.14 | `ruff check`, `ruff format --check`, `pytest` mit Abdeckung. 3.11 ist das Python im Image, 3.14 das der Entwicklung | `scripts/check.sh` |
| Oberfläche | `tsc --noEmit` und `vite build` | `scripts/check.sh` |
| Add-on, Workflows, Dockerfile | Add-on-Linter von Home Assistant für `config.yaml`/`build.yaml`, `actionlint` (mit shellcheck) für die Workflows, `hadolint` (Regeln in `.hadolint.yaml`) | — |
| Image und Smoke-Test | Bau für `amd64` mit dem Basisimage aus `build.yaml`, danach `scripts/smoke_test.sh` | `scripts/check.sh --docker` (Architektur des eigenen Rechners) |
| Sicherheit | `gitleaks` über die ganze Historie, `pip-audit`, `npm audit` (nur Laufzeit, ab „high“) | — |
| Release-Vorschau | Commit-Messages seit dem letzten Release (nur Warnungen), Versionssprung und fertiger Changelog-Abschnitt in der Zusammenfassung; warnt, wenn ein Release keinen Trailer hat | `git fetch && python3 scripts/release.py plan`; die Messages prüft der commit-msg-Hook |

Daneben laufen, ohne das Release zu blockieren: CodeQL für Python und TypeScript
([`codeql.yaml`](../.github/workflows/codeql.yaml), auch wöchentlich) und Dependabot für pip,
npm und die Actions ([`dependabot.yml`](../.github/dependabot.yml)).

## Prüfung bei Actions-Ausfall

Der [lokale CI-Fallback](git-workflow.md#lokaler-ci-fallback) führt den gemeinsamen lokalen
Prüfbefehl erneut aus und dokumentiert dessen tatsächlichen Umfang im PR. Ein Ausfall der
GitHub-Prüfung ersetzt keine lokale Prüfung; zusätzliche CI-Jobs bleiben separat nachzuweisen.
