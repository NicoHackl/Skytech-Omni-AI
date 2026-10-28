# D-022: Gemini über das Google-AI-Pro-Abo mit der Antigravity-CLI, Anmeldung im Add-on selbst

- **Datum:** 28.10.2026
- **Status:** Aktiv (Anmeldung mit echtem Konto noch nicht von Hand geprüft — siehe „Handprüfung“)
- **Betrifft:** `providers/gemini_sub_provider.py`, `providers/gemini_sub_login.py`, `providers/factory.py`, `app.py` (`/auth/gemini…`), `settings.py`, `api_v1.py`, `Dockerfile`, `config.yaml`, `web/src/components/GoogleLogin.tsx`

## Kontext

Der User will die Gemini-Modelle über sein **Google-AI-Pro-Abo** nutzen, so wie `claude_sub` (D-006)
und `codex_sub` (D-013) das Abo ihres Anbieters über dessen Befehlszeile nutzen. Die Recherche vom
27.10.2026 ([erweiterungen/gemini-provider/](../erweiterungen/gemini-provider/README.md)) ergab:

1. Die Gemini CLI bedient AI-Pro-Konten seit dem 18.06.2026 nicht mehr. Der Nachfolger ist die
   **Antigravity CLI** (`agy`), ein statisch gelinktes Binary mit Headless-Modus
   (`agy -p … --output-format json`).
2. **Google unterstützt es bei privaten Abos ausdrücklich nicht**, `agy` in andere Anwendungen
   einzubinden („Wrapping `agy` inside third-party coding agents or applications […] is not
   supported under consumer plans“); die Nutzungsbedingungen nennen Konten mit Fremdwerkzeugen
   einschränkbar oder sperrbar. Der von Google empfohlene Weg für Fremdanwendungen ist der
   API-Schlüssel — den bietet das Add-on mit dem Provider `gemini` (D-007).
3. Die Anmeldung ist das eigentliche Problem. Anders als bei Claude (`setup-token`) und Codex
   (`auth.json` zum Einfügen) hat `agy` **keinen Anmeldebefehl** und kein Token für Server. Wer ohne
   Anmeldung einen Auftrag erteilt, bekommt eine Google-Adresse gedruckt und wartet 60 Sekunden auf
   einen Code. Berichte nennen, dass eine in einem anderen Container erzeugte Anmeldung nicht
   angenommen wird.

Der User hat am 27.10.2026 **in Kenntnis dieses Risikos** entschieden, den Abo-Weg trotzdem zu
bauen („Wir versuchen es mit agy über meinen Abo weg“).

## Messungen vom 27.10.2026

Arm64-Container auf Basis von `ghcr.io/home-assistant/aarch64-base:3.19`, Version 1.4.8, **ohne
Konto**. Das amd64-Binary wurde lokal nur gehasht (SHA-512 stimmt, ELF x86-64); gebaut und gestartet
(`agy --version`) hat es die CI im Smoke-Test des amd64-Images.

| Beobachtung | Folge für den Entwurf |
|---|---|
| Es gibt keinen Anmeldebefehl; jeder Auftrag ohne Anmeldung löst sie aus | Die Anmeldung läuft über einen Probeauftrag |
| Eingabe `/dev/null`: Adresse auf der Fehlerausgabe, dann 60 s Warten, ohne zu lesen | Als Eingabe taugt das nicht |
| Eingabe Pipe: sofort Abbruch („authentication required. Run ‘agy’ to log in“) | Als Eingabe taugt das ebenfalls nicht |
| Eingabe **Pty**: Adresse, dann liest die CLI den Code von der Eingabe | So hält das Add-on die Anmeldung offen |
| Falscher Code → nach 0,7 s `oauth2: "invalid_grant"`, JSON-Umschlag mit `status: ERROR`, Exitcode 1 | Der Tausch bei Google geschieht in der CLI; Fehlertext ist erkennbar |
| Zielseite `antigravity.google/oauth-callback` zeigt den Code mit „Paste this code into your application“ | Der Nutzer kopiert den Code und fügt ihn in der Oberfläche ein |
| `strace`: Die CLI öffnet `~/.gemini/antigravity-cli/antigravity-oauth-token`; Logzeile „Using file-based token storage because SSH session detected“ | Mit `SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY` im Aufruf nimmt sie sicher den Dateispeicher; Pfad bestätigt |
| Das Binary prüft `/.dockerenv` und kennt als Gründe für den Dateispeicher „SSH session“, „container environment“ und einen Schlüsselbund-Timeout | Gleiche Umgebung bei Schreiben und Lesen vermeidet Streuung |
| Eine selbst gebaute Token-Datei (geratenes Format) wird nicht als Anmeldung erkannt | Das Format kennt nur die CLI selbst — **kein Einfügen einer Datei**, die Anmeldung muss in der CLI entstehen |
| Nach einem fehlgeschlagenen Auftrag liegen Gesprächsordner, Zusammenfassungs-Datenbank und Protokolle auf der Platte | Aufräumen nach jedem Lauf |

