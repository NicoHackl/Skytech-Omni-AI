# Abo-Weg über die Antigravity CLI (Entwurf `gemini_sub`)

> **Status: umgesetzt als Anbieter `gemini_sub`** (D-022, [ADR](../../adr/D-022-gemini-abo-antigravity.md)).
> Diese Datei hält die **Befunde zur CLI** fest, auf denen die Umsetzung beruht — den Steckbrief, die
> Messungen vom 27.10.2026 und die Risiken. Wie das Add-on die CLI benutzt, steht in
> [../../architektur.md](../../architektur.md); der Entwurf, der hier früher stand, ist durch den
> Code überholt und wurde entfernt. Die Handprüfung mit echtem Konto steht im ADR.

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
geladen, Prüfsumme (SHA-512) stimmte, **ohne Anmeldung**. Von Hand getestet wurde nur arm64; das
amd64-Binary hat die CI gebaut und mit `agy --version` gestartet.

| Versuch | Ergebnis |
|---|---|
| `agy --version` | `1.4.8` |
| `agy models` ohne Anmeldung | Exitcode 1, „Please sign in to view available models.“ nach 0,5 s |
| `agy -p "…" --output-format json` ohne Anmeldung, Standardeingabe `/dev/null` | Exitcode 1 nach **60 s**. Standardausgabe: `{"conversation_id":"","status":"ERROR","response":"","error":"authentication failed or timed out",…}`. Standardfehlerausgabe: Anmelde-Adresse, „Waiting for authentication (timeout 60s)“, Aufforderung, den Code einzufügen |
| Zustand danach | Verzeichnisse und Dateien wie in der Tabelle oben; im Log „Using file-based secret storage at …/plugin-secrets.json“ (kein Schlüsselbund vorhanden) |
| Suche im Binary nach `GEMINI_FORCE_FILE_STORAGE` | Zeichenkette kommt in 1.4.8 **nicht** vor (einige Berichte nennen sie als Hebel für den Dateispeicher) |
| Umgebungsvariablen im Binary | u. a. `AGY_CLI_NONINTERACTIVE_HEADLESS`, `AGY_CLI_INTERACTIVE_HEADLESS`, `AGY_CLI_DISABLE_AUTO_UPDATE`, `AGY_CLI_MODEL_API_MAX_RETRIES`, `AGY_ACCOUNT`, `AGY_ALLOWED_DOMAINS`, `AGY_ADC_AUTH`, `AGY_LLM_GATEWAY_*`, `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_DIR`, `ANTIGRAVITY_GEMINI_DIR`, `ANTIGRAVITY_APP_DATA_DIR`, `ANTIGRAVITY_CONFIG_REL_DIR`. Ob davon eine den Zustandsordner umlenkt, ist ungeprüft (Spike S9) |

Weitere Messungen am 27.10.2026 (gleicher Container, weiterhin ohne Konto), Grundlage von D-022:

| Versuch | Ergebnis |
|---|---|
| `agy --help`, `agy auth/login/logout --help` | Es gibt keine Unterbefehle zur Anmeldung (nur `agent`, `changelog`, `install`, `mcp`, `mic-serve`, `models`, `plugin`, `remote-control`, `update`); die Hilfe zeigt für jeden unbekannten Namen die Hauptseite |
| Auftrag ohne Anmeldung mit Eingabe `/dev/null`, mit und ohne `SSH_*` | Adresse auf der Fehlerausgabe, „Waiting for authentication (timeout 60s)“, „Or, paste the authorization code here and press Enter:“, nach 60 s Exitcode 1 |
| Dasselbe mit Pipe als Eingabe | Sofort „authentication required. Run ‘agy’ to log in, then retry.“, Exitcode 1 |
| Dasselbe mit **Pty** als Eingabe, Code `4/0FAKE…` eingespeist | Nach 0,7 s „authentication failed: token exchange failed: oauth2: ‘invalid_grant’ ‘Bad Request’“, JSON-Umschlag `status: ERROR`, Exitcode 1 |
| Anmeldeadresse | `accounts.google.com/o/oauth2/auth` mit PKCE (`S256`), `redirect_uri=https://antigravity.google/oauth-callback`, Bereiche `cloud-platform`, `userinfo.email`, `userinfo.profile`, `cclog`, `experimentsandconfigs`, `aicode`, `openid` |
| Zielseite `antigravity.google/oauth-callback` | Zeigt „Paste this code into your application to complete authentication:“ mit Schaltfläche zum Kopieren; ohne Code „No authorization code found“ |
| `strace -f` auf `agy models` | Öffnet `~/.gemini/antigravity-cli/antigravity-oauth-token` und `~/.config/antigravity/credential-user-scope`, prüft `/.dockerenv`; mit `SSH_*` Logzeile „Using file-based token storage because SSH session detected“ |
| Selbst gebaute Token-Datei (geratenes Format: `auth_method`, `token{access_token,refresh_token,expiry}`) am bestätigten Pfad | Wird nicht als Anmeldung erkannt („Auth mode is unspecified“, „You are not logged into Antigravity“) — Format nur der CLI bekannt |
| Zeichenketten im Binary | Gründe für den Dateispeicher: „SSH session“, „container environment“, „keyring timeout“; Meldungen „Failed to load stored token from keyring, falling back to file“; keine Umgebungsvariable für ein Token |
| amd64-Archiv | SHA-512 stimmt mit dem Manifest, ELF-Kopf x86-64. Die CI baut das amd64-Image und startet `agy --version` im Smoke-Test (28.10.2026, grün) |
| Bau des Bildes mit dem Block aus dem `Dockerfile` (arm64) | Gelingt; `agy --version` = 1.4.8 |

