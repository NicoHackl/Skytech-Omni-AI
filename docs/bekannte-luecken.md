# Bekannte Lücken und Stolpersteine

**Vor jeder Annahme lesen.** Diese Datei existiert, weil Doku und Code auseinanderlaufen. Steht
etwas in [architektur.md](architektur.md), heißt das nicht, dass es implementiert ist — hier steht,
wo nicht.

## Abweichungen Spec ↔ Code

| Thema | Doku sagt | Code macht | Folge für die Arbeit |
|---|---|---|---|
| API-Pfade | [frontend.md](frontend.md) beschreibt `/api/…` als Präfix | Die Endpunkte heißen `/ask`, `/models`, `/status`, `/health` ohne Präfix | Bewusst so, D-010. Beim Anlegen eines neuen Endpunkts kein `/api` voranstellen |
| Auslieferung | [frontend.md](frontend.md) nennt einen Webserver mit SPA-Fallback | Flask liefert das Bündel selbst aus | Bewusst so, D-009. Kein nginx im Bild |
| Vertrag v1 | [contracts/omniai-api-v1.yaml](contracts/omniai-api-v1.yaml) beschreibt `/v1/…` inklusive Agent-Läufen und Nutzungsdaten | Werkzeuge in Läufen nur mit `claude_sub`; `codex_sub` und `gemini` laufen ohne Werkzeuge als einzelne Anfrage. `/v1/completions` liefert keine Nutzungsdaten (M5) | Die Datei ist eine Kopie — geändert wird zuerst im Repo Skytech-X-Backend |
| Abbruch eines Laufs ohne Werkzeuge | Abbrechen beendet den Lauf | Eine laufende Einzelanfrage (`codex_sub`, `gemini`) lässt sich nicht unterbrechen; der Lauf endet erst mit ihrer Antwort und wird dann als abgebrochen gemeldet | Für lange Aufgaben `claude_sub` nehmen |

## Stolpersteine

- **Ein Push auf `agent/main` ist ein Release.** Ändert er etwas unter `skytech_omniai/` und ist
  die CI grün, bekommen alle Installationen das Update angeboten. Halbfertiges gehört auf einen
  `feature/`-Branch (D-017).
- **`main` ist kein Vorfahr von `agent/main`.** Jeder Release-Commit trägt Version und Changelog,
  die es auf `agent/main` nicht gibt. Nie von `main` abzweigen und nie `main` in `agent/main`
  mergen — sonst landen `version: "0.x.y"` und `skytech_omniai/CHANGELOG.md` im Arbeitsbranch,
  und der Konsistenztest schlägt an.
- **Ein Changelog-Trailer ist nach dem Push endgültig.** `agent/main` verbietet das Umschreiben
  der Historie. Ein falscher Eintrag bleibt stehen; ergänzt wird mit dem nächsten Commit. Der
  commit-msg-Hook fängt Tippfehler in der Kategorie ab, den Wortlaut prüft er nicht.
- **Die Oberfläche zeigt bei lokal gebautem Image „Version dev“.** Richtig so: die Nummer
  entsteht erst beim Release auf `main`.
- **Der Build-Kontext ist der Add-on-Ordner, nicht die Repo-Wurzel.** Eine Datei, die im
  `Dockerfile` mit `COPY` geholt wird, muss unter `skytech_omniai/` liegen. Deshalb steht `web/`
  dort und nicht in der Wurzel. Ein `COPY ../etwas` schlägt beim Supervisor fehl, auch wenn es
  lokal mit anderem Kontext funktioniert hat.
- **Der Ingress-Pfad wechselt mit jeder Sitzung.** Wer die `index.html` zwischenspeichern lässt
  oder einen absoluten Pfad im Bündel erzeugt, bekommt beim nächsten Öffnen eine leere Seite.
  Deshalb `base: './'` und `Cache-Control: no-store`.
- **Ohne Freigabe hat die CLI keine Werkzeuge — auch keine Websuche.** Im Modus `claude -p`
  gibt es keine interaktive Rückfrage, und was nicht ausdrücklich freigegeben ist, wird
  automatisch abgelehnt. Meldet das Modell, es könne nichts nachschlagen oder `WebFetch` sei
  unterbunden, ist **nichts blockiert** — es ist nur nichts freigegeben. Zuständig ist die Option
  `tool_access` (siehe [konfiguration.md](konfiguration.md)), nicht der Prompt.
- **Die Claude-CLI liest Projektkontext aus dem Arbeitsverzeichnis.** Läuft sie im Quellbaum,
  findet sie eine `CLAUDE.md` und deutet die Anfrage als Programmieraufgabe um. Sie wird deshalb
  ausdrücklich mit `cwd="/data"` gestartet — diese Zeile nicht wegoptimieren.
