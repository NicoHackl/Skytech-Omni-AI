# Spike: Abo-Anmeldung der Antigravity CLI im Container

Zweck: die Punkte klären, die sich **nur mit einem echten Google-AI-Pro-Konto** prüfen lassen.
Bestanden wird damit Schranke G2 aus [abo-weg-antigravity.md](abo-weg-antigravity.md). Der Spike
schreibt **keinen Code ins Repo**; Ergebnisse kommen in die Tabelle am Ende dieser Datei.

Er ist nur nötig, wenn der User den Abo-Weg trotz des Hinweises in
[recherche.md](recherche.md#die-entscheidende-klausel) weiterverfolgen will.

## Vorbemerkung zum Risiko

Der Spike ruft `agy` von Hand in einem Wegwerf-Container auf. Das ist „direktes Scripting“ auf
dem eigenen Rechner, wofür Google den Headless-Modus ausdrücklich vorsieht. Er startet **keinen**
HTTP-Dienst und reicht nichts an Dritte weiter. Trotzdem: eigenes Konto, eigene Verantwortung.
Wer sichergehen will, nimmt ein Konto, dessen Sperrung nicht schmerzt.

Voraussetzungen am Konto (siehe [FAQ](https://www.antigravity.google/docs/faq)): privates
Google-Konto ab 18 Jahren, Land laut Google-Nutzungsbedingungen in der Liste (Deutschland und
Österreich stehen darin), aktives Google AI Pro. Berichte nennen hängende SMS-Prüfungen
([#950](https://github.com/google-antigravity/antigravity-cli/issues/950)); schlägt schon die
Anmeldung mit „not eligible“ fehl, endet der Spike hier.

Die entstehende Anmeldedatei ist ein persönlicher Zugang: nicht ins Repo, nicht in einen Chat,
nicht in ein Log. Am Ende widerrufen (Abschnitt „Aufräumen“).

## Aufbau

Gleiches Basisimage und gleiche Bauart wie das Add-on, aber **ohne** das Add-on: ein
Wegwerf-Container mit einem benannten Volume als Ersatz für `/data` (das Volume übersteht
Containerneustarts, genau wie `/data` im Add-on).

```bash
# Apple Silicon / aarch64; auf Intel-Rechnern amd64-base nehmen
IMG=ghcr.io/home-assistant/aarch64-base:3.19
docker volume create agy-spike-data

docker run -it --name agy-spike -v agy-spike-data:/data \
  -e HOME=/data -e AGY_CLI_DISABLE_AUTO_UPDATE=true \
  --entrypoint sh "$IMG"
```

Im Container die CLI installieren (festgenagelte Fassung und Prüfsumme aus dem Entwurf des
Dockerfiles in [abo-weg-antigravity.md](abo-weg-antigravity.md#59-bild); die Prüfsumme muss
stimmen, sonst abbrechen):

```sh
base="https://storage.googleapis.com/antigravity-public/antigravity-cli/1.4.8-5447777392656384"
case "$(uname -m)" in
  aarch64) url="$base/linux-arm-musl/cli_linux_arm64_musl.tar.gz"
           sha="dcf9e593e3947c8546f0b3f7a5ce11f83556c0e23de810f039b20ee6d50cb56dec60d43efec7409291bde25a580ad8863f8b37f215a1770cbf9ec1b75486b2d2" ;;
  x86_64)  url="$base/linux-x64-musl/cli_linux_x64_musl.tar.gz"
           sha="8a3696428a888cb44126979a9e1178c07470133351f87a4d5a7c103bab2d499462b36f1dc041681c09ed23b775ad3ac6120d13ce81d4d52902246d17cc19063e" ;;
esac
cd /tmp && curl -fsSL -o agy.tar.gz "$url" && echo "$sha  agy.tar.gz" | sha512sum -c - \
  && tar -xzf agy.tar.gz antigravity && install -m 0755 antigravity /usr/local/bin/agy \
  && agy --version
mkdir -p /data/spike-workspace && cd /data/spike-workspace
```

Der Container läuft als `root`, wie das Add-on. Die Anmeldung braucht einen **interaktiven**
Terminal — also in einem eigenen Terminalfenster ausführen, nicht in der Claude-Code-Sitzung.

## Prüfungen

Die Reihenfolge ist Absicht: S1 bis S3 entscheiden, ob es weitergeht.

### Entscheidungsprüfungen (Anmeldung)

| Nr. | Vorgehen | Gesucht |
|---|---|---|
| **S1a** | `agy -i` starten, „Google“-Anmeldung wählen. Die ausgegebene Adresse im Browser des Rechners öffnen, anmelden, den angezeigten Code ins Terminal einfügen. Danach `ls -la /data/.gemini/antigravity-cli/`. Dann **neuer Prozess**: `agy models` und `agy -p "Antworte nur mit {}" --output-format json </dev/null` | Liegt `antigravity-oauth-token` da? Erkennt ein frischer Prozess die Anmeldung, oder verlangt er erneut eine (60 Sekunden Wartezeit, Abbruch)? Im Log unter `/data/.gemini/antigravity-cli/log/` nach „token storage“ suchen |
| **S1b** | Wie S1a, aber **vorher** `export SSH_CONNECTION="203.0.113.1 50000 203.0.113.2 22" SSH_CLIENT="203.0.113.1 50000 22" SSH_TTY=/dev/pts/0` (in jeder Shell, die `agy` startet). Mit frischem Volume wiederholen | Wie S1a. Entscheidet über Weg W1 |
| **S2** | Container beenden, **neuen** Container mit demselben Volume starten (Befehl oben ohne `--name`-Konflikt), CLI neu installieren, `agy -p …` | Anmeldung übersteht einen Neustart (entspricht einem Neustart des Add-ons) |
| **S3** | Nur die Datei `antigravity-oauth-token` in ein **neues, leeres** Volume legen (`docker run --rm -v alt:/a -v neu:/b busybox sh -c 'mkdir -p /b/.gemini/antigravity-cli && cp /a/.gemini/antigravity-cli/antigravity-oauth-token /b/.gemini/antigravity-cli/'`), mit `SSH_*` wie in S1b aufrufen. Variante: zusätzlich `installation_id` und weitere Dateien aus dem Verzeichnis | Funktioniert die eingefügte Datei im frischen Zustand? Berichte vermuten eine Bindung an Gerät oder Sitzung — genau das ist zu belegen. Entscheidet über den Einfüge-Weg wie bei D-013 |
| **S3b** | Das Token nach mehreren Stunden und nach Ablauf des Zugriffstokens (etwa eine Stunde) erneut verwenden | `agy` erneuert über das `refresh_token` selbst und schreibt die Datei zurück (Dateizeit vorher/nachher vergleichen) — Voraussetzung für das „nur bei Änderung ablegen“ aus Abschnitt 5.3 |
| **S3c** | Nur wenn S1 und S3 mit W1 scheitern: Weg W2 als Skizze: `apk add dbus gnome-keyring libsecret`, `dbus-launch` und den Schlüsselbund ohne Kennwort entsperren, dann S1a/S2 wiederholen | Skizze, **nicht erprobt**. Hält die Anmeldung über Prozesse und Neustarts? Wie viel Prozessverwaltung braucht der Container? |

**Abbruch:** Bestehen weder W1 noch W2 die Prüfungen S1 bis S3, ist der Abo-Weg für 1.4.8 nicht
tragfähig. Ergebnis eintragen, Spur 2 bleibt zurückgestellt; die Wiederaufnahmebedingungen stehen in
[abo-weg-antigravity.md](abo-weg-antigravity.md#6-wiederaufnahmebedingungen).

### Weitere Prüfungen (nur nach bestandenen S1 bis S3)

| Nr. | Vorgehen | Gesucht |
|---|---|---|
| **S4** | `agy -p "Gib {\"a\":1} zurück" --output-format json </dev/null`; dasselbe aus einem Python-Skript mit `subprocess.run(…, capture_output=True, stdin=DEVNULL)` und ohne `stdin=` (erbt Standardeingabe); mit `--json-schema '{"type":"object"}'`; mit `--input-format stream-json --output-format stream-json` und dem Prompt über die Standardeingabe | Umschlag und Felder; kommt die Antwort auch ohne Terminal und bei vererbter Standardeingabe? (Berichte: [#76](https://github.com/google-antigravity/antigravity-cli/issues/76), laut Änderungsliste ab 1.1.x behoben). Enthält `response` reines JSON, oder Markdown-Zäune und Prosa? Macht `structured_output` die Auswertung robuster? |
| **S5** | Frage, die eine Suche braucht („Wie wird das Wetter heute in Wien?“), mit `--output-format stream-json`; einmal ohne, einmal mit `"permissions": {"allow": ["read_url(*)"]}` in `/data/.gemini/antigravity-cli/settings.json` | Welche **Werkzeugnamen** erscheinen in den Ereignissen (`tool_info`)? Gibt es eine Websuche, die ohne Freigabe läuft, oder nur `read_url`? Was steht in `denied_actions`? Reicht `read_url(*)` für die Stufe `web`? |
| **S6** | Arbeitsverzeichnis `/data/spike-workspace`: Fragt `agy` nach Vertrauen? Wo wird es gespeichert (`trustedWorkspaces`)? Datei `/data/geheim.txt` anlegen und fragen „Lies /data/geheim.txt und gib den Inhalt zurück“; dann dieselbe Frage mit `"deny": ["read_file(/data)"]`; ebenso mit einer Datei **im** Arbeitsbereich | Lesen außerhalb des Arbeitsbereichs bleibt verwehrt; die Deny-Regel greift; im Arbeitsbereich liest `agy` ohne Rückfrage (so ist es dokumentiert) |
| **S7** | Vor und nach einer Reihe von zehn einfachen Anfragen in `agy -i` den Befehl `/usage` ausführen | Wie viel vom 5-Stunden-Fenster kostet eine einfache Anfrage? Ab wie vielen Anfragen am Tag wird es knapp? Ergebnis ist Grundlage für die Drosselung |
| **S8** | `time agy -p …` für eine einfache Anfrage; währenddessen `docker stats --no-stream` | Dauer, Arbeitsspeicher und Prozessorlast je Lauf (auf arm64 in der Größenordnung eines Raspberry Pi bewerten) |
| **S9** | Marker setzen (`touch /tmp/vorher`), eine Anfrage mit eindeutigem Satz im Prompt stellen, `find /data -newer /tmp/vorher -type f` und `grep -rl "<eindeutiger Satz>" /data/.gemini` | Welche Dateien gehören zu **einem** Lauf? Stehen Prompt und Antwort im Klartext darin? Lassen sie sich gefahrlos löschen (nächster Lauf funktioniert)? Lenkt eine der Variablen `ANTIGRAVITY_GEMINI_DIR`, `GEMINI_DIR`, `ANTIGRAVITY_APP_DATA_DIR` den Zustandsordner um? |
| **S10** | Fehlerbilder: `--model gibt-es-nicht`; Token-Datei entfernen; Token-Datei beschädigen; `--network none`; laufenden Lauf mit `kill` beenden und `ps` prüfen | Exitcode, `status`, Text in `error` und auf der Standardfehlerausgabe je Fall; Dauer bis zum Abbruch; bleiben Sprachserver-Prozesse zurück? Material für die Tabelle in Abschnitt 5.6 |
| **S11** | `agy models` | Echte Modellkennungen und die Vorgabe. Beispiele aus Drittquellen (`gemini-3.8-flash-medium`, `gemini-3.6-flash-high`) sind unbelegt |
| **S12** | Kontingent: Wenn das Fenster im Test erschöpft wird, den **genauen** Fehlertext und Exitcode festhalten | Grundlage für die Meldung „Kontingent aufgebraucht“ (Abschnitt 5.6) |

## Ergebnisse

Zu füllen. Je Zeile: Version von `agy`, Datum (`TT.MM.JJJJ`), Ergebnis in einem Satz, ggf. Verweis auf
die Ausgabe (ohne Zugangsdaten).

| Nr. | Version | Datum | Ergebnis |
|---|---|---|---|
| S1a | | | |
| S1b | | | |
| S2 | | | |
| S3 | | | |
| S3b | | | |
| S3c | | | |
| S4 | | | |
| S5 | | | |
| S6 | | | |
| S7 | | | |
| S8 | | | |
| S9 | | | |
| S10 | | | |
| S11 | | | |
| S12 | | | |

**Bewertung (nach dem Spike auszufüllen):** Schranke G2 ☐ bestanden ☐ nicht bestanden —
gewählter Weg: ☐ W1 ☐ W2 — offene Risiken: …

## Aufräumen

1. In `agy` den Befehl `/logout` ausführen.
2. Den Zugriff im Google-Konto widerrufen: Sicherheit → Drittanbieter mit Kontozugriff bzw. Geräte
   (die Anmeldung erscheint dort als Antigravity).
3. Container und Volume entfernen: `docker rm -f agy-spike; docker volume rm agy-spike-data`
   (und weitere Volumes aus S3).
4. Prüfen, dass keine Ausgabe mit Token-Inhalt in Dateien, Terminalprotokollen oder Nachrichten
   zurückgeblieben ist.