## Betrachtete Optionen

### Option A — Nur den API-Weg ausbauen (Empfehlung der Recherche)

- Dafür: Von Google für Fremdanwendungen vorgesehen; keine Sperrgefahr, keine neue Abhängigkeit.
- Dagegen: Nutzt das Abo-Kontingent nicht — und das war der Auftrag. (Bleibt als eigener Plan
  erhalten: [api-weg.md](../erweiterungen/gemini-provider/api-weg.md).)

### Option B — `agy` mit Anmeldung im Add-on (gewählt)

- Dafür: Nutzt das Abo wie gewünscht; die Anmeldung entsteht dort, wo sie gebraucht wird, und
  umgeht damit die Berichte über nicht übertragbare Anmeldungen; fügt sich in die Fabrik (D-005).
- Dagegen: Von Google nicht unterstützt (Sperrung möglich); das Risiko erreicht mit dem Release
  jeden, der sich anmeldet. Bild wächst um rund 200 MB. Verbrauch pro Auftrag unbekannt. Gesprächsdaten
  auf der Platte, bei privaten Konten gelten die Datenbedingungen für Verbraucher.

### Option C — `agy` mit eingefügter Token-Datei (wie D-013)

- Dafür: Eine Oberfläche weniger.
- Dagegen: Das Format der Datei ist undokumentiert (eigener Versuch scheiterte), auf macOS liegt die
  Anmeldung im Schlüsselbund und es gibt keine Datei, und die Berichte nennen genau diese Übertragung
  als nicht funktionierend.

## Entscheidung

**Option B.** Der Provider heißt `gemini_sub` („Google Gemini (Abo)“), getrennt vom Schlüssel-Weg
`gemini`. Ausschlaggebend ist der Auftrag des Users; die Entscheidung gegen die Empfehlung der
Recherche ist seine, nicht die des Agenten. Damit das Risiko nur trägt, wer es will:

- Ohne Anmeldung tut der Provider nichts; die Anmeldung geschieht ausdrücklich, auf der Seite
  „Einstellungen“, mit sichtbarem Hinweis auf Googles Haltung.
- `claude_sub` bleibt Vorgabe des Add-ons.

Bauweise (Einzelheiten in [architektur.md](../architektur.md)):

- **Anmeldung** (`gemini_sub_login`): Probeauftrag mit Pty als Eingabe, Adresse an die Oberfläche,
  Code zurück in die Eingabe, danach Prüfung in einem **frischen** Prozess (`agy models`).
- **Speicher**: Dateispeicher unter `/data/.gemini/…`, erzwungen über `SSH_*` bei jedem Aufruf;
  Sicherung der Datei nach jedem erfolgreichen Lauf, Wiederherstellung bei beschädigter Datei.
- **Lauf**: ein Prozess zur Zeit, eigener leerer Arbeitsbereich, Regeln für Werkzeuge in der
  `settings.json` der CLI (Befehle nie freigegeben), schmale Umgebung, sofortiger Abbruch, wenn die
  CLI eine Anmeldung verlangt, Aufräumen der Gesprächsdaten nach jedem Lauf.
- **Bild**: Version 1.4.8 mit SHA-512 je Architektur im `Dockerfile`; Selbstaktualisierung aus.
- **Modelle**: keine feste Liste im Code (sie sind erst nach der Anmeldung abrufbar). Das Add-on
  liest sie aus `agy models`, merkt sie sich und zeigt sie in Oberfläche und Schnittstelle. Eigene
  Option `gemini_sub_model` für das Standardmodell, weil das gemeinsame Auswahlfeld `model` des
  Supervisors eine feste Liste verlangt. Kurzformen (`flash-3.8`, `argon-4`) werden gegen die Liste
  aufgelöst (ohne Stufe: Medium, sonst High, Low, Max); Mehrdeutiges oder Unbekanntes nennt die
  Auswahl. Das Zeilenformat von `agy models` ist nicht dokumentiert und wurde ohne Konto nicht
  gesehen — die Liste wird deshalb tolerant gelesen (Handprüfung H6).

