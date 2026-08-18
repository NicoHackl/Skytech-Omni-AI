# Sicherheit und Datenschutz

## Zugangsdaten

- Keine Zugangsdaten im Code, in Logs, in Pfaden oder in Commit-Messages — siehe
  [`AGENTS.md`](../AGENTS.md), Regel 6. Handhabung: [konfiguration.md](konfiguration.md).
- Der Gemini-Schlüssel geht als Kopfzeile `x-goog-api-key` raus und **nicht** als Adressparameter:
  Adressen landen in Zugriffsprotokollen und bei Zwischenstationen, Kopfzeilen nicht.
- Das Claude-Token wird als Umgebungsvariable an den Unterprozess durchgereicht, nie als Argument
  auf der Befehlszeile — Argumente sind in der Prozessliste sichtbar.
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
  `model` fließt bei Claude als Argument in einen Unterprozess — der wird ohne Shell gestartet
  (`subprocess.run` mit Argumentliste), es gibt also keine Shell-Auswertung.
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

## Personenbezogene Daten

| Datenart | Wird verarbeitet? | Wo gespeichert | Löschfrist |
|---|---|---|---|
| Inhalt des Prompts | ja, im Durchlauf | nicht gespeichert; bei Google ausdrücklich `store: false` | entfällt |
| Antwort des Modells | ja, im Durchlauf | nicht gespeichert | entfällt |
| Anmeldezustand der Claude-CLI | ja | `/data/.claude` im Container | bis zur Deinstallation |
| Zugangsdaten | ja | `/data/options.json`, vom Supervisor verwaltet | bis zum Leeren des Felds |

Grundsatz Datenminimierung: Was nicht erhoben wird, kann nicht verloren gehen. Das Add-on legt
weder einen Verlauf noch ein Protokoll der Anfragen an.

**Wichtig für den Betreiber:** Was im Prompt steht, verlässt das Haus. Wer Zustände aus dem Smart
Home in eine Anfrage schreibt, gibt sie an Anthropic bzw. Google. Es gehört nur hinein, was für die
Aufgabe nötig ist.

## Externe Dienste

| Dienst | Welche Daten gehen dorthin | Warum nötig |
|---|---|---|
| Anthropic | Prompt, gewähltes Modell, Abo-Token bzw. Schlüssel | Der Prompt wird dort beantwortet |
| Google | Prompt, gewähltes Modell, Schlüssel | Dasselbe für Gemini. `store: false` unterbindet das Speichern des Verlaufs |

Ein neuer externer Dienst ist eine Design-Entscheidung → Eintrag in
[design-entscheidungen.md](design-entscheidungen.md), inklusive der Frage, welche Daten das Haus
verlassen.

## Abhängigkeiten

- Die Versionen von Flask, waitress, der Claude-CLI und der Basisimages sind festgenagelt. Ein
  Update ist damit ein sichtbarer Commit und kein stiller Seiteneffekt.
- Sicherheitsupdates zeitnah einspielen. Beim Anheben der Claude-CLI prüfen, ob `claude -p` sich
  noch gleich verhält — das Verhalten des Add-ons hängt daran.
- Neue Abhängigkeiten vor Aufnahme prüfen: Wartungsstand, Verbreitung, Lizenz. Für die Oberfläche
  gilt zusätzlich die Liste der ausgeschlossenen Pakete in [frontend.md](frontend.md).

## Grenzen für KI-Agenten

- Kein von einer KI erzeugter Code wird ungeprüft ausgeführt.
- Die Antwort eines Modells ist **Daten, kein Steuerbefehl**. Sie wird geparst und weitergereicht;
  das Add-on leitet daraus keine Aktion ab.
- An die Anbieter gehen nur die für die Aufgabe nötigen, verdichteten Daten — nie ganze
  Zustandsabbilder des Smart Homes, nie personenbezogene Daten ohne ausdrückliche Freigabe.
- Harte Sicherheitsgrenzen sind durch eine KI nicht änderbar.
