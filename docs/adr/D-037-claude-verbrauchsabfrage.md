# D-037: Claude-Verbrauch zusätzlich ohne Modellanfrage abfragen

- **Datum:** 02.11.2026
- **Status:** Aktiv, echte Kontoprüfung offen
- **Betrifft:** `providers/claude_usage.py`, `limits.py`, Karte „Kontingente“
- **Ersetzt:** D-035 nur hinsichtlich des Ausschlusses der direkten Verbrauchsabfrage;
  das Auswerten der CLI-Ereignisse bleibt bestehen.

## Kontext und Auftrag

Der User meldet zwei Grenzen: Claude zeigt einen Prozentwert erst nahe dem Limit;
„Aktualisieren“, Neuladen und Neustart bringen ohne Modellanfrage keinen neuen Stand.
Die bisherige Quelle ist das `rate_limit_event` einer Anfrage. Sie enthält unterhalb
Claude-eigener Warnschwellen keinen Prozentwert und meldet nur das engste Fenster.
Die Anwendung setzt selbst keine feste Schwelle von 90 %.

D-035 schloss die interne Verbrauchsabfrage aus, weil sie beim damaligen Test
abgewiesen wurde. Am 02.11.2026 beauftragt der User ausdrücklich einen erneuten
Versuch mit Zwischenspeicherung, Wartezeiten und vollständiger Dokumentation.

## Betrachtete Optionen

1. **Nur CLI-Ereignisse:** bewährt, aber löst keinen der beiden Punkte.
2. **Eine Modellanfrage beim Aktualisieren:** würde Kontingent verbrauchen und
   liefert unterhalb der Warnschwelle weiterhin keinen Prozentwert.
3. **Interne Verbrauchsabfrage ergänzen:** kann mehrere Fenster einschließlich
   niedriger Prozentwerte ohne Modellaufruf liefern. Undokumentiert, abhängig von
   den Rechten des hinterlegten Tokens und von Anthropic-seitigen Einschränkungen.

Gewählt ist Option 3 mit Rückfall auf vorhandene Werte. Es gibt keine Zusage,
wie oft Anthropic die Abfrage akzeptiert oder wie lange dieses Format funktioniert.

## Datenquelle und Auswertung

`GET https://api.anthropic.com/api/oauth/usage` mit `Authorization: Bearer …`,
`anthropic-beta: oauth-2025-04-20`, `Accept: application/json` und einem eigenen
User-Agent `Skytech-OmniAI`. Verwendet wird ausschließlich das vorhandene
`CLAUDE_CODE_OAUTH_TOKEN` aus der Umgebung, kein API-Schlüssel. Keine zusätzliche
Anmeldung, keine automatische Token-Erneuerung, kein Lesen des Rechner-Schlüsselbunds
oder fremder Anmeldedateien. Ohne Abo-Token wird der Abruf übersprungen.

Übernommen werden nur bekannte Fenster: `five_hour`, `seven_day`,
`seven_day_opus`, `seven_day_sonnet`. `utilization` ist hier bereits ein Prozentwert
von 0 bis 100; beim CLI-Ereignis dagegen ein Anteil von 0 bis 1. Nur endliche Zahlen
werden angenommen, keine Booleschen Werte. Fehlender Verbrauch wird nicht zu 0.
`resets_at` wird aus einem Zeitstempel mit Zone in Unix-Sekunden und das Maschinenformat
der bestehenden Antwort umgesetzt. Ein fehlender Rücksetzzeitpunkt bleibt unbekannt;
ein bekannter Prozentwert bleibt trotzdem erhalten. Ungültige Fenster werden ignoriert,
eine Antwort ohne gültiges Fenster gilt als Fehlversuch. Zusatzverbrauch, Geldbeträge,
Kontodaten und unbekannte Felder werden weder gespeichert noch ausgegeben.

Die Namen entsprechen dem bisherigen Datenmodell. Neue oder anders benannte
modellabhängige Fenster sind damit nicht automatisch unterstützt.

## Abruf, Zwischenspeicherung und Pausen

- Beide bestehenden Endpunkte `GET /limits` und `GET /v1/limits` nutzen denselben
  Abruf und Cache. Die vorhandene Authentifizierung bleibt bestehen.
- Der erste Abruf mit Abo-Token versucht die direkte Abfrage. Nach Erfolg frühestens
  nach **300 Sekunden** wieder. Es gibt keinen Hintergrundabruf und keinen erzwungenen
  Abruf: Öffnen, Aktualisieren und Neuladen verwenden innerhalb der Pause den Cache.
- Ein Aufruf verwendet eine Frist von **8 Sekunden** und liest höchstens **64 KiB**
  Antwort. Umleitungen werden abgelehnt, Umgebungs-Proxys werden nicht verwendet.
  Der Zugriff erfolgt mit der TLS-Prüfung der Python-Standardbibliothek.
- Gleichzeitige Aufrufe im Add-on-Prozess teilen eine Sperre und lösen nur einen
  Netzaufruf aus. Die Lösung ist für den einen Add-on-Prozess gedacht; mehrere
  unabhängige Instanzen koordinieren ihre Abfragen nicht untereinander.
