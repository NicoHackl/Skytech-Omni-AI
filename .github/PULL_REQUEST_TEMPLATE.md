## Was ändert sich

<Eine kurze Beschreibung aus Nutzersicht.>

## Warum

<Problem oder Anforderung. Bei Grundsatzentscheidungen: Verweis auf D-xxx in
`docs/design-entscheidungen.md`.>

## Checkliste

- [ ] Tests laufen fehlerfrei
- [ ] Linting läuft fehlerfrei
- [ ] `scripts/check.sh` lokal gelaufen — dieselben Prüfungen wie die CI (Regel 15)
- [ ] PR geht von `dev/main` nach `main`, kein zweiter PR offen
- [ ] Keine KI-Signatur / kein `Co-Authored-By` in Commits und Beschreibung
- [ ] Changelog-Trailer `Changelog-<Kategorie>: …` im Commit (bei funktionaler oder gestalterischer Änderung)
- [ ] Betroffene Dateien in `docs/` aktualisiert
- [ ] Neue Grundsatzentscheidung in `docs/design-entscheidungen.md` eingetragen
- [ ] Keine Secrets im Diff (`git diff --staged` geprüft)
- [ ] Sprachregeln aus [AGENTS.md](../AGENTS.md) eingehalten
- [ ] Keine technischen Angaben in sichtbaren Texten — keine Zeitzone, kein Statuscode, keine ID,
      kein Stacktrace (eiserne Regel 12, `docs/nutzertexte.md`)

## Wie getestet

<Konkrete Schritte oder Testfälle, mit denen die Änderung geprüft wurde.>
