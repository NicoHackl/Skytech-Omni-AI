# D-022: Gemini wird über die API mit Schlüssel angebunden; der Weg über das Google-AI-Pro-Abo wird zurückgestellt

- **Datum:** 27.10.2026
- **Status:** Vorgeschlagen (Entwurf — noch nicht beschlossen und **nicht** in [../../design-entscheidungen.md](../../design-entscheidungen.md) eingetragen)
- **Betrifft:** `providers/gemini_provider.py`, `providers/factory.py`, `config.yaml`, `Dockerfile`, ggf. ein neuer Provider `gemini_sub`

> Format nach [../../adr/0000-vorlage.md](../../adr/0000-vorlage.md). Wird die Entscheidung
> getroffen, wandert die Datei nach `docs/adr/D-022-gemini-api-statt-abo.md`, in die Tabelle von
> `design-entscheidungen.md` kommt eine Zeile, und dieser Ordner wird auf den Rest gekürzt.

## Kontext

Der Auftrag lautete, die Gemini-Modelle über das **Google-AI-Pro-Abo** zu nutzen, so wie
`claude_sub` (D-006) und `codex_sub` (D-013) das Abo ihres Anbieters über dessen Befehlszeile
nutzen. Die Recherche vom 27.10.2026 ([recherche.md](recherche.md)) ergab:

1. Die Gemini CLI bedient AI-Pro-Konten seit dem 18.06.2026 nicht mehr. Der Nachfolger ist die
   Antigravity CLI (`agy`).
2. `agy` läuft technisch im Add-on-Bild (musl-Binary, selbst geprüft), hat einen Headless-Modus mit
   JSON-Umschlag und nutzt das Abo-Kontingent.
3. Googles FAQ erklärt das Einpacken von `agy` in Anwendungen unter Verbraucherplänen für **nicht
   unterstützt**; die Nutzungsbedingungen nennen Fremdwerkzeuge einen Verstoß mit möglicher
   Sperrung. OmniAI ist eine solche Anwendung.
4. Die Anmeldung des Privatkontos lässt sich im Container nicht verlässlich halten (Schlüsselbund
   statt Datei, offener Fehler zum Dateispeicher, Wartezeit von 60 Sekunden ohne Anmeldung,
   Gesprächsdaten auf der Platte).
5. Der von Google für Fremdanwendungen empfohlene Weg ist ein API-Schlüssel — den bietet das Add-on
   mit `gemini` bereits (D-007). Er nutzt das Abo-Kontingent nicht, bietet aber Freikontingent
   und über AI Pro ein monatliches Cloud-Guthaben.
6. Der vorhandene Provider ist veraltet (Modellliste) und ohne Werkzeuge.

## Betrachtete Optionen

### Option A — API-Weg ausbauen, Abo-Weg zurückstellen

- Dafür: Von Google für Fremdanwendungen vorgesehen. Keine neue Abhängigkeit im Bild, keine
  Sperrgefahr für das Konto, keine Anmeldeprobleme, keine Gesprächsdaten auf der Platte, im EWR
  Datenschutzregeln der bezahlten Dienste. Behebt nebenbei die veraltete Modellliste.
- Dagegen: Das Abo-Kontingent von AI Pro bleibt ungenutzt; Verbrauch wird abgerechnet (mit
  Freikontingent für Flash-Modelle; das Cloud-Guthaben aus AI Pro deckt die Gemini API
  womöglich). Websuche nur mit Abrechnung und mit Auflagen, die zu Automationen schlecht passen.

### Option B — Neuer Provider `gemini_sub` über `agy -p` (Entwurf in [abo-weg-antigravity.md](abo-weg-antigravity.md))

- Dafür: Nutzt das Abo wie gewünscht, fügt sich in die Fabrik ein (D-005), Muster von D-013 passt.
- Dagegen: Nach Googles Wortlaut nicht unterstützt (Sperrung möglich); das Risiko ginge mit jedem
  Release an alle Nutzer des Add-ons. Anmeldung ungeklärt. Persönliche Daten laufen über ein Konto,
  dessen Datennutzung Google für Privatkonten nicht eindeutig ausschließt. Bild wächst um rund
  200 MB. Verbrauch je Anfrage und Verhalten bei Dauerbetrieb unbekannt; Automationen könnten das
  5-Stunden-Fenster leeren, das der User selbst braucht.

### Option C — Unternehmensweg (Gemini Enterprise, Workspace, Cloud-Projekt)

- Dafür: Es gelten die Bedingungen des Administrators, und Google empfiehlt ihn für Fremd-Agenten.
- Dagegen: Kein Abo des Users, eigene Lizenz und Kosten, anderer Zugangstyp. Nur bei konkretem Bedarf.

## Entscheidung (Vorschlag)

**Option A.** Der Provider `gemini` wird ausgebaut ([api-weg.md](api-weg.md),
[umsetzungsplan.md](umsetzungsplan.md#spur-1--api-weg-empfohlen)); der Abo-Weg wird
**zurückgestellt**, nicht verworfen. Ausschlaggebend ist nicht die Technik — die ginge —, sondern
Googles ausdrückliche Aussage, dass genau dieser Einsatz unter Verbraucherplänen nicht
unterstützt wird, zusammen mit dem Umstand, dass ein Provider im veröffentlichten Add-on das
Risiko an Nutzer weiterreicht, die es nicht kennen.

Zur Websuche bei Gemini: `tool_access = web` bedeutet bei Gemini nur Seitenabruf (`url_context`).
`google_search` wird nicht stillschweigend eingeschaltet, weil Googles Bedingungen die Anzeige
der Suchvorschläge beim Endnutzer und ein Verbot der Auswertung der Ergebnisse vorsehen.

Wer den Abo-Weg dennoch will, entscheidet das ausdrücklich (Schranke G1), besteht den Spike
(G2) und liest die Klausel am Tag des Baubeginns erneut (G3) — dann als eigener Beschluss
(D-023), nicht als Nebenwirkung dieses.

## Folgen

- **Positiv:** Ein unterstützter, wartungsarmer Weg; Gemini-Modelle bleiben aktuell nutzbar;
  keine neue Risikoquelle für Nutzer; die Recherche ist festgehalten und muss nicht wiederholt
  werden.
- **Negativ:** Das AI-Pro-Abo wird nicht angezapft; Gemini kostet nach Freikontingent Geld.
  Gemini bleibt ohne Websuche, solange Entscheidung 2 nicht anders fällt. Wer das Abo nutzen
  will, bleibt bei `claude_sub` oder `codex_sub`.
- **Aufwand:** Spur 1 des Umsetzungsplans, geschätzt 1 bis 2 Tage einschließlich Handprüfungen mit
  eigenem Schlüssel.

## Rücknahmebedingung

Die Entscheidung wird überprüft, wenn eines davon eintritt:

- Google nimmt in der FAQ der Antigravity CLI den Satz „not supported under consumer plans“ zurück
  oder erlaubt das Einpacken ausdrücklich (auch als eigener Plan).
- Google dokumentiert eine Anmeldung für Server und Container mit dem Privatabo (Token wie
  `claude setup-token`) oder eine Schnittstelle, die das Abo-Kontingent per Schlüssel anspricht.
- Der Betrieb mit Schlüssel erweist sich als zu teuer für den Zweck, und der User nimmt das Risiko
  des Abo-Wegs ausdrücklich an.
- Der Seitenabruf (`url_context`) bleibt für die Praxis ohne Nutzen und die Websuche lässt sich
  in einer Form einsetzen, die Googles Auflagen erfüllt.
