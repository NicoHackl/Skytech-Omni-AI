# Abo-Weg über die Antigravity CLI (Entwurf `gemini_sub`)

> **Status: zurückgestellt, nicht empfohlen.** Dieses Dokument beschreibt, wie ein Provider für
> das Google-AI-Pro-Abo aussehen würde, damit die Entscheidung auf Fakten beruht und die Arbeit
> nicht doppelt gemacht wird. Gebaut wird er erst, wenn **alle drei** Schranken offen sind:
>
> | Schranke | Bedingung |
> |---|---|
> | **G1 — Erlaubnis** | Der User hat das Risiko aus [recherche.md](recherche.md#die-entscheidende-klausel) ausdrücklich angenommen (ADR, siehe [adr-entwurf.md](adr-entwurf.md)) — oder Google erlaubt das Einpacken von `agy` unter Verbraucherplänen |
> | **G2 — Anmeldung** | Der Spike [spike-abo-anmeldung.md](spike-abo-anmeldung.md) zeigt, dass eine eingefügte Anmeldung Neustarts und frische Prozesse übersteht |
> | **G3 — Aktualität** | Die FAQ-Klausel und die Headless-Doku wurden am Tag des Baubeginns erneut gelesen |

## 1. Steckbrief der `agy`-CLI

Version 1.4.8, Stand 27.10.2026. Marken wie in [recherche.md](recherche.md).

### Installation und Laufzeit

| Thema | Befund | Marke |
|---|---|---|
| Form | Ein einzelnes Binary (laut Installer in Go gebaut), kein Node, kein Python nötig. `ldd` meldet unter Alpine „Not a valid dynamic program“ — statisch gelinkt | geprüft |
| Größe | Archiv 60 MB, entpacktes Binary 196 MB — das Bild würde um rund 200 MB wachsen | geprüft |
| Plattformen | Linux amd64/arm64, jeweils als glibc- und als musl-Build; macOS, Windows, Android | Google (Installer) |
| Alpine | Installer wählt bei erkanntem musl `linux_<arch>_musl`. `agy --version` → `1.4.8` auf `ghcr.io/home-assistant/aarch64-base:3.19` | geprüft |
| Herunterladen | Manifest je Plattform unter `https://antigravity-cli-auto-updater-974169037036.us-central1.run.app/manifests/<plattform>.json` mit `version`, `url`, `sha512`; Binary liegt im Archiv unter dem Namen `antigravity`, der Installer kopiert es nach `agy` | geprüft |
| Auto-Update | Die CLI aktualisiert sich im Hintergrund selbst. Abschalten: `AGY_CLI_DISABLE_AUTO_UPDATE=true`. Ohne Abschalten widerspräche sie dem Festnageln der Version (siehe [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md#abhängigkeiten)) | Google (Fehlersuche) |
| Prozessmodell | Jeder Aufruf startet einen eigenen lokalen Sprachserver (gRPC und HTTP auf zufälligen Ports von `localhost`); Hintergrundprozesse enden laut Änderungsliste (1.2.9) mit dem Headless-Lauf | geprüft (Log), Google |
| Netz | `antigravity.google` und `storage.googleapis.com` (Installation, Update), `accounts.google.com`, `oauth2.googleapis.com`, `www.googleapis.com` (Anmeldung), `cloudcode-pa.googleapis.com` (Anfragen) | Bericht |

### Zustand auf der Platte (alles unter `$HOME`)

| Pfad | Inhalt | Marke |
|---|---|---|
| `~/.gemini/antigravity-cli/` | Logs (`log/`, `cli.log`), `installation_id`, Gespräche (`conversations/`, `brain/`, `implicit/`, `conversation_summaries.db`), `cache/`, `builtin/` | geprüft |
| `~/.gemini/config/` | `mcp_config.json`, `projects/`, Migrationsmarke | geprüft |
| `~/.config/antigravity/plugin-secrets.json` | Dateispeicher für Plugin-Geheimnisse, wenn kein Schlüsselbund da ist | geprüft (Log) |
| `~/.gemini/antigravity-cli/settings.json` | Einstellungen, Berechtigungsregeln, `trustedWorkspaces` | Google |
| `~/.gemini/antigravity-cli/antigravity-oauth-token` | Anmeldung im **Dateispeicher**: JSON mit `auth_method` und `token` (`access_token`, `token_type`, `refresh_token`, `expiry`); Zugriffstoken gilt etwa eine Stunde, `refresh_token` ist langlebig | Bericht ([#479](https://github.com/google-antigravity/antigravity-cli/issues/479)) |

Zustandsdateien für Gespräche (`conversations/`, `implicit/`, `conversation_summaries.db`) werden
**schon bei einem fehlgeschlagenen Lauf** angelegt (geprüft). Ob nach einem erfolgreichen Lauf
Prompt und Antwort darin stehen, zeigt der Spike; Berichte nennen ein `transcript.jsonl` und eine
SQLite-Datei je Gespräch. Eine Option wie `--ephemeral` bei Codex gibt es nicht. Das berührt den
Grundsatz „kein Verlauf“ aus [../../architektur.md](../../architektur.md).

### Headless-Aufruf

Aus [Headless-Doku](https://antigravity.google/docs/cli/headless/) und `agy --help` (geprüft):

| Flag | Bedeutung |
|---|---|
| `-p`, `--print`, `--prompt` | Eine Anfrage ohne Oberfläche beantworten und beenden |
| `--output-format text\|json\|stream-json` | Ausgabeform; `json` liefert einen Umschlag am Ende |
| `--input-format text\|stream-json` | `stream-json` liest Anfragen als NDJSON von der Standardeingabe (braucht `stream-json` als Ausgabe) |
| `--json-schema <Text oder Datei>` | Erzwingt strukturierte Ausgabe; Ergebnis dann in `structured_output` |
| `--model <Kennung>` | Modell; unbekannte Kennung beendet den Lauf mit Fehler, ohne Ausweichen. Liste: `agy models` (nur angemeldet) |
| `--effort low\|medium\|high\|xhigh\|max` | Denkaufwand |
| `--print-timeout <Dauer>` | Obergrenze für die Antwort. Die Hilfe von 1.4.8 nennt Vorgabe `0s` (unbegrenzt), die Doku „5m“ — **immer ausdrücklich setzen** |
| `--sandbox` | Terminal-Sandbox für Befehle |
| `--dangerously-skip-permissions` | Alle Werkzeugfreigaben automatisch erteilen — für das Add-on tabu |
| `--continue`, `--conversation <id>` | Gespräch fortsetzen — für das Add-on tabu (kein Verlauf) |

Umschlag bei `--output-format json`: `conversation_id`, `status`, `response`, `error`,
`duration_seconds`, `num_turns`, `usage` (`input_tokens`, `output_tokens`, `thinking_tokens`,
`cache_read_tokens`, `total_tokens`), bei Schema zusätzlich `structured_output` und `json_schema`;
laut Änderungsliste ab 1.1.27 auch `denied_actions` (verweigerte Werkzeugaufrufe).
`status`: `SUCCESS`, `ERROR`, `CANCELED`, `INTERRUPTED`, `INVALID`, `WAITING`, `RUNNING`.

Exitcodes (Doku und Änderungsliste): `0` Erfolg; `1` Aufruffehler, unbekanntes Modell, fehlende
Anmeldung; `2` unzulässige Eingabe bei `stream-json`; `3` Agenten- oder API-Fehler (seit 1.2.6).
Bei API-Fehlern steht eine JSON-Zeile mit `AGY_ERROR` auf der Standardfehlerausgabe, Fehler
tragen die Marke `error:`. Kontingent erschöpft: „Your AI credits balance is too low to
continue.“ (seit 1.2.15).

Berechtigungen im Headless-Betrieb ([Doku](https://antigravity.google/docs/permissions?tab=cli)):
Lesen und Schreiben **im Arbeitsbereich** ist automatisch erlaubt; Befehle sind „Ask“ und werden
ohne Freigabe **weich abgelehnt** (Lauf geht mit Exitcode 0 weiter, die Standardfehlerausgabe
nennt das Werkzeug). Freigaben stehen in `settings.json` unter `permissions.allow|ask|deny`
(Reihenfolge Deny vor Ask vor Allow), z. B. `read_url(google.com)`, `read_url(*)`,
`command(git)`, `write_file(src/)`. Dateizugriff außerhalb des Arbeitsbereichs bleibt aus
(`allowNonWorkspaceAccess` = `false`). Ein Werkzeug „Websuche“ taucht in dieser Doku **nicht**
auf (nur `read_url` und `execute_url`) — offen, siehe Spike.

Anweisungsdateien: `AGENTS.md`/`GEMINI.md` im Arbeitsverzeichnis, global `~/.gemini/GEMINI.md`
und `~/.gemini/AGENTS.md` ([Regeln](https://antigravity.google/docs/rules)). Ob der Druckmodus sie
lädt, steht nicht in der Doku. Einen Schalter für einen Systemprompt gibt es **nicht**.

Kontingent ([Pläne](https://antigravity.google/docs/plans)): AI Pro hat ein Kontingent, das sich alle
fünf Stunden erneuert, bis das Wochenlimit erreicht ist. Es bemisst sich an der Arbeit des
Agenten, nicht an der Zahl der Anfragen. Zahlen nennt Google nicht; `/usage` zeigt den Stand
(nur interaktiv). Mehrverbrauch über gekaufte KI-Guthaben ist möglich (`useG1Credits`).

## 2. Eigene Messungen am 27.10.2026

Container: `ghcr.io/home-assistant/aarch64-base:3.19` (Alpine, musl), Archiv per Manifest
geladen, Prüfsumme (SHA-512) stimmte, **ohne Anmeldung**. Getestet wurde nur arm64 — das
amd64-Archiv liegt im Manifest, wurde aber nicht ausgeführt.

| Versuch | Ergebnis |
|---|---|
| `agy --version` | `1.4.8` |
| `agy models` ohne Anmeldung | Exitcode 1, „Please sign in to view available models.“ nach 0,5 s |
| `agy -p "…" --output-format json` ohne Anmeldung, Standardeingabe `/dev/null` | Exitcode 1 nach **60 s**. Standardausgabe: `{"conversation_id":"","status":"ERROR","response":"","error":"authentication failed or timed out",…}`. Standardfehlerausgabe: Anmelde-Adresse, „Waiting for authentication (timeout 60s)“, Aufforderung, den Code einzufügen |
| Zustand danach | Verzeichnisse und Dateien wie in der Tabelle oben; im Log „Using file-based secret storage at …/plugin-secrets.json“ (kein Schlüsselbund vorhanden) |
| Suche im Binary nach `GEMINI_FORCE_FILE_STORAGE` | Zeichenkette kommt in 1.4.8 **nicht** vor (einige Berichte nennen sie als Hebel für den Dateispeicher) |
| Umgebungsvariablen im Binary | u. a. `AGY_CLI_NONINTERACTIVE_HEADLESS`, `AGY_CLI_INTERACTIVE_HEADLESS`, `AGY_CLI_DISABLE_AUTO_UPDATE`, `AGY_CLI_MODEL_API_MAX_RETRIES`, `AGY_ACCOUNT`, `AGY_ALLOWED_DOMAINS`, `AGY_ADC_AUTH`, `AGY_LLM_GATEWAY_*`, `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_DIR`, `ANTIGRAVITY_GEMINI_DIR`, `ANTIGRAVITY_APP_DATA_DIR`, `ANTIGRAVITY_CONFIG_REL_DIR`. Ob davon eine den Zustandsordner umlenkt, ist ungeprüft (Spike S9) |

**Nicht geprüft** (braucht Anmeldung): alles ab dem ersten echten Modellaufruf.

## 3. Die Anmeldung im Container — der ungelöste Kern

Bei `claude_sub` ist die Anmeldung **ein Wert** (`claude setup-token`), bei `codex_sub` **eine
Datei, die die CLI selbst erneuert** (D-013). Bei `agy` gibt es keinen Vorgang, der das
Gleiche für ein Privatkonto vorsieht:

- Die persönliche Anmeldung ist laut Doku an den **Schlüsselbund** des Betriebssystems gebunden
  (Linux: Secret Service über D-Bus). Ein Alpine-Container hat keinen.
- Für CI empfiehlt Google den **API-Schlüssel** — der nutzt das Abo nicht
  (`"modelProvider": "gemini"` und `GEMINI_API_KEY`; die Variable allein wirkt nicht).
- Die Anmeldung läuft über einen Browser: `agy` druckt eine Adresse und wartet **60 Sekunden** auf
  den eingefügten Code (gemessen; ältere Quellen nennen 30). Im Add-on sitzt niemand davor, sie
  muss also — wie bei D-013 — **außerhalb** entstehen und eingefügt werden.

Was Berichte über den Dateispeicher sagen — widersprüchlich und je Version verschieden:

| Quelle | Aussage | Version |
|---|---|---|
| [#479](https://github.com/google-antigravity/antigravity-cli/issues/479) (offen) | Im Container wählt `agy` selbst den Dateispeicher („container environment detected“) und schreibt das Token, **liest es aber in einem neuen Prozess nicht** → erneut Anmeldung, nach 30 s Abbruch. Kopieren der Dateien in einen neuen Container half nicht | 1.0.10 bis 1.0.13 |
| Drittanleitung (`invoking-antigravity`) | Mit gesetzten `SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY` nutzt `agy` den Dateispeicher; Token sichern und im frischen Container zurückschreiben funktioniere, das `refresh_token` sei langlebig | unbekannt |
| [#1336](https://github.com/google-antigravity/antigravity-cli/issues/1336) (offen) | Bestätigt: bei gesetzten `SSH_*`-Variablen liest `agy` **nur** den Dateispeicher | 1.4.7 |
| [#950](https://github.com/google-antigravity/antigravity-cli/issues/950) (offen) | `GEMINI_FORCE_FILE_STORAGE=true` ließ die Anmeldung über Prozesse hinweg halten, dann kam aber die Eignungsprüfung („account is not eligible“, SMS-Prüfung hängt) — betraf ein Student-Konto, nicht AI Pro | 1.1.27 |
| [#223](https://github.com/google-antigravity/antigravity-cli/issues/223) (erledigt) | Headless-Anmeldung per Dienstkonto/ADC (1.1.10 bis 1.1.12) und `GEMINI_API_KEY` ohne Anmeldung (1.1.13) ergänzt — beides ist **nicht** das Privatabo | 1.1.x |

Es gibt damit drei denkbare Wege, die Anmeldung zu halten. Der Spike
([spike-abo-anmeldung.md](spike-abo-anmeldung.md)) muss klären, welcher mit 1.4.8 trägt:

| Weg | Idee | Einschätzung |
|---|---|---|
| **W1 — Datei + `SSH_*`** | Token einmal im Wegwerf-Container erzeugen, Datei einfügen, im Provider `SSH_CONNECTION`/`SSH_CLIENT`/`SSH_TTY` für `agy` setzen | Einfachster Weg, passt zum Muster von D-013. Hängt an einem Verhalten, das nicht dokumentiert ist und sich mit jeder Version ändern kann |
| **W2 — D-Bus + gnome-keyring im Container** | Pakete `dbus`, `gnome-keyring`, `libsecret` ins Bild, Daemon vor jedem Lauf starten und entsperren | Hält sich an Googles dokumentierten Weg, braucht aber Prozessverwaltung im Container (das Bild startet bewusst nur einen Befehl, D-009) und Entsperren ohne Benutzer. Aufwendig und fragil |
| **W3 — API-Schlüssel / ADC** | `modelProvider: gemini` | Funktioniert dokumentiert, ist aber **nicht das Abo** → siehe [api-weg.md](api-weg.md) |

Sicher ist nur: Ohne zuverlässiges W1 oder W2 gibt es keinen Abo-Provider.

## 4. Risiken

| Nr. | Risiko | Schwere | Gegenmaßnahme / Hinweis |
|---|---|---|---|
| R1 | **Verstoß gegen Googles Bedingungen, Kontosperre** (Wrapping unter Verbraucherplan) | hoch | Schranke G1. Sperrung betrifft laut Bedingungen „Antigravity und/oder Gemini CLI“-Konten; Reichweite auf andere Google-Dienste ungeklärt |
| R2 | Anmeldung hält nicht (Schlüsselbund fehlt, Dateispeicher wird nicht gelesen) | hoch | Schranke G2 |
| R3 | **Datenschutz:** Bei persönlichen Konten werden laut den Zusatzbedingungen „Interactions“ erfasst und genutzt (Löschung nur auf Antrag). Die FAQ verweist für das Abschalten auf die Einstellungen; Beiträge im Google-AI-Entwicklerforum nennen nur „Enable Telemetry“ und bezweifeln, dass das ein Training ausschließt — von Google **nicht bestätigt**. Smart-Home-Daten würden an Google gehen | hoch | Im Gegensatz dazu: Gemini API mit Abrechnung, im EWR ohnehin „Paid“-Regeln ([api-weg.md](api-weg.md#datenschutz)) |
| R4 | Gespräche und Protokolle bleiben unter `/data` liegen | mittel | Nach jedem Lauf löschen (Abschnitt 5.9), in [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md) aufnehmen |
| R5 | Der Agent hat im Arbeitsbereich Schreib- und Lesezugriff ohne Rückfrage; `/data` enthält alle Zugänge | hoch | Eigenes leeres Arbeitsverzeichnis (5.5), Deny-Regeln, Spike S6 |
| R6 | Kontingent: Automationen leeren das 5-Stunden-Fenster, die interaktive Nutzung des Abos (IDE, App) ist dann blockiert; Verbrauch je Anfrage unbekannt (Agent denkt, plant, ruft Werkzeuge) | mittel | Anfragen zählen und drosseln; Spike S7 misst den Verbrauch |
| R7 | Kein stabiler Vertrag: Die Headless-Doku ist dünn, Exitcodes, Stdin-Verhalten und Fehlerausgabe haben sich zwischen 1.1.x und 1.4.x mehrfach geändert | mittel | Version und Prüfsumme festnageln, Handprüfung nach jedem Anheben (wie D-013) |
| R8 | Last: ein Sprachserver je Aufruf, Raspberry-Pi-Klassen belastet | mittel | Parallelität begrenzen, Spike S8 misst Zeit und Speicher auf arm64 |
| R9 | Eignung: nur private Konten ab 18, nur freigegebene Länder; Berichte über hängende SMS-Prüfung | mittel | Vor dem Spike prüfen, ob das Konto sich anmelden lässt |
| R10 | Bild wächst um rund 200 MB, Bauzeit steigt; kein Dependabot-Signal für neue Versionen | niedrig | In [../../bekannte-luecken.md](../../bekannte-luecken.md) aufnehmen (wie bei den anderen CLIs) |

## 5. Entwurf des Providers `gemini_sub`

Nur gültig, wenn G1 bis G3 offen sind. Der Entwurf folgt `codex_sub_provider.py` und D-013;
Abweichungen sind benannt.

### 5.1 Name, Datei, Abgrenzung

- Neuer Provider `gemini_sub`, Anzeigename „Google Gemini (Abo)“, Datei
  `providers/gemini_sub_provider.py`, Klasse `GeminiSubProvider(BaseProvider)`.
- Der bestehende Provider `gemini` (API-Schlüssel) **bleibt** unverändert nebenher — er ist der
  unterstützte Weg und der Rückfall. Zwei Namen, weil Zugang, Abrechnung und Bedingungen verschieden
  sind (wie `claude_sub` gegenüber einem API-Weg).

### 5.2 Aufruf

```text
agy --output-format json --print-timeout <Sekunden>s [--model <Kennung>] -p "<Rolle + Prompt + JSON-Anweisung>"

Arbeitsverzeichnis : /data/omniai-gemini-workspace   (leer, Rechte 0700 — NICHT /data)
Standardeingabe    : DEVNULL
Umgebung           : HOME=/data, AGY_CLI_DISABLE_AUTO_UPDATE=true,
                     SSH_CONNECTION/SSH_CLIENT/SSH_TTY (nur wenn der Spike W1 wählt),
                     GEMINI_API_KEY und GOOGLE_API_KEY entfernt (kein ungewollter Wechsel auf Abrechnung)
Prozess            : eigene Sitzung (start_new_session), bei Zeitüberschreitung die ganze Gruppe beenden
```

- Der Prompt geht als Argument des `-p`-Flags mit, wie bei `claude_sub`. Die Alternative ist
  `--input-format stream-json` mit dem Prompt über die Standardeingabe und Auswertung des
  `result`-Ereignisses; sie hält den Prompt aus der Prozessliste, macht aber den Aufruf
  komplexer. Spike S3 entscheidet.
- Die Rolle „JSON-Endpunkt“ wird dem Prompt vorangestellt, auf Englisch wie bei Codex
  (`SYSTEM_PROMPT` dort). Ein Schalter für einen Systemprompt fehlt.
- Zeitlimit: `--print-timeout` knapp unter dem Limit des Prozesses, damit `agy` sich selbst
  beendet, bevor der Provider es abschießt.

### 5.3 Zugang (analog D-013)

- Neue Option `gemini_auth_json` (Passwortfeld, Umgebungsvariable `GEMINI_AUTH_JSON`): Inhalt der
  Datei `antigravity-oauth-token`.
- Der Provider legt den Wert unter `~/.gemini/antigravity-cli/antigravity-oauth-token` ab
  (Verzeichnis 0700, Datei 0600) — **nur bei geändertem Fingerabdruck** gegenüber der Marke
  `.seed`, aus demselben Grund wie bei Codex: `agy` erneuert das Zugriffstoken und schreibt die
  Datei zurück; ein blindes Überschreiben bei jedem Start ersetzte frische Tokens durch alte.
- Prüfung vor dem Ablegen: gültiges JSON mit `token.refresh_token`. Der Wert erscheint nie im Log.
- **Vorab-Prüfung vor jedem Lauf**: fehlt die Datei, sofort Fehler. Sonst wartet `agy` 60
  Sekunden auf einen Code, den niemand eingibt (gemessen).
- Wie der Wert entsteht: einmalig auf einem Rechner mit Browser, am sichersten in einem
  Wegwerf-Container derselben Bauart (Anleitung im Spike). Auf macOS liegt die Anmeldung im
  Schlüsselbund, nicht in einer Datei — der Weg über den eigenen Mac hat deshalb keine Datei zum
  Kopieren.
- **Kein** Rückfall auf einen API-Schlüssel innerhalb dieses Providers: der steht in `gemini`.
  Fehlt der Zugang, verweist die Meldung darauf.

### 5.4 Werkzeugstufen (`tool_access`)

Bildet der Provider auf `permissions` in `settings.json` ab, die er vor dem Lauf schreibt
(nur bei Änderung):

| Stufe | Regeln | Anmerkung |
|---|---|---|
| `off` | `deny`: `read_url(*)`, `execute_url(*)`, `command(*)`, `write_file(*)`, `mcp(*)` | Antwort aus dem Trainingswissen |
| `web` | `allow`: `read_url(*)`; `deny`: `execute_url(*)`, `command(*)`, `write_file(*)`, `mcp(*)` | Ob damit auch **Suchen** möglich ist (nicht nur Abruf bekannter Adressen), zeigt Spike S5 |
| `full` | wie `web` | Befehle im Container nie freigeben; `--dangerously-skip-permissions` wird **nicht** verwendet. In der Oberfläche als „entspricht web“ ausweisen |

Immer zusätzlich als Verteidigung in der Tiefe: `deny` für `read_file(/data)` und
`write_file(/data)`.

### 5.5 Arbeitsbereich

`agy` darf im Arbeitsbereich ohne Rückfrage lesen und schreiben, und es fragt beim ersten Start
nach Vertrauen für das Verzeichnis (`trustedWorkspaces`, Spike S6). Wäre `cwd="/data"` wie bei
den anderen Providern, läge `options.json` (alle Zugänge), `.claude` und `.codex` im Arbeitsbereich.
Deshalb ein eigenes leeres Verzeichnis, vorab als vertraut eingetragen.

### 5.6 Auswertung und Fehler

- `status == "SUCCESS"` → `response` an `BaseProvider.parse_json`. Ausgabe ohne gültiges JSON →
  `NotJson` wie überall. Prüfen, ob `--json-schema '{"type":"object"}'` die Auswertung robuster
  macht (`structured_output`) — Spike S4.
- Jede Ausgabe der CLI geht ins Log, nie an den Aufrufer (Regel 12). Meldungen wählt der
  Provider nach Merkmalen, wie `_cli_fehler` bei Codex:

| Merkmal | Meldung (Entwurf, Regel 12 beachten) |
|---|---|
| Datei fehlt | „Für Google Gemini (Abo) ist kein Zugang hinterlegt. …“ mit Hinweis auf Einstellungen |
| `authentication`, `not logged in`, `sign in`, Exitcode 1 bei Lauf mit Datei | „Die Anmeldung bei Google gilt nicht mehr. Bitte den Zugang erneut einfügen.“ |
| `credits balance is too low`, `quota`, `rate limit`, `exhausted` | „Das Kontingent des Google-AI-Pro-Abos ist aufgebraucht. Es erneuert sich in einigen Stunden.“ |
| Konto nicht berechtigt, Standort | „Dieses Google-Konto darf die Antigravity-Dienste nicht nutzen.“ |
| `status` `CANCELED`/`INTERRUPTED` oder Zeitlimit des Prozesses | `ProviderTimeout` mit Satz „Google Gemini hat zu lange gebraucht …“ |
| unbekanntes Modell | `UnknownModel` mit den gültigen Werten |
| sonst | „Google Gemini (Abo) hat die Anfrage nicht beantwortet. …“ |

### 5.7 Aufräumen

Nach jedem Lauf alles löschen, was ein Gespräch ausmacht: `conversations/<conversation_id>`,
zugehörige Einträge in `brain/` und `implicit/`, Zeilen in `conversation_summaries.db`; außerdem
`log/` begrenzen. Welche Pfade zu einem Lauf gehören, klärt Spike S9. Ersatz, falls sich einzelne
Spuren nicht zuordnen lassen: ein Zustandsordner **je Lauf** (`ANTIGRAVITY_GEMINI_DIR` o. Ä. oder
ein temporäres `HOME`), in den nur die Token-Datei kopiert wird. Das ist robust, kostet aber
Zeit je Lauf (Sprachserver legt Datenbanken neu an).

### 5.8 Parallelität

Höchstens ein bis zwei gleichzeitige `agy`-Prozesse (Semaphore im Provider). Ein Prozess je
Anfrage, jeweils mit eigener Sitzungsgruppe, damit Kindprozesse (Sprachserver) beim Abbruch nicht
zurückbleiben.

### 5.9 Bild

Entwurf für das Dockerfile; Version und Prüfsummen vom 27.10.2026 (Manifest), bei Baubeginn
neu vom Manifest holen. Der Bau schlägt fehl, wenn die Prüfsumme nicht stimmt.

```dockerfile
# Antigravity CLI: statisches Binary, Version und Prüfsumme festgenagelt.
# Die CLI aktualisiert sich sonst selbst (AGY_CLI_DISABLE_AUTO_UPDATE).
ENV AGY_CLI_DISABLE_AUTO_UPDATE=true
RUN set -eu; \
    base="https://storage.googleapis.com/antigravity-public/antigravity-cli/1.4.8-5447777392656384"; \
    case "$(uname -m)" in \
      x86_64) \
        url="$base/linux-x64-musl/cli_linux_x64_musl.tar.gz"; \
        sha="8a3696428a888cb44126979a9e1178c07470133351f87a4d5a7c103bab2d499462b36f1dc041681c09ed23b775ad3ac6120d13ce81d4d52902246d17cc19063e" ;; \
      aarch64) \
        url="$base/linux-arm-musl/cli_linux_arm64_musl.tar.gz"; \
        sha="dcf9e593e3947c8546f0b3f7a5ce11f83556c0e23de810f039b20ee6d50cb56dec60d43efec7409291bde25a580ad8863f8b37f215a1770cbf9ec1b75486b2d2" ;; \
      *) echo "Architektur nicht unterstützt" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/agy.tar.gz "$url"; \
    echo "$sha  /tmp/agy.tar.gz" | sha512sum -c -; \
    tar -xzf /tmp/agy.tar.gz -C /tmp antigravity; \
    install -m 0755 /tmp/antigravity /usr/local/bin/agy; \
    rm -f /tmp/agy.tar.gz /tmp/antigravity
```

Die Prüfsumme für arm64 wurde am 27.10.2026 gegen das heruntergeladene Archiv bestätigt; die für
amd64 stammt nur aus dem Manifest. Die Ordnernamen in den Adressen stammen aus den Manifesten —
der Ordner der arm64-Datei heißt dort tatsächlich `linux-arm-musl`, nicht `linux-arm64-musl`.

### 5.10 Was sonst zu ändern wäre

Alle Berührungspunkte im Code, in der Konfiguration und in den Tests stehen in
[umsetzungsplan.md](umsetzungsplan.md#spur-2--abo-weg-nur-nach-freigabe).

## 6. Wiederaufnahmebedingungen

Der Weg wird neu bewertet, wenn eines davon eintritt:

- Google nimmt den Satz „not supported under consumer plans“ aus der FAQ oder erlaubt das
  Einpacken ausdrücklich (auch gegen Zahlung, etwa als eigener Plan).
- Google bietet eine **dokumentierte** Anmeldung für Server und Container mit dem Privatabo (ein
  Token wie `claude setup-token`) oder eine Schnittstelle, die das Abo-Kontingent über einen
  Schlüssel anspricht.
- Der User entscheidet in Kenntnis des Risikos ausdrücklich dafür (G1) und der Spike ist
  bestanden (G2).
