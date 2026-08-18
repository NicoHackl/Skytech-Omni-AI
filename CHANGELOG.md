# Changelog

Alle nennenswerten Änderungen an Skytech OmniAI.
Format nach [Keep a Changelog](https://keepachangelog.com/de/1.1.0/),
Versionierung nach [Semantic Versioning](https://semver.org/lang/de/).

Kategorien: `Hinzugefügt`, `Geändert`, `Veraltet`, `Entfernt`, `Behoben`, `Sicherheit`.

Einträge sind aus **Nutzersicht** formuliert — was sich für den Anwender ändert, nicht welche
Datei angefasst wurde.

## [Unveröffentlicht]

## [0.7.0] — 18.08.2026

### Behoben

- **Die KI konnte nichts nachschlagen.** Anfragen, die aktuelle Fakten brauchen — Wetter,
  Nachrichten, Preise, Fahrpläne — endeten mit einer Absage wie „Wettervorhersage nicht möglich,
  da WebFetch unterbunden ist". Es war nie etwas blockiert: die Claude-Befehlszeile läuft im
  Add-on ohne Bildschirm und kann deshalb nicht nachfragen, ob sie ein Werkzeug benutzen darf —
  also lehnt sie ohne ausdrückliche Freigabe **jedes** ab. Die Freigabe fehlte schlicht. Sie ist
  jetzt da, und die KI wird zusätzlich angewiesen, aktuelle Fakten nachzuschlagen statt sie aus
  dem Gedächtnis zu raten. Scheitert eine Recherche wirklich, meldet sie das in der Antwort,
  statt sich etwas auszudenken.

  Diese Verbesserung war schon einmal fertig und ging beim Zusammenführen zweier Entwicklungsstände
  in Version 0.6.0 verloren. Sie ist hiermit wiederhergestellt; der Ablauf in
  `docs/git-workflow.md` wurde so ergänzt, dass sich das nicht wiederholt.

### Hinzugefügt

- **Neue Option `tool_access`** mit drei Stufen. `web` (Vorgabe) erlaubt Websuche und
  Seitenabruf — das deckt Wetter, Nachrichten und Preise ab. `full` erlaubt zusätzlich Befehle und
  Dateizugriff im Add-on und ist für Sonderfälle gedacht. `off` schaltet alle Werkzeuge ab und
  entspricht dem Verhalten davor. Ein vertippter Wert wird nicht übernommen, sondern fällt auf
  `web` zurück.
- Die Übersicht in der Oberfläche zeigt die eingestellte Stufe. Steht sie auf `full`, erscheint
  dort ein Hinweis, warum das mehr ist als nötig.
- Scheitert die Stufe `full`, weil das Add-on als Systembenutzer läuft, nennt die Meldung jetzt
  den Ausweg über `web` statt der englischen Originalmeldung.

### Sicherheit

- Die Vorgabe ist bewusst `web` und nicht `full`. In der Stufe `full` darf die KI im Add-on Dateien
  lesen — dort liegt auch das Token des Abos —, und Web-Zugriff hat sie dabei ebenfalls. Zusammen
  mit dem ungeschützten Port 8000 wäre das ein Weg, das Token nach außen zu bringen. Wer `full`
  braucht, sollte den Port schließen und nur die Oberfläche nutzen.

### Migration

- Keine. Die neue Option hat einen Vorgabewert, den Home Assistant beim Update selbst ergänzt —
  anders als beim Umbau des Modellfelds in 0.5.0 wird die Konfiguration **nicht** als ungültig
  gemeldet.
- Wer das bisherige Verhalten ohne Werkzeuge behalten will, stellt `tool_access` auf `off` und
  startet das Add-on neu.

## [0.6.0] — 18.08.2026

### Hinzugefügt

- **Eine Oberfläche direkt in Home Assistant.** Das Add-on bringt ein eigenes Panel mit
  (Seitenleiste links, Eintrag „OmniAI"). Es zeigt, welcher Anbieter aktiv ist, welches
  Standardmodell gilt und für welche Anbieter ein Zugang hinterlegt ist. Auf einer zweiten Seite
  lässt sich eine Testanfrage stellen und die Antwort ansehen, ohne `curl` und ohne Kommandozeile;
  eine dritte Seite listet die auswählbaren Modelle je Anbieter.
- **Hell- und Dunkel-Modus** mit sichtbarem Schalter in der Kopfzeile. Die Vorauswahl kommt vom
  Betriebssystem, die getroffene Wahl bleibt über das Neuladen hinweg erhalten.
- **Automatischer Neustart**, wenn das Add-on nicht mehr antwortet.
- Eine Projektdokumentation unter `docs/` und verbindliche Projektregeln in `AGENTS.md`.
- Tests und Linting, die vor jedem Commit fehlerfrei durchlaufen müssen.

### Geändert

- **Fehlermeldungen sind jetzt Sätze statt Technik.** Bisher kam bei einem Fehler der englische
  Originaltext der Gegenstelle zurück, teils samt Pfaden, Stacktrace oder der Rohausgabe des
  Modells. Jetzt antwortet das Add-on mit einem deutschen Satz, der sagt, was schiefging und was
  zu tun ist. Die technische Ursache steht vollständig im Log des Add-ons.
- **Eine fehlerhafte Anfrage wird als solche gemeldet.** Fehlt der Prompt oder passt der
  Anbietername nicht, kommt jetzt „Anfrage fehlerhaft" statt „Serverfehler". Automatisierungen,
  die auf den Antwortcode reagieren, können beides nun unterscheiden.
- **Das Add-on läuft auf einem Server für den Dauerbetrieb.** Bisher blockierte eine laufende
  Anfrage an ein Modell alles andere — auch die Zustandsabfrage. Jetzt bleiben Oberfläche und
  Zustandsabfrage währenddessen erreichbar.
- Die Beschreibung des Add-ons und alle Meldungen sind auf Deutsch.
- Die Versionen des Basisimages, der Claude-Befehlszeile und der Python-Pakete sind festgenagelt.
  Ein Update ist damit eine sichtbare Änderung und passiert nicht mehr nebenbei beim Neubauen.

### Sicherheit

- Zugangsdaten erscheinen an keiner Stelle mehr in einer Ausgabe. Das Log meldet nur noch,
  **welche** Zugänge hinterlegt sind, nicht womit; die Zustandsabfrage antwortet mit „ja"/„nein".
- Bekannt und weiterhin offen: der Port 8000 des Add-ons ist **nicht** durch ein Passwort
  geschützt. Wer ihn erreicht, kann Anfragen stellen und damit Kontingent verbrauchen. Er sollte
  nicht ins Internet weitergeleitet werden. Wer nur die neue Oberfläche nutzt, kann ihn ganz
  schließen.

## [0.5.0] — 02.08.2026

### Hinzugefügt

- **Google Gemini als zweiter Anbieter.** Das Add-on ist nicht mehr auf Claude festgelegt: unter
  `provider` lässt sich jetzt `gemini` wählen. Nötig ist ein Schlüssel aus Google AI Studio, der
  unter `gemini_api_key` eingetragen wird. Der Verlauf wird bei Google ausdrücklich **nicht**
  gespeichert.
- **Auswahl unter den aktuellen Gemini-Modellen**, add-on-weit und pro Anfrage:
  `gemini-flash-latest` (Vorgabe), `gemini-3.6-flash`, `gemini-3.5-flash`,
  `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`, `gemini-2.5-pro`, `gemini-2.5-flash`,
  `gemini-2.5-flash-lite`. Jede weitere `gemini-*`-Kennung wird ebenfalls angenommen, sodass neue
  Modelle von Google ohne Update nutzbar sind.
- **Abfrage der gültigen Werte** über `GET /models`: aktiver Anbieter, auswählbare Modelle und
  Standardmodell je Anbieter. Automatisierungen müssen die Liste nicht mehr fest eintragen.

### Geändert

- **Das Feld `model` ist ein Auswahlfeld statt eines Freitextfelds** und gilt für beide Anbieter.
  Es legt nur den add-on-weiten Standard fest — pro Anfrage lässt sich weiterhin jede Kennung
  setzen.
- Claude bleibt der vorausgewählte Anbieter; an bestehenden Installationen ändert sich nichts.

### Behoben

- Fehler von Google werden in verständlichen Sätzen gemeldet: fehlender oder ungültiger Schlüssel,
  fehlende Freigabe, unbekanntes Modell, aufgebrauchtes Kontingent, Überlastung, keine Verbindung.

### Migration

- Das Feld `model` hatte bisher keinen Vorgabewert; der ist im neuen Auswahlfeld nicht enthalten.
  Home Assistant meldet die Konfiguration deshalb einmalig als ungültig — Konfiguration öffnen,
  `auto` oder das gewünschte Modell wählen, speichern.

## [0.3.0] — 05.07.2026

### Hinzugefügt

- **Modellwahl pro Anfrage.** `POST /ask` nimmt neben `prompt` und `provider` jetzt auch `model`
  entgegen. Damit lässt sich pro Automatisierung entscheiden, ob es schnell und günstig oder
  gründlich sein soll. Ohne Angabe bleibt es beim Standard.
- Ein add-on-weites Standardmodell in der Konfiguration.

### Behoben

- Antworten, die das Modell in einen Markdown-Block verpackt oder mit erklärenden Sätzen umgeben
  hat, werden jetzt ausgewertet, statt die Anfrage scheitern zu lassen.

## [0.2.0] — 04.07.2026

### Behoben

- **Das Add-on ließ sich überhaupt nicht anmelden.** Der übliche Anmeldevorgang von Claude öffnet
  einen Browser — in einem Add-on gibt es keinen. Ein Feld für Zugangsdaten fehlte ebenfalls, also
  scheiterte jede Anfrage. Jetzt wird einmalig auf einem Rechner mit Browser ein langlebiges Token
  erzeugt (`claude setup-token`) und im Add-on unter `claude_oauth_token` eingetragen. Alternativ
  lässt sich unter `anthropic_api_key` ein nach Verbrauch abgerechneter Schlüssel hinterlegen.
- **Die Anmeldung überstand keinen Neustart.** Sie liegt jetzt im dauerhaften Datenverzeichnis
  des Add-ons.
- **Die Konfiguration wurde gar nicht gelesen.** Auch die Wahl des Anbieters blieb dadurch ohne
  Wirkung.
- Ohne hinterlegten Zugang antwortet das Add-on mit einer Anleitung statt mit einem Fehler.

## [0.1.0] — 04.07.2026

### Hinzugefügt

- Erste Version: Home-Assistant-Add-on mit `POST /ask` für Anfragen an Claude über das
  Pro/Max-Abo und `GET /health` für die Zustandsabfrage.
- Aufbau mit austauschbaren Anbietern, damit weitere KI-Dienste später ohne Umbau dazukommen
  können.

### Behoben

- Home Assistant erkannte das Repository nicht als Add-on-Repository an. Ursache war ein fehlendes
  Manifest in der Wurzel, nicht die Ordnertiefe.
