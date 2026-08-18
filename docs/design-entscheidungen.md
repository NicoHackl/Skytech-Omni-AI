# Design-Entscheidungen

**Quelle der Wahrheit fürs „warum".** Wer wissen will, weshalb etwas so gebaut ist, schaut hier —
und ändert es nicht, ohne die Entscheidung hier zu widerrufen.

## Wann ein Eintrag entsteht

Immer, wenn eine Festlegung getroffen wird, die später jemand hinterfragen könnte:
Technologiewahl, Datenformat, Namensschema, Zuständigkeitsgrenze, bewusst nicht Gebautes,
neue Laufzeit-Abhängigkeit.

**Nicht** eingetragen werden reine Umsetzungsdetails, die der Code selbst zeigt.

## Ablauf

1. Nächste freie `D-xxx` vergeben (fortlaufend, nie wiederverwenden).
2. Zeile in die Tabelle unten eintragen.
3. Bei tragweiter Entscheidung zusätzlich ein ADR anlegen:
   `docs/adr/D-xxx-kurzname.md` auf Basis von [adr/0000-vorlage.md](adr/0000-vorlage.md), und aus
   der Tabelle darauf verlinken.
4. Wird eine Entscheidung später gekippt: alte Zeile auf Status **Ersetzt** setzen und auf die neue
   `D-yyy` verweisen. **Zeilen werden nie gelöscht** — sonst geht die Begründung verloren, warum
   der frühere Weg verworfen wurde.

## Status-Werte

| Status | Bedeutung |
|---|---|
| Aktiv | Gilt und ist umgesetzt |
| Geplant | Beschlossen, aber noch nicht im Code — siehe [roadmap.md](roadmap.md) |
| Ersetzt | Durch eine spätere Entscheidung abgelöst, Verweis in der Begründung |
| Verworfen | Bewusst nicht umgesetzt, Begründung bleibt als Warnung stehen |

## Log

