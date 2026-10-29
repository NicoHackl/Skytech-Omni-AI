# Gemini Web und Umbenennung des AGY-Anbieters

Stand: 29.10.2026. **Anbieter und Oberfläche umgesetzt; Anhänge über `/ask` noch offen.**
Die Handprüfung mit einem echten Google-Konto führt der User nach Installation des Updates
im HA-Add-on durch. Die lokale Prüfung verwendet ausschließlich Attrappen und keine Anmeldung.

## Entscheidungen des Users

- Anzeigenamen „Google Gemini“, „Google Gemini (AGY)“, „Google Gemini (Web)“.
- Technische Schlüssel `gemini_agy` und `gemini_web`. Der alte Schlüssel entfällt ohne Alias;
  kein externer Aufrufer verwendet ihn. Bestehende Kontodatenpfade des AGY-Anbieters bleiben.
- Web-Zugang über `gemini-webapi`, Lizenzfolge AGPL-3.0 dokumentiert, mehrere separate Konten.
- Jede Anfrage als neuer temporärer Chat. Keine Gems, kein Deep Research, keine Chatverwaltung.
- Anhänge zunächst als Base64 über `/ask`; `/v1` erst nach Änderung des Vertragsmasters.
- Der Kontotest blockiert den Bau nicht und erfolgt erst nach Installation im HA-Add-on.

## Umgesetzt

| Teil | Stand |
|---|---|
| AGY-Umbenennung | Code, Konfiguration, Routen, Oberfläche, Tests und Doku umgestellt; [D-031](../../adr/D-031-umbenennung-gemini-agy.md) |
| Abhängigkeiten | Bibliothek und transitive Abhängigkeiten festgelegt; Import auf beiden Alpine-Basisimages ohne Compiler bestätigt |
| Lizenz | AGPL-Lizenztext und geprüftes Quellarchiv im Image, Hinweise in Oberfläche und README; [D-030](../../adr/D-030-gemini-web-inoffiziell.md) |
| Konten | Bis zu zehn getrennte Cookie-Konten, private Ablage, dynamische Modelle, offener Wechsel bei Kontingentfehler oder ungültiger Anmeldung |
| Verbindungssperre | Pause des gesamten Anbieters statt Kontowechsel, dauerhaft gespeicherte wachsende Wartezeit |
| Brücke | Eigener Thread, wiederverwendete Clients, temporäre Chats, Zeitlimit und Abbruch, Aufräumen temporärer Anhänge intern |
| Cookie-Cache | Unsicheren Standard mit Cookie im Dateinamen ersetzt; kontoabhängiger Kontext auch in Hintergrundaufgaben |
| Schnittstellen | `/auth/gemini-web`, Konfiguration, `/models`, `/status`, `/v1/capabilities` |
| Oberfläche | Konten anlegen und entfernen, Modelle neu laden, Passwortfelder nach Absenden geleert; Hell/Dunkel und schmale Ansicht geprüft |

## Noch offen

- **AP 9:** Der User entscheidet die lokalen Anhang-Grenzen. Gefragt ist: höchstens zehn
  Dateien mit zusammen 20 MiB, Bilder PNG/JPEG/WebP/GIF, PDF und Text TXT/Markdown/CSV/JSON.
  Das ist ein Vorschlag, keine gesetzte Vorgabe. `/ask` nimmt bis dahin noch keine Anhänge an.
- **AP 11:** Handprüfung nach Installation; Cookie-Haltbarkeit, reale Modelllisten, Limits,
  tatsächlicher Verlauf und Upload-Verhalten von Google sind ungeprüft.
- Der Supervisor wurde nicht mit einer inzwischen ungültigen Auswahl getestet.
  Vor dem Update vorübergehend Claude wählen; erst danach ist AGY als neuer Wert verfügbar.

## Quellen und Prüfung

- [Vorprüfung und Grenzen der Belege](spike-ergebnis.md)
- [Handprüfung mit echten Konten](handpruefung.md)
- [Ursprüngliche Recherche](recherche.md)
- [Entwurf](entwurf.md) und [Arbeitspakete](umsetzungsplan.md) als Planungshistorie;
  der aktuelle Stand steht hier und in der [Architektur](../../architektur.md).

Google erlaubt diesen inoffiziellen Zugang nicht und kann Konten sperren. Er hat keinen
stabilen Vertrag. Ohne angemeldetes Konto tut der Anbieter nichts; Claude bleibt die Vorgabe.