- Bei Netzfehlern, ungültigen Antworten oder Ablehnungen: **5, 10, 20, 40, dann
  höchstens 60 Minuten** Pause, bis eine gültige Abfrage gelingt. Erfolg setzt den
  Fehlerzähler zurück.
- Bei fehlender/abgelehnter Berechtigung (`401`/`403`) mindestens **60 Minuten** Pause.
  Das bedeutet nicht, dass Claude keine normalen Modellanfragen mehr annehmen kann.
- `Retry-After` als Sekunden oder HTTP-Datum verlängert die Pause, wenn der Anbieter
  länger warten lässt. Ein fehlender, ungültiger oder auf 0 gesetzter Wert verkürzt
  die lokale Pause nicht. Ein längerer Anbieterwert darf auch über 60 Minuten liegen.
- Die Pause wird schon vor dem Netzaufruf gespeichert. Ein Absturz während des
  Abrufs und ein Neustart lösen dadurch keine sofortige Wiederholung aus.

Die Datei `/data/limits/claude_usage.json` enthält nur normalisierte Messwerte,
Messzeitpunkt, Fehlerzähler, nächsten Versuch und einen SHA-256-Fingerabdruck des
Tokens zur Cache-Zuordnung. **Kein Token und keine Rohantwort.** Schreiben erfolgt
atomar mit Dateirechten `0600`, ein neu angelegtes Verzeichnis trägt `0700`.
`OMNIAI_LIMITS_DIR` verschiebt diese Ablage zusammen mit den bisherigen Limitdateien.
Bei Tokenwechsel werden direkte Messwerte und Abfragepause des alten Tokens verworfen.
Die bisherigen CLI-Beobachtungen bleiben wie bisher separat gespeichert; sie sind
nicht an eine Token-Identität gebunden.

Ist die Ablage nicht beschreibbar, gelten Cache und Pausen nur bis zum Prozessende;
das Log weist darauf hin. Beschädigte Messdaten werden verworfen, vorhandene
CLI-Beobachtungen bleiben nutzbar. Einen Neustart zum Umgehen einer Pause zu verwenden
ist weder nötig noch vorgesehen.

## Zusammenführen und sichtbares Verhalten

Die bestehende Vertragsantwort bleibt unverändert. Die Schnittstelle beschreibt
`source: measured` bereits als Abruf ohne Modellanfrage, `source: observed` als
Beobachtung aus einer Anfrage; beide Quellen sind zulässig. Kein neues Feld und
keine neue Semantik des gemeinsamen Vertrags, deshalb keine Vertragsänderung.

- Eine direkte Messung wird mit ihrem ursprünglichen `observedAt` ausgegeben.
- Je Fenster gilt die jüngere Quelle. Eine neuere CLI-Beobachtung kann eine ältere
  Messung ersetzen; die anderen gemessenen Fenster bleiben erhalten.
- Neue CLI-Ereignisse stammen weiterhin aus `/ask`, `/v1/completions` und Läufen,
  einschließlich Claude-Anfragen von Skytech X. Sie lösen keine direkte Abfrage aus.
- Ein Fehler beim direkten Abruf löscht den letzten Messstand nicht. Ohne Messstand
  gilt weiterhin die CLI-Beobachtung, ohne beide Quellen bleibt der Verbrauch unbekannt.
- Nach der bekannten Rücksetzzeit wird ein alter Verbrauch nicht weiter angezeigt.
  Es wird daraus auch kein erfundener Verbrauch von 0 %.
- Ein volles gültiges Fenster führt zu `exhausted`; `retryAt` ist, sofern bekannt,
  die späteste Rücksetzzeit der vollen Fenster. Abfragepausen werden niemals als
  Kontingenterschöpfung oder als `retryAt` ausgegeben.
- „Zuletzt gemeldet“ zeigt jetzt bei allen Konten den ursprünglichen Datenzeitpunkt.
  Der Kartenkopf heißt „Abgerufen“, damit der Zeitpunkt des Seitenabrufs nicht als
  neuer Verbrauchsstand missverstanden wird. Bei gemischten Quellen kann ein einzelnes
  Fenster älter sein als der Kontostand; maßgeblich ist dessen eigenes `observedAt`.
- Claude erhält einen Hinweis auf den Mindestabstand und auf spätere Wiederholung
  bei Problemen. Ohne Prozentwert bleibt der Balken aus.

## Zugang, Sicherheit und Grenzen

Das vorhandene Abo-Token genügt nur, wenn Anthropic ihm die Verbrauchsabfrage erlaubt.
Insbesondere kann ein für Modellanfragen gültiges Token die benötigten Leserechte
(etwa `user:profile`) nicht besitzen. Das Add-on erweitert keine Berechtigungen
und ersetzt das langlebige `setup-token` nicht durch einen kurzlebigen Zugang.
Eine Abweisung erfordert zunächst die Diagnose im Betreiberprotokoll; ein neues
Token garantiert keine Abhilfe. Niemals Zugangsdaten zum Prüfen in Chat, Issue oder Log kopieren.

