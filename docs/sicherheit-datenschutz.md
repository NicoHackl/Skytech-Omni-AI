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
  `model` fließt bei Claude und ChatGPT als Argument in einen Unterprozess — der wird ohne Shell
  gestartet (`subprocess.run` mit Argumentliste), es gibt also keine Shell-Auswertung.
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

Empfehlung an den Betreiber: den Port nicht ins Internet weiterleiten. Wer nur die Oberfläche
braucht, kann die Zeilen `ports` und `ports_description` aus `config.yaml` entfernen — der Ingress
funktioniert ohne veröffentlichten Port weiter.

## Werkzeuge der Befehlszeilen

`tool_access` entscheidet, was die KI während einer Anfrage tun darf. Die Stufen unterscheiden
sich **sicherheitlich**, nicht nur im Komfort:

| Stufe | Reichweite |
|---|---|
| `off` | Kein Zugriff nach außen und keiner ins Dateisystem |
| `web` | Lesender Zugriff auf öffentliche Webseiten. Was das Modell abruft, bestimmt der Prompt |
| `full` | Zusätzlich Befehle und Dateizugriff **im Add-on-Container** |

**Die Stufen sind nicht bei beiden Befehlszeilen gleich scharf.** Bei Claude ist `web` eine Liste
einzeln freigegebener Werkzeuge (`WebSearch`, `WebFetch`) — es gibt in dieser Stufe schlicht kein
Werkzeug, mit dem sich eine Datei lesen ließe. Bei Codex gibt es diese Liste nicht, sondern eine
Sandbox-Stufe: `read-only` verhindert Schreibzugriffe und eigenständige Netzverbindungen, **lesende
Befehle im Container bleiben aber möglich**. In der Vorgabestufe kann ChatGPT damit prinzipiell
Dateien unter `/data` lesen — Claude kann das dort nicht.

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

## Personenbezogene Daten

| Datenart | Wird verarbeitet? | Wo gespeichert | Löschfrist |
|---|---|---|---|
| Inhalt des Prompts | ja, im Durchlauf | nicht gespeichert; bei Google ausdrücklich `store: false` | entfällt |
| Antwort des Modells | ja, im Durchlauf | nicht gespeichert | entfällt |
| Anmeldezustand der Claude-CLI | ja | `/data/.claude` im Container | bis zur Deinstallation |
| Anmeldezustand der Codex-CLI | ja | `/data/.codex` im Container | bis zur Deinstallation |
| Abgerufene Webseiten (Stufe `web`/`full`) | nur im Durchlauf | nicht gespeichert | entfällt |
| Zugangsdaten | ja | `/data/options.json`, vom Supervisor verwaltet | bis zum Leeren des Felds |

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

Ein neuer externer Dienst ist eine Design-Entscheidung → Eintrag in
[design-entscheidungen.md](design-entscheidungen.md), inklusive der Frage, welche Daten das Haus
verlassen.

## Abhängigkeiten

- Die Versionen von Flask, waitress, der beiden Befehlszeilen und der Basisimages sind festgenagelt. Ein
  Update ist damit ein sichtbarer Commit und kein stiller Seiteneffekt.
- Sicherheitsupdates zeitnah einspielen. Beim Anheben einer der Befehlszeilen prüfen, ob `claude -p`
  bzw. `codex exec` sich noch gleich verhält — das Verhalten des Add-ons hängt daran.
- Neue Abhängigkeiten vor Aufnahme prüfen: Wartungsstand, Verbreitung, Lizenz. Für die Oberfläche
  gilt zusätzlich die Liste der ausgeschlossenen Pakete in [frontend.md](frontend.md).

## Grenzen für KI-Agenten

- Kein von einer KI erzeugter Code wird ungeprüft ausgeführt.
- Die Antwort eines Modells ist **Daten, kein Steuerbefehl**. Sie wird geparst und weitergereicht;
  das Add-on leitet daraus keine Aktion ab.
- An die Anbieter gehen nur die für die Aufgabe nötigen, verdichteten Daten — nie ganze
  Zustandsabbilder des Smart Homes, nie personenbezogene Daten ohne ausdrückliche Freigabe.
- Harte Sicherheitsgrenzen sind durch eine KI nicht änderbar.