**Nicht geprüft** (braucht Anmeldung): alles ab dem ersten echten Modellaufruf.

## 3. Die Anmeldung im Container

Bei `claude_sub` ist die Anmeldung **ein Wert** (`claude setup-token`), bei `codex_sub` **eine
Datei, die die CLI selbst erneuert** (D-013). Bei `agy` gibt es keinen Vorgang, der das Gleiche für
ein Privatkonto vorsieht: keinen Anmeldebefehl, kein Server-Token. Die persönliche Anmeldung ist laut
Doku an den Schlüsselbund des Betriebssystems gebunden, den ein Alpine-Container nicht hat; für CI
empfiehlt Google den API-Schlüssel — der nutzt das Abo nicht.

Was Berichte über den Dateispeicher sagen, ist widersprüchlich und je Version verschieden:

| Quelle | Aussage | Version |
|---|---|---|
| [#479](https://github.com/google-antigravity/antigravity-cli/issues/479) (offen) | Im Container wählt `agy` selbst den Dateispeicher und schreibt das Token, **liest es aber in einem neuen Prozess nicht** → erneut Anmeldung. Kopieren der Dateien in einen neuen Container half nicht | 1.0.10 bis 1.0.13 |
| Drittanleitung (`invoking-antigravity`) | Mit gesetzten `SSH_CONNECTION`, `SSH_CLIENT`, `SSH_TTY` nutzt `agy` den Dateispeicher; Token sichern und im frischen Container zurückschreiben funktioniere | unbekannt |
| [#1336](https://github.com/google-antigravity/antigravity-cli/issues/1336) (offen) | Bestätigt: bei gesetzten `SSH_*`-Variablen liest `agy` **nur** den Dateispeicher | 1.4.7 |
| [#950](https://github.com/google-antigravity/antigravity-cli/issues/950) (offen) | `GEMINI_FORCE_FILE_STORAGE=true` hielt die Anmeldung, dann kam die Eignungsprüfung („account is not eligible“) — Student-Konto, nicht AI Pro | 1.1.27 |
| [#223](https://github.com/google-antigravity/antigravity-cli/issues/223) (erledigt) | Headless-Anmeldung per Dienstkonto/ADC und `GEMINI_API_KEY` ergänzt — beides ist **nicht** das Privatabo | 1.1.x |

### Wie das Add-on damit umgeht (D-022)

| Befund | Antwort |
|---|---|
| Eine in einem anderen Container erzeugte Anmeldung wird nicht angenommen; das Dateiformat ist undokumentiert (eigener Versuch mit geratenem Format: nicht erkannt) | Die Anmeldung **entsteht im Add-on**, dort, wo sie gebraucht wird |
| Ohne Anmeldung druckt die CLI eine Adresse und wartet 60 s; die Eingabe entscheidet: `/dev/null` → wartet ohne zu lesen, Pipe → sofortiger Abbruch, **Pty → liest den Code** | Anmeldung über eine Pty, Code aus der Oberfläche |
| Schreiben und Lesen der Anmeldung können verschiedene Orte treffen | `SSH_*` bei **jedem** Aufruf: Dateispeicher, gleicher Weg |
| Die Anmeldung könnte beim Abbruch eines Laufs halb geschrieben sein | Sicherung nach jedem Lauf, Wiederherstellung |
| Nach der Anmeldung ist unklar, ob sie einen neuen Prozess überlebt (Fall von #479) | Prüfung in einem frischen Prozess (`agy models`), erst dann „angemeldet“ |

Offen bis zur Handprüfung: ob eine **echte** Anmeldung diese Prüfung besteht, Neustarts, die
Erneuerung des Zugriffstokens (etwa stündlich) und Updates übersteht.

## 4. Risiken

| Nr. | Risiko | Schwere | Gegenmaßnahme / Hinweis |
|---|---|---|---|
| R1 | **Verstoß gegen Googles Bedingungen, Kontosperre** (Wrapping unter Verbraucherplan) | hoch | Vom User angenommen (D-022); der Hinweis steht an der Anmeldung. Sperrung betrifft laut Bedingungen „Antigravity und/oder Gemini CLI“-Konten; Reichweite auf andere Google-Dienste ungeklärt |
| R2 | Anmeldung hält nicht (Schlüsselbund fehlt, Dateispeicher wird nicht gelesen) | hoch | Anmeldung im Add-on, Prüfung im frischen Prozess; Handprüfung H2, H3, H9 |
| R3 | **Datenschutz:** Bei persönlichen Konten werden laut den Zusatzbedingungen „Interactions“ erfasst und genutzt (Löschung nur auf Antrag). Die FAQ verweist für das Abschalten auf die Einstellungen; Beiträge im Google-AI-Entwicklerforum nennen nur „Enable Telemetry“ und bezweifeln, dass das ein Training ausschließt — von Google **nicht bestätigt**. Smart-Home-Daten würden an Google gehen | hoch | Im Gegensatz dazu: Gemini API mit Abrechnung, im EWR ohnehin „Paid“-Regeln ([api-weg.md](api-weg.md#datenschutz)) |
| R4 | Gespräche und Protokolle bleiben unter `/data` liegen | mittel | Nach jedem Lauf löschen (umgesetzt), in [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md) aufnehmen |
| R5 | Der Agent hat im Arbeitsbereich Schreib- und Lesezugriff ohne Rückfrage; `/data` enthält alle Zugänge | hoch | Eigenes leeres Arbeitsverzeichnis, Regeln in der `settings.json` (Befehle nie freigegeben), schmale Umgebung; Handprüfung H5 |
| R6 | Kontingent: Automationen leeren das 5-Stunden-Fenster, die interaktive Nutzung des Abos (IDE, App) ist dann blockiert; Verbrauch je Anfrage unbekannt (Agent denkt, plant, ruft Werkzeuge) | mittel | Anfragen laufen nacheinander; Handprüfung H7 misst den Verbrauch, eine Drosselung steht aus |
| R7 | Kein stabiler Vertrag: Die Headless-Doku ist dünn, Exitcodes, Stdin-Verhalten und Fehlerausgabe haben sich zwischen 1.1.x und 1.4.x mehrfach geändert | mittel | Version und Prüfsumme festnageln, Handprüfung nach jedem Anheben (wie D-013) |
| R8 | Last: ein Sprachserver je Aufruf, Raspberry-Pi-Klassen belastet | mittel | Ein Lauf zur Zeit (umgesetzt); Zeit und Speicher auf arm64 sind nicht gemessen |
| R9 | Eignung: nur private Konten ab 18, nur freigegebene Länder; Berichte über hängende SMS-Prüfung | mittel | Schlägt die Anmeldung mit „nicht berechtigt“ fehl, nennt das Add-on es in der Karte (Handprüfung H1) |
| R10 | Bild wächst um rund 200 MB, Bauzeit steigt; kein Dependabot-Signal für neue Versionen | niedrig | In [../../bekannte-luecken.md](../../bekannte-luecken.md) geführt (wie bei den anderen CLIs) |

## 5. Umsetzung

Der frühere Entwurf (Aufruf, Zugang, Werkzeugstufen, Arbeitsbereich, Fehlertabelle, Aufräumen,
Parallelität, Bild) ist im Code angekommen:

| Thema | Wo |
|---|---|
| Aufruf, Umgebung, Werkzeugregeln, Fehlerzuordnung, Aufräumen, Sicherung | `skytech_omniai/providers/gemini_sub_provider.py` |
| Anmeldung (Pty, Adresse, Code, Prüfung) | `skytech_omniai/providers/gemini_sub_login.py` |
| Endpunkte `/auth/gemini…` | `skytech_omniai/app.py`, beschrieben in [../../api-referenz.md](../../api-referenz.md) |
| Oberfläche | `skytech_omniai/web/src/components/GoogleLogin.tsx` |
| Bild (Version 1.4.8, SHA-512 je Architektur) | `skytech_omniai/Dockerfile` |
| Architektur und Sicherheit | [../../architektur.md](../../architektur.md), [../../sicherheit-datenschutz.md](../../sicherheit-datenschutz.md) |

Abweichungen vom früheren Entwurf: keine Option `gemini_auth_json` (die Anmeldung kommt nicht aus
einem eingefügten Wert), keine feste Modellliste, Befehle bei `full` nie freigegeben, nur ein Lauf
zur Zeit.

## 6. Wiederaufnahme- und Rücknahmebedingungen

Siehe „Rücknahmebedingung“ im [ADR](../../adr/D-022-gemini-abo-antigravity.md).
