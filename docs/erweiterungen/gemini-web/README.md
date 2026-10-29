# Erweiterung: Gemini Web (inoffiziell) und Umbenennung des AGY-Anbieters

> **Stand 29.10.2026: Plan. Nichts davon ist umgesetzt.** Was das Add-on heute tut, steht in
> [../../architektur.md](../../architektur.md); Abweichungen davon in
> [../../bekannte-luecken.md](../../bekannte-luecken.md). Diese Dateien beschreiben Geplantes und
> sind **kein Ist-Stand**.

## Auftrag

Der User hat am 29.10.2026 verlangt:

1. Der bisherige Anbieter `gemini_sub` (Google Gemini über die Antigravity-CLI `agy`, D-022, D-024)
   wird umbenannt, **einschließlich des technischen Schlüssels und ohne Übergang**.
2. Ein neuer, **inoffizieller** Anbieter nutzt die **Web-App von Gemini** (gemini.google.com) mit
   dem **Nutzungslimit, das ein Google-Konto in der Web-App hat**. Dafür ist ein eigenes Google-Konto
   vorgesehen, das nur diesem Zweck dient. Wie bei D-024 lassen sich **mehrere Konten** anlegen.
3. Der neue Anbieter nimmt **Dateien und Bilder als Anhang** entgegen.
4. Zuerst ein Plan in Markdown-Dateien; bei Unklarheiten wird gefragt, nicht geraten.

## Warum ein neuer Anbieter

Das Nutzungslimit der Web-App ist über keinen offiziellen Weg erreichbar: Die Gemini-API wird
getrennt abgerechnet, die Vorteile von AI Pro gelten dort nur in der Weboberfläche von AI Studio,
und `agy` hat laut Berichten einen eigenen Pool (Belege in [recherche.md](recherche.md)). Bleibt
der Weg über die Web-App selbst, den die Bibliothek `gemini-webapi` nachbildet.

## Was ausdrücklich nicht verschwiegen wird

- **Das ist ein Verstoß gegen Googles Nutzungsbedingungen.** Sie verbieten Reverse Engineering
  der Dienste und nennen Sperrung oder Löschung des Kontos als Folge. Der User trägt das in
  Kenntnis; es steht so im ADR und in der Oberfläche (siehe [entwurf.md](entwurf.md#risiko)).
- **Es gibt keinen stabilen Vertrag.** Jede Änderung der Web-App kann den Anbieter brechen.
- **Eine Bibliothek unter AGPL-3.0** kommt in ein ansonsten MIT-lizenziertes Repo
  ([entwurf.md](entwurf.md#abhängigkeit-und-lizenz)).

## Getroffene Entscheidungen

| Nr. | Entscheidung | Quelle |
|---|---|---|
| E1 | Der AGY-Anbieter wird umbenannt, **mit Schlüssel, ohne Übergang** | User, 29.10.2026 |
| E2 | Der neue Anbieter heißt **Gemini Web**, Schlüssel `gemini_web` | User, 29.10.2026 |
| E3 | Grundlage ist die Bibliothek **`gemini-webapi`**; die Lizenzfolge wird als ADR dokumentiert | User, 29.10.2026 |
| E4 | Anhänge (Dateien und Bilder) gehören zum Umfang. Nicht gewählt und deshalb **nicht** geplant: Deep Research, Gems, Löschen der Chats | User, 29.10.2026 |
| E5 | Mehrere Konten, Wechsel nach den Regeln von D-024 (erstes Konto mit Kontingent, wachsende Wartezeit, **keine Tarnung**) | User, 29.10.2026 („wieder so“) |
| E6 | Die Anmeldung geschieht durch **Einfügen der Cookies** des Kontos in der Oberfläche; die Bibliothek kennt keinen anderen Weg | Befund der Recherche |

E6 ist keine Entscheidung des Users, sondern folgt aus der Bibliothek. Sie steht hier, damit sie
auffällt, falls der User einen anderen Weg erwartet hat.

## Klärung durch den User am 29.10.2026

- **F1/F2:** Namen „Google Gemini“, „Google Gemini (AGY)“, „Google Gemini (Web)“;
  Schlüssel `gemini_agy` und `gemini_web`. Bestehende Datenpfade bleiben erhalten.
- **F3:** Temporäre Chats verwenden; die Bibliothek unterstützt `temporary=True`.
- **F4:** Anhänge zunächst in `/ask` als Base64; `/v1` bleibt ohne Anhänge.
- **F5:** Kein externer Aufrufer verwendet `gemini_sub`.
- **F6:** Der User prüft das separate Google-Konto nach Installation des Updates im
  HA-Add-on. Der Kontotest blockiert den Bau nicht mehr. Haltbarkeit der Anmeldung,
  tatsächliche Kontingente und Google-Grenzen bleiben bis dahin ausdrücklich ungeprüft.

Die lokale Vorprüfung hat die Installation und den Import von `gemini-webapi==2.1.1`
auf beiden Alpine-Basisimages ohne Compiler bestätigt. Der Standard-Cache der Bibliothek
verwendet einen Cookie-Wert im Dateinamen und muss in der Brücke ersetzt werden.
Anhang-Grenzen werden vor AP 9 gesondert mit dem User geklärt.

## Dateien

| Datei | Inhalt |
|---|---|
| [recherche.md](recherche.md) | Befunde mit Quellen und Belastbarkeit: Limits, Bibliothek, Bedingungen, Risiko |
| [entwurf.md](entwurf.md) | Aufbau: Anbieter, Konten, Anhänge, Oberfläche, Konfiguration, Sicherheit, Lizenz |
| [umbenennung-agy.md](umbenennung-agy.md) | Umbenennung von `gemini_sub`: alles, was sich ändert und was bleibt |
| [umsetzungsplan.md](umsetzungsplan.md) | Arbeitspakete in Reihenfolge, mit Dateien, Tests, Commit und Abnahme |
| [handpruefung.md](handpruefung.md) | Prüfungen mit echtem Konto nach dem Bau und Rücknahmebedingungen |

Verwandt: [../gemini-provider/](../gemini-provider/README.md) (Abo-Weg über `agy`, Schlüssel-Weg),
[D-022](../../adr/D-022-gemini-abo-antigravity.md), [D-024](../../adr/D-024-mehrere-google-konten.md).