- **Die CLI hängt ihren Zustand an `HOME`, nicht an `XDG_CONFIG_HOME`.** Ein früherer Versuch über
  `XDG_CONFIG_HOME=/data` hatte keinerlei Wirkung; die Anmeldung war nach jedem Neustart weg.
- **Die Codex-CLI schreibt ihre Anmeldung zurück.** Sie erneuert die Tokens im Betrieb und legt sie
  wieder unter `$CODEX_HOME/auth.json` ab. Der Wert aus der Option `codex_auth_json` darf diese
  Datei deshalb nur überschreiben, wenn er sich geändert hat — die Marke `.seed` daneben hält den
  Fingerabdruck des zuletzt übernommenen Werts. Wer diese Prüfung wegoptimiert, bekommt eine
  Anmeldung, die nach Ablauf der Ersttokens tot ist.
- **Auch die Codex-CLI liest Projektkontext aus dem Arbeitsverzeichnis** — dort heißt die Datei
  `AGENTS.md`. Sie wird deshalb mit `--cd /data` gestartet.
- **`--search` gehört vor `exec`, nicht dahinter.** Den Schalter kennt nur der Hauptbefehl;
  `codex exec --search` bricht mit „unexpected argument“ ab. Deshalb stehen Sandbox-Stufe und
  Websuche-Schalter im Aufruf **vor** dem Unterbefehl. Ein Test hält diese Reihenfolge fest.
- **`codex exec` kennt kein `--append-system-prompt`.** Die Rolle „JSON-Endpunkt“ wird dem Prompt
  vorangestellt. Wer sie in ein eigenes Feld verschieben will, findet keines.
- **Ohne `with-contenv` fehlt dem Prozess die Container-Umgebung.** Das Basisimage startet über
  s6-overlay (`/init`) und reicht den `CMD` mit bereinigter Umgebung weiter. Dann fehlen
  `SUPERVISOR_TOKEN` (die Seite „Einstellungen“ zeigt nur an) und das `TZ` aus dem Dockerfile
  (Log-Zeitstempel in UTC). Der `CMD` beginnt deshalb mit `/usr/bin/with-contenv` — nicht
  wegoptimieren. Fehlt der Token trotz Optionsdatei, warnt das Log beim Start.
- **Speichern der Einstellungen hängt an der Absenderadresse des Ingress-Proxys.** `PUT /settings`
  prüft `172.30.32.2`, die feste Adresse des Supervisor-Ingress. Ändert Home Assistant diese
  Adresse, lehnt das Add-on jedes Speichern mit „nur über die Seitenleiste“ ab — dann die Konstante
  `INGRESS_PROXY_ADDR` in `app.py` nachziehen. Lokal (ohne Supervisor) ist die Seite nur Anzeige.
- **Änderungen im Reiter „Konfiguration“ brauchen weiter einen Neustart.** Nur die Seite
  „Einstellungen“ setzt die Umgebung des laufenden Prozesses neu. Wer im Reiter speichert und nicht
  neu startet, sieht auf der Seite den neuen Wert, während die Anfragen noch mit dem alten laufen.
- **Die Antigravity-CLI hat keinen Anmeldebefehl, und ihre Eingabe entscheidet über ihr Verhalten.**
  Mit `/dev/null` als Eingabe druckt sie die Google-Adresse und wartet 60 Sekunden, ohne zu
  lesen; mit einer Pipe gibt sie sofort auf; erst eine **Pty** lässt sie den Code lesen. Die
  Anmeldung in `gemini_sub_login.py` läuft deshalb über `pty.openpty()` — nicht auf eine Pipe
  „vereinfachen“. Gemessen mit Version 1.4.8 (D-022).
- **Die CLI wählt den Speicher ihrer Anmeldung selbst.** Schlüsselbund, Datei bei SSH-Sitzung oder im
  Container. Das Add-on setzt in **jedem** Aufruf `SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY`
  (`FORCED_FILE_STORAGE_ENV`), bei Anmeldung wie Anfrage. Fehlt es in einem von beiden, schreiben und
  lesen sie womöglich verschiedene Orte — das ist der Fehler, über den Berichte zu `agy` in Containern
  klagen.
- **Ohne gültige Anmeldung wartet die CLI 60 Sekunden auf einen Code, den niemand eingibt.** Der Lauf
  bricht deshalb sofort ab, sobald „authentication required“ auf der Fehlerausgabe steht
  (`AUTH_REQUIRED_MARKER`). Das hängt am englischen Text der CLI; bei einer neuen Fassung prüfen.
