# Umsetzungsplan

Arbeitspakete für die [Umbenennung](umbenennung-agy.md) und den Anbieter „Gemini Web“
([Entwurf](entwurf.md)). **AP 0 geklärt, AP 1 umgesetzt; weitere Pakete folgen.** Vor AP 1 und AP 8 sind die offenen Fragen
aus [README.md](README.md#offene-fragen--vor-dem-genannten-arbeitspaket-zu-klären) zu klären.

## Rahmen für jedes Arbeitspaket

Die Regeln stehen in [`../../../AGENTS.md`](../../../AGENTS.md) und werden hier nicht wiederholt. Was
für dieses Vorhaben davon zählt:

| Regel | Folge hier |
|---|---|
| Git (Regel 1) | Arbeit auf `dev/dev`, nach jedem Arbeitspaket committen und pushen. **Der Merge des Pull Requests `dev/main` → `main` ist ein Release an alle Nutzer** (D-025); er liegt beim User, nie beim Agenten |
| Version (D-016) | AP 1 ist ein **Bruch** (`!` und `BREAKING CHANGE:`) und führt zu einem neuen **MAJOR**. Das ist beabsichtigt und der User weiß es; der Trockenlauf `git fetch && python3 scripts/release.py plan` zeigt es vor dem Merge |
| Changelog (Regel 4) | Trailer `Changelog-<Kategorie>:` aus Nutzersicht, nur bei nutzerrelevanter Änderung |
| Doku (Regel 5) | Betroffene `docs/`-Dateien im selben Arbeitspaket, keine Nachreichung |
| Nicht raten (Regel 7) | Die mit „offen“ markierten Punkte in [recherche.md](recherche.md) sind Prüfaufträge. Läuft etwas anders als angenommen, wird **gefragt** und der Plan angepasst |
| Oberfläche (Regeln 8, 10, 11) | Nur bestehende Komponenten und Klassen; Designsprache Home Assistant (`data-design="ha"`); neue Seite in beiden Modi ansehen |
| Nur zeigen, was betrifft (Regel 12) | Meldungen ohne Statuscodes, Pfade, Klassennamen, Rohausgabe der Bibliothek, Cookie-Werte |
| Keine Secrets (Regel 6) | Cookies stehen in keinem Log, keiner Antwort, keiner Adresse, keinem Test, keiner Commit-Message |
| Verträge (Regel 16) | `contract/` bleibt wortgleich mit dem Master. Anhänge in `/v1` erst nach Änderung dort (F4) |
| Lizenz (Regel 14) | AP 3 hält die AGPL-Folge im ADR fest; die `README.md` nennt sie im Abschnitt „Lizenz“ |
| Tests | Ohne Netz, ohne echte Zugänge, **ohne die Bibliothek**: Die Brücke wird ersetzt. Pflichtfälle Normal, Fehler, Leer; für Meldungen zusätzlich „keine Technik im Text“ ([../../test-strategie.md](../../test-strategie.md)) |
| Prüfung | `scripts/check.sh` vor jedem Commit; bei Änderungen an `requirements.txt` oder am Dockerfile zusätzlich `scripts/check.sh --docker`. Rot hat Vorrang (Regel 15) |

**Kein Arbeitspaket gibt den neuen Anbieter in der Oberfläche frei, bevor er benutzbar ist.**
`gemini_web` taucht in der `provider`-Liste (AP 6) und in der Seitenleiste (AP 8) auf; bis dahin ist
er im Add-on nicht wählbar. Der Pull Request nach `main` sollte erst nach AP 8 gemergt werden, es sei
denn, der User will AP 1 vorab als eigenen Release.

## Reihenfolge und Abhängigkeiten

| AP | Inhalt | Abhängig von | Wer |
|---|---|---|---|
| 0 | Offene Fragen F1 bis F6 klären | — | User |
| 1 | Umbenennung `gemini_sub` → `gemini_agy` | 0 (F1, F2, F5) | Agent |
| 2 | Spike mit Wegwerf-Konto | 0 (F6) | User führt aus, Agent wertet aus |
| 3 | Abhängigkeit und Lizenz | 2 | Agent |
| 4 | Gemeinsamer Kern der Kontenliste | 1 | Agent |
| 5 | Anbieter `gemini_web`: Brücke, Konten, Wechsel | 2, 3, 4 | Agent |
| 6 | Konfiguration und Schnittstellen | 5 | Agent |
| 7 | Routen der Anmeldung | 5 | Agent |
| 8 | Oberfläche | 7, 0 (F1) | Agent |
| 9 | Anhänge | 5, 0 (F4) | Agent |
| 10 | Doku, Sicherheit, Roadmap, Abschluss | alle | Agent |
| 11 | Handprüfung mit echten Konten | 10 | User |

AP 1 und AP 2 sind unabhängig und können gleichzeitig laufen.

## AP 0 — Klärung

Die sechs Fragen F1 bis F6 beantworten lassen. Danach in [README.md](README.md) die Zeilen von „offen“
nach „Getroffene Entscheidungen“ verschieben und die angenommenen Namen in
[umbenennung-agy.md](umbenennung-agy.md) bestätigen oder ändern.

## AP 1 — Umbenennung

Genaues Vorgehen und Tabelle der Änderungen: [umbenennung-agy.md](umbenennung-agy.md).

- **Code, Oberfläche, Konfiguration, Tests, Doku:** wie dort aufgelistet. Datenpfade bleiben.
- **ADR:** `docs/adr/D-031-umbenennung-gemini-agy.md`, Zeile in `design-entscheidungen.md`;
  Hinweis oben in D-022 und D-024.
- **Tests:** Die vorhandenen Tests laufen nach dem Umbenennen unverändert grün — das ist die
  Abnahme dafür, dass nur Namen und kein Verhalten sich geändert hat. Neu: Ein Test, dass `gemini_sub`
  von der Fabrik **abgelehnt** wird und die Meldung die gültigen Anbieter nennt.
- **Commit:** `refactor(agy)!: Anbieter gemini_sub heißt jetzt gemini_agy` mit
  `BREAKING CHANGE: …` und
  `Changelog-Geändert: Der Anbieter „Google Gemini (Abo)“ heißt jetzt „Google Gemini (AGY)“.
  Vor dem Update den Anbieter in den Einstellungen darauf umstellen, sonst startet das Add-on nicht.
  Das Standardmodell ist danach neu zu wählen; die Google-Konten bleiben angemeldet.`
- **Abnahme:** Suche nach `gemini_sub` und `Gemini (Abo)` findet nur noch ADRs und `CHANGELOG.md`;
  `scripts/check.sh --docker` grün; Seitenleiste in beiden Modi und bei 375px angesehen.

## AP 2 — Spike (Ablauf geändert durch den User)

Der User führt den Kontotest erst nach Installation des Updates aus. Der Bau geht nach
der lokalen Plattformprüfung weiter; kontobezogene Ergebnisse werden nicht vorweggenommen.
Die Forderung „bevor gebaut wird“ unten ist damit für Kontotests aufgehoben.

Ziel: Die „offen“-Punkte aus [recherche.md](recherche.md) beantworten, **bevor** gebaut wird. Ergebnis
ist eine Datei `spike-ergebnis.md` in diesem Ordner, sonst nichts im Add-on.

**Der Agent bekommt keine Cookies.** Er schreibt ein Skript (im Scratchpad, nicht im Repo), der User
führt es lokal aus (`! python3 …`) und gibt nur das Ergebnis weiter. Cookies werden nie in eine
Datei im Repo, nie in den Chat und nie in eine Befehlszeile geschrieben, die im Verlauf der Shell
landet: das Skript liest sie aus einer Datei außerhalb des Repos, die der User anlegt (Rechte `0600`)
und danach löscht.

| Nr. | Frage | Ergebnis soll zeigen |
|---|---|---|
| S1 | Läuft die Bibliothek auf dem Basisimage des Add-ons (Alpine 3.19, musl) für **aarch64 und amd64** mit `curl-cffi`, `orjson`, `pydantic-core`? | Installation ohne Compiler oder die Liste der fehlenden Wheels |
| S2 | Gibt es Wheels für **Python 3.14** (CI-Matrix)? | Ja, oder die Tests laufen ohne Bibliothek (Entwurf) |
| S3 | Startzeit des Clients, und hält ein Client über Stunden? | Entscheidung „Client halten“ oder „je Anfrage neu“ |
| S4 | Welche Modellnamen bietet ein AI-Pro-Konto an? Wie lassen sich Kurzformen auflösen? | Liste, Auflösungsregeln |
| S5 | Gelingt eine Anfrage mit JSON-Anweisung zuverlässig? Wie oft kommt Prosa oder ein Codeblock? | Trefferquote von `parse_json` |
| S6 | Wie sieht `UsageLimitExceededError` aus, wenn das 5-Stunden-Fenster leer ist, und wenn das **Wochenlimit** erreicht ist? Nennt Google einen Zeitpunkt? | Wartezeiten, Unterscheidung der Fälle |
| S7 | Wie verhalten sich die Cookies: Wie lange gelten sie auf einer Serveradresse? Verlangt Google erneute Anmeldung? Läuft die Erneuerung von `__Secure-1PSIDTS` ohne Browser? Lässt sich der Cookie-Pfad **je Konto** setzen? | Haltbarkeit, Ablauf für die Oberfläche, Entwurf der Speicherung |
| S8 | Gibt es **temporäre Chats** für Anfragen? Bleibt sonst jede Anfrage im Verlauf? | Antwort auf F3 |
| S9 | Anhänge: Welche Typen, welche Größen, wie viele? Was meldet die Web-App bei Ablehnung? | Grenzen für AP 9 |
| S10 | Verhalten bei zwei gleichzeitigen Anfragen auf einem Konto | Entscheidung zur Parallelität |
| S11 | **Update-Verhalten bei ungültigem `provider`:** Home Assistant (Testinstanz) mit gespeichertem `gemini_sub`, Update auf ein Schema ohne diesen Wert | Antwort auf F5: Startet das Add-on nicht, mit welcher Meldung? |
| S12 | Pflegezustand: Datum der Version 2.1.1, Abstand der letzten Veröffentlichungen, offene Fehler zu `UsageLimitExceededError` und `AuthError` | Einschätzung, wie oft Google die Bibliothek bricht |

**Abbruchkriterium:** Scheitern S1 oder S7 grundlegend (keine lauffähige Installation im Add-on oder
Cookies, die nach Stunden verfallen und sich nicht erneuern), wird **nicht weitergebaut**, sondern
mit dem User entschieden: eigener Client, anderes Image, oder Verzicht.

## AP 3 — Abhängigkeit und Lizenz

- **`requirements.txt`:** `gemini-webapi` und seine Abhängigkeiten mit fester Version, im Stil der
  vorhandenen Kommentare (warum, Wheels für musl). Versionen aus S1 und S2.
- **ADR:** `docs/adr/D-030-gemini-web-inoffiziell.md` — Kontext, Optionen (Bibliothek, eigener
  Client, Verzicht), Entscheidung des Users, **Lizenzfolge (AGPL-3.0 in MIT-Repo)** mit dem, was
  bekannt ist, und ohne Rechtsberatung; Risiko (Bedingungen von Google); Rücknahmebedingungen aus
  [handpruefung.md](handpruefung.md). Zeile in `design-entscheidungen.md`.
- **Lizenzhinweise:** `README.md` (Abschnitt „Lizenz“) nennt die Bibliothek und ihre Lizenz;
  Quelle und Lizenztext der Bibliothek werden im Image mitgeliefert, wo die Lizenz es verlangt.
- **Prüfung:** `scripts/check.sh --docker`; der Smoke-Test des Images importiert die Bibliothek.
- **Commit:** `build(gemini-web): gemini-webapi festgenagelt, ADR D-030`, ohne Changelog-Trailer
  (für Nutzer nichts sichtbar).
- **Abnahme:** Image baut für beide Architekturen; die Lizenzfolge ist dokumentiert und vom User gelesen.

## AP 4 — Gemeinsamer Kern der Kontenliste

- **Code:** `providers/google_accounts.py` mit dem neutralen Teil aus `gemini_agy_accounts.py`
  (Liste lesen und schreiben, Reihenfolge, Zustand, `ready_accounts`, `mark_exhausted` mit
  wachsender Wartezeit, `mark_needs_login`, `mark_ok`, `next_try_time`). Parametriert durch Dateiname,
  Ordner und eine Beschreibung des Kontos auf der Platte. `gemini_agy_accounts.py` nutzt ihn.
- **Tests:** Alle vorhandenen Tests von `gemini_agy_accounts` laufen unverändert grün. Neu: Tests
  des Kerns mit einer zweiten, künstlichen Kontenart (zeigt, dass er nicht an `agy` hängt).
- **Commit:** `refactor(konten): gemeinsamer Kern der Google-Kontenliste`, kein Trailer.
- **Abnahme:** Verhalten von `gemini_agy` unverändert (Tests); Kern ohne Verweis auf `agy`.

## AP 5 — Anbieter `gemini_web`

- **Brücke:** `providers/gemini_web_client.py` — Thread mit Ereignisschleife, Client je Konto (oder
  je Anfrage, nach S3), Zeitlimit, Schließen, Import der Bibliothek erst beim Gebrauch.
- **Konten:** `providers/gemini_web_accounts.py` — Cookies auf der Platte (Rechte `0600`), Liste über
  den Kern aus AP 4, Rückschreiben der erneuerten Cookies (nach S7).
- **Anbieter:** `providers/gemini_web_provider.py` — `execute`, Wechsel nach der Tabelle im
  [Entwurf](entwurf.md#wechsel-wie-d-024), Modelle lesen und merken, Auflösung von Kurzformen,
  `parse_json`, temporärer Chat nach F3 und S8.
- **Fabrik:** Eintrag `gemini_web` in `factory.py` (Name, Anzeigename in den Meldungen).
- **Tests** (Brücke ersetzt, keine Bibliothek, keine Cookies): Normalfall liefert JSON; leeres
  Ergebnis und Prosa ohne JSON → `NotJson`; `UsageLimitExceededError` wechselt zum zweiten Konto und
  setzt Wartezeit; alle Konten leer → sofortige Meldung mit Uhrzeit, **Brücke nicht aufgerufen**;
  `AuthError` → `login_expired`; `TemporarilyBlockedError` → **kein** Wechsel; `ModelInvalidError` →
  Meldung mit Auswahl; Zeitlimit → `ProviderTimeout`; Meldungen ohne Technik und **ohne
  Cookie-Werte** (auch nicht im Log: `caplog` prüfen).
- **Commit:** `feat(gemini-web): Anbieter Gemini Web mit mehreren Google-Konten`, noch ohne
  Changelog-Trailer (nicht wählbar, bis AP 6 und 8 fertig sind).
- **Abnahme:** Unit-Tests grün; im Spike-Skript lässt sich derselbe Anbieter mit einem echten
  Wegwerf-Konto ansprechen (Handprüfung HW1, HW2).

## AP 6 — Konfiguration und Schnittstellen

- **Konfiguration:** `config.yaml` (`provider`-Liste, Option `gemini_web_model`), `config_loader.py`,
  `settings.py` (Anbieter, Prüfung der Bezeichnung), Konsistenztest zwischen Schema und
  `PROVIDER_MODELS`.
- **Schnittstellen:** `GET /status` (`credentials`), `GET /models`, `GET /v1/capabilities`,
  `api_v1.py`.
- **Doku:** `api-referenz.md`, `konfiguration.md`.
- **Tests:** Anbieter ist wählbar und speicherbar; leere Modellliste ohne Konto; `credentials` nennt
  nur ja/nein.
- **Commit:** `feat(gemini-web): Anbieter in Konfiguration und Schnittstellen`.
- **Abnahme:** `GET /models` und `GET /v1/capabilities` nennen `gemini_web`.

## AP 7 — Routen der Anmeldung

- **Code:** `app.py` — die vier Routen aus dem [Entwurf](entwurf.md#schnittstelle-des-add-ons), gleiche
  Sperre (Ingress) wie `/auth/gemini-agy…`. Cookies nur im Rumpf; Antworten ohne Werte.
- **Tests:** Anlegen mit gültigem Konto (Brücke ersetzt), mit ungültigem → Satz ohne Technik und
  **kein** angelegtes Konto; Entfernen löscht den Ordner; ohne Ingress → abgelehnt; kein Cookie-Wert
  in Antwort und Log.
- **Doku:** `api-referenz.md`.
- **Commit:** `feat(gemini-web): Routen zum Anmelden und Entfernen von Konten`.
- **Abnahme:** Alle Routen mit `curl` und ersetzter Brücke ausprobiert.

## AP 8 — Oberfläche

- **Code:** `pages/einstellungen/GeminiWeb.tsx`, Eintrag in `settingsSections.ts`, Route in
  `App.tsx`, `provider.ts`, `types.ts`, `api.ts`, Dashboard und Modelle.
- **Texte:** Hinweis zum Risiko, Anleitung zum Kopieren der Werte (aufklappbar), Fehlersätze; alle
  nach [nutzertexte.md](../../nutzertexte.md), Anrede „du“ wie im Rest der Oberfläche prüfen.
- **Prüfung:** `npm run typecheck`, Build; Seite in Hell und Dunkel und bei 375px ansehen; keine
  Literalfarbe, kein gestaltender Inline-Style; kein Cookie-Wert im DOM nach dem Absenden (Eingabefelder
  werden geleert).
- **Doku:** `frontend.md` (Bereich), `konfiguration.md` (Anleitung für den User).
- **Commit:** `feat(gemini-web): Bereich „Gemini Web“ in den Einstellungen` mit
  `Changelog-Hinzugefügt: Neuer Anbieter „Gemini Web“: nutzt das Nutzungslimit der Gemini-Web-App
  über eigene Google-Konten, mit Wechsel zwischen mehreren Konten. Von Google nicht unterstützt —
  das Konto kann gesperrt werden.`
- **Abnahme:** Konto anlegen, entfernen und Zustände sichtbar machen (mit ersetzter Schnittstelle);
  erst danach zeigt der Plan den Anbieter als „fertig“.

## AP 9 — Anhänge

Nur nach Antwort auf F4. Grenzen aus S9.

- **Code:** `base_provider.py` (`Attachment`, `attachments`, Ablehnung ohne Unterstützung),
  `app.py` (`/ask` mit `attachments`, Prüfung von Anzahl, Größe, Typ, gültigem Base64),
  Brücke (temporäre Dateien, **immer** gelöscht), `gemini_web_provider.py`.
- **Alle anderen Anbieter** bekommen die Ablehnung durch die Basisklasse; keiner ignoriert Anhänge.
- **Tests:** Anhang erreicht die Brücke; Datei wird danach gelöscht, auch bei Fehler; zu groß, zu
  viele, falscher Typ, ungültiges Base64 → ein Satz; Anbieter ohne Anhänge → 400 mit Satz; `/v1`
  unverändert.
- **Doku:** `api-referenz.md`, `architektur.md`, `sicherheit-datenschutz.md` (Anhänge gehen an Google).
- **`/v1`:** nur nach Änderung im Master; dann beide Kopien des Vertrags im selben Arbeitspaket
  (eiserne Regel 16) und Meldung an Skytech X.
- **Commit:** `feat(gemini-web): Dateien und Bilder als Anhang in /ask` mit
  `Changelog-Hinzugefügt: Anfragen an Gemini Web können Dateien und Bilder als Anhang mitschicken.`
- **Abnahme:** Handprüfung HW6.

## AP 10 — Doku, Sicherheit, Roadmap, Abschluss

- `architektur.md` (Komponente, Datenfluss, Ablage unter `/data`), `bekannte-luecken.md`
  (Risiko, keine Werkzeugstufe, Verlauf im Konto, Cookie-Haltbarkeit, Lizenz), `sicherheit-datenschutz.md`
  (Cookies, Konto ohne Daten, Daten an Google), `roadmap.md`, `docs/README.md`, `info.md`.
- Diesen Ordner auf den Ist-Stand bringen: Kopf von [README.md](README.md) auf „umgesetzt“, die
  Dateien `entwurf.md` und `umsetzungsplan.md` kürzen oder entfernen, wie es bei
  [../gemini-provider/](../gemini-provider/README.md) geschah. `spike-ergebnis.md` bleibt als Beleg.
- Suche nach Cookie-Werten, Tokens und Zugangsdaten in Repo, Log-Ausgaben der Tests und Dokumentation.
- **Commit:** `docs(gemini-web): Doku auf den Stand der Umsetzung`.

## AP 11 — Handprüfung

[handpruefung.md](handpruefung.md) mit echten, eigens eingerichteten Konten. Der User führt sie aus; der
Agent trägt Abweichungen in ADR D-030 und `bekannte-luecken.md` nach.
