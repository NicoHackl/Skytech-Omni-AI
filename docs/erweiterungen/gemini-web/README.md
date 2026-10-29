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

## Offene Fragen — vor dem genannten Arbeitspaket zu klären

Nichts davon wird geraten. Jede Zeile blockiert das genannte Arbeitspaket, nicht den ganzen Plan.

| Nr. | Frage | Blockiert | Vorschlag |
|---|---|---|---|
| F1 | **Anzeigenamen.** Im Auftrag stand „Gemini AGY“, in der Antwort „Google Gemini (AGY)“. Soll der neue Anbieter „Gemini Web“ oder „Google Gemini (Web)“ heißen? | AP 1, AP 8 | Einheitlich vier Namen: „Google Gemini“ (Schlüssel), „Google Gemini (AGY)“, „Google Gemini (Web)“ — Schlüssel `gemini_web` bleibt |
| F2 | **Technischer Schlüssel des umbenannten Anbieters.** Angenommen wird `gemini_agy`. Mit ihm ziehen die Option `gemini_sub_model`, die Dateien `gemini_sub_*.py` und die Routen `/auth/gemini…` um. Die **Datenpfade** (`/data/.gemini`, `omniai-gemini-accounts…`) würden bei einer Umbenennung eine Neuanmeldung aller Konten erzwingen | AP 1 | Alles umbenennen außer den Datenpfaden ([umbenennung-agy.md](umbenennung-agy.md#was-ausdrücklich-bleibt)) |
| F3 | **Verlauf im Konto.** Das Löschen der Chats wurde nicht gewählt, also bleibt jede Anfrage als Chat im Verlauf des Kontos. Die Bibliothek nennt „temporary chats“; ob sie sich für Anfragen nutzen lassen, prüft der Spike. Soll der Anbieter sie nutzen, wenn es geht? | AP 5 | Ja: kein Verlauf, kein Löschen nötig |
| F4 | **Anhänge über `/v1`.** `/ask` kennt heute nur `prompt`, `provider`, `model`. `/ask` lässt sich allein hier erweitern. Der Vertrag für `/v1` hat seinen **Master im Backend von Skytech X**, das nicht in diesem Arbeitsordner liegt; dort müsste das Feld zuerst entstehen. Nur `/ask` jetzt, `/v1` nach Änderung im Master? Und: Übergabe als Base64 im JSON oder als Multipart? | AP 9 | `/ask` jetzt mit Base64; `/v1` erst nach Änderung im Master |
| F5 | **Bruch durch die Umbenennung.** Wer `provider: gemini_sub` gespeichert hat, hat nach dem Update einen Wert, der nicht mehr im Schema steht. Erwartet wird, dass Home Assistant die Konfiguration dann ablehnt, bis `provider` umgestellt ist (**ungeprüft**, der Spike stellt es nach). Schickt Skytech X oder eine Automation `gemini_sub`? Das Add-on kennt den Schlüssel danach nicht mehr | AP 1 | Changelog-Eintrag mit Hinweis „vor dem Update den Anbieter wechseln“; Skytech X vorher benachrichtigen |
| F6 | **Testkonto für den Spike.** Der Spike braucht die Cookies eines Wegwerf-Kontos. Cookies tragen die volle Anmeldung des Kontos. Wer führt den Spike aus? | AP 2 | Der User führt ein Skript lokal aus (`! python …`) und gibt nur das Ergebnis weiter — der Agent bekommt **keine** Cookies |

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