- **Die CLI legt Gespräche auf der Platte ab** (`conversations`, `brain`, `implicit`, eine
  Zusammenfassungs-Datenbank, Protokolle). Aufbau und Namen sind nicht zugesichert; aufgeräumt wird
  deshalb alles, was ein Lauf **neu** angelegt hat, nicht nach Namen. Das setzt voraus, dass immer nur
  ein Lauf zur Zeit läuft (`RUN_LOCK`) — die Sperre nicht entfernen.
- **Das Auswahlfeld `model` ist für alle Anbieter dasselbe.** Steht dort ein Claude-Alias und der
  Anbieter ist auf Gemini oder ChatGPT gestellt, lehnt der Provider die Anfrage ab — mit einer
  Meldung, die die gültigen Werte nennt. Das ist gewollt und kein Bug.

## Offene Bugs

| Thema | Auswirkung | Umgehung |
|---|---|---|
| Port 8000 ist unauthentifiziert | Wer den Port erreicht, kann Anfragen stellen und Kontingent verbrauchen | Port nicht ins Internet weiterleiten; wer nur die Oberfläche braucht, kann `ports` aus `config.yaml` entfernen und ausschließlich den Ingress nutzen |
| Werkzeugstufe `full` zusammen mit dem offenen Port | Ein Prompt von außen kann Befehle im Container ausführen und käme damit an das Token unter `/data` | Bei `full` den Port schließen und nur den Ingress nutzen. Vorgabe ist `web`, dort tritt der Fall nicht auf — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md) |
| Googles Schrittformat ist nicht zugesichert | Benennt Google die Schritttypen um, findet `_extract_text` den Text nicht mehr am erwarteten Ort | Ein Notfallpfad sammelt dann alles ein, was Text enthält. Bleibt auch das leer, kommt eine verständliche Meldung statt eines Absturzes |
| Die Pfade über die Befehlszeilen sind nur mit Attrappe getestet | Ein Verhaltenswechsel von `claude -p`, `codex exec` oder `agy -p` fällt in den Tests nicht auf | Nach jedem Anheben einer CLI-Version einmal von Hand eine Anfrage über den betroffenen Anbieter stellen |
| Das Image für `aarch64` wird in der CI nicht gebaut | Ein Fehler, der nur auf ARM auftritt (etwa ein fehlendes Binary der Codex- oder Antigravity-CLI), erreicht die Nutzer ungeprüft. Das `amd64`-Binary der Antigravity-CLI dagegen baut und startet die CI mit (Prüfsumme, `agy --version` im Smoke-Test) | `scripts/check.sh --docker` auf einem Apple-Silicon-Rechner baut und prüft genau dieses Image — vor Änderungen am Dockerfile von Hand ausführen |
| Basisimage und Befehlszeilen hält Dependabot nicht aktuell | Die Alpine-Fassung in `build.yaml` und die Versionen der Claude-, Codex- und Antigravity-CLI im Dockerfile veralten still (bei der Antigravity-CLI zusätzlich zwei SHA-512-Summen aus dem Manifest) | Von Hand anheben; bei den Befehlszeilen danach die Handprüfung aus der Zeile darüber |
| Google unterstützt `agy` in fremden Anwendungen bei privaten Abos nicht | Das Konto, das sich für `gemini_sub` anmeldet, kann eingeschränkt oder gesperrt werden; Googles Bedingungen nennen die Nutzung von Fremdwerkzeugen als Grund | Nur mit einem Konto anmelden, dessen Verlust nicht schmerzt. Unterstützter Weg: `gemini` mit Schlüssel aus Google AI Studio — D-022, [erweiterungen/gemini-provider/](erweiterungen/gemini-provider/README.md) |
| Mehrere Google-Konten wechseln automatisch (D-024) | Google nennt „automating account rotation“ bei privaten Abos ausdrücklich nicht unterstützt. Das Add-on wechselt ohne jede Tarnung (ein Rechner, eine Software, im Protokoll sichtbar), aber das Risiko steigt mit jedem Konto, und eine Maßnahme kann alle Konten treffen | Nur Konten anmelden, deren Verlust nicht schmerzt; nicht mehr Konten als nötig. Wer es nicht will, meldet nur ein Konto an — dann wechselt nichts |
| Wartezeit eines leeren Kontos ist geschätzt | Wie lange ein aufgebrauchtes Konto leer bleibt, sagt die CLI nicht (Google nennt ein Fenster von etwa fünf Stunden und ein Wochenlimit). Das Add-on versucht es nach 30 Minuten wieder, dann nach 1, 2, 4 und 5 Stunden. Ist das Wochenlimit erreicht, kostet jeder Versuch einen schnellen Fehler | In der Liste steht der nächste Versuch; Handprüfung H11 in D-024 |
| Erkennung „Kontingent aufgebraucht“ hängt am Text der CLI | Der Wechsel zum nächsten Konto löst `QUOTA_MARKER` aus („credits balance is too low“, „quota“, „rate limit“ …). Meldet die CLI das mit anderen Worten, wechselt nichts und die Anfrage scheitert mit der allgemeinen Meldung | Handprüfung H11; Marker in `gemini_sub_provider.py` ergänzen |
| Alle Google-Konten teilen eine Modellliste | Sie wird vom ersten angemeldeten Konto geholt. Gehören die Konten verschiedenen Tarifen an, nennt die Auswahl Modelle, die ein Konto nicht kennt | Konten desselben Tarifs anmelden |
| Anmeldung bei Google nur gegen die Attrappe getestet | Der Ablauf ist in einem Container der Zielarchitektur bis zum Austausch des Codes geprüft; dass eine **echte** Anmeldung Neustarts, Erneuerung des Zugriffstokens und Updates übersteht, ist nicht belegt | Handprüfung H1 bis H10 in D-022 nach der ersten Anmeldung durchgehen |
| Modellliste von Google Gemini (Abo) ist nur gelesen, nicht belegt | Das Zeilenformat von `agy models` ist nicht dokumentiert und wurde ohne Konto nie gesehen; `parse_models` liest tolerant (Aufzählungszeichen, „(default)“, Zusatzspalten). Auch dass `--model` genau die gelistete Bezeichnung versteht, ist ungeprüft. Das gemeinsame Auswahlfeld `model` der Konfiguration enthält für diesen Anbieter nur `auto`; das Standardmodell steht in `gemini_sub_model` | Handprüfung H6 in D-022. Stimmt die Liste in der Auswahl nicht, steht die Rohausgabe im Protokoll („Modelle der Google-CLI“ bzw. „Keine Modelle … gelesen“) |
| Kurzformen bei Google Gemini (Abo) wählen eine Stufe | `flash-3.8` ohne Stufe wird zu Medium (sonst High, Low, Max); wer eine andere Stufe will, nennt sie (`flash-3.8-high`). Die Stufen sind Teil der Bezeichnung, nicht der `--effort`-Schalter der CLI | In [konfiguration.md](konfiguration.md#modelle-bei-google-gemini-abo) beschrieben |
| Eingebaute Websuche der Antigravity-CLI lässt sich nicht abschalten | Bei `tool_access: off` bittet das Add-on das Modell nur, keine Werkzeuge zu nutzen | Wer sicher keine Suche will, nimmt `gemini` mit Schlüssel — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md) |
| Verbrauch von Google Gemini (Abo) je Anfrage unbekannt | Die CLI arbeitet als Agent (denkt, plant, ruft Werkzeuge); Automationen können das 5-Stunden-Kontingent leeren, das auch die eigene Nutzung von AI Pro braucht. Anfragen laufen nacheinander | Anfragen sparsam stellen; Handprüfung H7 liefert die Größenordnung |
| Stufe `web` ist bei ChatGPT weiter gefasst als bei Claude | `--sandbox read-only` verhindert Schreiben und eigene Netzverbindungen, lesende Befehle im Container aber nicht | Wer das ausschließen will, stellt `tool_access` auf `off` oder nutzt `claude_sub` — siehe [sicherheit-datenschutz.md](sicherheit-datenschutz.md) |