An Anthropic gehen das vorhandene Token und gewöhnliche Verbindungsmetadaten,
**kein Prompt und kein Modellauftrag**. Im Log stehen nur feste deutsche Meldungen
und bei HTTP-Ablehnungen der Status. Kein Antworttext, Token oder Ausnahme-Rohtext.
Der bisherige offene Port kann weiterhin Limitdaten abrufen; Cache und Sperre verhindern,
dass häufige Seitenabrufe die externe Schnittstelle pro Aufruf belasten.

## Nachweise und offene Handprüfung

**Lokal belegt:** Tests mit vollständig ersetzten Netzwerkaufrufen für niedrige Werte,
mehrere Fenster, gültige Nullwerte, fehlende Rücksetzzeit, leere/ungültige Antworten,
Erfolgscache über Prozessneustart, Tokenwechsel, gleichzeitige Abrufe, Netzfehler,
fehlende Rechte, wachsende Pausen, `Retry-After` als Sekunden/Datum einschließlich 0,
Schreibfehler, beschädigte Ablage, Quellenreihenfolge, Erschöpfung und Geheimhaltung.
Die Transportprüfung prüft Adresse, Header, Frist und Antwortgrößenbegrenzung.

**Nicht lokal belegt:** Annahme des vorhandenen Tokens im realen Konto, tatsächliche
Datenaktualität bei Anthropic, Verhalten auf dem Home-Assistant-System und dauerhafte
Verfügbarkeit. In der lokalen Prozessumgebung war kein Abo-Token gesetzt. Es wurde
kein Schlüsselbund ausgelesen und keine echte Kontenabfrage durchgeführt.

Nach Installation im Add-on:

| Schritt | Durchführung | Erwartung / Auswertung |
|---|---|---|
| H1 | Übersicht öffnen, ohne vorher eine Modellanfrage zu stellen | Bei akzeptiertem Token erscheinen Fünf-Stunden-/Wochenwerte auch unterhalb der Warnschwelle. Mit Claude Codes `/usage` vergleichen; Unterschiede des Abrufzeitpunkts beachten |
| H2 | Innerhalb von fünf Minuten aktualisieren und Seite neu laden | „Abgerufen“ ändert sich, „Zuletzt gemeldet“ und Prozentwerte stammen weiterhin aus dem Cache; keine zusätzliche externe Abfrage |
| H3 | Claude außerhalb von OmniAI nutzen, mindestens fünf Minuten nach H1 erneut aktualisieren | Bei erfolgreicher Abfrage neuer Messzeitpunkt und gegebenenfalls geänderter Verbrauch, ohne Anfrage in OmniAI |
| H4 | Add-on innerhalb der Cache-Zeit neu starten, Übersicht öffnen | Gesicherter Stand und Pause bleiben erhalten |
| H5 | Bei ohnehin auftretender Ablehnung das Betreiberprotokoll ansehen | Status nur im Log, letzter Stand bleibt sichtbar. Nicht absichtlich schnell abfragen, um eine Sperre zu erzwingen |
| H6 | Bei fehlenden Leserechten eine normale Claude-Anfrage über OmniAI oder Skytech X stellen | Anfrage bleibt unabhängig von der Limitabfrage nutzbar; neue CLI-Beobachtung kann sichtbar werden |
| H7 | Eine bekannte Rücksetzzeit abwarten, Aktualisieren während einer Abfragepause | Alter Prozentwert des abgelaufenen Fensters verschwindet; kein erfundener Nullwert |

Scheitert H1 an fehlenden Rechten oder dauerhafter Abweisung, ist die experimentelle
Datenquelle für dieses Konto noch nicht bestätigt. Die zwei ursprünglichen Grenzen
sind dann durch den Rückfall weiter vorhanden; ein grüner lokaler Test behauptet
keinen erfolgreichen Kontozugriff. Ergebnisse ohne Token oder Rohantwort dokumentieren.

### Recherchequellen und Aussagegrenzen

- [Fehlerbericht im offiziellen Claude-Code-Repository](https://github.com/anthropics/claude-code/issues/30930),
  geprüft am 02.11.2026: Berichte über anhaltende Abweisung der Usage-Abfrage und
  `Retry-After: 0`. Ein Nutzerbericht, keine API-Zusage von Anthropic.
- Das interne Antwortformat ist keine öffentliche Anthropic-Spezifikation.
  Die tolerante Auswertung und die Netzattrappen ersetzen deshalb nicht H1.

## Rücknahmebedingung

Wenn das installierte Konto trotz ausreichender Wartezeit dauerhaft abgewiesen wird,
Leserechte fehlen oder Anthropic das Format ändert, keinen engeren Takt, keine
Token-Rotation und keine automatische Modellanfrage ergänzen. Die direkte Abfrage
wird dann aus `claude_entry` entfernt; CLI-Ereignisse und deren Ablage funktionieren
weiter. Die ausschließlich dafür genutzte Datei `claude_usage.json` kann anschließend
entfernt werden. Die Entscheidung und die bekannte Lücke sind entsprechend nachzuziehen.
