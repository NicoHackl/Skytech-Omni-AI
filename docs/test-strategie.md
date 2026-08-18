# Teststrategie

## Befehle

```bash
pytest                                              # alle Tests
pytest tests/unit/test_app.py                       # gezielt eine Datei
ruff check . && ruff format --check .               # Linting und Formatprüfung
npm run typecheck --prefix skytech_omniai/web       # Typprüfung der Oberfläche
```

Alles davon muss vor jedem Commit fehlerfrei durchlaufen — siehe
[git-workflow.md](git-workflow.md).

## Testarten

| Art | Umfang | Ort |
|---|---|---|
| Unit | Eine Funktion oder Klasse, keine externen Zugriffe | `tests/unit/` |
| Schnittstelle | Die Endpunkte über den Testclient von Flask, Anbieter als Attrappe | `tests/unit/test_app.py` |
| Regression | Ein konkret aufgetretener Bug, damit er nicht wiederkehrt | beim jeweiligen Modul |

Die Teststruktur spiegelt die Struktur des Quellcodes. Zu `skytech_omniai/providers/factory.py`
gehört `tests/unit/providers/test_factory.py`. Die Module werden dabei flach importiert
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

Beispiele dafür stehen in `test_gemini_provider.py`
(`test_http_errors_carry_no_status_code`) und in `test_app.py`
(`test_a_provider_failure_stays_free_of_technical_detail`).

Ein Bugfix ohne Regressionstest ist nicht abgeschlossen. Der Test muss **vor** dem Fix
nachweislich fehlschlagen.

## Grundregeln

- Tests laufen **ohne** Netzwerkzugriff, ohne echte Zugangsdaten und ohne die Claude-CLI.
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
verfolgt. Abdeckung ist ein Warnsignal, kein Ziel an sich — 100 % ohne Zusicherungen im Test ist
wertlos.

Ungetestet bleiben dürfen: die Verdrahtung in `main.tsx`, reine Anzeigekomponenten und der Aufruf
der echten Claude-CLI. Letzterer ist als Lücke in [bekannte-luecken.md](bekannte-luecken.md)
geführt — nach jedem Anheben der CLI-Version wird von Hand eine Anfrage gestellt.