## Folgen

- **Positiv:** Gemini über das AI-Pro-Kontingent, in derselben Bedienung wie die anderen Anbieter;
  der unterstützte API-Weg bleibt daneben bestehen.
- **Negativ:** Googles Haltung bleibt ein Risiko für das Konto des Betreibers. Datenschutz schwächer
  als beim Schlüssel (Eingaben bei privaten Konten laut Zusatzbedingungen nutzbar). Das Kontingent
  teilt sich mit der eigenen Nutzung von AI Pro; Automationen können es leeren. Anfragen laufen
  nacheinander. Die CLI ist ein Programmierassistent mit Werkzeugen — das Add-on engt sie ein, kann
  aber eine eingebaute Websuche nicht abschalten.
- **Aufwand:** Umgesetzt; Handprüfung mit echtem Konto steht aus.

## Handprüfung nach der ersten echten Anmeldung

Offen, weil sie ein Konto und einen Browser braucht. Jeden Punkt von Hand prüfen und bei
Abweichung hier und in [bekannte-luecken.md](../bekannte-luecken.md) nachtragen:

| Nr. | Prüfung | Erwartet |
|---|---|---|
| H1 | Karte „Google-Anmeldung“ durchlaufen | „Angemeldet“; im Protokoll des Add-ons steht die Liste der Modelle |
| H2 | Add-on neu starten, dann `POST /ask` mit `"provider": "gemini_sub"` | Anmeldung besteht, Antwort kommt |
| H3 | Mehr als eine Stunde warten, wieder fragen | Zugriffstoken wird erneuert, Datei verändert sich, Anfrage klappt |
| H4 | Nach einer Anfrage in `/data/.gemini/antigravity-cli/` nachsehen (`conversations`, `brain`, `implicit`, Datenbank) und nach dem Prompt-Text suchen | Nichts davon liegt noch da; der Satz steht nirgends im Klartext |
| H5 | Wetterfrage mit `web`; dieselbe mit `off`; Befehlsversuch im Prompt („führe `ls` aus“) | `web` recherchiert, `off` nicht, ein Befehl wird nie ausgeführt |
| H6 | Auswahl „Standardmodell“ auf der Seite „Einstellungen“ öffnen und mit dem Protokoll vergleichen (Zeile „Modelle der Google-CLI“); `model` pro Anfrage mit einer Bezeichnung aus der Liste, mit `flash-3.8` und `argon-4`, und mit einem erfundenen Namen | Die Liste stimmt mit der Ausgabe von `agy models` überein, eine Bezeichnung aus der Liste klappt wirklich (das beweist, dass `--model` sie so versteht), die Kurzformen finden Medium, der erfundene Name nennt die Auswahl. Weicht etwas ab: `parse_models` oder die Übergabe an `--model` anpassen |
| H7 | Zehn Anfragen, Verbrauch in der Google-Oberfläche vergleichen | Größenordnung je Auftrag notieren (Grundlage für Drosselung) |
| H8 | `/v1`-Anfrage mit kurzer Zeitgrenze | Zeitgrenze greift, danach läuft kein `agy`-Prozess mehr |
| H9 | Add-on-Update einspielen | Anmeldung bleibt |
| H10 | Zugriff im Google-Konto widerrufen, dann fragen | Meldung „Anmeldung gilt nicht mehr“ **sofort**, nicht nach 60 s |

## Rücknahmebedingung

Die Entscheidung wird überprüft, wenn eines davon eintritt:

- Google schränkt oder sperrt ein Konto wegen dieser Nutzung — Provider vom Auswahlfeld nehmen und
  den Nutzern sagen, warum.
- Die Anmeldung hält in der Handprüfung nicht (H2, H3, H9): ohne dauerhafte Anmeldung gibt es keinen
  Provider; dann Option A.
- Google dokumentiert eine Anmeldung für Server oder erlaubt die Einbindung ausdrücklich — dann die
  Hinweise auf das Risiko anpassen.
- Eine neue Fassung der CLI ändert den Ablauf der Anmeldung (Adresse, Prompt, Dateispeicher). Die
  Version ist festgenagelt; beim Anheben die Messungen oben und die Handprüfung wiederholen.