| ID | Datum | Entscheidung | Status | Begründung / Verweis |
|---|---|---|---|---|
| D-001 | 18.08.2026 | Regeln für KI-Agenten liegen in `AGENTS.md`; `CLAUDE.md`, `GEMINI.md`, `copilot-instructions.md` und `.cursor/rules/` sind reine Verweise darauf | Aktiv | Jede Regel existiert genau einmal. Alternative „je Tool eine eigene Datei" wurde verworfen, weil die Kopien erfahrungsgemäß auseinanderlaufen. |
| D-002 | 18.08.2026 | Datum immer `TT.MM.JJJJ`, Uhrzeit immer Berliner Zeit als `hh:mm` bzw. `hh:mm:ss`, ohne Offset oder Zonenkürzel (eiserne Regel 9 in [`AGENTS.md`](../AGENTS.md)) | Aktiv | Einheitliche Lesart in Doku, Changelog, Logs und UI. Alternative „ISO 8601 mit Offset überall" wurde verworfen: technisch korrekt, für die deutschsprachige Zielgruppe aber unlesbar. Maschinenformate bleiben davon ausgenommen. |
| D-003 | 18.08.2026 | Designsprachen über `data-design` (`ha` = Home Assistant mit `#18BCF2`, `fcr` = FC Ruderting), ohne Default und mit grauem Akzent als sichtbarem „nicht entschieden"; Hell/Dunkel über `data-theme` in jeder Sprache Pflicht (eiserne Regeln 10 und 11 in [`../AGENTS.md`](../AGENTS.md)) | Aktiv | Ein Vokabular, mehrere Akzentsätze. Alternative „je Designsprache eine eigene styles.css" wurde verworfen, weil dann jede Klassenänderung doppelt gepflegt werden müsste. Ein stiller Default wurde ebenfalls verworfen: er hätte fremde Projekte in den Farben eines anderen erscheinen lassen, statt die offene Entscheidung zu zeigen. |
| D-004 | 18.08.2026 | Ausgaben an den Nutzer zeigen nur, was ihn betrifft: keine Zeitzonen, Statuscodes, IDs, internen Zustandsnamen oder Stacktraces in der Oberfläche; Rohwerte laufen durch eine Formatierschicht (eiserne Regel 12 in [`../AGENTS.md`](../AGENTS.md), Details in [nutzertexte.md](nutzertexte.md)) | Aktiv | Umsetzungsvorgaben sind an mehreren Stellen als Anzeigetext gelandet („21:03 Berliner Zeit", „Anfrage fehlgeschlagen (500)"). Alternative „im Zweifel mehr anzeigen" wurde verworfen: technische Zusätze beantworten keine Frage des Nutzers, machen die Oberfläche unruhig und verlagern die Deutungsarbeit zu ihm. Die Angaben gehen nicht verloren, sie stehen im Log. |
| D-005 | 04.07.2026 | Anbieter liegen hinter einer gemeinsamen Schnittstelle und werden über eine Fabrik (`providers/factory.py`) nach Namen gewählt | Aktiv | Ein neuer Anbieter ist eine neue Datei plus ein Eintrag in der Fabrik; `app.py` bleibt unberührt. Alternative „Verzweigung im Endpunkt“ wurde verworfen, weil sie mit jedem Anbieter unübersichtlicher wird. |
| D-006 | 04.07.2026 | Claude wird über die Claude-Code-CLI als Unterprozess angesprochen, nicht über die Anthropic-API | Aktiv | Nur über die CLI zählt eine Anfrage auf das rollierende Limit des Pro/Max-Abos; über die API entstünden zusätzliche Kosten. Preis dafür: Node im Bild, ein Unterprozess je Anfrage und die Abhängigkeit vom Verhalten von `claude -p`. Ausführlich: [adr/D-006-claude-cli.md](adr/D-006-claude-cli.md). |
| D-007 | 02.08.2026 | Google Gemini wird über `urllib` aus der Standardbibliothek angesprochen, nicht über das offizielle SDK | Aktiv | Das SDK zieht über pydantic-core eine Rust-Werkzeugkette nach; das Bild ist Alpine-basiert und wird auch für armv7/armhf gebaut, wo daraus lange Bauzeiten oder Fehlschläge werden. Für einen einzelnen JSON-POST lohnt die Abhängigkeit nicht. |
| D-008 | 18.08.2026 | waitress als WSGI-Server statt `flask.run` | Aktiv | Der Entwicklungsserver von Flask ist für Dauerbetrieb weder gedacht noch geeignet und warnt selbst davor. waitress ist reines Python und baut damit auf musl und armv7 ohne Werkzeugkette. Alternativen gunicorn (fork-Modell, unter Alpine mehr Aufwand) und uvicorn (ASGI, passt nicht zu Flask) wurden verworfen. Ausführlich: [adr/D-008-waitress.md](adr/D-008-waitress.md). |
| D-009 | 18.08.2026 | Die Oberfläche wird als gebautes Bündel von Flask im selben Prozess ausgeliefert; der Ingress-Pfad kommt zur Laufzeit aus dem Kopf `X-Ingress-Path` in ein `<base>`-Element | Aktiv | Ein Add-on-Container startet genau einen Befehl; ein zweiter Webserver bräuchte einen Prozessverwalter. Der Ingress-Pfad wechselt je Sitzung, ein fest gebautes `base` wäre schon beim zweiten Öffnen falsch. Ausführlich: [adr/D-009-oberflaeche-ueber-ingress.md](adr/D-009-oberflaeche-ueber-ingress.md). |
| D-010 | 18.08.2026 | Die Endpunkte behalten ihre Namen ohne `/api`-Präfix und ohne Version im Pfad | Aktiv | [frontend.md](frontend.md) sieht `/api/…` vor, aber bestehende Automatisierungen zeigen seit der ersten Fassung auf `/ask`. Ein Präfix nachzuschieben wäre ein Bruch ohne Gegenwert; ein Parallelbetrieb beider Pfade wäre doppelte Pflege. Die Abweichung steht in [bekannte-luecken.md](bekannte-luecken.md). |
| D-011 | 18.08.2026 | Die Klasse `.code-block` ergänzt das Design-System für Rohtext, dessen Aufbau vorher nicht feststeht | Aktiv | Die Antwort eines Modells ist JSON beliebiger Form; sie waagerecht scrollen zu lassen ist die einzige lesbare Darstellung. Formuliert ausschließlich mit Tokens, damit sie in beiden Modi trägt. Alternative „`.table-wrap` mitbenutzen“ wurde verworfen: der Name verspricht eine Tabelle. |
| D-012 | 18.08.2026 | Die Werkzeuge der Claude-CLI werden in drei Stufen freigegeben (`tool_access`: `off`, `web`, `full`); Vorgabe ist `web` | Aktiv | Im Modus `claude -p` gibt es keine Rückfrage, also lehnt die CLI ohne Freigabe **jedes** Werkzeug ab — auch die Websuche. Eine pauschale Freigabe aller Werkzeuge wurde verworfen: `full` erlaubt auch Befehle und Dateizugriff im Container, wo unter `/data` das Token liegt, und Port 8000 ist unauthentifiziert. `web` deckt den eigentlichen Anwendungsfall (etwas nachschlagen) vollständig ab, ohne diesen Weg zu öffnen. `full` bleibt wählbar, mit Warnung in [sicherheit-datenschutz.md](sicherheit-datenschutz.md). Der Systemprompt gehört zur Entscheidung dazu: ohne den Hinweis auf die Werkzeuge behauptet das Modell, es habe kein Internet, statt zu suchen. |
| D-013 | 18.08.2026 | ChatGPT wird über die Codex-CLI angesprochen (`codex exec`), nicht über die OpenAI-API; die Anmeldung wird als Inhalt von `auth.json` eingetragen und nur bei Änderung ins Datenverzeichnis geschrieben | Aktiv | Wie bei Claude zählt nur der Weg über die Befehlszeile auf das Abo; ein Schlüssel würde nach Verbrauch abgerechnet. Ein langlebiges Einzel-Token wie bei `claude setup-token` gibt es bei Codex nicht — die CLI erneuert ihre Tokens selbst und schreibt sie zurück. Deshalb wird der eingetragene Wert nur bei geändertem Fingerabdruck übernommen; sonst ersetzte jeder Neustart den frischen Stand durch den alten. Die Geräte-Anmeldung aus der Oberfläche heraus wurde zurückgestellt, nicht verworfen. Ausführlich: [adr/D-013-codex-cli.md](adr/D-013-codex-cli.md). |
| D-014 | 18.08.2026 | Das Add-on wird nur noch für 64 Bit gebaut (`amd64`, `aarch64`); `armv7`, `armhf` und `i386` entfallen | Aktiv | Die Codex-CLI wird ausschließlich als vorgebautes Binary für x86_64 und aarch64 ausgeliefert; für 32 Bit gibt es keines. Die Alternative „Codex nur dort installieren, wo es Binaries gibt“ wurde verworfen: sie ergäbe zwei verschiedene Add-ons unter einem Namen, bei denen ein Anbieter je nach Gerät fehlt. Preis: bestehende Installationen auf 32-Bit-Geräten bekommen ab 0.8.0 kein Update mehr. |
