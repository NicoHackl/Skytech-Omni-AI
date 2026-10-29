# D-030: Gemini Web über gemini-webapi

- **Datum:** 29.10.2026
- **Status:** Aktiv; Handprüfung mit echtem Konto nach Installation offen
- **Betrifft:** Gemini Web, Cookie-Anmeldung, Kontenwechsel, Lizenz des ausgelieferten Images

## Kontext und Entscheidung

Der User möchte das Kontingent der Gemini-Web-App nutzen. API und Antigravity sind
andere Zugänge. Gewählt ist `gemini-webapi==2.1.1`, ausdrücklich in Kenntnis der
AGPL-3.0 und des Risikos einer Kontosperre. Alternativen waren ein eigener Client
(höherer Wartungsaufwand) und Verzicht (erfüllt den Auftrag nicht).

Anzeigename: „Google Gemini (Web)“, Schlüssel: `gemini_web`. Anmeldung durch Einfügen
zweier Cookies aus einem separaten Google-Konto. Höchstens zehn Konten. Das erste
mit verfügbarem Kontingent wird verwendet; Kontingentfehler und ungültige Anmeldung
führen zum nächsten. Wartezeit: 30 Minuten, dann 1, 2, 4 und höchstens 5 Stunden.
Eine Verbindungssperre pausiert den ganzen Anbieter mit derselben wachsenden
Wartezeit, auch nach einem Neustart. Kein Ausweichen auf andere Konten oder Adressen.

Jede Anfrage ist ein eigener temporärer Chat (`temporary=True`). Kein Deep Research,
keine Gems, keine Verwaltung oder Löschung des Kontoverlaufs. Die Werkzeugstufe des
Add-ons kontrolliert die Funktionen der Web-App nicht.

Der User hat den Kontotest ausdrücklich auf die Zeit nach Installation im HA-Add-on
verschoben. Lokale Tests ersetzen die Bibliothek, die Plattformprüfung nutzt keine
Anmeldung. Haltbarkeit der Cookies, echte Modelllisten, Limits und Upload-Verhalten
werden deshalb nicht als belegt dargestellt.

## Technischer Aufbau und Schutz der Anmeldung

Ein Ereignisschleifen-Thread hält einen Client je Konto. Sämtliche Operationen laufen
nacheinander, mit Frist und Abbruch. Die Initialisierung kann als Gast erfolgreich
sein; erst `AccountStatus.AVAILABLE` wird als gelungene Anmeldung angenommen.

Die Bibliothek schreibt standardmäßig den vollen Cookie-Wert in Cache-Dateinamen.
Die Brücke ersetzt deshalb bei der festgelegten Version beide Importstellen der
Cache-Funktionen. Ein eigener Kontext je Konto bestimmt `session.json` in dessen
privatem Verzeichnis; Hintergrundaufgaben übernehmen denselben Kontext. Die
Umgebungsvariable der Bibliothek wird nicht zwischen Konten umgeschaltet.
Bibliothekslogs sind deaktiviert; nach außen und ins eigene Log gehen nur bekannte
Fehlerarten, nie deren Rohtexte. Das Cookie-Original und die erneuerte Sitzung liegen
unter `/data` in Dateien mit `0600`, Kontoverzeichnisse mit `0700`. Nach Entfernen
werden Clients zuerst geschlossen und dann deren Dateien gelöscht.

Gemeinsame Ablagefunktionen, Lesen der Kontenlisten, Reihenfolge und Wartezeit liegen
in `providers/google_accounts.py`. Eine vollständige gemeinsame Kontenklasse wurde
vermieden: Die AGY-Anbindung hat eine Bestandsmigration und CLI-spezifische Zustände,
die Web-Anbindung eine streng getrennte Cookie-Ablage. Die bestehenden AGY-Tests
prüfen das unveränderte Verhalten.

## Abhängigkeit und Lizenz

Die Bibliothek und sämtliche transitiven Abhängigkeiten sind festgelegt. Installation
und Import auf beiden Alpine-Basisimages gelingen ohne Compiler. Das Image installiert
nur Wheels; ein fehlendes Wheel stoppt den Bau.

Das eigene Repository trägt weiterhin MIT. Die Bibliothek trägt AGPL-3.0; die
MIT-Lizenz hebt deren Pflichten nicht auf. Lizenztext und unverändertes Quellarchiv
von PyPI liegen im Image unter `third_party/gemini-webapi/`. Das Archiv wird über
seine SHA-256 geprüft. Die Quelltexte der Integrationsanpassung sind im öffentlichen
Projekt-Repository verfügbar, und Oberfläche, Store-Text und Projekt-README nennen
Bibliothek, Quelle und Lizenz. Eine pauschale Aussage, das kombinierte Image stehe
allein unter MIT, wird nicht getroffen. Die rechtliche Bewertung des Gesamtwerks
bleibt eine eigenständige Frage; diese Entscheidung behauptet keine Rechtssicherheit.

## Risiken und Rücknahmebedingungen

Googles Bedingungen erlauben diese Nutzung nicht; Einschränkung oder Sperrung des
Kontos ist möglich. Nur separate Konten ohne persönliche Daten verwenden. Eingaben
und Anhänge werden an Google übertragen. Temporäre Chats sind keine Zusage, dass
Google Eingaben nicht verarbeitet oder speichert.

Bei dauerhaft nicht erneuerbaren Cookies, nicht mehr lauffähiger Bibliothek, nicht
beherrschbarem Ressourcenverbrauch oder Konto-Sperren wird der Anbieter deaktiviert
und mit dem User über eigenen Client, anderes Image oder Verzicht entschieden.
Die Vorgabe des Add-ons bleibt Claude. Ohne angemeldetes Konto erzeugt Gemini Web
keine Anfrage. Die Handprüfung steht im Erweiterungsordner.
