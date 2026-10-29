# Handprüfung und Rücknahmebedingungen

> Plan. Die Prüfungen setzen **echte Google-Konten** voraus, die nur diesem Zweck dienen, und einen
> Browser. Sie laufen nach AP 10. Jede Abweichung wird im ADR D-030 und in
> [bekannte-luecken.md](../../bekannte-luecken.md) nachgetragen. Nummern mit `HW`, damit sie nicht
> mit H1 bis H15 aus D-022 und D-024 verwechselt werden.

## Vorbereitung

- Mindestens **zwei** Wegwerf-Konten mit AI Pro, getrennt von allen anderen Konten des Users: keine
  gemeinsame Wiederherstellungsadresse, keine gemeinsame Zahlungsart, keine Daten darin, Verbindungen
  zu Gmail, Drive und anderen Diensten in der Web-App abgeschaltet.
- Cookies aus einem **privaten Browserfenster** holen. Sie sind die Anmeldung des Kontos: nirgends
  hinterlegen außer in der Oberfläche des Add-ons, danach das Fenster schließen **ohne** Abmelden (sonst
  werden sie ungültig).

## Prüfungen

| Nr. | Prüfung | Erwartet |
|---|---|---|
| HW1 | Bereich „Gemini Web“: ein Konto anmelden | Konto steht auf „Bereit“; im Protokoll steht die Liste der Modelle; **kein Cookie-Wert** im Protokoll |
| HW2 | `POST /ask` mit `"provider": "gemini_web"` und einer Frage mit JSON-Anweisung | Antwort ist JSON; im Verlauf des Kontos steht **kein** Chat (temporär, F3) oder genau einer (sonst) |
| HW3 | Add-on neu starten, wieder fragen | Konto besteht, Antwort kommt |
| HW4 | Mehr als einen Tag warten, wieder fragen | Cookies wurden erneuert, Konto weiter „Bereit“ — oder die Oberfläche zeigt „Anmeldung abgelaufen“ und Entfernen und neu Anmelden stellt es her. Notieren, wie lange es hielt |
| HW5 | Zwei Konten anmelden; viele Anfragen, bis das erste leer ist | Im Protokoll „Konto … Kontingent aufgebraucht“, „Wechsel auf das nächste Google-Konto“; Antwort vom zweiten Konto; das erste steht mit „nächster Versuch“ in der Liste |
| HW6 | Anfrage mit einem Bild und mit einer Textdatei als Anhang; mit zu großer Datei; mit nicht erlaubtem Typ | Die Antwort bezieht sich auf den Anhang; die beiden Fehlerfälle liefern je einen Satz; unter `/tmp` bleibt nichts liegen |
| HW7 | Beide Konten leer machen, noch eine Anfrage | Sofort ein Satz mit Uhrzeit des nächsten Versuchs, Google wird nicht gefragt |
| HW8 | Nach der Wartezeit des ersten Kontos fragen | Das erste Konto wird wieder versucht; ist sein Limit erneuert, ist es wieder „Bereit“ |
| HW9 | Das **Wochenlimit** erreichen (oder in Google testweise einschränken) | Das Konto wartet; Verhalten und Meldung notieren (S6) |
| HW10 | Die Anmeldung eines Kontos in Google beenden (Abmelden im Browser), dann fragen | Konto steht auf „Anmeldung abgelaufen“, Antwort kommt vom anderen Konto; Entfernen und neu Anmelden stellt es her |
| HW11 | Konto entfernen, Add-on neu starten | Der Ordner des Kontos ist gelöscht (`/data/omniai-gemini-web-accounts/…`); das andere Konto besteht |
| HW12 | Zehn Anfragen, Verbrauch in der Web-App vergleichen | Größenordnung je Anfrage notieren (Grundlage für Drosselung) |
| HW13 | Anfrage mit kurzer Zeitgrenze über `/v1` | Zeitgrenze greift (`TIMEOUT`), danach läuft nichts mehr im Hintergrund |
| HW14 | Add-on-Update einspielen | Konten bleiben angemeldet |
| HW15 | Seite in Hell und Dunkel, bei 375px, per Tastatur | Alles lesbar und erreichbar; kein Cookie-Wert nach dem Absenden im Feld |
| HW16 | Update von einer Installation mit `provider: gemini_sub` (nach AP 1) | Verhalten wie in S11 notiert; Changelog-Hinweis erscheint im Release |

## Rücknahmebedingungen

Die Entscheidung wird überprüft, wenn eines davon eintritt:

- **Google schränkt oder sperrt ein Konto** wegen dieser Nutzung — Anbieter aus der `provider`-Liste
  nehmen, den Nutzern sagen warum, den Hinweis in der Oberfläche verschärfen.
- **Die Cookies halten nicht** (HW3, HW4): ohne dauerhafte Anmeldung ist der Anbieter nicht betreibbar;
  dann Verzicht oder anderer Weg.
- **Die Bibliothek bricht wiederholt** durch Änderungen von Google und wird nicht nachgezogen
  (S12): dann eigener Client oder Verzicht.
- **Google erkennt und blockiert** die Adresse (`TemporarilyBlockedError` häufig): Anbieter ist nicht
  zuverlässig; keine Umgehung bauen.
- **Google dokumentiert** einen erlaubten Weg zum Limit der Web-App — dann den Plan neu bewerten und
  den inoffiziellen Weg ablösen.
- **Die Lizenzfolge** der Bibliothek erweist sich als nicht tragbar — dann eigener Client (nur
  `gemini_web_client.py` ändert sich).