## Bewusst nicht umgesetzt

| Thema | Warum nicht | Verweis |
|---|---|---|
| Authentifizierung des offenen Ports | Automatisierungen in Home Assistant bräuchten dann ein zusätzliches Token; der Nutzen steht im Heimnetz nicht dafür | [roadmap.md](roadmap.md) |
| Verlauf über mehrere Anfragen | Jede Anfrage steht für sich. Ein Verlauf hieße Persistenz und ein Datenschutzthema, das keiner gefordert hat | [architektur.md](architektur.md) |
| Lokale Modelle über Ollama | Die Fabrik ist darauf vorbereitet, der Bedarf war bisher nicht da | [roadmap.md](roadmap.md) |
| Geräte-Anmeldung für ChatGPT in der Oberfläche | Der Zugang wird einmalig eingefügt; ein eigener Anmeldevorgang lohnt für einen einmaligen Schritt nicht. (Bei Google Gemini ist es umgekehrt: dort gibt es nichts zum Einfügen, deshalb entsteht die Anmeldung im Add-on — D-022) | D-013 |
| 32-Bit-Architekturen | Die Codex- und die Antigravity-CLI gibt es nur für 64 Bit | D-014, D-022 |
| Antwort gegen ein Schema prüfen | Das Add-on weiß nicht, welche Form der Aufrufer erwartet | — |

---

Wird ein Punkt behoben, wird er hier **gelöscht** und mit einem Changelog-Trailer im Commit vermerkt.
Eine Liste voller erledigter Einträge liest niemand mehr.
