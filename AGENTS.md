# AGENTS.md — Skytech OmniAI

> **Diese Datei ist die einzige Quelle der Wahrheit für Projektregeln.**
> `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md` und `.cursor/rules/` sind reine
> Verweise hierher und enthalten selbst **keine** Regeln. Regeln werden ausschließlich hier gepflegt.

## Projektzweck

Home-Assistant-Add-on und modulare Brücke zwischen dem Smart Home und mehreren KI-Anbietern: nimmt Prompts über eine HTTP-Schnittstelle entgegen, leitet sie an Claude (Pro/Max-Abo über die Claude-CLI) oder Google Gemini weiter und liefert geprüftes JSON zurück. Eine Weboberfläche über den Ingress von Home Assistant zeigt den Zustand und erlaubt Testanfragen.

Tech-Stack: Python 3, Flask, waitress; React 18 + TypeScript + Vite; Alpine-Image als Home-Assistant-Add-on

## Präzedenz bei Widersprüchen

1. **Direkte Anweisung des Users im Gespräch** — schlägt alles.
2. **Diese Datei (`AGENTS.md`)** — die eisernen Regeln.
3. **`docs/`** — ausführliche technische Referenz.

Wenn `docs/` dieser Datei widerspricht, ist `docs/` falsch und wird korrigiert — nicht umgekehrt.

## Eiserne Regeln (nicht verhandelbar)

1. **Git:** Commit und Push erfolgen ausschließlich im Arbeitsbranch `dev/dev` — nie direkt auf
   `dev/main` oder `main`. Existiert der Branch weder lokal noch remote, wird er beim ersten
   Arbeitspaket neu angelegt, nicht auf einen anderen Branch ausgewichen. Nach jeder
   abgeschlossenen Aufgabe wird committet und gepusht. Danach prüft die CI und führt bei grünen
   Tests selbsttätig nach `dev/main` zusammen (nur in diese Richtung). Nach `main` geht **ein**
   Pull Request von `dev/main`, den der User freigibt — nie ein Agent — und der beim Anlegen dem
   Repo-Besitzer zugewiesen wird (`--assignee`). **`main` und die Version
   schreibt ausschließlich die CI**, und zwar erst nach dem Merge dieses Pull Requests — nie von
   Hand, nie durch einen Agenten; auf `dev/dev` und `dev/main` steht `version: "dev"` (D-025).
   Der Merge eines Pull Requests mit Änderung unter `skytech_omniai/` ist damit ein Release an
   alle Nutzer. Details: [docs/git-workflow.md](docs/git-workflow.md).
2. **Sprache Code:** Variablen, Funktionen, Klassen, Dateinamen **englisch**.
3. **Sprache Text:** Kommentare, Commit-Messages, Log-Meldungen, UI-Texte, Labels und
   User-Hinweise **deutsch**.
