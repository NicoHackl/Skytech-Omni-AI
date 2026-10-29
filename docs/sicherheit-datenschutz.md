# Sicherheit und Datenschutz

## Zugangsdaten

- Keine Zugangsdaten im Code, in Logs, in Pfaden oder in Commit-Messages — siehe
  [`AGENTS.md`](../AGENTS.md), Regel 6. Handhabung: [konfiguration.md](konfiguration.md).
- Der Gemini-Schlüssel geht als Kopfzeile `x-goog-api-key` raus und **nicht** als Adressparameter:
  Adressen landen in Zugriffsprotokollen und bei Zwischenstationen, Kopfzeilen nicht.
- Das Claude-Token wird als Umgebungsvariable an den Unterprozess durchgereicht, nie als Argument
  auf der Befehlszeile — Argumente sind in der Prozessliste sichtbar. Aus demselben Grund geht der
  Prompt an die Codex-CLI über die Standardeingabe.
- Die Anmeldung des ChatGPT-Abos liegt als Datei unter `/data/.codex/auth.json`, nur für den
  Add-on-Prozess lesbar (`0600`, Verzeichnis `0700`). Sie wird aus der Konfiguration nur dann neu
  geschrieben, wenn sich der eingetragene Wert geändert hat — sonst überschriebe ein Neustart die
  von der CLI erneuerten Tokens.
- Die Anmeldungen bei Google (`gemini_agy`) liegen je Konto als Datei unter `/data` (Rechte `0600`,
  das erste in `/data/.gemini/antigravity-cli/`, weitere unter `/data/omniai-gemini-accounts/konto-N/`),
  dazu eine Sicherung daneben. Die Kontenliste (`omniai-gemini-accounts.json`) enthält Namen,
  Reihenfolge und Wartezeiten, keine Anmeldedaten; ihre Pfade sind relativ und werden beim Lesen auf
  Ausbrüche geprüft. Sie entsteht im Add-on und erscheint nie in einer
  Antwort. Der **Code**, den der Nutzer von Google kopiert, und die **Anmeldeadresse** (sie trägt
  Zufallswerte der Sitzung) stehen nie im Log; der Code geht nur in die Eingabe der CLI. Die
  Adresse liefert das Add-on ausschließlich über den Ingress aus.
- `GET /status` meldet zu jedem Zugang nur `true` oder `false`. Weder der Wert noch ein Ausschnitt
  noch seine Länge verlässt das Add-on.
- Vor jedem Commit `git diff --staged` prüfen.
- Ein versehentlich gepushtes Token gilt als kompromittiert: **neu erzeugen**, nicht nur aus der
  Historie entfernen. Ein `git rebase` macht das Leak nicht ungeschehen.

## Eingaben

- Der Kopf `X-Ingress-Path` wird gegen ein Muster geprüft, bevor er in die `index.html` eingesetzt
  wird. Er ist der einzige Wert von außen, der ins Markup gelangt.
- Pfade unterhalb der Wurzel werden von `send_from_directory` aufgelöst; Ausbruchsversuche mit
  `..` weist es ab, und die Anfrage landet auf der Auffangroute.
- `provider` und `model` werden gegen bekannte Werte geprüft, bevor irgendetwas damit geschieht.
  `model` fließt bei Claude, ChatGPT und Gemini (AGY) als Argument in einen Unterprozess — der wird
  ohne Shell gestartet (Argumentliste), es gibt also keine Shell-Auswertung. Ein Prompt, der mit
  `/` beginnt, wird bei Gemini (AGY) nicht als Befehl der CLI gedeutet (`--disable-slash-commands`).
  Der eingefügte Code der Google-Anmeldung wird gegen ein Muster geprüft (Zeichen eines Codes,
  höchstens 2048), bevor er in die Eingabe der CLI geschrieben wird.
- Der Prompt selbst wird nicht geprüft: er ist der Inhalt der Anfrage und geht unverändert an das
  Modell.

## Ausgaben

Was der Nutzer nicht zu sehen braucht, ist nicht nur Rauschen, sondern eine Auskunft über das
System — Regel 12 hat damit auch eine Sicherheitsseite:

- Fehlermeldungen nennen **nie** Pfade, Hostnamen, Ports, Versionen der Gegenstelle, Stacktraces
  oder Rohausgaben des Modells. Das alles geht ins Log.
- Der Antwortcode der Gegenstelle bleibt im Log. Nach oben geht die Ursache in Worten
  („Der hinterlegte Gemini-Schlüssel ist ungültig."), nicht die Zahl.
- Die Rohausgabe eines Modells kann alles enthalten, was im Prompt stand. Sie wird deshalb nie in
  eine Fehlermeldung übernommen.

Formulierung und Format der sichtbaren Texte: [nutzertexte.md](nutzertexte.md).

## Der offene Port

Das Add-on veröffentlicht Port 8000 **ohne Authentifizierung**. Wer ihn im Netz erreicht, kann
Anfragen stellen und damit fremdes Abo-Kontingent oder Guthaben verbrauchen. Das ist bewusst so,
weil Automatisierungen in Home Assistant sonst ein zusätzliches Token bräuchten — es ist aber eine
bekannte Lücke und in [bekannte-luecken.md](bekannte-luecken.md) geführt.

**Ausnahme: die Schnittstelle v1** (`/v1/…`, für Skytech X, D-019) verlangt bei jedem Aufruf
`Authorization: Bearer <api_token>`. Der Vergleich läuft in konstanter Zeit; ist kein Token
eingerichtet, ist `/v1` geschlossen. Das Token steht nur in den Add-on-Optionen und in Skytech X
(dort verschlüsselt), nie im Log.

Empfehlung an den Betreiber: den Port nicht ins Internet weiterleiten. Wer nur die Oberfläche
braucht, kann die Zeilen `ports` und `ports_description` aus `config.yaml` entfernen — der Ingress
funktioniert ohne veröffentlichten Port weiter.

## Die Seite „Einstellungen“

Die Oberfläche kann Zugänge und Werkzeugstufe ändern. Damit das nicht zum zweiten offenen Weg
neben Port 8000 wird:

- **Speichern nur über den Ingress.** `PUT /settings` nimmt nur Aufrufe an, die vom Ingress-Proxy
  des Supervisors kommen (`172.30.32.2`) — also erst, nachdem Home Assistant den Nutzer angemeldet
  hat. Der Kopf `X-Ingress-Path` taugt dafür nicht, den kann jeder Aufrufer selbst schicken. Ohne
  diese Sperre könnte jeder, der Port 8000 erreicht, `full` einschalten und über einen Prompt die
  Zugänge auslesen.
- **Nur für Administratoren.** `panel_admin` (Vorgabe `true`, deshalb nicht eigens in `config.yaml` gesetzt) blendet die Oberfläche für andere Nutzer aus
  der Seitenleiste aus.
- **Anmeldung bei Google nur über den Ingress.** Starten, Code einreichen, Abbrechen und Abmelden
  (`/auth/gemini-agy…`, auch Konto hinzufügen und entfernen) gelten wie `PUT /settings`: nur von der Absenderadresse des Ingress-Proxys.
  Sonst könnte jeder, der Port 8000 erreicht, die Anmeldung des Betreibers entfernen oder eine
  fremde Anmeldung anstoßen.
- **Zugänge nur schreiben.** `GET /settings` liefert jedes Zugangsfeld leer und dazu nur
  „hinterlegt ja/nein“ — dieselbe Auskunft wie `GET /status`. Ein Wert kommt nie zurück.
- **Manager-Rolle.** Das Add-on fordert `hassio_role: manager` an, weil der Supervisor das
  Speichern der eigenen Optionen sonst verweigert. Der Supervisor-Token verlässt den Prozess nur
  in Richtung Supervisor, ausdrücklich ohne Proxy, und erscheint nie im Log.
- Die Rückmeldung des Supervisors (englisch, mit Schemafeldern) geht ins Log, nicht auf den
  Bildschirm.

## Werkzeuge der Befehlszeilen

`tool_access` entscheidet, was die KI während einer Anfrage tun darf. Die Stufen unterscheiden
sich **sicherheitlich**, nicht nur im Komfort:

| Stufe | Reichweite |
|---|---|
| `off` | Kein Zugriff nach außen und keiner ins Dateisystem |
| `web` | Lesender Zugriff auf öffentliche Webseiten. Was das Modell abruft, bestimmt der Prompt |
| `full` | Zusätzlich Befehle und Dateizugriff **im Add-on-Container** |

**Die Stufen sind nicht bei allen Befehlszeilen gleich scharf.** Bei Claude ist `web` eine Liste
einzeln freigegebener Werkzeuge (`WebSearch`, `WebFetch`) — es gibt in dieser Stufe schlicht kein
Werkzeug, mit dem sich eine Datei lesen ließe. Bei Codex gibt es diese Liste nicht, sondern eine
Sandbox-Stufe: `read-only` verhindert Schreibzugriffe und eigenständige Netzverbindungen, **lesende
Befehle im Container bleiben aber möglich**. In der Vorgabestufe kann ChatGPT damit prinzipiell
Dateien unter `/data` lesen — Claude kann das dort nicht.

**Gemini (AGY)** kennt weder die Liste noch die Sandbox. Die CLI ist ein Programmierassistent mit
Datei-, Befehls- und Webwerkzeugen. Das Add-on schränkt sie dreifach ein: (1) ein eigener, leerer
Arbeitsbereich unter `/data` — außerhalb davon ist der Dateizugriff der CLI aus, die Optionen mit
allen Zugängen sind also nicht lesbar; (2) Regeln in ihrer `settings.json`, die **Befehle, URL-Ausführung
und MCP in jeder Stufe verbieten** (auch bei `full`) und das Lesen von Webseiten nur bei `web` und
`full` erlauben; (3) eine schmale Umgebung ohne die Zugänge der anderen Anbieter. Nicht abschaltbar
ist eine eventuell eingebaute Websuche der CLI — bei `off` steht nur die Bitte an das Modell, keine
Werkzeuge zu nutzen. Fehlt die `settings.json` oder lässt sie sich nicht schreiben, läuft die CLI
nicht. Das ist enger als Claude mit `full` und vergleichbar mit Claude in `web`; ein Rest bleibt, weil
Anweisungen aus abgerufenen Webseiten das Modell erreichen können — es kann damit höchstens im
leeren Arbeitsbereich schreiben, dessen Inhalt nach jedem Lauf gelöscht wird.

Das ist deutlich weniger als `full` (kein Schreiben, kein freier Netzzugang; hinausgehen könnte
Gelesenes allenfalls über eine Suchanfrage), aber mehr als bei Claude in derselben Stufe. Wer das
nicht will, stellt `tool_access` auf `off` oder betreibt `codex_sub` nur über den Ingress mit
geschlossenem Port 8000.

Zu `full` gehört eine Kette, die man zusammen betrachten muss:

1. Unter `/data` liegt das Token des Claude-Abos und der Anmeldezustand der CLI.
2. `full` erlaubt der KI, Dateien dort zu lesen und Befehle auszuführen.
3. Web-Zugriff ist in dieser Stufe ebenfalls frei — es gibt also einen Weg nach draußen.
4. Port 8000 ist unauthentifiziert (siehe unten).

Wer den Port erreicht, kann damit über einen entsprechend formulierten Prompt das Token auslesen
und wegschicken lassen. Deshalb ist die Vorgabe `web`: sie deckt den eigentlichen Anwendungsfall
— etwas nachschlagen — vollständig ab und lässt Schritt 2 der Kette weg. Begründung als D-012 in
[design-entscheidungen.md](design-entscheidungen.md).

Wer `full` braucht, sollte es nur zusammen mit einem geschlossenen Port 8000 einschalten; über den
Ingress von Home Assistant greift dessen Anmeldung.

Der Prompt selbst ist in **jeder** Stufe die Eingabe eines Aufrufers und wird nicht geprüft.
Was darin steht, ist eine Anweisung an das Modell — und in Stufe `full` mittelbar eine Anweisung
an den Container.

## Agent-Läufe für Skytech X

Läufe (D-021) folgen **nicht** der Stufe `tool_access`, sondern sind enger:

- Die eingebauten Werkzeuge der Claude-CLI (Befehle, Dateien) sind in Läufen immer abgeschaltet
  (`--tools`), auch bei `full`. Unter `/data` liegt der Zugang des Abos; ein Lauf kann ihn nicht
  lesen. Websuche und Seitenabruf gibt es nur, wenn `tool_access` nicht `off` ist.
- Werkzeuge kommen ausschließlich vom Backend über MCP. Das Lauf-Token des Backends steht nur in
  einer Datei mit Rechten `600` im Arbeitsverzeichnis des Laufs, nie in der Befehlszeile, im Log
  oder in den gespeicherten Laufdaten; Datei und Verzeichnis werden nach dem Lauf gelöscht.
- Einstellungen, Hooks und `CLAUDE.md` von außen werden nicht geladen, Sitzungen nicht
  gespeichert.
- In Ereignissen stehen Name, Dauer und Ausgang eines Werkzeugaufrufs, nie Argumente oder
  Ergebnisse. Die Texte des Modells (Zwischenstände, Übergabe) können Inhalte aus den Werkzeugen
  wiedergeben; sie liegen bis 24 Stunden nach Laufende unter `/data/runs`.

## Embeddings für Skytech X

`POST /v1/embeddings` (D-023) schickt die übergebenen Texte — Wissenseinträge und
Suchanfragen aus Skytech X — mit dem Gemini-Schlüssel an Google (`gemini-embedding-001`).
Das Add-on speichert weder Texte noch Vektoren; im Log stehen nur Anzahl und Dimensionen.

## Personenbezogene Daten

| Datenart | Wird verarbeitet? | Wo gespeichert | Löschfrist |
|---|---|---|---|
| Inhalt des Prompts | ja, im Durchlauf | nicht gespeichert; bei Google ausdrücklich `store: false` | entfällt |
| Antwort des Modells | ja, im Durchlauf | nicht gespeichert | entfällt |
| Anmeldezustand der Claude-CLI | ja | `/data/.claude` im Container | bis zur Deinstallation |
| Anmeldezustand der Codex-CLI | ja | `/data/.codex` im Container | bis zur Deinstallation |
| Anmeldungen bei Google (Gemini-Abo), je Konto | ja | `/data` im Container (`.gemini/antigravity-cli/` je Kontoordner), mit Sicherung | bis „Entfernen“ des Kontos bzw. zur Deinstallation |
| Namen der Google-Konten (frei gewählt, z. B. „Privat“) | ja | `/data/omniai-gemini-accounts.json` | bis „Entfernen“ des Kontos |
| Gespräche der Antigravity-CLI (Prompt, Antwort, Zusammenfassung) | während eines Laufs | unter `/data/.gemini/…` — die CLI legt sie selbst an | werden nach **jedem Lauf** gelöscht; von den Protokollen der CLI bleiben die jüngsten fünf |
| Abgerufene Webseiten (Stufe `web`/`full`) | nur im Durchlauf | nicht gespeichert | entfällt |
| Zugangsdaten | ja | `/data/options.json`, vom Supervisor verwaltet — geschrieben über den Reiter „Konfiguration“ oder die Seite „Einstellungen“ | bis zum Leeren bzw. „Entfernen“ |

Grundsatz Datenminimierung: Was nicht erhoben wird, kann nicht verloren gehen. Das Add-on legt
weder einen Verlauf noch ein Protokoll der Anfragen an.

**Wichtig für den Betreiber:** Was im Prompt steht, verlässt das Haus. Wer Zustände aus dem Smart
Home in eine Anfrage schreibt, gibt sie an Anthropic, OpenAI bzw. Google. Es gehört nur hinein, was für die
Aufgabe nötig ist.

## Externe Dienste

| Dienst | Welche Daten gehen dorthin | Warum nötig |
|---|---|---|
| Anthropic | Prompt, gewähltes Modell, Abo-Token bzw. Schlüssel | Der Prompt wird dort beantwortet |
| OpenAI | Prompt, gewähltes Modell, Anmeldung des ChatGPT-Abos bzw. Schlüssel | Dasselbe für ChatGPT. Kein Verlauf: jeder Lauf ist eigenständig (`--ephemeral`) |
| Google | Prompt, gewähltes Modell, Schlüssel | Dasselbe für Gemini. `store: false` unterbindet das Speichern des Verlaufs |
| Google (Abo) | Prompt, gewähltes Modell, Anmeldung des Google-Kontos, abgerufene Webseiten | Dasselbe für Gemini über Google AI Pro. **Anders als beim Schlüssel** gelten die Bedingungen für private Konten: nach den Zusatzbedingungen der Antigravity-Dienste werden Eingaben erfasst und können zur Verbesserung genutzt werden, Löschung nur auf Antrag ([Recherche](erweiterungen/gemini-provider/recherche.md)). Smart-Home-Daten im Prompt verlassen das Haus unter diesen Bedingungen |

Ein neuer externer Dienst ist eine Design-Entscheidung → Eintrag in
[design-entscheidungen.md](design-entscheidungen.md), inklusive der Frage, welche Daten das Haus
verlassen.

## Release-Zugang

- Nach `main` — also an alle Installationen — schreibt nur der Release-Job, über einen
  Deploy-Key mit Schreibrecht (Secret `RELEASE_DEPLOY_KEY`). Das Ruleset von `main` lässt außer
  ihm nur Repo-Admins zu; Force-Push und Löschen sind auf `main`, `dev/main` und `dev/dev` gesperrt; Änderungen an `main` laufen nur über einen Pull Request, den der Repo-Besitzer mergt (auch in der GitHub-App; kein Admin-Bypass).
- Der private Schlüssel existiert ausschließlich als GitHub-Secret, keine lokale Kopie. Taucht er
  je anderswo auf: Deploy-Key unter Settings → Deploy keys löschen, neuen erzeugen
  (`ssh-keygen -t ed25519`), öffentlichen Teil mit Schreibrecht eintragen, privaten als Secret
  setzen.
- Der Admin-Bypass gilt für jeden, der mit Admin-Zugangsdaten pusht — auch für einen Agenten,
  der die Zugangsdaten des Users nutzt. Davor schützt nur Regel 1 in [`AGENTS.md`](../AGENTS.md).
- Die CI sucht bei jedem Lauf mit gitleaks in der ganzen Historie nach Secrets, prüft die
  Abhängigkeiten mit `pip-audit` und `npm audit` und den Code mit CodeQL (Reiter „Security“).

## Abhängigkeiten

- Die Versionen von Flask, waitress, der Befehlszeilen und der Basisimages sind festgenagelt. Die
  Antigravity-CLI (Version und SHA-512 je Architektur im `Dockerfile`) aktualisiert sich sonst selbst;
  das ist abgeschaltet (`AGY_CLI_DISABLE_AUTO_UPDATE`). Wer sie anhebt, holt beide Prüfsummen neu aus
  dem Manifest und wiederholt die Handprüfung aus D-022. Ein
  Update ist damit ein sichtbarer Commit und kein stiller Seiteneffekt. Dependabot schlägt
  Updates wöchentlich als PR gegen `dev/dev` vor; Befehlszeilen und Basisimage hebt er nicht an.
- Sicherheitsupdates zeitnah einspielen. Beim Anheben einer der Befehlszeilen prüfen, ob `claude -p`,
  `codex exec` bzw. `agy -p` sich noch gleich verhält — das Verhalten des Add-ons hängt daran.
- Neue Abhängigkeiten vor Aufnahme prüfen: Wartungsstand, Verbreitung, Lizenz. Für die Oberfläche
  gilt zusätzlich die Liste der ausgeschlossenen Pakete in [frontend.md](frontend.md).

## Grenzen für KI-Agenten

- Kein von einer KI erzeugter Code wird ungeprüft ausgeführt.
- Die Antwort eines Modells ist **Daten, kein Steuerbefehl**. Sie wird geparst und weitergereicht;
  das Add-on leitet daraus keine Aktion ab.
- An die Anbieter gehen nur die für die Aufgabe nötigen, verdichteten Daten — nie ganze
  Zustandsabbilder des Smart Homes, nie personenbezogene Daten ohne ausdrückliche Freigabe.
- Harte Sicherheitsgrenzen sind durch eine KI nicht änderbar.