4. **Changelog-Pflicht:** Jede funktionale oder gestalterische Änderung bekommt im selben
   Commit einen Eintrag aus Nutzersicht — als Trailer `Changelog-<Kategorie>: …` am Ende der
   Commit-Message, nicht in einer Datei. Format und Kategorien:
   [docs/git-workflow.md](docs/git-workflow.md#changelog-einträge-als-trailer).
5. **Doku-Pflicht:** Ändert sich Verhalten, das in `docs/` beschrieben ist, wird die betroffene
   `docs/`-Datei im selben Arbeitspaket mitgeändert. Keine Nachreichung.
6. **Keine Secrets:** Keine API-Keys, Tokens oder Zugangsdaten im Code, in Logs, in Pfaden oder in
   Commit-Messages. Ausschließlich über Umgebungsvariablen, siehe
   [docs/konfiguration.md](docs/konfiguration.md).
7. **Nicht raten:** Ist eine Anforderung unklar, wird gefragt statt geraten. Getroffene Annahmen
   werden explizit genannt.
8. **Oberfläche:** Web-Oberflächen folgen dem festgelegten Stack und Design-System — React +
   TypeScript (`strict`) + Vite, eine `styles.css` mit Design-Tokens, eigenes Icon-Set. **Keine**
   UI-Bibliothek, kein CSS-Framework, kein State- oder Data-Fetching-Paket, keine Literalfarben und
   keine gestaltenden Inline-Styles. Vor der ersten Zeile Frontend-Code
   [docs/frontend.md](docs/frontend.md), [docs/design-system.md](docs/design-system.md) und
   [docs/nutzertexte.md](docs/nutzertexte.md) lesen.
9. **Datum und Uhrzeit:** Datumsangaben ausnahmslos als `TT.MM.JJJJ` (z. B. `13.08.2026`).
   Uhrzeiten ausnahmslos in Berliner Zeit (`Europe/Berlin`, Sommer- wie Winterzeit) als `hh:mm`,
   bei Bedarf auf die Sekunde genau als `hh:mm:ss`. **Nie** ein Zeitzonen-Kürzel oder einen Offset
   anhängen — weder als Zeichen noch als Wort: kein `+02:00`, kein `Z`, kein `MESZ`, kein `UTC`,
   und ebenso wenig „Berliner Zeit", „Ortszeit" oder `(Europe/Berlin)` als Zusatz. Die Zeitzone ist
   eine **Umrechnungsvorschrift, kein Anzeigetext**; der Leser sieht `21:03`. Gilt für alle für
   Menschen lesbaren Ausgaben: Doku, Changelog, ADRs, Commit-Messages, Log-Meldungen,
   UI-Texte und Fehlermeldungen. Maschinenformate (Datenbankspalten, API-Nutzlasten, Dateinamen)
   dürfen intern abweichen; bei der Ausgabe an den User wird nach Berliner Zeit in dieses Format
   umgesetzt. Wie viel davon überhaupt angezeigt wird, regelt Regel 12 und
   [docs/nutzertexte.md](docs/nutzertexte.md).
10. **Designsprache:** Es gibt vier festgelegte, **einen Default gibt es nicht**, und geraten wird
    nie:
    - **FCR** (`data-design="fcr"`) — Vereinsfarben des FC Ruderting — für Aufgaben und Projekte
      mit Bezug zum **FC Ruderting**.
    - **Home Assistant** (`data-design="ha"`) — Weiß bzw. Schwarz je nach Hell-/Dunkel-Modus,
      Akzentfarbe **`#18BCF2`** an Stelle des Rots — für Aufgaben und Projekte mit Bezug zu
      **Home Assistant**.
    - **Skytech** (`data-design="skytech"`) — Markenblau `#007ACC` (hell) / `#3AA0E8` (dunkel) —
      für Web-Oberflächen der **Skytech**-Projekte.
    - **Skytech iOS** (`skytech-ios`) — dieselbe Markenfarbe als natives SwiftUI-Theme, ohne
      `data-design` — für **iOS-Apps** der Skytech-Projekte.

    Für **jedes andere Projekt** und immer dann, wenn die Zuordnung nicht zweifelsfrei ist, wird
    die Farbwahl **erfragt, bevor die erste Zeile Oberfläche entsteht**. Die Frage entfällt nur,
    wenn der User die Designsprache bereits genannt hat — dann gilt ohne Rückfrage genau diese.
    Verlangt er ausdrücklich eine Rückfrage, wird **immer** gefragt, auch wenn die Zuordnung
    offensichtlich scheint. Fehlt `data-design`, bleibt der Akzent grau: eine Oberfläche ohne
    entschiedene Designsprache soll unfertig aussehen, nicht nach einem fremden Projekt.
    Für dieses Projekt gilt: **Home Assistant — Akzent `#18BCF2` (`data-design="ha"`)**.
    Details: [docs/design-system.md](docs/design-system.md).
11. **Hell und Dunkel:** Jede Oberfläche bietet einen sichtbaren Schalter zwischen Hell- und
    Dunkel-Modus. Beide Modi sind vollständig ausgestaltet — kein Modus ist ein nachträglich
    invertierter Notbehelf. Die Wahl bleibt über Neuladen hinweg erhalten, die Voreinstellung
    kommt vom Betriebssystem.
12. **Nur zeigen, was den Nutzer betrifft:** Eine Vorgabe an die Umsetzung ist **kein
    Anzeigetext**. Was der Nutzer sieht, beantwortet eine Frage, die er hat — alles andere gehört
    ins Log. Nie sichtbar sind deshalb: Zeitzonen und Offsets (Regel 9), HTTP-Statuscodes,
    Ausnahme- und Klassennamen, Stacktraces, Dateipfade, SQL, technische IDs, interne
    Zustands- und Feldnamen, Werkzeug- und Framework-Namen, `null`/`undefined`/`NaN` sowie
    Genauigkeit, die die Daten nicht hergeben. Prüffrage vor jeder Angabe: *Kann der Nutzer
    deswegen etwas anderes tun?* Nein → weglassen. Maßstab ist das **Publikum**: Was der
    Endnutzer liest, bleibt frei von Technik; was der Betreiber liest (Startabbruch,
    Konfigurationsfehler, Admin-CLI), nennt Pfad und Variablenname weiterhin — er soll es
    reparieren. Muss Technisches in einer Oberfläche doch erreichbar sein (Support,
    Administration), steht es aufgeklappt oder auf einer eigenen Seite, nie in der Hauptzeile.
    Details und Beispiele: [docs/nutzertexte.md](docs/nutzertexte.md).
13. **Keine KI-Accounts als Contributor:** Weder Commits noch Pull Requests tragen einen
    `Co-Authored-By`-Trailer, ein „Generated with"-Zeichen oder sonst eine Namensnennung von
    Claude, Codex, Gemini, Copilot oder einem anderen KI-Account. Auch Git-Autor und -Committer
    sind der Mensch hinter dem Repo. Eine Voreinstellung des Werkzeugs, die eine solche Zeile
    anhängt, wird überstimmt.
14. **Lizenz und Unterstützung:** Das Repo hat eine `LICENSE` (MIT) im Wurzelverzeichnis, und die
    `README.md` nennt sie im Abschnitt „Lizenz". Dieselbe `README.md` verlinkt im Abschnitt
    „Unterstützen" den BuyMeACoffee-Link. Fehlt eines von beidem, ist das Repo nicht fertig
    eingerichtet.
15. **Lokal = CI:** Die Befehle in der Tabelle „Befehle" sind die **einzige** Definition der
    Prüfung. Die CI führt exakt diese Prüfungen aus (`scripts/check.sh` ist der gemeinsame
    Einstiegspunkt) — keine zweite, abweichende Befehlsliste in `.github/workflows/`. Vor jedem
    Push läuft die **vollständige** Prüfung lokal, nicht nur der gerade betroffene Test. Ein
    roter CI-Lauf nach dem Push hat Vorrang vor jeder neuen Aufgabe und wird in der Reihenfolge
    behoben: Ursache finden, **lokal nachstellen**, beheben, erneut pushen. Details:
    [docs/test-strategie.md](docs/test-strategie.md).
16. **Projektübergreifende Verträge:** Schnittstellen zu anderen Skytech-Projekten stehen in
    [`contract/`](contract/README.md) — dort gilt die Struktur `contract/contract_<projektpaar>/`.
    Wer eine solche Schnittstelle ändert (Felder, Endpunkte, Semantik), liest zuerst
    `contract/README.md` und den betreffenden Vertrag und zieht **beide Kopien** (dieses Repo und
    die Gegenstelle) im **selben Arbeitspaket** nach. Der Master der HTTP-Schnittstelle liegt im
    Backend; die Kopie hier bleibt inhaltlich unverändert.

## Befehle

| Zweck | Befehl |
|---|---|
| Abhängigkeiten installieren | `pip install -r skytech_omniai/requirements.txt -r requirements-dev.txt && npm ci --prefix skytech_omniai/web` |
| Hooks aktivieren (einmalig) | `git config core.hooksPath .githooks` |
| **Alle Prüfungen (wie CI)** | `scripts/check.sh` — mit `--docker` zusätzlich Image und Smoke-Test |
| Tests | `pytest` |
| Linting / Formatierung | `ruff check . && ruff format --check . && npm run typecheck --prefix skytech_omniai/web` |
| Build | `docker build -t skytech-omniai skytech_omniai` |
| Release-Trockenlauf | `git fetch && python3 scripts/release.py plan` |

Vor jedem Commit muss `scripts/check.sh` fehlerfrei durchlaufen. Dieselben Prüfungen laufen in
GitHub bei jedem Push auf `dev/dev` ([docs/test-strategie.md](docs/test-strategie.md)).

## Wo steht was

Diese Datei enthält bewusst **keine** technischen Details. Vor der Arbeit an einem Thema die
passende Datei lesen, statt zu raten:

| Datei | Inhalt |
|---|---|
| [docs/README.md](docs/README.md) | Einstieg und Index der gesamten Doku |
| [docs/architektur.md](docs/architektur.md) | Komponenten, Datenfluss, Grenzen, Tech-Stack |
| [docs/entwicklerrichtlinien.md](docs/entwicklerrichtlinien.md) | Naming, Struktur, Fehlerbehandlung, Kommentarstil |
| [docs/frontend.md](docs/frontend.md) | Frontend-Stack, Ordnerstruktur, Routing, API-Client, Seiten- und Formularmuster |
| [docs/design-system.md](docs/design-system.md) | Design-Tokens, Klassenkatalog, Zustände, Responsiv, Icons, Barrierefreiheit |
| [docs/nutzertexte.md](docs/nutzertexte.md) | Was der Nutzer zu sehen bekommt: Formatierung, Fehlermeldungen, Formulierung |
| [docs/git-workflow.md](docs/git-workflow.md) | Branches (`dev/dev` → `dev/main` → `main`), Pull Request, Commit-Format, Changelog-Trailer, Hooks, Versionierung, automatisches Release |
| [docs/test-strategie.md](docs/test-strategie.md) | Testarten, Pflicht-Testfälle, Coverage-Ziel, Jobs der CI |
| [docs/design-entscheidungen.md](docs/design-entscheidungen.md) | Entscheidungs-Log — Quelle der Wahrheit fürs „warum" |
| [docs/konfiguration.md](docs/konfiguration.md) | Env-Variablen, Config-Optionen, Secrets-Handhabung |
| [docs/api-referenz.md](docs/api-referenz.md) | Endpunkte und öffentliche Schnittstellen |
| [contract/README.md](contract/README.md) | Projektübergreifende Verträge: Struktur, Regeln, Index der Gegenstellen (Vertrag v1 mit Skytech X: [contract/contract_skytech_x_omniai/omniai-api-v1.yaml](contract/contract_skytech_x_omniai/omniai-api-v1.yaml)) |
| [docs/sicherheit-datenschutz.md](docs/sicherheit-datenschutz.md) | Secrets, personenbezogene Daten, externe Dienste |
| [docs/bekannte-luecken.md](docs/bekannte-luecken.md) | Abweichungen Spec ↔ Code, Stolpersteine, offene Bugs |
| [docs/roadmap.md](docs/roadmap.md) | Meilensteine und Umsetzungsstand |

## Arbeitsablauf

1. Passende `docs/`-Datei lesen, bevor Code entsteht.
2. [docs/bekannte-luecken.md](docs/bekannte-luecken.md) prüfen, bevor angenommen wird, eine in der
   Doku beschriebene Funktion sei tatsächlich implementiert.
3. Implementieren, dann `scripts/check.sh` grün bekommen (Tests, Linting, Bau — wie die CI).
4. Betroffene `docs/`-Dateien im selben Arbeitspaket nachziehen.
5. Committen — bei nutzerrelevanter Änderung mit `Changelog-<Kategorie>:`-Trailer (Regel 4) —
   und pushen auf `dev/dev`. Version, Changelog-Datei und `main` fasst nur die CI an; nach
   dem Push ist nichts weiter zu tun, auch kein `git pull --rebase`. Das CI-Ergebnis wird
   abgewartet (`gh run watch`); rot hat Vorrang (Regel 15). Ist ein Vorhaben abgeschlossen,
   geht **ein** Pull Request `dev/main` → `main`, zugewiesen an den Repo-Besitzer.
6. Neue Grundsatzentscheidung? → Eintrag in
   [docs/design-entscheidungen.md](docs/design-entscheidungen.md), ausführlich als ADR unter
   [docs/adr/](docs/adr/).
